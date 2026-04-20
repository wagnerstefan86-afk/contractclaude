"""Intra-theme relation detection between obligations via LLM."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from infosec_contract_review.llm.client import LLMClient
from infosec_contract_review.llm.schemas import RELATION_SCHEMA
from infosec_contract_review.models.enums import RelationType, RunStatus, StepType
from infosec_contract_review.models.obligation import Obligation
from infosec_contract_review.models.relation import ObligationRelation
from infosec_contract_review.models.run import RunStep

logger = logging.getLogger(__name__)

_DEVELOPER_PROMPT = """Du bist ein Vertragsanalyst. Du analysierst Beziehungen zwischen extrahierten Vertragspflichten.

Prüfe die folgenden Obligations auf inhaltliche Beziehungen:
- contradicts: Die Obligations widersprechen sich inhaltlich
- supplements: Eine Obligation ergänzt die andere um zusätzliche Details
- overrides: Eine Obligation verdrängt oder ersetzt die andere (z.B. durch eine spezifischere Regelung)
- duplicates: Die Obligations beschreiben denselben Sachverhalt redundant

Regeln:
- Nur echte, inhaltlich begründbare Beziehungen melden
- Keine Beziehung zwischen einer Obligation und sich selbst
- Jede Beziehung nur einmal melden (A→B, nicht auch B→A)
- Bei Unsicherheit: confidence=low setzen"""


@dataclass
class RelationResult:
    relations_count: int = 0
    skipped_low_confidence: int = 0
    skipped_invalid: int = 0
    errors: int = 0
    token_usage: dict = field(default_factory=dict)


def _build_obligation_prompt(obligations: list[Obligation]) -> str:
    parts = ["Obligations:\n"]
    for obl in obligations:
        parts.append(
            f"---\n[OBL-ID: {obl.id}]\n"
            f"[Theme: {obl.theme.value}]\n"
            f"[Type: {obl.obligation_type.value}]\n"
            f"{obl.summary}\n"
        )
    return "\n".join(parts)


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

    user_prompt = _build_obligation_prompt(obligations)
    valid_ids = {o.id for o in obligations}

    try:
        llm_resp = llm_client.call(_DEVELOPER_PROMPT, user_prompt, RELATION_SCHEMA)
    except Exception as e:
        logger.error("Relation detection LLM call failed: %s", e)
        step.status = RunStatus.FAILED
        step.error_message = str(e)
        result.errors = 1
        db.flush()
        return result

    usage = llm_resp.get("token_usage", {})
    result.token_usage = usage

    seen_pairs: set[tuple[str, str]] = set()
    relations_data = llm_resp.get("data", {}).get("relations", [])

    for rel in relations_data:
        src = rel.get("source_obligation_id", "")
        tgt = rel.get("target_obligation_id", "")

        if src not in valid_ids or tgt not in valid_ids:
            result.skipped_invalid += 1
            continue
        if src == tgt:
            result.skipped_invalid += 1
            continue
        if rel.get("confidence") == "low":
            result.skipped_low_confidence += 1
            continue

        pair = tuple(sorted([src, tgt]))
        if pair in seen_pairs:
            continue
        seen_pairs.add(pair)

        try:
            rel_type = RelationType(rel["relation_type"])
        except ValueError:
            result.skipped_invalid += 1
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

    step.status = RunStatus.COMPLETED
    step.output_summary = {
        "relations": result.relations_count,
        "skipped_low_confidence": result.skipped_low_confidence,
        "skipped_invalid": result.skipped_invalid,
        "token_usage": usage,
    }
    db.flush()
    return result
