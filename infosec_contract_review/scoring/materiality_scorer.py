"""Deterministic materiality scoring for obligations."""
from __future__ import annotations

import logging

from infosec_contract_review.models.enums import Materiality
from infosec_contract_review.models.finding import MissingSafeguard
from infosec_contract_review.models.obligation import Obligation
from infosec_contract_review.models.relation import ObligationRelation

logger = logging.getLogger(__name__)

_MATERIALITY_ORDER = {
    Materiality.LOW: 0,
    Materiality.MEDIUM: 1,
    Materiality.HIGH: 2,
    Materiality.CRITICAL: 3,
}

_MATERIALITY_BY_VALUE = {m.value: m for m in Materiality}


def _max_materiality(a: Materiality, b: Materiality) -> Materiality:
    return a if _MATERIALITY_ORDER[a] >= _MATERIALITY_ORDER[b] else b


def score_obligation_materiality(
    obligation: Obligation,
    missing_safeguards: list[MissingSafeguard],
    relations: list[ObligationRelation],
) -> Materiality:
    """Score materiality for a single obligation based on deterministic rules.

    Starts from MEDIUM (default from extraction) and escalates based on signals.
    """
    mat = Materiality.MEDIUM

    # Rule 1: baseline_match_status = not_supported → at least HIGH
    if obligation.baseline_match_status == "not_supported":
        mat = _max_materiality(mat, Materiality.HIGH)

    # Rule 2: all limits null → escalate by one level
    all_limits_null = True
    if obligation.limits:
        for f in ("frequency_limit", "time_limit", "cost_limit", "scope_limit"):
            if getattr(obligation.limits, f, None) is not None:
                all_limits_null = False
                break
        if all_limits_null and obligation.limits.other_limits:
            if any(v is not None for v in obligation.limits.other_limits.values()):
                all_limits_null = False
    if all_limits_null:
        mat = _max_materiality(mat, Materiality.HIGH)

    # Rule 3: missing safeguards referencing this obligation's theme
    obl_theme = obligation.theme.value if hasattr(obligation.theme, "value") else str(obligation.theme)
    relevant_missing = [
        ms for ms in missing_safeguards
        if ms.status == "missing"
    ]
    if len(relevant_missing) >= 3:
        mat = _max_materiality(mat, Materiality.CRITICAL)
    elif len(relevant_missing) >= 1:
        mat = _max_materiality(mat, Materiality.HIGH)

    # Rule 4: contradicts relation → escalate
    for rel in relations:
        rel_type = rel.relation_type.value if hasattr(rel.relation_type, "value") else str(rel.relation_type)
        if rel_type == "contradicts":
            if rel.obligation_a_id == obligation.id or rel.obligation_b_id == obligation.id:
                mat = _max_materiality(mat, Materiality.HIGH)
                break

    # Rule 5: tightens relation → at least MEDIUM (already default, but explicit)
    for rel in relations:
        rel_type = rel.relation_type.value if hasattr(rel.relation_type, "value") else str(rel.relation_type)
        if rel_type == "tightens":
            if rel.obligation_b_id == obligation.id:
                mat = _max_materiality(mat, Materiality.MEDIUM)

    return mat
