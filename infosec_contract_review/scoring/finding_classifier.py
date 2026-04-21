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
    "soc 2", "soc2", "soc 1", "soc1",
    "bsi c5", "c5 testat", "trusted info security assurance", "tisax",
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
    if _contains_any(text, _NEGATION_NEAR_POSITIVE):
        # Negation short-circuits. Any negation nearby means we can't be
        # sure the statement is positive — treat as ambiguous.
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
) -> bool:
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
    # 1. Hard risk signals
    if playbook is not None:
        return Classification("risk", "playbook match")
    if _has_missing_safeguard_for_group(group_obls, missing_safeguards):
        return Classification("risk", "missing safeguard")
    if _has_risky_relation(group_obls, relations):
        return Classification("risk", "contradicts relation")
    if _has_explicit_gap(group_obls):
        return Classification("risk", "baseline gap")

    # 2. Positive classification: every member must look positive
    categories: set[str] = set()
    for obl in group_obls:
        text = _normalize((obl.summary or "") + " " + (obl.verbatim_quote or ""))
        if not text:
            return Classification("risk", "empty text (default to risk)")
        is_pos, cat = _is_positive_text(text)
        if not is_pos:
            return Classification("risk", "at least one member not positive")
        categories.add(cat)

    reason = "informational: " + "+".join(sorted(categories))
    return Classification("informational", reason)
