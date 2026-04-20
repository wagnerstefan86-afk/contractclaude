"""Analysis pipeline: extraction → baseline → safeguards → relations → cross-theme."""
from __future__ import annotations

import logging

from sqlalchemy.orm import Session, joinedload

from infosec_contract_review.extraction.baseline_matcher import match_obligation_to_baseline
from infosec_contract_review.extraction.cross_theme_checker import run_cross_theme_checks
from infosec_contract_review.extraction.obligation_extractor import extract_obligations_for_lens
from infosec_contract_review.extraction.relation_detector import detect_relations
from infosec_contract_review.extraction.safeguard_checker import check_missing_safeguards
from infosec_contract_review.llm.client import LLMClient
from infosec_contract_review.models.baseline import ProviderBaseline
from infosec_contract_review.models.config import CrossThemeRule, LensConfig
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
            .options(joinedload(LensConfig.expected_safeguards))
            .filter(LensConfig.lens_id.in_(lens_ids), LensConfig.is_active == True)
            .all()
        )
    else:
        lenses = (
            db.query(LensConfig)
            .options(joinedload(LensConfig.expected_safeguards))
            .filter_by(is_active=True)
            .all()
        )

    if not lenses:
        raise ValueError("No active lens configurations found")

    baseline = (
        db.query(ProviderBaseline)
        .options(
            joinedload(ProviderBaseline.standard_positions),
            joinedload(ProviderBaseline.certifications),
            joinedload(ProviderBaseline.service_profiles),
        )
        .filter_by(is_active=True)
        .first()
    )

    run.status = RunStatus.RUNNING
    prompt_versions = {}
    db.flush()

    llm_client = LLMClient()
    total_obligations = 0
    total_tokens = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    total_errors = 0
    total_missing_safeguards = 0
    total_not_automatable = 0
    total_baseline_summary = {"already_supported": 0, "partially_supported": 0, "not_supported": 0}
    total_relations = 0
    lens_results = []
    step_counter = 0

    # --- Phase 1+2: per-lens extraction, baseline match, safeguard check ---
    for lens in lenses:
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
                step_index=step_counter,
            )
            step_counter += 1
        except Exception as e:
            logger.exception("Extraction failed for lens %s", lens.lens_id)
            total_errors += 1
            step_counter += 1
            lens_results.append({"lens_id": lens.lens_id, "error": str(e)})
            continue

        total_obligations += result.obligations_count
        for k in total_tokens:
            total_tokens[k] += result.token_usage.get(k, 0)
        total_errors += result.errors

        lens_obligations = (
            db.query(Obligation)
            .options(joinedload(Obligation.limits))
            .filter_by(run_id=run_id, lens_config_id=lens.id)
            .all()
        )

        baseline_summary = {"already_supported": 0, "partially_supported": 0, "not_supported": 0}
        if baseline and lens_obligations:
            for obl in lens_obligations:
                status, desc = match_obligation_to_baseline(obl, baseline)
                obl.baseline_match_status = status
                obl.baseline_gap_description = desc
                baseline_summary[status] = baseline_summary.get(status, 0) + 1
            db.flush()

        for k in baseline_summary:
            total_baseline_summary[k] += baseline_summary[k]

        sg_result = check_missing_safeguards(lens, lens_obligations, run_id, db)
        total_missing_safeguards += sg_result["created"]
        total_not_automatable += sg_result["skipped_not_automatable"]

        lens_results.append({
            "lens_id": lens.lens_id,
            "obligations": result.obligations_count,
            "skipped_low_confidence": result.skipped_low_confidence,
            "skipped_invalid_evidence": result.skipped_invalid_evidence,
            "errors": result.errors,
            "missing_safeguards_count": sg_result["created"],
            "not_automatable_safeguards_count": sg_result["skipped_not_automatable"],
            "baseline_match_summary": baseline_summary,
            "relations_count": 0,
        })

    # --- Phase 3: Intra-theme relation detection ---
    all_run_obligations = (
        db.query(Obligation)
        .filter_by(run_id=run_id)
        .all()
    )

    if len(all_run_obligations) >= 2:
        try:
            rel_result = detect_relations(
                obligations=all_run_obligations,
                run_id=run_id,
                llm_client=llm_client,
                db=db,
                step_index=step_counter,
            )
            step_counter += 1
            total_relations = rel_result.relations_count
            for k in total_tokens:
                total_tokens[k] += rel_result.token_usage.get(k, 0)
            total_errors += rel_result.errors
        except Exception as e:
            logger.exception("Relation detection failed")
            total_errors += 1
            step_counter += 1
    else:
        total_relations = 0

    # --- Phase 4: Cross-theme checks ---
    cross_theme_candidates = 0
    cross_theme_skipped = 0

    ct_rules = db.query(CrossThemeRule).filter_by(is_active=True).all()
    if ct_rules and len(all_run_obligations) >= 1:
        try:
            ct_result = run_cross_theme_checks(
                obligations=all_run_obligations,
                rules=ct_rules,
                run_id=run_id,
                llm_client=llm_client,
                db=db,
                step_index=step_counter,
            )
            step_counter += 1
            cross_theme_candidates = ct_result.candidates_created
            cross_theme_skipped = ct_result.rules_skipped
            for k in total_tokens:
                total_tokens[k] += ct_result.token_usage.get(k, 0)
            total_errors += ct_result.errors
        except Exception as e:
            logger.exception("Cross-theme checks failed")
            total_errors += 1
            step_counter += 1

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
        "relations_count": total_relations,
        "cross_theme_candidates_count": cross_theme_candidates,
        "cross_theme_rules_skipped": cross_theme_skipped,
        "missing_safeguards_total": total_missing_safeguards,
        "not_automatable_safeguards_total": total_not_automatable,
        "baseline_match_summary": total_baseline_summary,
        "tokens_used": total_tokens,
        "errors": total_errors,
        "lenses": lens_results,
    }
