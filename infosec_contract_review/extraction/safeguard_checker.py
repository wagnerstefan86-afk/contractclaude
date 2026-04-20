"""Deterministic check: are expected safeguards covered by extracted obligations?"""
from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from infosec_contract_review.models.config import LensConfig, ExpectedSafeguard
from infosec_contract_review.models.finding import MissingSafeguard
from infosec_contract_review.models.obligation import Obligation, ObligationLimits

logger = logging.getLogger(__name__)

_LIMIT_FIELD_TO_COLUMN = {
    "frequency_limit": "frequency_limit",
    "time_limit": "time_limit",
    "cost_limit": "cost_limit",
    "scope_limit": "scope_limit",
    "access_limit": None,
}


def check_missing_safeguards(
    lens_config: LensConfig,
    obligations: list[Obligation],
    run_id: str,
    db: Session,
) -> dict:
    """Check expected safeguards against extracted obligations.

    Returns {"created": N, "skipped_not_automatable": N}
    """
    created = 0
    skipped_not_automatable = 0

    for es in lens_config.expected_safeguards:
        if not es.maps_to_limit_field:
            skipped_not_automatable += 1
            logger.info(
                "Safeguard %s (%s): skipped, maps_to_limit_field is null (not automatable)",
                es.safeguard_key, es.label,
            )
            continue

        limit_field = es.maps_to_limit_field
        col_name = _LIMIT_FIELD_TO_COLUMN.get(limit_field)

        found = False
        for obl in obligations:
            if not obl.limits:
                continue

            if col_name:
                val = getattr(obl.limits, col_name, None)
                if val is not None:
                    found = True
                    break
            elif limit_field == "access_limit":
                other = obl.limits.other_limits or {}
                if other.get("access_limit") is not None:
                    found = True
                    break

        if not found:
            ms = MissingSafeguard(
                finding_id=None,
                run_id=run_id,
                lens_config_id=lens_config.id,
                obligation_id=None,
                safeguard_key=es.safeguard_key,
                label=es.label,
                explanation=f"Kein Limit '{limit_field}' in den extrahierten Obligations gefunden.",
                status="missing",
            )
            db.add(ms)
            created += 1
            logger.info(
                "MissingSafeguard created: %s (%s) for lens %s",
                es.safeguard_key, es.label, lens_config.lens_id,
            )

    db.flush()
    return {"created": created, "skipped_not_automatable": skipped_not_automatable}
