"""Match obligations to playbook entries.

Matching strategy (explicit, auditable):
1. Normalize text: lowercase + accent strip + whitespace collapse.
2. Combine obligation.summary + verbatim_quote as the search corpus.
3. For each playbook entry, look up a curated KeywordSignature:
     - required_groups: every group must produce at least one substring hit.
     - support_groups:  count of groups that have at least one hit.
     - negative_any:    if any phrase appears, the entry is disqualified.
   An entry matches when required is satisfied AND support-hit count >=
   its min_support_hits threshold AND no negative phrase is present.
4. If multiple entries match, the one with the most support hits wins
   (ties broken by the number of matching required-group members).
5. Playbook entries without a signature fall back to the legacy
   token-overlap heuristic (unchanged, still gated by a score threshold).

Design goals:
- No fuzzy magic; every rule is explicit Python data.
- Synonyms, DE/EN mixed terminology, singular/plural and common
  inflection stems live in the signature tables — readable & diff-able.
- Conservative: requires at least one direct topic hit AND a supporting
  keyword, so generic terms like "Audit" alone don't trigger a match.
"""
from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import dataclass, field

from infosec_contract_review.models.obligation import Obligation
from infosec_contract_review.models.playbook import PlaybookEntry

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Text normalization
# ---------------------------------------------------------------------------

_WS_RE = re.compile(r"\s+")
_NON_TEXT_RE = re.compile(r"[^\wäöüß%/°\- ]+", flags=re.UNICODE)


def normalize(text: str | None) -> str:
    """Lowercase, strip accents, collapse whitespace. Keep umlauts intact."""
    if not text:
        return ""
    t = text.lower()
    # Preserve German umlauts / ß, strip other accents.
    out = []
    for ch in t:
        if ch in "äöüß":
            out.append(ch)
            continue
        decomposed = unicodedata.normalize("NFD", ch)
        stripped = "".join(c for c in decomposed if unicodedata.category(c) != "Mn")
        out.append(stripped)
    t = "".join(out)
    t = _NON_TEXT_RE.sub(" ", t)
    t = _WS_RE.sub(" ", t).strip()
    return t


# ---------------------------------------------------------------------------
# Keyword signatures per playbook entry
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class KeywordSignature:
    required_groups: tuple[tuple[str, ...], ...]
    support_groups: tuple[tuple[str, ...], ...] = ()
    negative_any: tuple[str, ...] = ()
    min_support_hits: int = 1


def _g(*terms: str) -> tuple[str, ...]:
    """Helper: a keyword group (all entries are lowercase, normalized)."""
    return tuple(normalize(t) for t in terms)


