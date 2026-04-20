"""Deterministic baseline match: compare obligations against provider baseline."""
from __future__ import annotations

import logging

from infosec_contract_review.models.baseline import ProviderBaseline, StandardPosition
from infosec_contract_review.models.obligation import Obligation

logger = logging.getLogger(__name__)


def match_obligation_to_baseline(
    obligation: Obligation,
    baseline: ProviderBaseline,
) -> tuple[str, str]:
    """Match a single obligation against the provider baseline.

    Returns (baseline_match_status, baseline_gap_description).
    Three simple rules for the PoC.
    """
    raw = obligation.raw_extraction or {}
    obl_type = raw.get("obligation_type", "")
    beneficiary = raw.get("beneficiary", "")

    # Rule 3: provider rights are already supported
    if obl_type == "right" and beneficiary == "provider":
        return (
            "already_supported",
            "Recht des Auftragnehmers – kein Gap.",
        )

    all_limits_null = True
    if obligation.limits:
        for field in ("frequency_limit", "time_limit", "cost_limit", "scope_limit"):
            if getattr(obligation.limits, field, None) is not None:
                all_limits_null = False
                break
        if all_limits_null and obligation.limits.other_limits:
            if any(v is not None for v in obligation.limits.other_limits.values()):
                all_limits_null = False

    # Rule 1: no limits at all
    if all_limits_null:
        return (
            "not_supported",
            "Keine Begrenzungen gefunden – unbegrenzte Pflichten entsprechen nie dem Standard.",
        )

    # Rule 2: some limits present and theme has a standard position
    theme_val = obligation.theme.value if hasattr(obligation.theme, "value") else str(obligation.theme)
    has_position = any(
        sp.theme == theme_val for sp in baseline.standard_positions
    )

    if has_position:
        return (
            "partially_supported",
            "Teilweise Begrenzungen vorhanden, Abgleich mit Standard-Position empfohlen.",
        )

    # Default
    return (
        "partially_supported",
        "Teilweise Begrenzungen vorhanden, keine Standard-Position für dieses Thema.",
    )
