"""Import 22.04 live fixtures into the local DB and run the scoring pipeline.

Read-only for the fixtures themselves. Creates the following rows in the
active database:

  - ContractPackage + Document + Segment placeholder per fixture
  - AnalysisRun per fixture
  - Obligation rows with theme / summary / verbatim_quote /
    baseline_match_status / baseline_gap_description and lens mapping
  - ObligationRelation rows for any two obligations that shared the
    same current_finding_id in the 22.04 live dump (type="supplements")
    — this reconstructs the relation signal that drove the original
    cluster merges without requiring the original relation_detector
    output, which is not captured in the fixtures.

Then runs score + generate_findings and prints the resulting Findings.

Usage:
  DATABASE_URL=... python scripts/run_fixture_live.py eval/gold_set/fixtures/GS-03-2026-04-22.yaml
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import yaml

# Make the project importable when run from repo root.
HERE = Path(__file__).resolve()
ROOT = HERE.parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from infosec_contract_review.core.database import SessionLocal
from infosec_contract_review.models.config import LensConfig
from infosec_contract_review.models.enums import (
    Materiality,
    ObligationDirection,
    ObligationType,
    RelationType,
    RunStatus,
    SegmentType,
    Theme,
)
from infosec_contract_review.models.finding import Finding
from infosec_contract_review.models.obligation import Obligation
from infosec_contract_review.models.package import ContractPackage, Document
from infosec_contract_review.models.relation import ObligationRelation
from infosec_contract_review.models.run import AnalysisRun
from infosec_contract_review.models.segment import Segment
from infosec_contract_review.scoring.finding_generator import generate_findings


def _run(path: str) -> str:
    with open(path, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)

    contract_id = data["contract_id"]
    obligations_data = data["obligations"]
    db = SessionLocal()
    try:
        lens_map = {l.lens_id: l.id for l in db.query(LensConfig).all()}

        pkg = ContractPackage(name=f"{contract_id} (2026-04-22 live)")
        db.add(pkg)
        db.flush()

        doc = Document(
            package_id=pkg.id,
            filename=f"{contract_id}.pdf",
            doc_type="contract",
            language="de",
            ingestion_status="completed",
        )
        db.add(doc)
        db.flush()

        seg = Segment(
            document_id=doc.id,
            segment_index=0,
            segment_type=SegmentType.PARAGRAPH,
            text="(Placeholder segment for fixture import — see individual obligations.)",
        )
        db.add(seg)
        db.flush()

        run = AnalysisRun(package_id=pkg.id, status=RunStatus.RUNNING)
        db.add(run)
        db.flush()

        # Obligations
        obl_by_fixture_id: dict[str, Obligation] = {}
        finding_to_obls: dict[str, list[str]] = {}
        for entry in obligations_data:
            theme_val = entry.get("theme")
            theme_enum = Theme(theme_val) if theme_val in [t.value for t in Theme] else Theme.OTHER
            lens_pk = lens_map.get(entry.get("lens") or "")

            obl = Obligation(
                segment_id=seg.id,
                theme=theme_enum,
                obligation_type=ObligationType.MUST,
                direction=ObligationDirection.PROVIDER_TO_CLIENT,
                summary=entry.get("summary") or "",
                verbatim_quote=entry.get("verbatim_quote") or "",
                materiality=Materiality.MEDIUM,
                run_id=run.id,
                lens_config_id=lens_pk,
                extraction_method="llm",
                baseline_match_status="not_supported",
                baseline_gap_description=entry.get("baseline_gap_description") or "",
            )
            db.add(obl)
            db.flush()
            fid = entry.get("obligation_id")
            obl_by_fixture_id[fid] = obl

            cur_f = entry.get("current_finding_id") or ""
            if cur_f:
                finding_to_obls.setdefault(cur_f, []).append(obl.id)

        # Reconstruct relations: obligations that shared a current_finding_id
        # in the 22.04 dump were merged by the original pipeline via some
        # combination of relations + playbook-id merge. We emit "supplements"
        # edges between every such pair so the component builder can rebuild
        # the original cluster, and let the updated finding_generator decide
        # whether to keep them as one risk finding or split them.
        for members in finding_to_obls.values():
            if len(members) < 2:
                continue
            anchor = members[0]
            for other in members[1:]:
                db.add(ObligationRelation(
                    run_id=run.id,
                    obligation_a_id=anchor,
                    obligation_b_id=other,
                    relation_type=RelationType.SUPPLEMENTS,
                    confidence="medium",
                ))

        db.flush()
        generate_findings(run.id, db, step_index=0)
        run.status = RunStatus.COMPLETED
        db.commit()

        print(f"\n=== {contract_id}  run_id={run.id} ===")
        findings = db.query(Finding).filter_by(run_id=run.id).all()
        visible = [f for f in findings if f.severity.value != "info"]
        info = [f for f in findings if f.severity.value == "info"]
        print(f"Findings: {len(findings)}  visible(non-info): {len(visible)}  info: {len(info)}")
        print()
        for f in findings:
            sev = f.severity.value if hasattr(f.severity, "value") else str(f.severity)
            mat = f.materiality.value if hasattr(f.materiality, "value") else str(f.materiality)
            pb = f.playbook_entry_id or "—"
            print(f"  [{sev:<8}] [{mat:<8}] pb={pb:<14} | {(f.title or '')[:110]}")

        return run.id
    finally:
        db.close()


def main():
    if len(sys.argv) < 2:
        print("usage: run_fixture_live.py <fixture.yaml> [<fixture.yaml> ...]", file=sys.stderr)
        sys.exit(64)
    run_ids = []
    for path in sys.argv[1:]:
        run_ids.append(_run(path))
    print("\nrun_ids:", run_ids)


if __name__ == "__main__":
    main()