# Signatures are keyed by the stable playbook entry id string ("PB-AUDIT-001").
# Each term is matched as a substring against the normalized corpus — that
# covers "auditfrequenz" matching "audit" and "frequenz" individually.
PLAYBOOK_SIGNATURES: dict[str, KeywordSignature] = {
    # ------------------------------------------------------------------ AUDIT
    "PB-AUDIT-001": KeywordSignature(
        # Unlimited audit right, no notice/frequency cap
        required_groups=(
            _g("audit", "prüfung", "prüfungsrecht", "prüfer", "inspection", "inspektion"),
        ),
        support_groups=(
            _g(
                "unbegrenzt", "unlimitiert", "unlimited",
                "ohne begrenzung", "keine begrenzung", "nicht begrenzt",
                "ohne limit", "kein limit",
                "jederzeit", "anytime",
                "ohne vorlaufzeit", "ohne ankündigung",
                "outside business hours", "außerhalb",
            ),
            _g(
                "häufigkeit", "frequenz", "frequency",
                "vorlaufzeit", "notice", "ankündigungsfrist",
                "zeitfenster", "geschäftszeiten", "business hours",
                "limit",
            ),
        ),
        min_support_hits=1,
    ),
    "PB-AUDIT-002": KeywordSignature(
        # Direct audit right for end customers / third parties.
        # Theme filter already constrains us to audit_rights, so we only
        # need the distinctive "third-party / end-customer" marker.
        required_groups=(
            _g(
                "endkunde", "endkunden",
                "dritte", "drittprüfer", "dritter prüfer",
                "third party", "third-party",
                "kunde des auftraggebers",
            ),
        ),
        support_groups=(
            _g(
                "ohne ankündigung", "ohne vorherige", "jederzeit",
                "eigenständig", "direkt", "unmittelbar",
                "mandantenschutz", "auditrecht", "prüfungsrecht",
                "eingesetzt", "zugang",
            ),
        ),
        min_support_hits=1,
    ),
    "PB-AUDIT-003": KeywordSignature(
        # Free-of-charge audit support. Theme filter covers the audit
        # context; the distinctive marker here is "at no cost" combined
        # with a resource/support keyword.
        required_groups=(
            _g(
                "kostenfrei", "kostenlos", "ohne kosten", "ohne entgelt",
                "free of charge", "at no cost",
                "unentgeltlich",
            ),
            _g(
                "unterstützung", "unterlagen", "dokumentation",
                "personal", "ressourcen", "zugang", "zugänge",
                "support", "audit", "prüfung", "bereitstellen", "zur verfügung",
            ),
        ),
        min_support_hits=0,
    ),

    # -------------------------------------------------------------- INCIDENT
    "PB-INC-001": KeywordSignature(
        # Unrealistically short reporting deadline (<4h or outside service window).
        # Intentionally conservative: the 24h standard case must NOT match.
        required_groups=(
            _g(
                "meldung", "meldepflicht", "meldefrist",
                "report", "reporting", "notification",
                "sicherheitsvorfall", "sicherheitsvorfälle", "security incident", "vorfall",
            ),
            # Must contain a tight-time marker — broad "stunden"/"hours" is
            # deliberately excluded so that "innerhalb von 24 Stunden" does
            # not trigger a match.
            _g(
                "unverzüglich", "sofort", "umgehend", "immediately",
                " 1h", " 2h", " 3h", " 4h",
                "1 stunde", "2 stunden", "3 stunden", "4 stunden",
                "einer stunde", "zwei stunden",
                "within one hour", "within two hours", "within four hours",
                "minuten", "minutes",
                "außerhalb der servicezeit", "outside business hours",
                "außerhalb der geschäftszeit",
            ),
        ),
        negative_any=(
            # Explicit 24h-style deadlines are acceptable per playbook.
            "24 stunden", "24 stunde", " 24h", "innerhalb von 24",
            "innerhalb 24", "within 24",
        ),
        min_support_hits=0,
    ),
    "PB-INC-002": KeywordSignature(
        # Reporting obligation for EVERY security event (no threshold)
        required_groups=(
            _g(
                "meldung", "meldepflicht",
                "notify", "reporting", "report",
            ),
            _g(
                "jedes", "jeder", "jeden", "alle", "sämtliche",
                "any", "every", "all",
                "ohne schwellenwert", "kein schwellenwert",
                "no threshold", "without threshold",
            ),
        ),
        support_groups=(
            _g(
                "security-event", "security event", "sicherheitsereignis",
                "ereignis", "event", "vorfall", "vorfälle",
            ),
        ),
        min_support_hits=0,
    ),
    "PB-INC-003": KeywordSignature(
        # Regulatory reporting duties passed through to vendor
        required_groups=(
            _g(
                "meldung", "meldepflicht",
                "notification", "reporting obligation",
            ),
            _g(
                "aufsichtsbehörde", "aufsicht", "behörde",
                "regulator", "regulatory", "regulatorisch",
                "bafin", "bsi", "dsgvo",
            ),
        ),
        support_groups=(
            _g(
                "auftragnehmer meldet", "durch den auftragnehmer",
                "on behalf of", "im auftrag",
                "gegenüber", "an die behörde",
            ),
        ),
        min_support_hits=0,
    ),

    # ------------------------------------------------------------------- SLA
    "PB-SLA-001": KeywordSignature(
        # SLA without maintenance-window exemption
        required_groups=(
            _g("sla", "service level", "verfügbarkeit", "availability"),
        ),
        support_groups=(
            _g(
                "wartung", "wartungsfenster", "maintenance", "maintenance window",
                "planned maintenance",
            ),
            _g(
                "ausgenommen", "exempt", "nicht einbezogen",
                "ohne ausnahme", "keine ausnahme",
                "fehlt", "ohne wartungsfenster",
            ),
        ),
        min_support_hits=2,
    ),
    "PB-SLA-002": KeywordSignature(
        # Availability >= 99.99% or transactional measurement
        required_groups=(
            _g("verfügbarkeit", "availability", "uptime"),
        ),
        support_groups=(
            _g(
                "99.99", "99,99", "99.999", "99,999",
                "four nines", "vier neunen",
                "transaktion", "transaktionsbasiert", "transactional",
                "per transaction",
            ),
        ),
        min_support_hits=1,
    ),
    "PB-SLA-003": KeywordSignature(
        # No SLA suspension during DR / BCM
        required_groups=(
            _g("sla", "verfügbarkeit", "service level"),
            _g(
                "dr", "disaster recovery", "bcm",
                "business continuity", "notfall", "notfallbetrieb",
                "itscm",
            ),
        ),
        support_groups=(
            _g(
                "suspendier", "suspension", "ausgesetzt", "ausnahme",
                "nicht ausgesetzt", "ohne suspension",
                "weiter gelten", "gilt weiter",
            ),
        ),
        min_support_hits=0,
    ),
}


