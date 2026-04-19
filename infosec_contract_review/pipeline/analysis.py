"""Analysis pipeline: runs obligation extraction across lenses."""
from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from infosec_contract_review.extraction.obligation_extractor import extract_obligations_for_lens
from infosec_contract_review.llm.client import LLMClient
from infosec_contract_review.models.config import LensConfig
from infosec_contract_review.models.enums import RunStatus
from infosec_contract_review.models.obligation import Obligation
from infosec_contract_review.models.package import ContractPackage
from infosec_contract_review.models.run import AnalysisRun
from infosec_contract_review.models.segment import Segment

logger = logging.getLogger(__name__)


def run_obligation_extraction(
    package_id: str,
    run_id: str,
    lens_ids: list[str] | None,
    db: Session,
) -> dict:
    run = db.get(AnalysisRun, run_id)
    if not run or run.package_id != package_id:
        raise ValueError(f"Run {run_id} not found in package {package_id}")

    if run.status != RunStatus.PENDING:
        raise ValueError(f"Run {run_id} has status '{run.status.value}', expected 'pending'")

    existing_count = db.query(Obligation).filter_by(run_id=run_id).count()
    if existing_count > 0:
        raise ValueError(f"Run {run_id} already has {existing_count} obligations")

    pkg = db.get(ContractPackage, package_id)
    doc_ids = [d.id for d in pkg.documents]
    segments = (
        db.query(Segment)
        .filter(Segment.document_id.in_(doc_ids))
        .order_by(Segment.document_id, Segment.segment_index)
        .all()
    ) if doc_ids else []

    if not segments:
        raise ValueError("No parsed segments found. Parse documents before extracting obligations.")

    if lens_ids:
        lenses = (
            db.query(LensConfig)
            .filter(LensConfig.lens_id.in_(lens_ids), LensConfig.is_active == True)
            .all()
        )
    else:
        lenses = db.query(LensConfig).filter_by(is_active=True).all()

    if not lenses:
        raise ValueError("No active lens configurations found")

    run.status = RunStatus.RUNNING
    prompt_versions = {}
    db.flush()

    llm_client = LLMClient()
    total_obligations = 0
    total_tokens = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    total_errors = 0
    lens_results = []

    for step_idx, lens in enumerate(lenses):
        logger.info("Running extraction for lens %s (theme: %s)", lens.lens_id, lens.theme.value)
        prompt_versions[lens.lens_id] = lens.prompt_template_id

        try:
            result = extract_obligations_for_lens(
                package_id=package_id,
                run_id=run_id,
                lens=lens,
                segments=segments,
                llm_client=llm_client,
                db=db,
                step_index=step_idx,
            )
        except Exception as e:
            logger.exception("Extraction failed for lens %s", lens.lens_id)
            total_errors += 1
            lens_results.append({"lens_id": lens.lens_id, "error": str(e)})
            continue

        total_obligations += result.obligations_count
        for k in total_tokens:
            total_tokens[k] += result.token_usage.get(k, 0)
        total_errors += result.errors

        lens_results.append({
            "lens_id": lens.lens_id,
            "obligations": result.obligations_count,
            "skipped_low_confidence": result.skipped_low_confidence,
            "skipped_invalid_evidence": result.skipped_invalid_evidence,
            "errors": result.errors,
        })

    run.status = RunStatus.COMPLETED if total_errors == 0 else RunStatus.FAILED
    if run.config_snapshot:
        run.config_snapshot = {
            **run.config_snapshot,
            "prompt_versions": prompt_versions,
            "model_name": llm_client.model,
            "model_version": llm_client.model,
        }
    db.commit()

    return {
        "run_id": run_id,
        "status": run.status.value,
        "obligations_extracted": total_obligations,
        "tokens_used": total_tokens,
        "errors": total_errors,
        "lenses": lens_results,
    }
