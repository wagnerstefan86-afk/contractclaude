from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload

from infosec_contract_review.core.database import get_db
from infosec_contract_review.models.package import ContractPackage, Document
from infosec_contract_review.models.finding import Finding, MissingSafeguard
from infosec_contract_review.models.obligation import Obligation
from infosec_contract_review.models.run import AnalysisRun
from infosec_contract_review.models.segment import Segment
from infosec_contract_review.models.baseline import ProviderBaseline
from infosec_contract_review.models.enums import RunStatus
from infosec_contract_review.schemas.domain import (
    FindingBrief,
    FindingDetail,
    MissingSafeguardDetailOut,
    ObligationOut,
    RunBrief,
    RunDetail,
    SegmentOut,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/packages", tags=["analysis"])


# ---------------------------------------------------------------------------
# Findings
# ---------------------------------------------------------------------------

@router.get("/{package_id}/findings", response_model=list[FindingBrief])
def list_findings(
    package_id: str,
    materiality: Optional[str] = Query(None),
    theme: Optional[str] = Query(None),
    review_status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    pkg = db.get(ContractPackage, package_id)
    if not pkg:
        raise HTTPException(404, f"Package {package_id} not found")

    run_ids = [r.id for r in db.query(AnalysisRun.id).filter_by(package_id=package_id).all()]
    if not run_ids:
        return []

    q = db.query(Finding).filter(Finding.run_id.in_(run_ids))
    if materiality:
        q = q.filter(Finding.materiality == materiality)
    if theme:
        q = q.filter(Finding.theme == theme)
    if review_status:
        q = q.filter(Finding.status == review_status)

    return q.order_by(Finding.created_at.desc()).all()


@router.get("/{package_id}/findings/{finding_id}", response_model=FindingDetail)
def get_finding(package_id: str, finding_id: str, db: Session = Depends(get_db)):
    finding = (
        db.query(Finding)
        .options(joinedload(Finding.evidences), joinedload(Finding.missing_safeguards))
        .filter_by(id=finding_id)
        .first()
    )
    if not finding:
        raise HTTPException(404, f"Finding {finding_id} not found")
    run = db.get(AnalysisRun, finding.run_id)
    if not run or run.package_id != package_id:
        raise HTTPException(404, f"Finding {finding_id} not found in package {package_id}")
    return finding


# ---------------------------------------------------------------------------
# Analysis Runs
# ---------------------------------------------------------------------------

@router.post("/{package_id}/runs", status_code=202)
def create_run(package_id: str, db: Session = Depends(get_db)):
    pkg = db.get(ContractPackage, package_id)
    if not pkg:
        raise HTTPException(404, f"Package {package_id} not found")

    baseline = db.query(ProviderBaseline).filter_by(is_active=True).first()
    baseline_version = baseline.version if baseline else "unknown"

    run = AnalysisRun(
        package_id=package_id,
        status=RunStatus.PENDING,
        config_snapshot={
            "model_name": "not_configured",
            "model_version": "not_configured",
            "playbook_version": "1.0",
            "baseline_version": baseline_version,
            "parser_version": "not_configured",
            "prompt_versions": {},
            "cross_theme_rule_versions": {},
        },
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    logger.info("Created analysis run %s for package %s", run.id, package_id)
    return {"id": run.id, "status": run.status.value, "created_at": run.created_at.isoformat()}


@router.get("/{package_id}/runs", response_model=list[RunBrief])
def list_runs(package_id: str, db: Session = Depends(get_db)):
    pkg = db.get(ContractPackage, package_id)
    if not pkg:
        raise HTTPException(404, f"Package {package_id} not found")
    return (
        db.query(AnalysisRun)
        .filter_by(package_id=package_id)
        .order_by(AnalysisRun.created_at.desc())
        .all()
    )


@router.get("/{package_id}/runs/{run_id}", response_model=RunDetail)
def get_run(package_id: str, run_id: str, db: Session = Depends(get_db)):
    run = (
        db.query(AnalysisRun)
        .options(joinedload(AnalysisRun.steps))
        .filter_by(id=run_id, package_id=package_id)
        .first()
    )
    if not run:
        raise HTTPException(404, f"Run {run_id} not found in package {package_id}")
    return run


# ---------------------------------------------------------------------------
# Segments
# ---------------------------------------------------------------------------

@router.get("/{package_id}/segments", response_model=list[SegmentOut])
def list_segments(
    package_id: str,
    document_id: Optional[str] = Query(None),
    routing_tier: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    pkg = db.get(ContractPackage, package_id)
    if not pkg:
        raise HTTPException(404, f"Package {package_id} not found")

    doc_ids = [d.id for d in pkg.documents]
    if not doc_ids:
        return []

    q = db.query(Segment).filter(Segment.document_id.in_(doc_ids))
    if document_id:
        q = q.filter(Segment.document_id == document_id)
    if routing_tier:
        q = q.filter(Segment.routing_tier == routing_tier)

    offset = (page - 1) * page_size
    return q.order_by(Segment.document_id, Segment.segment_index).offset(offset).limit(page_size).all()


# ---------------------------------------------------------------------------
# Obligation extraction
# ---------------------------------------------------------------------------

class ExtractRequest(BaseModel):
    lens_ids: list[str] | None = None


@router.post("/{package_id}/runs/{run_id}/extract")
def extract_obligations(
    package_id: str,
    run_id: str,
    body: ExtractRequest = ExtractRequest(),
    db: Session = Depends(get_db),
):
    from infosec_contract_review.pipeline.analysis import run_obligation_extraction

    pkg = db.get(ContractPackage, package_id)
    if not pkg:
        raise HTTPException(404, f"Package {package_id} not found")

    try:
        result = run_obligation_extraction(package_id, run_id, body.lens_ids, db)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except RuntimeError as e:
        raise HTTPException(500, str(e))

    logger.info("Extraction complete for run %s: %d obligations", run_id, result["obligations_extracted"])
    return result


# ---------------------------------------------------------------------------
# Obligations
# ---------------------------------------------------------------------------

@router.get("/{package_id}/obligations", response_model=list[ObligationOut])
def list_obligations(
    package_id: str,
    theme: Optional[str] = Query(None),
    obligation_type: Optional[str] = Query(None),
    run_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    pkg = db.get(ContractPackage, package_id)
    if not pkg:
        raise HTTPException(404, f"Package {package_id} not found")

    run_ids_q = db.query(AnalysisRun.id).filter_by(package_id=package_id)
    if run_id:
        run_ids_q = run_ids_q.filter_by(id=run_id)
    run_ids = [r.id for r in run_ids_q.all()]
    if not run_ids:
        return []

    q = db.query(Obligation).filter(Obligation.run_id.in_(run_ids))
    if theme:
        q = q.filter(Obligation.theme == theme)
    if obligation_type:
        q = q.filter(Obligation.obligation_type == obligation_type)

    return q.order_by(Obligation.created_at.desc()).all()


# ---------------------------------------------------------------------------
# Missing Safeguards
# ---------------------------------------------------------------------------

@router.get("/{package_id}/missing-safeguards", response_model=list[MissingSafeguardDetailOut])
def list_missing_safeguards(
    package_id: str,
    theme: Optional[str] = Query(None),
    run_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    pkg = db.get(ContractPackage, package_id)
    if not pkg:
        raise HTTPException(404, f"Package {package_id} not found")

    run_ids_q = db.query(AnalysisRun.id).filter_by(package_id=package_id)
    if run_id:
        run_ids_q = run_ids_q.filter_by(id=run_id)
    run_ids = [r.id for r in run_ids_q.all()]
    if not run_ids:
        return []

    q = db.query(MissingSafeguard).filter(MissingSafeguard.run_id.in_(run_ids))

    if theme:
        from infosec_contract_review.models.config import LensConfig
        lens_ids = [
            lc.id for lc in
            db.query(LensConfig).filter(LensConfig.theme == theme).all()
        ]
        if lens_ids:
            q = q.filter(MissingSafeguard.lens_config_id.in_(lens_ids))
        else:
            return []

    return q.order_by(MissingSafeguard.created_at.desc()).all()
