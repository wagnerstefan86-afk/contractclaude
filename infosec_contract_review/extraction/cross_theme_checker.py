"""Cross-theme conflict detection using LLM with CrossThemeRule prompts."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from infosec_contract_review.llm.client import LLMClient
from infosec_contract_review.llm.schemas import CROSS_THEME_SCHEMA
from infosec_contract_review.models.config import CrossThemeRule
from infosec_contract_review.models.enums import Materiality, RunStatus, StepType
from infosec_contract_review.models.obligation import Obligation
from infosec_contract_review.models.relation import CrossThemeFindingCandidate
from infosec_contract_review.models.run import RunStep

logger = logging.getLogger(__name__)

_MATERIALITY_MAP = {v.value: v for v in Materiality}


@dataclass
class CrossThemeResult:
    candidates_created: int = 0
    rules_checked: int = 0
    rules_skipped: int = 0
    errors: int = 0
    token_usage: dict = field(default_factory=dict)


def _build_cross_theme_prompt(
    rule: CrossThemeRule,
    obligations_a: list[Obligation],
    obligations_b: list[Obligation],
) -> str:
    theme_a_val = rule.theme_a.value if hasattr(rule.theme_a, "value") else str(rule.theme_a)
    theme_b_val = rule.theme_b.value if hasattr(rule.theme_b, "value") else str(rule.theme_b)

    parts = [
        f"Prüfe den folgenden Cross-Theme-Konflikt.\n\n",
        f'Obligations zum Thema "{theme_a_val}":\n',
    ]
    for obl in obligations_a:
        parts.append(f"  [OBL-ID: {obl.id}] {obl.summary}\n")

    parts.append(f'\nObligations zum Thema "{theme_b_val}":\n')
    for obl in obligations_b:
        parts.append(f"  [OBL-ID: {obl.id}] {obl.summary}\n")

    parts.append(f"\nTrigger-Kontext: {rule.trigger_condition}\n")

    return "".join(parts)


def run_cross_theme_checks(
    obligations: list[Obligation],
    rules: list[CrossThemeRule],
    run_id: str,
    llm_client: LLMClient,
    db: Session,
    step_index: int,
) -> CrossThemeResult:
    result = CrossThemeResult()

    step = RunStep(
        run_id=run_id,
        step_type=StepType.CROSS_THEME,
        step_index=step_index,
        status=RunStatus.RUNNING,
        input_summary={
            "obligation_count": len(obligations),
            "rule_count": len(rules),
        },
    )
    db.add(step)
    db.flush()

    obl_by_theme: dict[str, list[Obligation]] = {}
    for obl in obligations:
        theme_val = obl.theme.value if hasattr(obl.theme, "value") else str(obl.theme)
        obl_by_theme.setdefault(theme_val, []).append(obl)

    total_tokens = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    for rule in rules:
        theme_a_val = rule.theme_a.value if hasattr(rule.theme_a, "value") else str(rule.theme_a)
        theme_b_val = rule.theme_b.value if hasattr(rule.theme_b, "value") else str(rule.theme_b)

        obls_a = obl_by_theme.get(theme_a_val, [])
        obls_b = obl_by_theme.get(theme_b_val, [])

        if not obls_a or not obls_b:
            logger.info(
                "Cross-theme rule %s skipped: theme_a=%s (%d obls), theme_b=%s (%d obls)",
                rule.rule_id, theme_a_val, len(obls_a), theme_b_val, len(obls_b),
            )
            result.rules_skipped += 1
            continue

        user_prompt = _build_cross_theme_prompt(rule, obls_a, obls_b)
        developer_prompt = rule.check_prompt

        try:
            llm_resp = llm_client.call(developer_prompt, user_prompt, CROSS_THEME_SCHEMA)
        except Exception as e:
            logger.error("Cross-theme LLM call failed for rule %s: %s", rule.rule_id, e)
            result.errors += 1
            continue

        usage = llm_resp.get("token_usage", {})
        for k in total_tokens:
            total_tokens[k] += usage.get(k, 0)

        data = llm_resp.get("data", {})
        check_result = data.get("result", "unclear")
        result.rules_checked += 1

        if check_result == "no_conflict":
            logger.info("Cross-theme rule %s: no conflict", rule.rule_id)
            continue

        mat_floor = _MATERIALITY_MAP.get(
            rule.default_materiality_floor.value
            if hasattr(rule.default_materiality_floor, "value")
            else str(rule.default_materiality_floor),
            Materiality.HIGH,
        )

        candidate = CrossThemeFindingCandidate(
            rule_id=rule.id,
            run_id=run_id,
            result=check_result,
            rationale=data.get("rationale"),
            confidence=data.get("confidence"),
            materiality=mat_floor,
            obligation_ids_theme_a=[o for o in data.get("involved_obligation_ids_a", [])],
            obligation_ids_theme_b=[o for o in data.get("involved_obligation_ids_b", [])],
        )
        db.add(candidate)
        result.candidates_created += 1

    result.token_usage = total_tokens
    step.status = RunStatus.COMPLETED
    step.output_summary = {
        "candidates_created": result.candidates_created,
        "rules_checked": result.rules_checked,
        "rules_skipped": result.rules_skipped,
        "errors": result.errors,
        "token_usage": total_tokens,
    }
    db.flush()
    return result
