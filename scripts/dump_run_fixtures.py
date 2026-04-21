"""Dump live obligation + finding data for a single analysis run into a
Phase-2a-Repair fixture YAML.

Read-only. No schema / data changes. Reads from the configured DB
(via DATABASE_URL / existing models) and writes a single YAML file
matching the schema in eval/gold_set/fixtures/schema.md.

Usage (inside the container):

    python scripts/dump_run_fixtures.py \\
        --run-id <analysis_runs.id> \\
        --contract-id GS-03 \\
        --out eval/gold_set/fixtures/GS-03.yaml

The Reviewer then fills in expected_outcome / expected_playbook /
regression_case / hypothesis / root_cause per obligation.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import date

from sqlalchemy.orm import joinedload

from infosec_contract_review.core.database import SessionLocal
from infosec_contract_review.models.config import LensConfig
from infosec_contract_review.models.finding import Evidence, Finding
from infosec_contract_review.models.obligation import Obligation
from infosec_contract_review.models.run import AnalysisRun


def _short_sha() -> str:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], stderr=subprocess.DEVNULL
        )
        return out.decode().strip()
    except Exception:
        return ""


def _enum_val(v) -> str:
    if v is None:
        return ""
    return v.value if hasattr(v, "value") else str(v)


def _yaml_escape(s: str | None) -> str:
    """Quote a string so it survives as a YAML block scalar value.

    Uses the literal "|-" indicator so original line breaks and quotes
    are preserved verbatim. Safe for LLM output that may contain
    colons, dashes and German umlauts.
    """
    if s is None:
        return '""'
    s = str(s)
    if s == "":
        return '""'
    # Indent each line by 6 spaces for block-scalar alignment under
    # the field name.
    indented = "\n".join("      " + line for line in s.split("\n"))
    return "|-\n" + indented


def _yaml_escape_short(s: str | None) -> str:
    """Short single-line string. Wraps in double quotes, escapes " and \\."""
    if s is None:
        return '""'
    s = str(s).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{s}"'


def dump(run_id: str, contract_id: str, out_path: str) -> None:
    db = SessionLocal()
    try:
        run = db.get(AnalysisRun, run_id)
        if not run:
            print(f"ERROR: run_id {run_id} not found", file=sys.stderr)
            sys.exit(2)

        obligations = (
            db.query(Obligation)
            .filter_by(run_id=run_id)
            .order_by(Obligation.theme, Obligation.id)
            .all()
        )

        # Resolve lens_id for each obligation
        lens_ids = {o.lens_config_id for o in obligations if o.lens_config_id}
        lens_map = {}
        if lens_ids:
            lens_rows = (
                db.query(LensConfig)
                .filter(LensConfig.id.in_(lens_ids))
                .all()
            )
            lens_map = {l.id: l.lens_id for l in lens_rows}

        # Map obligation_id → (finding_id, severity, materiality, playbook_id, title)
        ev_rows = (
            db.query(Evidence, Finding)
            .join(Finding, Finding.id == Evidence.finding_id)
            .filter(Evidence.obligation_id.in_([o.id for o in obligations]))
            .all()
        ) if obligations else []

        obl_to_finding: dict[str, dict] = {}
        for ev, f in ev_rows:
            # Keep the first finding per obligation (the primary one)
            if ev.obligation_id in obl_to_finding:
                continue
            obl_to_finding[ev.obligation_id] = {
                "finding_id": f.id,
                "severity": _enum_val(f.severity),
                "materiality": _enum_val(f.materiality),
                "playbook_id": f.playbook_entry_id or None,
                "title": f.title or "",
            }

        # Collect active lenses from the run's obligations
        used_lens_ids = sorted({lens_map.get(o.lens_config_id, "") for o in obligations
                                if o.lens_config_id}) or []

        lines: list[str] = []
        lines.append("# Auto-dumped by scripts/dump_run_fixtures.py — please fill the")
        lines.append("# Reviewer fields (expected_outcome, regression_case, hypothesis,")
        lines.append("# root_cause) per obligation. See fixtures/schema.md.")
        lines.append(f"contract_id: {_yaml_escape_short(contract_id)}")
        lines.append(f"run_id: {_yaml_escape_short(run_id)}")
        lines.append(f"git_sha: {_yaml_escape_short(_short_sha())}")
        lines.append(f"captured_at: {_yaml_escape_short(date.today().isoformat())}")
        lines.append(f'source: "live-container"')
        lines.append(f"active_lenses: {used_lens_ids}")
        lines.append("")
        lines.append("obligations:")

        for o in obligations:
            fb = obl_to_finding.get(o.id, {})
            lens = lens_map.get(o.lens_config_id, "")
            theme = _enum_val(o.theme)
            lines.append(f"  - obligation_id: {_yaml_escape_short(o.id)}")
            lines.append(f"    lens: {_yaml_escape_short(lens)}")
            lines.append(f"    theme: {_yaml_escape_short(theme)}")
            lines.append(f"    summary: {_yaml_escape(o.summary)}")
            lines.append(f"    verbatim_quote: {_yaml_escape(o.verbatim_quote)}")
            lines.append(f"    baseline_gap_description: {_yaml_escape(o.baseline_gap_description)}")
            lines.append(f"    current_finding_id: {_yaml_escape_short(fb.get('finding_id', ''))}")
            lines.append(f"    current_severity: {_yaml_escape_short(fb.get('severity', ''))}")
            lines.append(f"    current_materiality: {_yaml_escape_short(fb.get('materiality', ''))}")
            pb = fb.get("playbook_id")
            if pb:
                lines.append(f"    current_playbook_id: {_yaml_escape_short(pb)}")
            else:
                lines.append(f"    current_playbook_id: null")
            lines.append(f"    current_finding_title: {_yaml_escape(fb.get('title', ''))}")
            lines.append(f"    expected_outcome: risk          # risk | info | suppress  <-- Reviewer")
            lines.append(f"    expected_playbook: null         #                          <-- Reviewer")
            lines.append(f"    regression_case: false          #                          <-- Reviewer")
            lines.append(f'    hypothesis: ""                  #                          <-- Reviewer')
            lines.append(f"    root_cause: ok                  # see schema.md            <-- Reviewer")
            lines.append("")

        with open(out_path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines))

        print(f"Wrote {len(obligations)} obligations → {out_path}")
    finally:
        db.close()


def main():
    p = argparse.ArgumentParser(description="Dump a run's obligations + findings to a YAML fixture")
    p.add_argument("--run-id", required=True, help="analysis_runs.id")
    p.add_argument("--contract-id", required=True, help="stable Gold-Set ID, e.g. GS-03")
    p.add_argument("--out", required=True, help="Output path (overwritten)")
    args = p.parse_args()
    dump(args.run_id, args.contract_id, args.out)


if __name__ == "__main__":
    main()