# ---------------------------------------------------------------------------
# Matching
# ---------------------------------------------------------------------------

@dataclass
class MatchScore:
    entry: PlaybookEntry
    required_hits: int
    support_hits: int
    total_hits: int


def _corpus_for(obligation: Obligation) -> str:
    parts = [obligation.summary or "", obligation.verbatim_quote or ""]
    if obligation.baseline_gap_description:
        parts.append(obligation.baseline_gap_description)
    return normalize(" ".join(parts))


def _count_group_hits(text: str, groups: tuple[tuple[str, ...], ...]) -> tuple[int, int]:
    """Return (groups_with_at_least_one_hit, total_distinct_term_hits)."""
    hit_groups = 0
    total_terms = 0
    for group in groups:
        any_hit = False
        for term in group:
            if term and term in text:
                total_terms += 1
                any_hit = True
        if any_hit:
            hit_groups += 1
    return hit_groups, total_terms


def _signature_match(
    obligation: Obligation,
    pe: PlaybookEntry,
    text: str,
) -> MatchScore | None:
    sig = _signature_for_entry(pe)
    if sig is None:
        return None

    for neg in sig.negative_any:
        if neg and neg in text:
            return None

    required_hit_groups, _ = _count_group_hits(text, sig.required_groups)
    if required_hit_groups < len(sig.required_groups):
        return None

    support_hit_groups, support_total = _count_group_hits(text, sig.support_groups)
    if support_hit_groups < sig.min_support_hits:
        return None

    return MatchScore(
        entry=pe,
        required_hits=required_hit_groups,
        support_hits=support_hit_groups,
        total_hits=required_hit_groups * 10 + support_total,
    )


def _signature_for_entry(pe: PlaybookEntry) -> KeywordSignature | None:
    # The playbook entry's natural key is the business id (e.g. PB-AUDIT-001).
    # The seed loader stores it in the ``id`` column, but downstream we only
    # receive the DB uuid. We therefore fall back to matching by a short
    # business-key embedded in one of the text fields.
    candidates = [
        getattr(pe, "id", "") or "",
        getattr(pe, "version", "") or "",
    ]
    for cand in candidates:
        for key in PLAYBOOK_SIGNATURES:
            if key in cand:
                return PLAYBOOK_SIGNATURES[key]
    # Fallback: derive the key from the risk_pattern (stable heuristic).
    pattern_key = _derive_key_from_pattern(pe)
    if pattern_key and pattern_key in PLAYBOOK_SIGNATURES:
        return PLAYBOOK_SIGNATURES[pattern_key]
    return None


