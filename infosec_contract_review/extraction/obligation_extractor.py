"""Obligation extraction using LLM with lens-based segment filtering."""
from __future__ import annotations

import logging
import pathlib
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from infosec_contract_review.llm.client import LLMClient
from infosec_contract_review.llm.schemas import OBLIGATION_SCHEMA
from infosec_contract_review.models.config import LensConfig
from infosec_contract_review.models.enums import (
    Materiality,
    ObligationDirection,
    ObligationType,
    RunStatus,
    StepType,
    Theme,
)
from infosec_contract_review.models.obligation import Obligation, ObligationLimits
from infosec_contract_review.models.run import RunStep
from infosec_contract_review.models.segment import Segment

logger = logging.getLogger(__name__)

PROMPTS_DIR = pathlib.Path(__file__).parent / "prompts"

_MODALITY_MAP = {
    "must": ObligationType.MUST,
    "shall": ObligationType.SHALL,
    "may": ObligationType.MAY,
    "should": ObligationType.SHOULD,
    "is_entitled_to": ObligationType.MAY,
    "is_prohibited_from": ObligationType.MUST,
}

_DIRECTION_MAP = {
    "provider": ObligationDirection.PROVIDER_TO_CLIENT,
    "client": ObligationDirection.CLIENT_TO_PROVIDER,
    "both": ObligationDirection.MUTUAL,
    "unclear": ObligationDirection.UNCLEAR,
}

_THEME_MAP = {lc.value: lc for lc in Theme}


@dataclass
class ExtractionResult:
    lens_id: str
    obligations_count: int = 0
    skipped_low_confidence: int = 0
    skipped_invalid_evidence: int = 0
    errors: int = 0
    token_usage: dict = field(default_factory=dict)


def _load_prompt(template_id: str) -> str:
    path = PROMPTS_DIR / f"{template_id}.txt"
    if not path.exists():
        raise FileNotFoundError(f"Prompt template not found: {path}")
    return path.read_text(encoding="utf-8")


def _filter_segments(
    segments: list[Segment], lens: LensConfig
) -> list[Segment]:
    sf = lens.segment_filter or {}
    tiers = set(sf.get("routing_tiers", []))
    flags_any = set(sf.get("deterministic_flags_any", []))

    filtered = []
    for seg in segments:
        if seg.routing_tier not in tiers:
            continue
        seg_flags = set(seg.deterministic_flags or [])
        if not seg_flags.intersection(flags_any):
            continue
        filtered.append(seg)
    return filtered


def _build_user_prompt(batch: list[Segment], context_map: dict[str, Segment]) -> str:
    parts = ["Analysiere die folgenden Segmente.\n\nSegmente:"]
    for seg in batch:
        heading = " > ".join(seg.heading_path) if seg.heading_path else "–"
        parts.append(f"---\n[SEG-ID: {seg.id}]\n[Seite: {seg.page_number}]\n[Heading: {heading}]\n{seg.text}")

    if context_map:
        parts.append("\n\nKontext-Segmente (nicht analysieren, nur als Referenz):")
        for seg_id, seg in context_map.items():
            parts.append(f"---\n[CONTEXT SEG-ID: {seg_id}]\n{seg.text}")

    return "\n".join(parts)


