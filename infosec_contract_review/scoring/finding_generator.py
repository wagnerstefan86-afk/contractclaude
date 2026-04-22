"""Generate findings from obligations, relations, missing safeguards, and cross-theme candidates."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from sqlalchemy.orm import Session, joinedload

from infosec_contract_review.models.enums import (
    FindingSeverity,
    FindingStatus,
    Materiality,
    StepType,
    RunStatus,
    Theme,
)
from infosec_contract_review.models.finding import Evidence, Finding, MissingSafeguard
from infosec_contract_review.models.obligation import Obligation
from infosec_contract_review.models.playbook import PlaybookEntry
from infosec_contract_review.models.relation import CrossThemeFindingCandidate, ObligationRelation
from infosec_contract_review.models.run import RunStep
from infosec_contract_review.models.segment import Segment
from infosec_contract_review.scoring.materiality_scorer import score_obligation_materiality
from infosec_contract_review.scoring.playbook_matcher import match_obligation_to_playbook
from infosec_contract_review.scoring.finding_classifier import classify_group

logger = logging.getLogger(__name__)

_SEVERITY_FROM_MATERIALITY = {
    Materiality.LOW: FindingSeverity.LOW,
    Materiality.MEDIUM: FindingSeverity.MEDIUM,
    Materiality.HIGH: FindingSeverity.HIGH,
    Materiality.CRITICAL: FindingSeverity.CRITICAL,
}

_THEME_LABELS = {
    "audit_rights": "Audit- und Prüfungsrechte",
    "incident_reporting": "Incident Reporting und Meldepflichten",
    "sla_feasibility": "SLA-Machbarkeit",
    "bcm_itscm": "BCM/ITSCM",
    "security_controls": "Sicherheitskontrollen",
    "certifications": "Zertifizierungen",
    "liability_transfer": "Haftungsübertragung",
    "subcontractor": "Subunternehmer",
    "exit": "Exit-Regelungen",
    "change_management": "Change Management",
    "regulatory_passthrough": "Regulatorische Durchreichung",
    "data_protection": "Datenschutz",
}


@dataclass
class FindingGenerationResult:
    findings_created: int = 0
    obligations_grouped: int = 0
    cross_theme_findings: int = 0
    playbook_matches: int = 0
    informational_findings: int = 0
    errors: int = 0


_GROUPABLE_RELATION_TYPES = {"supplements", "specifies", "references", "tightens"}


def _split_risk_and_info_members(
    group_obls: list[Obligation],
) -> tuple[list[Obligation], list[Obligation]]:
    """Split a cluster into (risk-members, info-members) via per-obligation
    classification.

    An obligation is treated as informational *in the context of this cluster*
    if classify_group([obl], None, [], []) returns informational — i.e. the
    text alone reads as a limit / positive / defensive clause. Such members
    must not pollute the evidence of a risk finding they were pulled into
    via a groupable relation (supplements/specifies/references/tightens).
    """
    risk_members: list[Obligation] = []
    info_members: list[Obligation] = []
    for obl in group_obls:
        solo_cls = classify_group([obl], None, [], [])
        if solo_cls.kind == "informational":
            info_members.append(obl)
        else:
            risk_members.append(obl)
    return risk_members, info_members


def _build_connected_components(
    obligations: list[Obligation],
    relations: list[ObligationRelation],
) -> list[list[Obligation]]:
    """Group obligations into connected components via groupable relations.

    Two obligations end up in the same component if they are connected
    (directly or transitively) by a relation whose type is in
    _GROUPABLE_RELATION_TYPES. 'contradicts' is intentionally excluded
    because contradicting obligations should appear as separate findings.
    """
    obl_ids = {o.id for o in obligations}
    parent: dict[str, str] = {o.id: o.id for o in obligations}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for rel in relations:
        rel_type = rel.relation_type.value if hasattr(rel.relation_type, "value") else str(rel.relation_type)
        if rel_type not in _GROUPABLE_RELATION_TYPES:
            continue
        a_id = rel.obligation_a_id
        b_id = rel.obligation_b_id
        if a_id in obl_ids and b_id in obl_ids:
            union(a_id, b_id)

    components: dict[str, list[Obligation]] = {}
    for obl in obligations:
        root = find(obl.id)
        components.setdefault(root, []).append(obl)

    return list(components.values())


def _group_obligations_by_risk(
    obligations: list[Obligation],
    playbook_entries: list[PlaybookEntry],
    relations: list[ObligationRelation],
) -> list[tuple[list[Obligation], PlaybookEntry | None]]:
    """Group obligations into findings.

    Two-pass grouping:
    1. Build connected components via supplements/specifies/references/
       tightens relations (LLM-provided structural signal).
    2. Merge components that resolve to the SAME playbook entry. This
       catches near-duplicate obligations that the LLM did not link
       explicitly but that point at the identical risk pattern (e.g.
       two paragraphs both describing unlimited audit frequency).

    Grouping only merges via playbook identity, never via similarity of
    surface text. That keeps the deduplication conservative: obligations
    that matched different playbook entries remain separate, and
    unmatched obligations stay as singletons.
    """
    components = _build_connected_components(obligations, relations)

    # Pass 1: determine a playbook match per component (match any member).
    component_matches: list[tuple[list[Obligation], PlaybookEntry | None]] = []
    for component in components:
        pb_match: PlaybookEntry | None = None
        for obl in component:
            pb_match = match_obligation_to_playbook(obl, playbook_entries)
            if pb_match:
                break
        component_matches.append((component, pb_match))

    # Pass 2: merge components that share the same playbook entry.
    # Guard: a component whose obligations are all individually informational
    # (when classified without a playbook match) must not be pulled into a
    # risk cluster just because another component shares the same playbook.
    merged_by_playbook: dict[str, tuple[list[Obligation], PlaybookEntry]] = {}
    unmatched: list[tuple[list[Obligation], PlaybookEntry | None]] = []
    for component, pb in component_matches:
        if pb is None:
            unmatched.append((component, None))
            continue
        solo_cls = classify_group(component, None, [], [])
        if solo_cls.kind == "informational":
            unmatched.append((component, None))
            continue
        key = pb.id
        if key in merged_by_playbook:
            merged_by_playbook[key][0].extend(component)
        else:
            merged_by_playbook[key] = (list(component), pb)

    groups: list[tuple[list[Obligation], PlaybookEntry | None]] = []
    for obls, pb in merged_by_playbook.values():
        groups.append((obls, pb))
    groups.extend(unmatched)

    return groups


def _build_finding_title(
    obligations: list[Obligation],
    playbook: PlaybookEntry | None,
    theme_val: str,
) -> str:
    theme_label = _THEME_LABELS.get(theme_val, theme_val)
    if playbook:
        return f"{theme_label}: {playbook.risk_pattern}"
    if len(obligations) == 1:
        summary = obligations[0].summary
        return f"{theme_label}: {summary[:120]}" if len(summary) > 120 else f"{theme_label}: {summary}"
    return f"{theme_label}: {len(obligations)} Pflichten ohne Playbook-Zuordnung"


def _build_finding_description(
    obligations: list[Obligation],
    playbook: PlaybookEntry | None,
    missing_safeguards: list[MissingSafeguard],
) -> str:
    parts: list[str] = []

    parts.append("**Feststellung:**")
    for obl in obligations:
        parts.append(f"- {obl.summary}")

    if missing_safeguards:
        parts.append("\n**Fehlende Schutzmechanismen:**")
        for ms in missing_safeguards:
            parts.append(f"- {ms.label}: {ms.explanation or 'nicht vorhanden'}")

    if playbook:
        parts.append(f"\n**Standardposition:**\n{playbook.standard_position.strip()}")
        if playbook.escalation_note:
            parts.append(f"\n**Eskalationshinweis:** {playbook.escalation_note.strip()}")

    return "\n".join(parts)


def _build_recommendation(
    playbook: PlaybookEntry | None,
    obligations: list[Obligation],
) -> str:
    parts: list[str] = []

    if playbook:
        if playbook.alt_wordings:
            parts.append("**Empfohlene Alternativformulierung:**")
            parts.append(playbook.alt_wordings[0].strip() if isinstance(playbook.alt_wordings[0], str) else str(playbook.alt_wordings[0]))
        if playbook.bidder_questions:
            parts.append("\n**Bieterfragen:**")
            for q in playbook.bidder_questions:
                parts.append(f"- {q}")
    else:
        parts.append("Manuelle Prüfung empfohlen. Keine Playbook-Zuordnung vorhanden.")
        for obl in obligations:
            if obl.baseline_gap_description:
                parts.append(f"- {obl.baseline_gap_description}")
                break

    return "\n".join(parts)


def generate_findings(
    run_id: str,
    db: Session,
    step_index: int,
) -> FindingGenerationResult:
    result = FindingGenerationResult()

    step = RunStep(
        run_id=run_id,
        step_type=StepType.AGGREGATION,
        step_index=step_index,
        status=RunStatus.RUNNING,
        input_summary={},
    )
    db.add(step)
    db.flush()

    obligations = (
        db.query(Obligation)
        .options(joinedload(Obligation.limits))
        .filter_by(run_id=run_id)
        .all()
    )

    if not obligations:
        step.status = RunStatus.COMPLETED
        step.output_summary = {"findings": 0, "reason": "no obligations"}
        db.flush()
        return result

    missing_safeguards = (
        db.query(MissingSafeguard)
        .filter_by(run_id=run_id)
        .all()
    )

    relations = (
        db.query(ObligationRelation)
        .filter_by(run_id=run_id)
        .all()
    )

    cross_theme_candidates = (
        db.query(CrossThemeFindingCandidate)
        .filter_by(run_id=run_id)
        .all()
    )

    playbook_entries = db.query(PlaybookEntry).filter_by(is_active=True).all()

    # Score materiality for all obligations
    for obl in obligations:
        obl.materiality = score_obligation_materiality(obl, missing_safeguards, relations)
    db.flush()

    # Group by theme, then by risk pattern
    by_theme: dict[str, list[Obligation]] = {}
    for obl in obligations:
        theme_val = obl.theme.value if hasattr(obl.theme, "value") else str(obl.theme)
        by_theme.setdefault(theme_val, []).append(obl)

    obl_id_set = {o.id for o in obligations}

    for theme_val, theme_obls in by_theme.items():
        groups = _group_obligations_by_risk(theme_obls, playbook_entries, relations)

        theme_ms = [
            ms for ms in missing_safeguards
            if ms.lens_config_id and any(
                o.lens_config_id == ms.lens_config_id for o in theme_obls
            )
        ]

        for group_obls, playbook in groups:
            # Classify the group up-front so we know whether this cluster
            # represents a risk or an informational finding.
            classification = classify_group(
                group_obls, playbook, missing_safeguards, relations,
            )
            is_informational = classification.kind == "informational"

            # For a risk cluster with > 1 member, split off members that
            # individually read as informational (limit / positive /
            # defensive clauses pulled in via supplements/specifies/
            # references/tightens relations). Those must not sit inside
            # the risk finding's evidence. They each become a standalone
            # informational finding below.
            expelled_info: list[Obligation] = []
            if not is_informational and len(group_obls) > 1:
                risk_members, info_members = _split_risk_and_info_members(group_obls)
                if info_members and risk_members:
                    group_obls = risk_members
                    expelled_info = info_members
                    logger.info(
                        "cluster %s: expelled %d informational member(s) from risk cluster",
                        playbook.id if playbook else "(no-pb)",
                        len(info_members),
                    )

            max_mat = max(
                (o.materiality for o in group_obls),
                key=lambda m: {"low": 0, "medium": 1, "high": 2, "critical": 3}.get(
                    m.value if hasattr(m, "value") else str(m), 1
                ),
            )

            title = _build_finding_title(group_obls, playbook, theme_val)
            if is_informational:
                title = f"[Informativ] {title}"
            description = _build_finding_description(group_obls, playbook, theme_ms)
            if is_informational:
                description = (
                    f"*{classification.reason}*\n\n" + description
                )
            recommendation = _build_recommendation(playbook, group_obls)

            if is_informational:
                severity = FindingSeverity.INFO
                materiality = Materiality.LOW
            else:
                severity = _SEVERITY_FROM_MATERIALITY.get(max_mat, FindingSeverity.MEDIUM)
                materiality = max_mat

            # Diagnostic line: per-cluster severity rationale. Emits enough
            # signal to reconstruct after the fact why a finding ended up at
            # its severity without schema changes or user-visible debug UI.
            logger.info(
                "finding severity | theme=%s playbook=%s severity=%s materiality=%s "
                "members=%d informational=%s reason=%r",
                theme_val,
                playbook.id if playbook else None,
                severity.value if hasattr(severity, "value") else str(severity),
                materiality.value if hasattr(materiality, "value") else str(materiality),
                len(group_obls),
                is_informational,
                classification.reason,
            )

            theme_enum = Theme(theme_val) if theme_val in [t.value for t in Theme] else Theme.OTHER

            finding = Finding(
                run_id=run_id,
                theme=theme_enum,
                title=title,
                description=description,
                severity=severity,
                materiality=materiality,
                status=FindingStatus.OPEN,
                playbook_entry_id=playbook.id if playbook else None,
                recommendation=recommendation,
            )
            db.add(finding)
            db.flush()

            for obl in group_obls:
                ev = Evidence(
                    finding_id=finding.id,
                    obligation_id=obl.id,
                    segment_id=obl.segment_id,
                    quote=obl.verbatim_quote,
                    rationale=obl.summary,
                )
                db.add(ev)

            if playbook:
                result.playbook_matches += 1
            if is_informational:
                result.informational_findings += 1

            result.findings_created += 1
            result.obligations_grouped += len(group_obls)

            # Spin off one informational finding per expelled member so
            # their text remains visible under ?include_info=1 without
            # contaminating the risk cluster.
            for info_obl in expelled_info:
                info_cls = classify_group([info_obl], None, [], [])
                info_title = _build_finding_title([info_obl], None, theme_val)
                info_title = f"[Informativ] {info_title}"
                info_desc = _build_finding_description([info_obl], None, [])
                info_desc = f"*{info_cls.reason}*\n\n" + info_desc
                info_rec = _build_recommendation(None, [info_obl])
                info_finding = Finding(
                    run_id=run_id,
                    theme=theme_enum,
                    title=info_title,
                    description=info_desc,
                    severity=FindingSeverity.INFO,
                    materiality=Materiality.LOW,
                    status=FindingStatus.OPEN,
                    playbook_entry_id=None,
                    recommendation=info_rec,
                )
                db.add(info_finding)
                db.flush()
                db.add(Evidence(
                    finding_id=info_finding.id,
                    obligation_id=info_obl.id,
                    segment_id=info_obl.segment_id,
                    quote=info_obl.verbatim_quote,
                    rationale=info_obl.summary,
                ))
                result.findings_created += 1
                result.informational_findings += 1
                result.obligations_grouped += 1

    # Create findings for cross-theme candidates
    for ct in cross_theme_candidates:
        if ct.result not in ("conflict_found", "unclear"):
            continue

        # Cross-theme findings are currently analyst-debug output with
        # mixed-language rationale. They should stay in the DB for audit
        # trail but be hidden from the default reviewer view, so we file
        # them as severity=INFO / materiality=LOW. The existing UI/Excel
        # default filter (severity != "info") then hides them;
        # ?include_info=1 makes them visible again.
        ct_finding = Finding(
            run_id=run_id,
            theme=Theme.OTHER,
            title=f"[Cross-Theme] {ct.rationale[:100] if ct.rationale else 'Themenübergreifender Konflikt'}",
            description=f"**Cross-Theme-Prüfergebnis:** {ct.result}\n\n**Begründung:** {ct.rationale or '–'}",
            severity=FindingSeverity.INFO,
            materiality=Materiality.LOW,
            status=FindingStatus.OPEN,
            recommendation="Manuelle Prüfung der themenübergreifenden Wechselwirkung empfohlen.",
        )
        db.add(ct_finding)
        db.flush()

        for obl_id in (ct.obligation_ids_theme_a or []):
            if obl_id in obl_id_set:
                db.add(Evidence(
                    finding_id=ct_finding.id,
                    obligation_id=obl_id,
                ))
        for obl_id in (ct.obligation_ids_theme_b or []):
            if obl_id in obl_id_set:
                db.add(Evidence(
                    finding_id=ct_finding.id,
                    obligation_id=obl_id,
                ))

        result.findings_created += 1
        result.cross_theme_findings += 1

    # Link MissingSafeguards to their findings
    for ms in missing_safeguards:
        if ms.finding_id:
            continue
        best_finding = None
        for f in db.query(Finding).filter_by(run_id=run_id).all():
            if f.theme.value == (
                next(
                    (o.theme.value for o in obligations if o.lens_config_id == ms.lens_config_id),
                    None,
                )
            ):
                best_finding = f
                break
        if best_finding:
            ms.finding_id = best_finding.id

    db.flush()

    step.status = RunStatus.COMPLETED
    step.output_summary = {
        "findings_created": result.findings_created,
        "obligations_grouped": result.obligations_grouped,
        "cross_theme_findings": result.cross_theme_findings,
        "playbook_matches": result.playbook_matches,
        "informational_findings": result.informational_findings,
    }
    db.flush()

    logger.info(
        "Finding generation complete: %d findings (%d informational), %d playbook matches",
        result.findings_created,
        result.informational_findings,
        result.playbook_matches,
    )
    return result