def _derive_key_from_pattern(pe: PlaybookEntry) -> str | None:
    """Map a playbook entry to a signature key by inspecting its risk_pattern.

    This is a deterministic bridge so signatures keep working even if the
    entry id column stores a UUID (production DB) rather than the business
    key from the seed YAML. The mapping is explicit and audit-friendly.
    """
    pattern = normalize(pe.risk_pattern or "")
    theme = pe.theme.value if hasattr(pe.theme, "value") else str(pe.theme)

    if theme == "audit_rights":
        if "unbegrenzt" in pattern or "häufigkeitslimit" in pattern or "vorlaufzeit" in pattern:
            return "PB-AUDIT-001"
        if "endkunde" in pattern or "dritte" in pattern or "drittprüfer" in pattern:
            return "PB-AUDIT-002"
        if "kostenfrei" in pattern:
            return "PB-AUDIT-003"
    if theme == "incident_reporting":
        if "kurz" in pattern and ("meldefrist" in pattern or "meldung" in pattern):
            return "PB-INC-001"
        if "jedes" in pattern or "security-event" in pattern or "security event" in pattern or "schwellenwert" in pattern:
            return "PB-INC-002"
        if "regulatorisch" in pattern:
            return "PB-INC-003"
    if theme == "sla_feasibility":
        if "wartungsfenster" in pattern:
            return "PB-SLA-001"
        if "99.99" in pattern or "99,99" in pattern or "transakt" in pattern:
            return "PB-SLA-002"
        if "dr" in pattern or "bcm" in pattern or "suspension" in pattern:
            return "PB-SLA-003"
    return None


# ---------------------------------------------------------------------------
# Fallback: legacy token-overlap heuristic (kept for entries w/o signature)
# ---------------------------------------------------------------------------

def _legacy_token_score(pe: PlaybookEntry, text: str) -> int:
    pattern_words = [
        w for w in normalize(pe.risk_pattern or "").split()
        if len(w) > 3
    ]
    applicable_words = [
        w for w in normalize(pe.applicable_when or "").split()
        if len(w) > 3
    ]
    score = sum(1 for w in pattern_words if w in text) * 2
    score += sum(1 for w in applicable_words if w in text)
    return score


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def match_obligation_to_playbook(
    obligation: Obligation,
    playbook_entries: list[PlaybookEntry],
) -> PlaybookEntry | None:
    """Return the best-matching PlaybookEntry for the obligation, or None."""
    obl_theme = obligation.theme.value if hasattr(obligation.theme, "value") else str(obligation.theme)
    theme_entries = [
        pe for pe in playbook_entries
        if pe.is_active and (
            pe.theme.value if hasattr(pe.theme, "value") else str(pe.theme)
        ) == obl_theme
    ]
    if not theme_entries:
        return None

    text = _corpus_for(obligation)
    if not text:
        return None

    # 1) Try signature-based matching first.
    sig_matches: list[MatchScore] = []
    for pe in theme_entries:
        score = _signature_match(obligation, pe, text)
        if score is not None:
            sig_matches.append(score)

    if sig_matches:
        sig_matches.sort(
            key=lambda s: (s.required_hits, s.support_hits, s.total_hits),
            reverse=True,
        )
        return sig_matches[0].entry

    # 2) Fallback to the legacy overlap heuristic (conservative threshold).
    best: PlaybookEntry | None = None
    best_score = 0
    for pe in theme_entries:
        if _signature_for_entry(pe) is not None:
            # Signature existed but did not match → don't fall back for it.
            continue
        score = _legacy_token_score(pe, text)
        if score > best_score:
            best_score = score
            best = pe
    if best_score >= 3:
        return best
    return None
