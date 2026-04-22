"""Per-finding severity / materiality diagnostic for a live run.

Read-only. No schema or data changes. Reads from the configured DB
(via DATABASE_URL / existing models) and prints, for each Finding in the
run, the signals that shaped its severity and materiality:

  - current severity / materiality / playbook_entry_id
  - number and id/lens of MissingSafeguards that count for the members
    (under the scoped Rule 3 filter)
  - each member's baseline_match_status and baseline_gap_description
    (truncated) plus whether limits are all null
  - which classifier reason (risk / informational: <cat>) the cluster
    currently lands on

Used to explain the 22.04 GS-02 Kritisch/Kritisch pattern and to verify
the scoped-missing-safeguards fix in scoring/materiality_scorer.py.

Usage (inside the container):

    python scripts/diag_severity.py --run-id <analysis_runs.id>

"""
from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path

# Make the project importable when run from repo root.
HERE = Path(__file__).resolve()
ROOT = HERE.parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy.orm import joinedload

from infosec_contract_review.core.database import SessionLocal
from infosec_contract_review.models.config import LensConfig
from infosec_contract_review.models.finding import Evidence, Finding, MissingSafeguard
from infosec_contract_review.models.obligation import Obligation
from infosec_contract_review.models.playbook import PlaybookEntry
from infosec_contract_review.models.relation import ObligationRelation
from infosec_contract_review.models.run import AnalysisRun
from infosec_contract_review.scoring.finding_classifier import classify_group


def _ev(v) -> str:
    if v is None:
        return "—"
    return v.value if hasattr(v, "value") else str(v)


def _limits_all_null(obl: Obligation) -> bool:
    if not obl.limits:
        return True
    for f in ("frequency_limit", "time_limit", "cost_limit", "scope_limit"):
        if getattr(obl.limits, f, None) is not None:
            return False
    if obl.limits.other_limits:
        if any(v is not None for v in obl.limits.other_limits.values()):
            return False
    return True


def diag(run_id: str) -> int:
    db = SessionLocal()
    try:
        run = db.get(AnalysisRun, run_id)
        if not run:
            print(f"ERROR: run_id {run_id} not found", file=sys.stderr)
            return 2

        findings = (
            db.query(Finding)
            .filter_by(run_id=run_id)
            .order_by(Finding.severity.desc(), Finding.theme)
            .all()
        )
        obligations = (
            db.query(Obligation)
            .options(joinedload(Obligation.limits))
            .filter_by(run_id=run_id)
            .all()
        )
        ms_list = db.query(MissingSafeguard).filter_by(run_id=run_id).all()
        rel_list = db.query(ObligationRelation).filter_by(run_id=run_id).all()

        lens_ids = {o.lens_config_id for o in obligations if o.lens_config_id}
        lens_map: dict[str, str] = {}
        if lens_ids:
            for lc in db.query(LensConfig).filter(LensConfig.id.in_(lens_ids)).all():
                lens_map[lc.id] = lc.lens_id

        # finding_id -> [obligation, ...]
        ev_by_finding: dict[str, list[Obligation]] = defaultdict(list)
        obl_by_id = {o.id: o for o in obligations}
        for ev in db.query(Evidence).filter(Evidence.finding_id.in_([f.id for f in findings])).all():
            obl = obl_by_id.get(ev.obligation_id)
            if obl is not None:
                ev_by_finding[ev.finding_id].append(obl)

        print("=" * 96)
        print(f"Run: {run_id}")
        print(f"Findings: {len(findings)}   Obligations: {len(obligations)}   "
              f"MissingSafeguards: {len(ms_list)}   Relations: {len(rel_list)}")
        print("=" * 96)

        # Count MissingSafeguards by lens / by obligation for scope reasoning.
        ms_by_lens: dict[str, int] = defaultdict(int)
        ms_by_obl: dict[str, int] = defaultdict(int)
        for ms in ms_list:
            if ms.status != "missing":
                continue
            if ms.lens_config_id:
                ms_by_lens[ms.lens_config_id] += 1
            if ms.obligation_id:
                ms_by_obl[ms.obligation_id] += 1
        print("MissingSafeguards by lens:")
        for lc_id, n in ms_by_lens.items():
            print(f"  {lens_map.get(lc_id, lc_id)}: {n}")
        print()

        for f in findings:
            members = ev_by_finding.get(f.id, [])
            sev = _ev(f.severity)
            mat = _ev(f.materiality)
            pb = f.playbook_entry_id or "—"
            print(f"[{sev:<8}] [{mat:<8}] pb={pb:<14} theme={_ev(f.theme):<22} "
                  f"members={len(members)}  id={f.id[:8]}")
            print(f"  title: {(f.title or '')[:110]}")

            # Signals per member
            for m in members:
                lens = lens_map.get(m.lens_config_id, "—") if m.lens_config_id else "—"
                relevant_ms = [
                    ms for ms in ms_list
                    if ms.status == "missing"
                    and (
                        (ms.obligation_id is not None and ms.obligation_id == m.id)
                        or (
                            ms.lens_config_id is not None
                            and m.lens_config_id is not None
                            and ms.lens_config_id == m.lens_config_id
                        )
                    )
                ]
                contradicts = sum(
                    1 for r in rel_list
                    if (
                        (r.relation_type.value if hasattr(r.relation_type, "value") else str(r.relation_type))
                        == "contradicts"
                    )
                    and (r.obligation_a_id == m.id or r.obligation_b_id == m.id)
                )
                limits_null = _limits_all_null(m)
                gap = (m.baseline_gap_description or "").strip().replace("\n", " ")
                print(f"   - obl={m.id[:8]} lens={lens:<12} "
                      f"baseline={m.baseline_match_status or '—'} "
                      f"limits_null={limits_null} "
                      f"scoped_ms={len(relevant_ms)} contradicts={contradicts}")
                print(f"       summary: {(m.summary or '')[:95]}")
                if gap:
                    print(f"       gap    : {gap[:95]}")

            # Classifier view (playbook + missing_safeguards + relations from run)
            pb_obj: PlaybookEntry | None = None
            if f.playbook_entry_id:
                pb_obj = db.get(PlaybookEntry, f.playbook_entry_id)
            cls = classify_group(members, pb_obj, ms_list, rel_list)
            solo_cls = classify_group(members, None, [], [])
            print(f"  classifier: live={cls.kind}/{cls.reason!r}  "
                  f"solo-no-pb={solo_cls.kind}/{solo_cls.reason!r}")
            print()

        return 0
    finally:
        db.close()


def main():
    p = argparse.ArgumentParser(description="Per-finding severity / materiality diagnostic")
    p.add_argument("--run-id", required=True, help="analysis_runs.id")
    args = p.parse_args()
    sys.exit(diag(args.run_id))


if __name__ == "__main__":
    main()
