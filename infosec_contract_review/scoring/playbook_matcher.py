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
        # Unlimited audit right, no notice/frequency cap.
        # Must NOT match when the clause already states a standard
        # frequency / notice period / time-window.
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
        negative_any=(
            # Frequency is capped → not an unlimited-audit risk.
            "einmal jährlich", "1x jährlich", "1 x jährlich",
            "jährlich einmal", "pro jahr", "pro kalenderjahr",
            "max einmal", "max. einmal", "max 1x", "max. 1x",
            "maximal einmal", "maximal 1x", "höchstens einmal", "höchstens 1x",
            "once a year", "once per year", "annually",
            # Notice period is given → not a no-notice risk.
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
            # Time-window is restricted to business hours → standard.
            "während geschäftszeiten", "während der geschäftszeiten",
            "während üblicher geschäftszeiten", "zu üblichen geschäftszeiten",
            "innerhalb der geschäftszeiten", "innerhalb normaler geschäftszeiten",
            "during business hours", "during normal business hours",
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
                # Matrix v1.3 AUD-008 evidence marker: unkoordinierter
                # Drittzugriff "ohne mandat" ist ein zusätzliches
                # Risk-Support-Signal, wenn der Drittauditor-Trigger
                # (required) bereits vorliegt.
                "ohne mandat",
            ),
        ),
        negative_any=(
            # Third-party audits subject to approval → standard defensive
            # regulation, not the risk pattern this entry warns about.
            "mit zustimmung", "mit schriftlicher zustimmung",
            "nach zustimmung", "nach vorheriger zustimmung",
            "nach vorheriger schriftlicher zustimmung",
            "mit genehmigung", "mit vorheriger genehmigung",
            "nach genehmigung",
            "mit einwilligung", "nach einwilligung",
            "with consent", "with prior consent",
            "with written consent", "with prior written consent",
            "subject to approval", "subject to prior approval",
            "prior approval", "prior written approval",
            "nur mit zustimmung", "nur nach zustimmung",
            "only with consent", "only upon approval",
            # Matrix v1.3 AUD-011 (controlled third-party audit — the
            # positive variant): a clause that ships mandat + vertraulich-
            # keitsverpflichtung + wirtschaftsprüfer is the CONTROLLED
            # case and must not escalate as PB-AUDIT-002 risk.
            "schriftliches mandat", "schriftlich mandatiert",
            "schriftlich beauftragt",
            "wirtschaftsprüfer", "wirtschaftspruefer",
            "zur verschwiegenheit verpflichtet",
            "zur vertraulichkeit verpflichtet",
            "gesetzlich zur verschwiegenheit",
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
        negative_any=(
            # Compensation is explicitly regulated → not a free-lunch risk.
            "nach aufwand", "gegen aufwand", "gegen erstattung",
            "gegen kostenerstattung", "gegen nachweis",
            "nach tagessatz", "zu tagessätzen", "zu aktuellen tagessätzen",
            "zu marktüblichen sätzen", "zu den marktüblichen",
            "gegen honorar", "gegen vergütung", "gegen bezahlung",
            "gegen pauschale", "gegen eine pauschale",
            "gesondert vergütet", "gesondert abgerechnet",
            "zu vergütenden aufwand", "zu vergütender aufwand",
            "berechnet nach", "abgerechnet nach",
            "time and material", "time & material",
            "at cost", "on a cost basis", "on time and material basis",
            # Matrix v1.3 AUD-004: "X Personentage inklusive, darüber
            # nach vereinbarten Sätzen" is the approved bounded model
            # and must disqualify the "kostenfreie Unterstützung"-risk
            # match even without "nach aufwand" literal.
            "personentage inklusive", "pt inklusive",
            "personentage inkl", "pt inkl",
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
        # SLA without maintenance-window exemption.
        # Risk is the ABSENCE of an exemption. The previous signature
        # matched on any co-occurrence of "wartung" + "ausgenommen",
        # which also fires for the SAFE case "Wartungsarbeiten sind
        # ausgenommen". Support group 2 is therefore restricted to
        # risk markers (no exemption / explicitly included / missing);
        # the SAFE exemption phrases are in negative_any.
        required_groups=(
            _g(
                "sla", "service level", "verfügbarkeit", "availability",
                # Live-run GS-01 fixture shortens the summary to
                # "Geplante Wartungsfenster werden nicht aus der
                # Berechnung herausgerechnet." with no "Verfügbarkeit"
                # noun. Within the sla_feasibility theme filter the
                # word "berechnung" is specific enough to keep the
                # match SLA-scoped.
                "berechnung",
            ),
            _g(
                "wartung", "wartungsfenster", "maintenance", "maintenance window",
                "planned maintenance",
            ),
        ),
        support_groups=(
            _g(
                "nicht ausgenommen", "nicht einbezogen",
                "ohne ausnahme", "keine ausnahme",
                "ohne wartungsfenster-ausnahme",
                "wartungsfenster fehlt", "keine wartungsfenster-ausnahme",
                "werden einbezogen", "werden mitgerechnet",
                "not exempt", "not excluded",
                "included in availability",
                # "nicht (aus der Berechnung) herausgerechnet" is the
                # risk-indicating counterpart to the SAFE phrases in
                # negative_any. GS-01 / GS-02 22.04-live both use it
                # verbatim; without these support entries neither
                # obligation surfaced with a PB-SLA-001 match.
                "nicht herausgerechnet",
                "nicht aus der berechnung",
            ),
        ),
        negative_any=(
            # Maintenance is explicitly regulated → risk is NOT there.
            "wartung ausgenommen", "wartung ist ausgenommen",
            "wartungsfenster sind ausgenommen", "wartungsfenster ausgenommen",
            "wartungsfenster werden ausgenommen",
            "wartungsarbeiten sind ausgenommen", "wartungsarbeiten ausgenommen",
            "geplante wartung ausgenommen",
            "geplante wartungsarbeiten sind ausgenommen",
            "von der verfügbarkeitsmessung ausgenommen",
            "von der sla-messung ausgenommen",
            "von der messung ausgenommen",
            "nicht berücksichtigt",
            "excluded from availability", "excluded maintenance",
            "planned maintenance is excluded",
        ),
        min_support_hits=1,
    ),
    "PB-SLA-002": KeywordSignature(
        # Availability >= 99.99% or transactional measurement.
        # Bare "transaktion" removed — too many billing-/count-related
        # false positives. Only phrases that actually denote the
        # measurement method remain.
        required_groups=(
            _g("verfügbarkeit", "availability", "uptime"),
        ),
        support_groups=(
            _g(
                "99.99", "99,99", "99.999", "99,999",
                "four nines", "vier neunen",
                "transaktionsbasiert", "auf transaktionsebene",
                "pro transaktion", "je transaktion",
                "transactional", "per transaction",
                "measured per transaction",
            ),
        ),
        negative_any=(
            # Dedicated / single-tenant hosting makes four-nines plausibly
            # achievable → not the risk pattern this entry warns about.
            "dediziert", "dedicated", "single tenant", "single-tenant",
            "dedizierte infrastruktur", "dedicated infrastructure",
        ),
        min_support_hits=1,
    ),
    "PB-SLA-003": KeywordSignature(
        # No SLA suspension during DR / BCM.
        # The risk is the ABSENCE of a suspension clause, so the signature
        # must only fire when the clause explicitly says SLA keeps
        # running during DR/BCM (or such a suspension is absent / denied).
        # Positive-suspension phrases are therefore in negative_any.
        required_groups=(
            _g("sla", "verfügbarkeit", "service level"),
            _g(
                "dr", "disaster recovery", "bcm",
                "business continuity", "notfall", "notfallbetrieb",
                "itscm",
                # Blanket-no-suspension clauses ("Eine Aussetzung der
                # SLAs ist ausgeschlossen.") subsume the DR/BCM concern
                # without naming a specific scenario. Scoped to the
                # sla_feasibility theme and to the SLA+risk-marker
                # required groups, so the broader word is safe here.
                "aussetzung", "suspension",
            ),
            _g(
                # Risk markers: SLA keeps applying during DR/BCM.
                "gilt weiter", "weiter gelten", "gelten weiter",
                "gelten auch bei dr", "gelten auch bei bcm",
                "gelten auch während", "gilt auch während",
                "gilt auch bei dr", "gilt auch bei bcm",
                "ohne suspension", "keine suspension",
                "keine ausnahme bei dr", "keine ausnahme bei bcm",
                "ohne ausnahme bei dr", "ohne ausnahme bei bcm",
                "nicht ausgesetzt", "nicht suspendiert",
                "werden nicht ausgesetzt", "wird nicht ausgesetzt",
                "werden nicht suspendiert", "wird nicht suspendiert",
                "gelten unverändert", "unverändert fort",
                # "uneingeschränkt" inserts itself between verb and time
                # clause ("gelten uneingeschränkt auch während ..."), which
                # breaks the "gelten auch während" substring match above.
                "gelten uneingeschränkt", "gilt uneingeschränkt",
                "uneingeschränkt auch während", "uneingeschränkt während",
                # Blanket risk markers used with the "Aussetzung"
                # required-group entries above.
                "ist ausgeschlossen", "sind ausgeschlossen",
                "ist unzulässig", "sind unzulässig",
            ),
        ),
        negative_any=(
            # Explicit suspension clause present → risk is NOT there.
            "werden bei dr ausgesetzt", "werden bei bcm ausgesetzt",
            "wird bei dr ausgesetzt", "wird bei bcm ausgesetzt",
            "werden im dr-fall ausgesetzt", "werden im bcm-fall ausgesetzt",
            "ausgesetzt bei dr", "ausgesetzt bei bcm",
            "ausgesetzt im dr-fall", "ausgesetzt im bcm-fall",
            "suspendiert bei dr", "suspendiert bei bcm",
            "suspendiert im dr-fall", "suspendiert im bcm-fall",
            "suspension gilt", "suspendierung gilt",
            "für die dauer des notfallbetriebs ausgesetzt",
            "für die dauer des dr-falls ausgesetzt",
            "für die dauer des bcm-falls ausgesetzt",
            "sla-suspension ist geregelt",
            "explizite suspension",
            "suspension im dr", "suspension im bcm",
        ),
        min_support_hits=0,
    ),
    "PB-SLA-004": KeywordSignature(
        # Unrealistically short reaction / restore times (e.g. 15-min P1).
        # Required: a response/restore keyword AND a tight-time marker.
        # Tight-time group narrowed to <= 2 hours — 3h and 4h markers
        # dropped to avoid matching standard P3 / Managed-Print-scale
        # times (GS-03 false positives, GS-01 P3-4h granularity issue).
        required_groups=(
            _g(
                "reaktion", "reaktionszeit", "response time",
                "wiederherstell", "wiederherstellungszeit",
                "restore time", "restore-zeit", "resolution time",
                "entstör", "entstörzeit",
                "p1", "priorität 1", "priority 1",
                "severity 1", "sev1", "sev 1",
                # Hard recovery goals (RPO / RTO with a tight value) live in
                # the same family as an unrealistic-response-time risk.
                # GS-02 22.04-live "RPO 0 Minuten" and "RTO 30 Minuten"
                # both belong here; keep these abbreviations as first-tier
                # triggers to catch clauses that don't name a priority.
                "rpo", "rto",
                "recovery point", "recovery time",
                "datenverlusttoleranz",
            ),
            _g(
                "15 min", "20 min", "30 min",
                "15 minuten", "20 minuten", "30 minuten",
                "fifteen minutes", "thirty minutes",
                "eine stunde", "1 stunde", "within one hour", "within 1 hour",
                "2 stunden", "two hours", "2 hours", "within 2 hours",
                # "RPO 0 Minuten" style values. The leading space in
                # " 0 minuten" keeps this from matching embedded
                # substrings of "10 minuten" / "20 minuten" / ...
                # (which have no space before the trailing 0). The
                # "null 0" pattern matches the verbose "null (0)"
                # notation used in the GS-02 fixture.
                " 0 minuten", "null 0", "null minuten",
                "zero minutes",
            ),
        ),
        negative_any=(
            # Standard / mild deadlines do not belong here.
            "3 stunden", "three hours", "3 hours", "within 3 hours",
            "4 stunden", "four hours", "4 hours", "within 4 hours",
            "8 stunden", "acht stunden", "8 hours", "eight hours",
            "24 stunden", "twenty-four hours",
            "next business day", "nbd",
        ),
        min_support_hits=0,
    ),
    "PB-SLA-005": KeywordSignature(
        # Uncapped / unlimited contractual penalty or service credit.
        required_groups=(
            _g(
                "vertragsstrafe", "vertragsstrafen",
                "pönale", "poenale", "pönalen",
                "penalty", "penalties",
                "service credit", "service-credit", "service credits",
            ),
        ),
        support_groups=(
            _g(
                "unbegrenzt", "ohne begrenzung", "ohne deckelung",
                "ohne cap", "ohne obergrenze", "ohne limit",
                "keine deckelung", "keine obergrenze", "keine begrenzung",
                "kein cap", "kein limit",
                "unlimited", "uncapped", "without cap", "no cap",
                "unlimitiert",
                # "Eine Deckelung ... besteht nicht" — explicit statement that
                # no cap exists. Combined with required "vertragsstrafe" this
                # is unambiguous.
                "besteht nicht",
            ),
        ),
        min_support_hits=1,
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
    # Only the actual contract text is searched. baseline_gap_description
    # is excluded on purpose: it is produced by the baseline matcher and
    # contains generic risk phrases like "Keine Begrenzungen gefunden –
    # unbegrenzte Pflichten entsprechen nie dem Standard", which would
    # make positive obligations (e.g. "Maßnahmenplan innerhalb von 30
    # Tagen") falsely match PB-AUDIT-001 via "keine begrenzung" /
    # "unbegrenzt" substrings.
    parts = [obligation.summary or "", obligation.verbatim_quote or ""]
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
        if ("reaktion" in pattern or "wiederherstell" in pattern
                or "restore" in pattern or "resolution" in pattern):
            return "PB-SLA-004"
        if (("vertragsstrafe" in pattern or "pönale" in pattern
             or "poenale" in pattern or "penalty" in pattern
             or "service credit" in pattern)
                and ("unbegrenzt" in pattern or "gedeckelt" in pattern
                     or "cap" in pattern or "deckelung" in pattern)):
            return "PB-SLA-005"
        if ("suspension" in pattern or "bcm" in pattern
                or "disaster recovery" in pattern or "dr-" in pattern):
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
