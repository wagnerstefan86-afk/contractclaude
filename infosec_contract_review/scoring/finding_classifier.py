"""Classify obligation groups as 'risk' or 'informational'.

Reasoning
---------
Not every obligation extracted from a contract is a negotiable risk for
the reviewer. Three common kinds of clauses are NOT reviewer-relevant
negative findings:

  A. Positive compliance evidence
     e.g. "Der Auftragnehmer verfügt über ISO 27001 Zertifizierung"
     These reduce risk; they must not surface as HIGH findings.

  B. Remediation / follow-up commitments
     e.g. "Maßnahmen werden innerhalb von 30 Tagen umgesetzt"
     These also reduce risk.

  C. Standard defensive scope limitations
     e.g. "Der Auditumfang ist auf den Vertragsgegenstand beschränkt"
     These are market-standard defensive clauses, not risks.

The upstream pipeline today pushes all of these into HIGH severity
because (a) such statements typically have no frequency/time/cost
limits and (b) the baseline matcher then flags them as
``not_supported``, which the materiality scorer escalates to HIGH.

This classifier adds a conservative downstream gate: a group of
obligations is re-classified as *informational* only when NONE of the
hard risk signals fire AND every member text matches a curated
positive / remediation / defensive pattern AND none of them contains a
negation marker near that pattern. Anything ambiguous stays a normal
risk finding — we prefer false positives (a reviewer dismissing an
informational finding) over false negatives (suppressing a real risk).

The rules are plain Python data, auditable in git diff.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from infosec_contract_review.models.finding import MissingSafeguard
from infosec_contract_review.models.obligation import Obligation
from infosec_contract_review.models.playbook import PlaybookEntry
from infosec_contract_review.models.relation import ObligationRelation


# ---------------------------------------------------------------------------
# Normalization (identical idea to playbook_matcher, kept local to avoid a
# circular import and to allow cheap evolution of either set of rules).
# ---------------------------------------------------------------------------

_WS_RE = re.compile(r"\s+")
_NON_TEXT_RE = re.compile(r"[^\wäöüß%/°\- ]+", flags=re.UNICODE)


def _normalize(text: str | None) -> str:
    if not text:
        return ""
    out = []
    for ch in text.lower():
        if ch in "äöüß":
            out.append(ch)
            continue
        decomposed = unicodedata.normalize("NFD", ch)
        out.append("".join(c for c in decomposed if unicodedata.category(c) != "Mn"))
    t = "".join(out)
    t = _NON_TEXT_RE.sub(" ", t)
    return _WS_RE.sub(" ", t).strip()


# ---------------------------------------------------------------------------
# Pattern catalogues
# ---------------------------------------------------------------------------

# Each entry is a list of substrings. A text that contains ANY substring in
# a group counts as hitting that group.

_POSITIVE_CERTIFICATION = (
    "iso 27001", "iso27001",
    "iso 9001", "iso9001",
    "iso 20000", "iso 22301",
    "iso 27017", "iso 27018",
    "iso 27005",
    "soc 2", "soc2", "soc 1", "soc1",
    "bsi c5", "c5 testat", "trusted info security assurance", "tisax",
    # Matrix v1.3 CERT-002 / CERT-003: additional standard proofs that
    # belong to "positive compliance evidence" (ISAE testation, EN 50600
    # data-centre certification). GOV-001 adds ISMS / IS-Risikomanagement
    # as equivalents to the Zertifikat/Testat family for scope clauses.
    "isae 3402", "isae3402",
    "en 50600", "en50600",
    "vk3", "verfügbarkeitsklasse 3",
    "rechenzentrumszertifizierung",
    "is-risikomanagement", "is risikomanagement",
    "ismssystem",
    "zertifiziert", "zertifizierung", "zertifikat",
    "attestation", "attestierung",
    "auditbericht", "prüfbericht", "testat",
    "nachweis", "certificate", "certification", "certified",
    "assurance report",
)

_POSITIVE_COMMITMENT_VERBS = (
    "verfügt über", "verfuegt ueber", "ist zertifiziert",
    "hält", "haelt", "hat bereits", "besitzt",
    "stellt bereit", "wird bereitgestellt",
    "has a ", "holds a ", "is certified", "maintains",
    "provides a ", "ensures",
)

_REMEDIATION_PATTERN = (
    "maßnahmenplan", "maßnahmen plan", "massnahmenplan",
    "remediation plan", "action plan", "corrective action",
    "korrekturmaßnahmen", "korrekturmassnahmen",
    "behebung", "beheben", "beseitigung", "behoben",
    "umsetzung", "umgesetzt", "implementierung", "implementation",
    "nachbesserung", "nachbessern",
    "follow-up", "follow up",
    "within 30 days", "within 60 days",
)
_REMEDIATION_TIMEBOX = (
    "innerhalb von", "innerhalb einer frist", "vereinbarte frist",
    "vereinbarten fristen", "vereinbarten frist", "within",
    "binnen",
)

_DEFENSIVE_SCOPE_LIMIT = (
    "auf den vertragsgegenstand", "auf den auftragsgegenstand",
    "auf den vertrag beschränkt", "auf den vertrag begrenzt",
    "beschränkt auf den vertrag", "begrenzt auf den vertrag",
    "beschränkt auf die leistungen", "begrenzt auf die leistungen",
    "limited to the contract", "limited to the services",
    "limited to the scope of", "scope limited to",
    "im rahmen des vertrags", "im rahmen der leistung",
    "zweck des vertrags", "for the purpose of the contract",
    "nur für zwecke des vertrags", "only for the purposes of the contract",
    "auftragsumfang", "vertragsumfang",
    # "Erforderlich" bounds an audit-support obligation to what is
    # actually needed for the audit, instead of an open-ended "all
    # documents/information" duty. Live-run GS-03 showed
    # "stellt die für das Audit erforderlichen Unterlagen und Auskünfte
    # zur Verfügung" as visible high risk although the obligation is
    # explicitly scope-limited via "erforderlichen". Patterns are kept
    # narrow on audit-context wording (Unterlagen/Auskünfte) — bare
    # "erforderliche Informationen / Daten" is intentionally NOT
    # included because it misfires on incident-passthrough clauses
    # ("durch zeitnahe Bereitstellung der erforderlichen Informationen").
    "erforderlichen unterlagen", "erforderliche unterlagen",
    "erforderlichen auskünfte", "erforderliche auskünfte",
    # "Wichtiger Grund" is a German legal-language construct that bounds
    # discretionary refusal/withdrawal: "kann nur aus wichtigem Grund
    # verweigern" = the vendor MAY ONLY refuse for good cause. From the
    # buyer perspective this is a defensive limit on the vendor's veto.
    # Live-run GS-03 still surfaces the Mandantentrennung-Schutz clause
    # as visible risk without these patterns.
    "nur aus wichtigem grund", "nur bei wichtigem grund",
    "nur aus wichtigen gründen", "nur bei wichtigen gründen",
    "aus wichtigem grund verweigern", "aus wichtigem grund widersprechen",
    "for good cause only", "only for good cause",
    # Matrix v1.3 AUD-010: scope limited to contract object AND
    # "unmittelbarer Zusammenhang"-processes. The umbrella
    # "vertragsgegenstand" is already above; add the connector so
    # clauses that omit the noun but keep the relational wording also
    # land on scope_limit.
    "unmittelbarer zusammenhang", "unmittelbarem zusammenhang",
    "in unmittelbarem zusammenhang",
)

# ---------------------------------------------------------------------------
# Explicit-limit patterns (Phase 2a)
# ---------------------------------------------------------------------------
# Clauses that regulate a risk (frequency cap, notice period, time window,
# consent requirement, compensation model, penalty cap, maintenance
# exclusion, DR/BCM suspension) must not surface as normal HIGH/HIGH
# findings. These phrases mark "the risk is limited" in the obligation
# text. A RISK-AMPLIFIER check guards against inversions like
# "NICHT ausgenommen" or "OHNE Cap".

_EXPLICIT_LIMITS_FREQUENCY = (
    "1x jährlich", "1 x jährlich", "einmal jährlich", "einmal im jahr",
    "jährlich einmal", "pro jahr", "pro kalenderjahr",
    "max einmal", "max. einmal", "max 1x", "max. 1x",
    "maximal einmal", "maximal 1x", "höchstens einmal", "höchstens 1x",
    "once a year", "once per year", "annually",
)
_EXPLICIT_LIMITS_NOTICE = (
    "werktage vorlauf", "werktagen vorlauf",
    "werktage vorher", "werktagen vorher",
    "tage vorlauf", "tagen vorlauf",
    "mit vorlaufzeit von", "mit vorlauf von",
    "einer vorlaufzeit von", "vorlaufzeit von mindestens",
    "mit ankündigungsfrist", "ankündigungsfrist von",
    "nach vorheriger ankündigung", "mit vorheriger ankündigung",
    "mit vorheriger schriftlicher ankündigung",
    "vorab angekündigt", "with advance notice",
    "advance notice of",
    # Matrix v1.3 AUD-003: audit-questionnaire preparation — "15
    # Kalendertage vorab" / "Werktage vorab". Different wording than
    # the above Vorlauf-variants (describes the TIMING of question
    # delivery, not the audit announcement itself) but functionally
    # the same scope-limit signal.
    "kalendertage vorab", "kalendertagen vorab",
    "werktage vorab", "werktagen vorab",
    "tage vorab", "tagen vorab",
)
_EXPLICIT_LIMITS_TIMEWINDOW = (
    "während geschäftszeiten", "während der geschäftszeiten",
    "während üblicher geschäftszeiten", "zu üblichen geschäftszeiten",
    "innerhalb der geschäftszeiten", "innerhalb normaler geschäftszeiten",
    "during business hours", "during normal business hours",
    # Servicezeiten is the contract-speak variant of Geschäftszeiten.
    # GS-03 live-run showed "P1 4h während der Servicezeiten" as visible
    # high risk even though the time window IS explicitly bounded.
    "während der servicezeiten", "während servicezeiten",
    "innerhalb der servicezeiten", "innerhalb servicezeiten",
    "zu servicezeiten", "zu den servicezeiten",
    "während der service-zeiten", "während service-zeiten",
    "during service hours",
)
_EXPLICIT_LIMITS_CONSENT = (
    "mit zustimmung", "mit schriftlicher zustimmung",
    "nach zustimmung", "nach vorheriger zustimmung",
    "nach vorheriger schriftlicher zustimmung",
    "mit genehmigung", "mit vorheriger genehmigung",
    "mit einwilligung", "nach einwilligung",
    "with consent", "with prior consent",
    "with written consent", "with prior written consent",
    "subject to approval", "subject to prior approval",
    "prior approval", "prior written approval",
    "nur mit zustimmung", "nur nach zustimmung",
    "only with consent", "only upon approval",
    # Genitive / passive phrasings common in German contract language.
    "der zustimmung", "der schriftlichen zustimmung",
    "der vorherigen zustimmung", "der vorherigen schriftlichen zustimmung",
    "vorheriger zustimmung", "vorheriger schriftlicher zustimmung",
    "einer zustimmung", "einer vorherigen zustimmung",
    "der genehmigung", "der vorherigen genehmigung",
    "vorheriger genehmigung",
    "bedürfen der zustimmung", "bedarf der zustimmung",
    "bedürfen der genehmigung", "bedarf der genehmigung",
    "bedürfen einer zustimmung", "bedarf einer zustimmung",
    "zustimmungspflichtig", "genehmigungspflichtig",
)
_EXPLICIT_LIMITS_PRIORITY_MATRIX = (
    # Priority 2+ tickets with an "hours" magnitude are almost always
    # standard SLA-matrix content, not a 15-min-P1 risk. P1 with tight
    # times is already caught upstream by PB-SLA-004's matcher.
    "priorität 2", "priorität 3", "priorität 4",
    "priority 2", "priority 3", "priority 4",
    "prio 2", "prio 3", "prio 4",
    " p2 ", " p3 ", " p4 ",
    "p2 reaktionszeit", "p3 reaktionszeit", "p4 reaktionszeit",
    "p2 reaktion", "p3 reaktion", "p4 reaktion",
    "sev2", "sev 2", "severity 2",
    "sev3", "sev 3", "severity 3",
    "sev4", "sev 4", "severity 4",
    "für störungen der priorität 2", "für störungen der priorität 3",
    "für störungen der priorität 4",
)
_EXPLICIT_LIMITS_COST_MODEL = (
    "nach aufwand", "gegen aufwand", "gegen erstattung",
    "gegen kostenerstattung", "gegen nachweis",
    "nach tatsächlichem aufwand", "vereinbarten tagessätze",
    "auf basis der vereinbarten tagessätze",
    "nach tagessatz", "zu tagessätzen", "zu aktuellen tagessätzen",
    "zu marktüblichen sätzen", "zu den marktüblichen",
    "gegen honorar", "gegen vergütung", "gegen bezahlung",
    "gegen pauschale", "gegen eine pauschale",
    "gesondert vergütet", "gesondert abgerechnet",
    "berechnet nach", "abgerechnet nach",
    "time and material", "time & material",
    "at cost", "on a cost basis",
    # Matrix v1.3 AUD-004: "X Personentage inklusive, darüber nach Aufwand"
    # is the approved audit-cost-model. Mark the "inklusive"-side as a
    # positive cost-limit; the "nach aufwand"-side is already covered
    # above.
    "personentage inklusive", "personentage inkl.",
    "pt inklusive", "pt inkl.",
    "personentage inkl",
)
_EXPLICIT_LIMITS_PENALTY_CAP = (
    "gedeckelt auf", "gedeckelt bei", "gedeckelt",
    "gedeckelte service credit", "gedeckelte vertragsstrafe",
    "cap auf", "cap bei", "capped at", "capped",
    "jahres-cap", "jahrescap", "monats-cap", "monatscap",
    "monthly cap", "annual cap",
    "deckelung auf", "deckelung bei", "deckelung von",
    "begrenzt auf", "limitiert auf", "limit auf",
    "auf maximal",
    "max % des monatsentgelts", "max. % des monatsentgelts",
    "maximal % des monatsentgelts", "maximal % des jahresentgelts",
    "höchstens % des monatsentgelts", "höchstens % des jahresentgelts",
    "obergrenze von", "jährliche obergrenze", "monatliche obergrenze",
)
_EXPLICIT_LIMITS_STANDARD_DEADLINE = (
    # Standard incident-reporting deadlines (24 h is explicitly acceptable
    # per playbook PB-INC-001). These markers flag "the deadline is the
    # standard one, not the risky-short variant".
    "innerhalb von 24 stunden", "innerhalb 24 stunden",
    "binnen 24 stunden", "within 24 hours", "within twenty-four hours",
    "24-stunden-frist", "24h-frist",
    "spätestens 24 stunden", "spätestens innerhalb von 24",
    "innerhalb von 72 stunden", "within 72 hours",
)
_EXPLICIT_LIMITS_MAINTENANCE_EXCLUDED = (
    "wartungsfenster sind ausgenommen", "wartungsfenster ausgenommen",
    "wartung ist ausgenommen", "wartung ausgenommen",
    "wartungsfenster werden ausgenommen",
    "wartungsarbeiten sind ausgenommen",
    "geplante wartungsarbeiten sind ausgenommen",
    "geplante wartung ausgenommen",
    "excluded from availability", "excluded maintenance",
    "planned maintenance is excluded",
    "wartungszeiten nicht berücksichtigt",
    "von der verfügbarkeitsmessung ausgenommen",
    "von der sla-messung ausgenommen",
    "aus der berechnung der verfügbarkeit herausgerechnet",
    "herausgerechnet",
)
_EXPLICIT_LIMITS_DR_SUSPENSION_PRESENT = (
    "sla werden bei dr", "sla werden bei bcm",
    "sla wird bei dr", "sla wird bei bcm",
    "werden bei dr ausgesetzt", "werden bei bcm ausgesetzt",
    "wird bei dr ausgesetzt", "wird bei bcm ausgesetzt",
    "werden im dr-fall ausgesetzt", "werden im bcm-fall ausgesetzt",
    "ausgesetzt bei dr", "ausgesetzt bei bcm",
    "ausgesetzt im dr-fall", "ausgesetzt im bcm-fall",
    "suspendiert bei dr", "suspendiert bei bcm",
    "suspendiert im dr-fall", "suspendiert im bcm-fall",
    "suspension gilt bei dr", "suspension gilt bei bcm",
    "für die dauer des notfallbetriebs ausgesetzt",
    "für die dauer des dr-falls ausgesetzt",
    "für die dauer des bcm-falls ausgesetzt",
    "ausgenommen bei dr", "ausgenommen bei bcm",
    "ausgenommen im dr-fall", "ausgenommen im bcm-fall",
)

_EXPLICIT_LIMIT_ALL = (
    _EXPLICIT_LIMITS_FREQUENCY
    + _EXPLICIT_LIMITS_NOTICE
    + _EXPLICIT_LIMITS_TIMEWINDOW
    + _EXPLICIT_LIMITS_CONSENT
    + _EXPLICIT_LIMITS_COST_MODEL
    + _EXPLICIT_LIMITS_PENALTY_CAP
    + _EXPLICIT_LIMITS_MAINTENANCE_EXCLUDED
    + _EXPLICIT_LIMITS_DR_SUSPENSION_PRESENT
    + _EXPLICIT_LIMITS_STANDARD_DEADLINE
    + _EXPLICIT_LIMITS_PRIORITY_MATRIX
)

# Risk amplifiers veto the explicit_limit classification. If any of these
# occurs, the clause is NOT a standard limit — it is the risky case.
# Substring form is deliberately specific (e.g. "nicht ausgenommen" rather
# than plain "nicht") to avoid misfiring on unrelated negations.
_EXPLICIT_LIMIT_RISK_AMPLIFIERS = (
    "unbegrenzt", "unlimitiert", "unlimited",
    "ohne begrenzung", "keine begrenzung", "nicht begrenzt",
    "ohne limit", "kein limit",
    "ohne cap", "kein cap", "uncapped", "without cap", "no cap",
    "ohne deckelung", "keine deckelung",
    "nicht gedeckelt", "ungedeckelt",
    "ohne obergrenze", "keine obergrenze",
    "jederzeit", "anytime",
    "ohne ankündigung", "ohne vorlaufzeit",
    "outside business hours", "unangekündigt",
    "außerhalb der servicezeiten", "außerhalb der geschäftszeiten",
    "außerhalb servicezeiten", "außerhalb geschäftszeiten",
    "ohne zustimmung", "ohne genehmigung", "without consent",
    "nicht ausgenommen", "nicht ausgesetzt",
    "nicht suspendiert",
    "nicht aus der berechnung",
    "werden nicht ausgesetzt", "wird nicht ausgesetzt",
    "werden nicht suspendiert", "wird nicht suspendiert",
    "gilt auch bei dr", "gilt auch bei bcm",
    "gelten auch bei dr", "gelten auch bei bcm",
    "weiter gelten", "gilt weiter", "gelten weiter",
    # Tight-time markers that must NOT count as "standard deadlines":
    "2 stunden", "two hours", "2 hours",
    "3 stunden", "3 hours",
    "unverzüglich", "sofort", "immediately",
    # Risk-marker for "every event" (PB-INC-002 territory):
    "jedes security-event", "jedes security event", "jeder vorfall",
)


_NEGATION_NEAR_POSITIVE = (
    # If these appear in the text, do not count it as positive. This is
    # a cheap "negation nearby" heuristic — good enough when the text is
    # the LLM-cleaned obligation summary, which is typically one claim.
    "nicht ", "kein ", "keine ", "keinen ", "keiner ", "keines ",
    "ohne ", "fehlt", "fehlen", "mangeln", "unzureichend",
    "nicht nachgewiesen", "nicht vorhanden", "nicht erfüllt", "nicht belegt",
    "not ", " no ", "missing", "lack of", "without", "insufficient",
    "inadequate", "cannot", "unable",
)


@dataclass
class Classification:
    kind: str  # "risk" | "informational"
    reason: str  # short audit trail, persisted in the Finding description


def _contains_any(text: str, needles: tuple[str, ...]) -> bool:
    return any(n in text for n in needles)


def _is_positive_text(text: str) -> tuple[bool, str]:
    """True if text matches a positive/remediation/defensive pattern AND
    no negation marker is near it.

    Returns (is_positive, matched_category) for diagnostics.
    """
    # Explicit-limit detection runs FIRST because it has its own, tighter
    # risk-amplifier veto. The generic "nicht/kein/ohne"-check used by
    # the other categories would misfire on legitimate limit sentences
    # that happen to contain "ohne" (e.g. "ohne zusätzliche Kosten").
    if _contains_any(text, _EXPLICIT_LIMIT_ALL) and not _contains_any(
        text, _EXPLICIT_LIMIT_RISK_AMPLIFIERS
    ):
        return True, "explicit_limit"

    if _contains_any(text, _NEGATION_NEAR_POSITIVE):
        # Generic negation short-circuit for the remaining categories.
        return False, ""

    cert_hit = _contains_any(text, _POSITIVE_CERTIFICATION)
    commit_hit = _contains_any(text, _POSITIVE_COMMITMENT_VERBS)
    if cert_hit and (commit_hit or "zertifiz" in text or "nachweis" in text
                     or "testat" in text or "auditbericht" in text):
        return True, "certification"

    remediation_hit = _contains_any(text, _REMEDIATION_PATTERN)
    timebox_hit = _contains_any(text, _REMEDIATION_TIMEBOX)
    # Timebox alone is not enough — it must co-occur with a concrete
    # remediation context word. "maßnahme" + "innerhalb vereinbarter
    # Fristen" is a classic remediation commitment; "meldefrist" is not,
    # because it co-occurs with "meldung" which is not in this list.
    remediation_context = (
        "maßnahme" in text or "massnahme" in text
        or "tag" in text or "day" in text
        or "woche" in text or "week" in text
        or "monat" in text or "month" in text
    )
    if remediation_hit or (timebox_hit and remediation_context):
        return True, "remediation"

    if _contains_any(text, _DEFENSIVE_SCOPE_LIMIT):
        return True, "scope_limit"

    return False, ""


# ---------------------------------------------------------------------------
# Hard risk signals
# ---------------------------------------------------------------------------

def _has_missing_safeguard_for_group(
    group_obls: list[Obligation],
    missing_safeguards: list[MissingSafeguard],
    obligation_only: bool = False,
) -> bool:
    """Does a MissingSafeguard point into this cluster?

    With ``obligation_only=True`` only direct obligation-id links count.
    That is the "strong" signal: this specific obligation is missing a
    safeguard, so it must surface as a risk regardless of text patterns.

    With ``obligation_only=False`` (default) lens-level links also count.
    That is the "weak" signal: some obligation on the same lens has a
    missing safeguard. Used as a fallback when the text itself is not
    clearly positive — see classify_group.
    """
    obl_ids = {o.id for o in group_obls}
    lens_ids = {o.lens_config_id for o in group_obls if o.lens_config_id}
    for ms in missing_safeguards:
        if ms.status != "missing":
            continue
        if ms.finding_id is not None:
            # Already attached elsewhere; only count if it points into our group
            continue
        if ms.obligation_id and ms.obligation_id in obl_ids:
            return True
        if obligation_only:
            continue
        if ms.lens_config_id and ms.lens_config_id in lens_ids:
            return True
    return False


def _has_risky_relation(
    group_obls: list[Obligation],
    relations: list[ObligationRelation],
) -> bool:
    obl_ids = {o.id for o in group_obls}
    for rel in relations:
        rt = rel.relation_type.value if hasattr(rel.relation_type, "value") else str(rel.relation_type)
        if rt != "contradicts":
            continue
        if rel.obligation_a_id in obl_ids or rel.obligation_b_id in obl_ids:
            return True
    return False


def _has_explicit_gap(group_obls: list[Obligation]) -> bool:
    """baseline_match_status other than not_supported-by-default. We only
    accept it as a real gap if the gap description is actually non-empty
    AND the text does not itself look positive."""
    for obl in group_obls:
        if obl.baseline_match_status == "not_supported":
            # not_supported alone is not enough — baseline_matcher also
            # sets it whenever there are no limits, which is exactly the
            # false-positive we try to fix here. So we only count it if
            # the gap description is informative AND the text doesn't
            # read positive.
            gap = (obl.baseline_gap_description or "").strip().lower()
            if gap and "keine begrenzungen" not in gap:
                text = _normalize(
                    (obl.summary or "") + " " + (obl.verbatim_quote or "")
                )
                positive, _cat = _is_positive_text(text)
                if not positive:
                    return True
    return False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def classify_group(
    group_obls: list[Obligation],
    playbook: PlaybookEntry | None,
    missing_safeguards: list[MissingSafeguard],
    relations: list[ObligationRelation],
) -> Classification:
    """Decide whether a group of obligations should surface as a normal
    negative finding or as an informational/positive one.

    The decision is intentionally conservative: anything with a hard
    risk signal stays a risk. Only when NO risk signals fire and every
    member text clearly matches a positive pattern does the group get
    flipped to informational.
    """
    # 1a. Strong risk signals — these always win, regardless of text.
    #     - direct playbook match,
    #     - direct obligation-id link on a missing safeguard,
    #     - contradicts relation.
    if playbook is not None:
        return Classification("risk", "playbook match")
    if _has_missing_safeguard_for_group(
        group_obls, missing_safeguards, obligation_only=True
    ):
        return Classification("risk", "missing safeguard (obligation-linked)")
    if _has_risky_relation(group_obls, relations):
        return Classification("risk", "contradicts relation")

    # 2. Positive-text check. If every member clearly reads as a
    #    limit / certification / remediation / defensive-scope clause,
    #    surface the group as informational. Lens-only missing
    #    safeguards and generic baseline_gap markers (tier-2 signals)
    #    must not drown out that explicit textual evidence — GS-03
    #    22.04-live showed all-audit-positive clauses flipping back to
    #    visible HIGH because a LENS-AUDIT-wide MissingSafeguard was
    #    treated as a hard signal here.
    categories: set[str] = set()
    all_positive = True
    for obl in group_obls:
        text = _normalize((obl.summary or "") + " " + (obl.verbatim_quote or ""))
        if not text:
            return Classification("risk", "empty text (default to risk)")
        is_pos, cat = _is_positive_text(text)
        if not is_pos:
            all_positive = False
            break
        categories.add(cat)

    # 1b. Tier-2 risk signals. Fire only when the text itself is not
    #     already clearly positive.
    if not all_positive:
        if _has_missing_safeguard_for_group(group_obls, missing_safeguards):
            return Classification("risk", "missing safeguard (lens-linked)")
        if _has_explicit_gap(group_obls):
            return Classification("risk", "baseline gap")
        return Classification("risk", "at least one member not positive")

    reason = "informational: " + "+".join(sorted(categories))
    return Classification("informational", reason)