def extract_obligations_for_lens(
    package_id: str,
    run_id: str,
    lens: LensConfig,
    segments: list[Segment],
    llm_client: LLMClient,
    db: Session,
    step_index: int,
) -> ExtractionResult:
    result = ExtractionResult(lens_id=lens.lens_id)

    filtered = _filter_segments(segments, lens)
    logger.info(
        "Lens %s: %d/%d segments match filter",
        lens.lens_id, len(filtered), len(segments),
    )

    step = RunStep(
        run_id=run_id,
        step_type=StepType.LENS_ANALYSIS,
        step_index=step_index,
        status=RunStatus.RUNNING,
        input_summary={
            "lens_id": lens.lens_id,
            "theme": lens.theme.value,
            "total_segments": len(segments),
            "filtered_segments": len(filtered),
        },
    )
    db.add(step)
    db.flush()

    if not filtered:
        step.status = RunStatus.COMPLETED
        step.output_summary = {"obligations": 0, "reason": "no matching segments"}
        db.flush()
        return result

    try:
        developer_prompt = _load_prompt(lens.prompt_template_id)
    except FileNotFoundError as e:
        step.status = RunStatus.FAILED
        step.error_message = str(e)
        result.errors = 1
        db.flush()
        return result

    seg_by_id = {s.id: s for s in segments}
    valid_seg_ids = {s.id for s in filtered}
    # All segment IDs that appear in the prompt (batch + context) are acceptable evidence
    all_prompt_seg_ids: set[str] = set()

    batch_size = lens.max_segments_per_call or 25
    total_tokens = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    for i in range(0, len(filtered), batch_size):
        batch = filtered[i:i + batch_size]
        batch_seg_ids = {s.id for s in batch}

        context_map: dict[str, Segment] = {}
        if lens.include_neighbor_context:
            for seg in batch:
                if seg.preceding_segment_id and seg.preceding_segment_id not in valid_seg_ids:
                    prev = seg_by_id.get(seg.preceding_segment_id)
                    if prev:
                        context_map[prev.id] = prev
                if seg.following_segment_id and seg.following_segment_id not in valid_seg_ids:
                    nxt = seg_by_id.get(seg.following_segment_id)
                    if nxt:
                        context_map[nxt.id] = nxt

        # IDs the LLM can legitimately reference: batch segments + context segments
        prompt_seg_ids = batch_seg_ids | set(context_map.keys())
        all_prompt_seg_ids.update(prompt_seg_ids)

        user_prompt = _build_user_prompt(batch, context_map)

        try:
            llm_resp = llm_client.call(developer_prompt, user_prompt, OBLIGATION_SCHEMA)
        except Exception as e:
            logger.error("LLM call failed for lens %s batch %d: %s", lens.lens_id, i, e)
            result.errors += 1
            continue

        usage = llm_resp.get("token_usage", {})
        for k in total_tokens:
            total_tokens[k] += usage.get(k, 0)

        obligations_data = llm_resp.get("data", {}).get("obligations", [])

        for obl_raw in obligations_data:
            if obl_raw.get("confidence") == "low":
                result.skipped_low_confidence += 1
                continue

            ev_ids = obl_raw.get("evidence_segment_ids", [])
            # Accept IDs from batch segments, context segments, or any known segment
            valid_ev = [eid for eid in ev_ids if eid in prompt_seg_ids or eid in seg_by_id]

            if not valid_ev:
                # Defensive fallback: if the LLM returned unrecognizable IDs but
                # we have batch segments, use the first batch segment as evidence.
                # This prevents losing obligations entirely due to ID format mismatches.
                if batch:
                    valid_ev = [batch[0].id]
                    logger.warning(
                        "Lens %s: evidence_segment_ids %s unrecognized, falling back to batch segment %s",
                        lens.lens_id, ev_ids, batch[0].id,
                    )
                else:
                    result.skipped_invalid_evidence += 1
                    logger.warning(
                        "Obligation skipped: no valid evidence_segment_ids in %s", ev_ids
                    )
                    continue

            primary_seg_id = valid_ev[0]
            modality = _MODALITY_MAP.get(obl_raw.get("modality", "must"), ObligationType.MUST)
            direction = _DIRECTION_MAP.get(obl_raw.get("obligated_party", "unclear"), ObligationDirection.UNCLEAR)
            theme = _THEME_MAP.get(lens.theme.value, Theme.OTHER)

            obl = Obligation(
                segment_id=primary_seg_id,
                theme=theme,
                obligation_type=modality,
                direction=direction,
                summary=obl_raw.get("obligation_text", ""),
                verbatim_quote=obl_raw.get("obligation_text", ""),
                materiality=Materiality.MEDIUM,
                confidence=obl_raw.get("confidence"),
                run_id=run_id,
                lens_config_id=lens.id,
                extraction_method="llm",
                evidence_segment_ids=valid_ev,
                raw_extraction=obl_raw,
            )
            db.add(obl)
            db.flush()

            limits_raw = obl_raw.get("limits", {})
            if limits_raw and any(v is not None for v in limits_raw.values()):
                obl_limits = ObligationLimits(
                    obligation_id=obl.id,
                    frequency_limit=limits_raw.get("frequency_limit"),
                    time_limit=limits_raw.get("time_limit"),
                    cost_limit=limits_raw.get("cost_limit"),
                    scope_limit=limits_raw.get("scope_limit"),
                    other_limits={"access_limit": limits_raw.get("access_limit")}
                    if limits_raw.get("access_limit") else None,
                )
                db.add(obl_limits)

            result.obligations_count += 1

    result.token_usage = total_tokens
    step.status = RunStatus.COMPLETED
    step.output_summary = {
        "obligations": result.obligations_count,
        "skipped_low_confidence": result.skipped_low_confidence,
        "skipped_invalid_evidence": result.skipped_invalid_evidence,
        "errors": result.errors,
        "token_usage": total_tokens,
    }
    db.flush()
    return result
