"""Run the real matcher + classifier code path against a Live-Fixture
YAML and print a diagnostic table.

Usage:
    python eval/gold_set/fixtures/run_fixture_tests.py \\
        eval/gold_set/fixtures/GS-03.yaml

What it does:
1. Reads obligations from the fixture.
2. For each obligation, builds a SimpleNamespace that quacks like an
   Obligation ORM object (theme, summary, verbatim_quote,
   baseline_gap_description, baseline_match_status).
3. Calls `match_obligation_to_playbook` with stub playbook entries
   constructed from the signature keys in playbook_matcher.
4. Calls `classify_group` as the finding_generator would, with an
   empty missing_safeguards / relations list.
5. Prints one line per obligation: got vs expected, plus hypothesis
   and root_cause from the fixture.
6. Summary: count of deltas per root_cause bucket.

No DB, no LLM, no pipeline. Just the deterministic rule code against
real LLM-produced text.
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import yaml

# Make the project importable when run from repo root.
HERE = Path(__file__).resolve()
ROOT = HERE.parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from infosec_contract_review.scoring.finding_classifier import classify_group
from infosec_contract_review.scoring.playbook_matcher import (
    PLAYBOOK_SIGNATURES,
    match_obligation_to_playbook,
)


# Known playbook → theme mapping (matches the seed YAML).
_PB_THEME = {
    "PB-AUDIT-001": "audit_rights",
    "PB-AUDIT-002": "audit_rights",
    "PB-AUDIT-003": "audit_rights",
    "PB-INC-001":   "incident_reporting",
    "PB-INC-002":   "incident_reporting",
    "PB-INC-003":   "incident_reporting",
    "PB-SLA-001":   "sla_feasibility",
    "PB-SLA-002":   "sla_feasibility",
    "PB-SLA-003":   "sla_feasibility",
    "PB-SLA-004":   "sla_feasibility",
    "PB-SLA-005":   "sla_feasibility",
}

# Known playbook → risk_pattern mapping (must match the seed YAML so that
# _derive_key_from_pattern in the matcher can bridge UUID ↔ business key).
_PB_RISK_PATTERN = {
    "PB-AUDIT-001": "Unbegrenztes Auditrecht ohne Vorlaufzeit und Häufigkeitslimit",
    "PB-AUDIT-002": "Direktes Auditrecht für Endkunden oder Dritte",
    "PB-AUDIT-003": "Kostenfreie Auditunterstützung",
    "PB-INC-001":   "Unrealistisch kurze Meldefrist",
    "PB-INC-002":   "Meldepflicht für jedes Security-Event",
    "PB-INC-003":   "Regulatorische Meldepflichten durchgereicht",
    "PB-SLA-001":   "SLA ohne Wartungsfenster-Ausnahme",
    "PB-SLA-002":   "Verfügbarkeit >= 99.99% oder Transaktionsmessung",
    "PB-SLA-003":   "Keine SLA-Suspension bei DR/BCM",
    "PB-SLA-004":   "Unrealistisch kurze Reaktions- oder Wiederherstellungszeiten",
    "PB-SLA-005":   "Unbegrenzte oder nicht gedeckelte Vertragsstrafe",
}


class _ThemeStub:
    def __init__(self, v): self.value = v


def _build_stub_playbooks() -> list:
    stubs = []
    for pb_id in PLAYBOOK_SIGNATURES:
        stubs.append(SimpleNamespace(
            id=pb_id,
            theme=_ThemeStub(_PB_THEME.get(pb_id, "other")),
            is_active=True,
            risk_pattern=_PB_RISK_PATTERN.get(pb_id, pb_id),
            applicable_when="",
            alt_wordings=[], bidder_questions=[],
            standard_position="", escalation_note=None, version="1.0",
        ))
    return stubs


def _obl_from_fixture(entry: dict):
    return SimpleNamespace(
        id=entry.get("obligation_id") or "x",
        theme=_ThemeStub(entry.get("theme", "other")),
        summary=entry.get("summary") or "",
        verbatim_quote=entry.get("verbatim_quote") or "",
        baseline_gap_description=entry.get("baseline_gap_description") or "",
        baseline_match_status="not_supported",
        lens_config_id=None,
        materiality=None,
    )


# Accepted root_cause codes (kept in sync with fixtures/schema.md).
# Anything outside this set gets flagged as unknown.
KNOWN_ROOT_CAUSES = {
    "ok",
    "matcher_negative_gap",
    "matcher_over_support",
    "matcher_required_wrong",
    "classifier_positive_gap",
    "classifier_amplifier_overblock",
    "classifier_generic_negation",
    "escalation_limits_null",
    "escalation_baseline_gap",
    "assembly_wrong_merge",
}


def _expected_visible(expected_outcome: str) -> bool:
    return expected_outcome == "risk"


def run(path: str) -> int:
    with open(path, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)

    if not data:
        print(f"Fixture {path} is empty.", file=sys.stderr)
        return 1

    contract_id = data.get("contract_id", "?")
    run_id = data.get("run_id", "?")
    obligations = data.get("obligations") or []

    print("=" * 78)
    print(f"Fixture: {path}")
    print(f"Contract: {contract_id}    Run: {run_id}")
    print(f"Obligations: {len(obligations)}")
    print("=" * 78)

    pbs = _build_stub_playbooks()

    deltas_by_root_cause: dict[str, int] = {}
    assembly_flags: list[tuple[int, str]] = []  # (#, summary) for assembly_wrong_merge
    unknown_codes: dict[str, int] = {}
    ok = 0
    fail = 0
    regression_deltas = 0

    for i, entry in enumerate(obligations, 1):
        obl = _obl_from_fixture(entry)
        pb_match = match_obligation_to_playbook(obl, pbs)
        cls = classify_group([obl], pb_match, [], [])
        visible_as_risk = cls.kind == "risk"
        expected = entry.get("expected_outcome", "risk")
        exp_visible = _expected_visible(expected)

        is_regression = bool(entry.get("regression_case"))
        rc = entry.get("root_cause") or "ok"
        if rc not in KNOWN_ROOT_CAUSES:
            unknown_codes[rc] = unknown_codes.get(rc, 0) + 1

        # Harness prediction matches reviewer expectation?
        harness_matches_expected = visible_as_risk == exp_visible

        # Special marker for assembly_wrong_merge: the harness sees the
        # obligation in isolation as info/ok, but the live pipeline
        # pulls it into a risk finding via playbook-id merge. The
        # harness itself CANNOT reproduce this — it only runs matcher
        # + classifier per obligation. We surface these cases explicitly
        # so they don't get lost in the "ok" bucket.
        is_assembly_case = (rc == "assembly_wrong_merge")

        if harness_matches_expected and is_assembly_case:
            mark = "⚠"
        elif harness_matches_expected:
            mark = "✓"
        else:
            mark = "✗"

        got_label = "RISK" if visible_as_risk else "info/—"
        exp_label = expected.upper() if expected else "?"

        pb_got = pb_match.id if pb_match else "—"
        pb_exp = entry.get("expected_playbook") or "—"

        summary_short = (entry.get("summary") or "").strip().replace("\n", " ")[:60]

        print(
            f"{mark} #{i:02d} {entry.get('theme','?'):<20} "
            f"got={got_label:<8} exp={exp_label:<8} pb_got={pb_got:<13} pb_exp={pb_exp:<13} "
            f"cls={cls.kind:<13} | {summary_short}"
        )

        if not harness_matches_expected:
            fail += 1
            deltas_by_root_cause[rc] = deltas_by_root_cause.get(rc, 0) + 1
            hyp = entry.get("hypothesis") or ""
            if hyp:
                print(f"       hypothesis : {hyp}")
            print(f"       root_cause : {rc}")
            if is_regression:
                regression_deltas += 1
        else:
            ok += 1
            if is_assembly_case:
                assembly_flags.append((i, summary_short))
                hyp = entry.get("hypothesis") or ""
                print(
                    "       [assembly_wrong_merge] Harness zeigt Einzelfall-"
                    "Klassifikation als info/ok. Das Problem liegt laut Reviewer "
                    "im Finding-Generator-Merge, nicht im Matcher/Klassifikator."
                )
                if hyp:
                    print(f"       hypothesis : {hyp}")

    print("-" * 78)
    print(f"Summary: {ok} match / {fail} mismatch (regression subset: {regression_deltas})")

    if assembly_flags:
        print(
            f"\n{len(assembly_flags)} obligation(s) flagged as assembly_wrong_merge "
            "(harness-ok, live-pipeline produces risk-finding via playbook-id "
            "merge — not reproducible by this harness):"
        )
        for idx, summ in assembly_flags:
            print(f"  #{idx:02d}  {summ}")

    combined: dict[str, int] = dict(deltas_by_root_cause)
    if assembly_flags:
        # Surface assembly_wrong_merge in the histogram even though the
        # harness did not register a delta for these rows.
        combined["assembly_wrong_merge"] = (
            combined.get("assembly_wrong_merge", 0) + len(assembly_flags)
        )

    if combined:
        print("\nRoot-cause distribution (mismatches + assembly flags):")
        for rc, n in sorted(combined.items(), key=lambda x: -x[1]):
            tag = "  (harness-ok, live-pipeline issue)" if rc == "assembly_wrong_merge" else ""
            print(f"  {rc:<36} {n}{tag}")

    if unknown_codes:
        print("\nWARN: unknown root_cause codes in fixture (see fixtures/schema.md):")
        for code, n in sorted(unknown_codes.items()):
            print(f"  {code!r:<36} {n}")

    print()
    return 0 if fail == 0 else 2


def main():
    if len(sys.argv) != 2:
        print("usage: run_fixture_tests.py <fixture.yaml>", file=sys.stderr)
        sys.exit(64)
    sys.exit(run(sys.argv[1]))


if __name__ == "__main__":
    main()
