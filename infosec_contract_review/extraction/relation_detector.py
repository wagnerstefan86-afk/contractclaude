"""Intra-theme relation detection between obligations via LLM."""
from __future__ import annotations

import logging
import pathlib
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from infosec_contract_review.llm.client import LLMClient
from infosec_contract_review.llm.schemas import RELATION_SCHEMA
from infosec_contract_review.models.enums import RelationType, RunStatus, StepType
from infosec_contract_review.models.obligation import Obligation
from infosec_contract_review.models.relation import ObligationRelation
from infosec_contract_review.models.run import RunStep

logger = logging.getLogger(__name__)

PROMPTS_DIR = pathlib.Path(__file__).parent / "prompts"
MAX_OBLIGATIONS_PER_BUNDLE = 15


@dataclass
class RelationResult:
    relations_count: int = 0
    skipped_low_confidence: int = 0
    skipped_invalid: int = 0
    errors: int = 0
    token_usage: dict = field(default_factory=dict)


def _load_developer_prompt() -> str:
    path = PROMPTS_DIR / "PT-RELATIONS-v1.0.txt"
    return path.read_text(encoding="utf-8")


def _build_user_prompt(obligations: list[Obligation], theme: str) -> str:
    parts = [
        f'Analysiere die Beziehungen zwischen diesen Obligations zum Thema "{theme}":\n'
    ]
    for obl in obligations:
        raw = obl.raw_extraction or {}
        obl_type = raw.get("obligation_type", obl.obligation_type.value)
        modality = raw.get("modality", obl.obligation_type.value)
        limits_str = "keine"
        if obl.limits:
            limit_parts = []
            for f in ("frequency_limit", "time_limit", "cost_limit", "scope_limit"):
                v = getattr(obl.limits, f, None)
                if v:
                    limit_parts.append(f"{f}: {v}")
            limits_str = ", ".join(limit_parts) if limit_parts else "keine"

        parts.append(
            f"---\n[OBL-ID: {obl.id}]\n"
            f"{obl.summary}\n"
            f"Typ: {obl_type}, Modality: {modality}\n"
            f"Limits: {limits_str}\n"
        )
    parts.append("\nGib nur materiale Relationen zurück.")
    return "\n".join(parts)


def _process_llm_response(
    llm_resp: dict,
    valid_ids: set[str],
    run_id: str,
    db: Session,
    result: RelationResult,
    seen_pairs: set[tuple[str, str]],
) -> None:
    usage = llm_resp.get("token_usage", {})
    for k in ("prompt_tokens", "completion_tokens", "total_tokens"):
        result.token_usage[k] = result.token_usage.get(k, 0) + usage.get(k, 0)

    for rel in llm_resp.get("data", {}).get("relations", []):
        src = rel.get("source_obligation_id", "")
        tgt = rel.get("target_obligation_id", "")

        if src not in valid_ids or tgt not in valid_ids:
            result.skipped_invalid += 1
            logger.debug("Relation skipped: invalid IDs %s → %s", src, tgt)
            continue
        if src == tgt:
            result.skipped_invalid += 1
            continue
        if rel.get("confidence") == "low":
            result.skipped_low_confidence += 1
            continue

        pair_key = (min(src, tgt), max(src, tgt), rel["relation_type"])
        if pair_key in seen_pairs:
            continue
        seen_pairs.add(pair_key)

        try:
            rel_type = RelationType(rel["relation_type"])
        except ValueError:
            result.skipped_invalid += 1
            logger.warning("Unknown relation_type: %s", rel["relation_type"])
            continue

        db.add(ObligationRelation(
            obligation_a_id=src,
            obligation_b_id=tgt,
            relation_type=rel_type,
            rationale=rel.get("rationale"),
            confidence=rel.get("confidence"),
            run_id=run_id,
        ))
        result.relations_count += 1


def detect_relations(
    obligations: list[Obligation],
    run_id: str,
    llm_client: LLMClient,
    db: Session,
    step_index: int,
) -> RelationResult:
    result = RelationResult()

    step = RunStep(
        run_id=run_id,
        step_type=StepType.RELATION_DETECTION,
        step_index=step_index,
        status=RunStatus.RUNNING,
        input_summary={"obligation_count": len(obligations)},
    )
    db.add(step)
    db.flush()

    if len(obligations) < 2:
        step.status = RunStatus.COMPLETED
        step.output_summary = {"relations": 0, "reason": "fewer than 2 obligations"}
        db.flush()
        return result

    # Group by theme for intra-theme detection
    by_theme: dict[str, list[Obligation]] = {}
    for obl in obligations:
        theme_val = obl.theme.value if hasattr(obl.theme, "value") else str(obl.theme)
        by_theme.setdefault(theme_val, []).append(obl)

    developer_prompt = _load_developer_prompt()
    seen_pairs: set[tuple[str, str]] = set()
    all_valid_ids = {o.id for o in obligations}

    for theme, theme_obls in by_theme.items():
        if len(theme_obls) < 2:
            continue

        # Split into batches if >15 obligations
        batches = []
        if len(theme_obls) <= MAX_OBLIGATIONS_PER_BUNDLE:
            batches = [theme_obls]
        else:
            for i in range(0, len(theme_obls), MAX_OBLIGATIONS_PER_BUNDLE):
                batch = theme_obls[i:i + MAX_OBLIGATIONS_PER_BUNDLE]
                if len(batch) >= 2:
                    batches.append(batch)

        for batch in batches:
            user_prompt = _build_user_prompt(batch, theme)
            batch_ids = {o.id for o in batch}

            try:
                llm_resp = llm_client.call(developer_prompt, user_prompt, RELATION_SCHEMA)
            except Exception as e:
                logger.error("Relation detection failed for theme %s: %s", theme, e)
                result.errors += 1
                continue

            _process_llm_response(llm_resp, batch_ids, run_id, db, result, seen_pairs)

    step.status = RunStatus.COMPLETED
    step.output_summary = {
        "relations": result.relations_count,
        "skipped_low_confidence": result.skipped_low_confidence,
        "skipped_invalid": result.skipped_invalid,
        "errors": result.errors,
        "themes_processed": list(by_theme.keys()),
        "token_usage": result.token_usage,
    }
    db.flush()
    return result
