"""
Seed loader for infosec_contract_review.

Reads YAML seed files and upserts them into Postgres.
Idempotent: existing records (matched by stable business key) are updated,
new records are inserted. No silent duplicates.

Usage:
    from infosec_contract_review.seed.loader import load_all_seeds
    load_all_seeds(session)
"""
from __future__ import annotations

import logging
import pathlib
from typing import Any

import yaml
from sqlalchemy.orm import Session

from infosec_contract_review.models.baseline import (
    Certification,
    ProviderBaseline,
    ServiceProfile,
    StandardPosition,
)
from infosec_contract_review.models.config import (
    CrossThemeRule,
    ExpectedSafeguard,
    LensConfig,
)
from infosec_contract_review.models.enums import (
    DeliveryModel,
    Materiality,
    ServiceType,
    TenantModel,
    Theme,
)
from infosec_contract_review.models.playbook import PlaybookEntry

logger = logging.getLogger(__name__)

SEED_DIR = pathlib.Path(__file__).parent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read_yaml(filename: str) -> dict:
    """Read and parse a YAML file from the seed directory."""
    path = SEED_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"Seed file not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if data is None:
        raise ValueError(f"Seed file is empty or invalid YAML: {path}")
    return data


def _require_fields(record: dict, fields: list[str], context: str) -> None:
    """Validate that all required fields are present and non-None."""
    missing = [f for f in fields if f not in record or record[f] is None]
    if missing:
        raise ValueError(
            f"Missing required field(s) {missing} in {context}: {record}"
        )


def _resolve_enum(enum_cls, value: str, field_name: str, context: str):
    """Resolve a string value to an enum member with clear error."""
    try:
        return enum_cls(value)
    except ValueError:
        valid = [e.value for e in enum_cls]
        raise ValueError(
            f"Invalid {field_name} '{value}' in {context}. "
            f"Valid values: {valid}"
        )


# ---------------------------------------------------------------------------
# Individual seed loaders
# ---------------------------------------------------------------------------

def _load_provider_baseline(session: Session) -> int:
    """Load provider_baseline.yaml → ProviderBaseline + children."""
    data = _read_yaml("provider_baseline.yaml")
    bl = data.get("baseline")
    if not bl:
        raise ValueError("provider_baseline.yaml: missing top-level 'baseline' key")

    _require_fields(bl, ["version", "valid_from"], "provider_baseline")

    # Business key: version + valid_from
    existing = (
        session.query(ProviderBaseline)
        .filter_by(version=bl["version"], valid_from=bl["valid_from"])
        .first()
    )

    if existing:
        logger.info(
            "ProviderBaseline v%s (%s) already exists – updating.",
            bl["version"], bl["valid_from"],
        )
        baseline = existing
        baseline.is_active = bl.get("is_active", True)
        # Clear children for re-creation
        baseline.certifications.clear()
        baseline.standard_positions.clear()
        baseline.service_profiles.clear()
    else:
        baseline = ProviderBaseline(
            version=bl["version"],
            valid_from=bl["valid_from"],
            is_active=bl.get("is_active", True),
        )
        session.add(baseline)

    session.flush()  # ensure baseline.id is available

    # Certifications
    for cert in bl.get("certifications", []):
        _require_fields(cert, ["standard", "scope"], "certification")
        baseline.certifications.append(Certification(
            standard=cert["standard"],
            scope=cert["scope"],
            valid_until=cert.get("valid_until"),
            covers_all_services=cert.get("covers_all_services", False),
            excluded_services=cert.get("excluded_services"),
        ))

    # Standard positions (dict keyed by theme)
    for theme_key, pos in bl.get("standard_positions", {}).items():
        _require_fields(pos, ["accepted", "not_accepted", "escalation_threshold"],
                        f"standard_position[{theme_key}]")
        baseline.standard_positions.append(StandardPosition(
            theme=theme_key,
            accepted=pos["accepted"].strip(),
            not_accepted=pos["not_accepted"].strip(),
            escalation_threshold=pos["escalation_threshold"].strip(),
        ))

    # Service profiles
    for sp in bl.get("service_profiles", []):
        _require_fields(sp, ["service_type", "delivery_model", "tenant_model",
                             "baseline_controls"], "service_profile")
        baseline.service_profiles.append(ServiceProfile(
            service_type=_resolve_enum(ServiceType, sp["service_type"],
                                       "service_type", "service_profile"),
            delivery_model=_resolve_enum(DeliveryModel, sp["delivery_model"],
                                         "delivery_model", "service_profile"),
            tenant_model=_resolve_enum(TenantModel, sp["tenant_model"],
                                       "tenant_model", "service_profile"),
            baseline_controls=sp["baseline_controls"],
        ))

    session.flush()
    count = (1 + len(baseline.certifications) +
             len(baseline.standard_positions) + len(baseline.service_profiles))
    logger.info("ProviderBaseline: %d records upserted.", count)
    return count


def _load_lens_configs(session: Session) -> int:
    """Load lens_configs.yaml → LensConfig + ExpectedSafeguard."""
    data = _read_yaml("lens_configs.yaml")
    lenses = data.get("lenses")
    if not lenses:
        raise ValueError("lens_configs.yaml: missing top-level 'lenses' key")

    count = 0
    for lc in lenses:
        _require_fields(lc, ["lens_id", "version", "theme",
                             "prompt_template_id", "segment_filter"],
                        "lens_config")
        theme = _resolve_enum(Theme, lc["theme"], "theme", f"lens {lc['lens_id']}")

        existing = (
            session.query(LensConfig)
            .filter_by(lens_id=lc["lens_id"])
            .first()
        )

        if existing:
            logger.info("LensConfig %s already exists – updating.", lc["lens_id"])
            existing.version = lc["version"]
            existing.theme = theme
            existing.prompt_template_id = lc["prompt_template_id"]
            existing.segment_filter = lc["segment_filter"]
            existing.include_neighbor_context = lc.get("include_neighbor_context", True)
            existing.max_segments_per_call = lc.get("max_segments_per_call", 25)
            existing.is_active = lc.get("is_active", True)
            existing.owner = lc.get("owner")
            existing.expected_safeguards.clear()
            session.flush()
            lens = existing
        else:
            lens = LensConfig(
                lens_id=lc["lens_id"],
                version=lc["version"],
                theme=theme,
                prompt_template_id=lc["prompt_template_id"],
                segment_filter=lc["segment_filter"],
                include_neighbor_context=lc.get("include_neighbor_context", True),
                max_segments_per_call=lc.get("max_segments_per_call", 25),
                is_active=lc.get("is_active", True),
                owner=lc.get("owner"),
            )
            session.add(lens)
            session.flush()

        for sg in lc.get("expected_safeguards", []):
            _require_fields(sg, ["safeguard_key", "label"],
                            f"expected_safeguard in lens {lc['lens_id']}")
            lens.expected_safeguards.append(ExpectedSafeguard(
                safeguard_key=sg["safeguard_key"],
                label=sg["label"],
                maps_to_limit_field=sg.get("maps_to_limit_field"),
            ))

        count += 1 + len(lc.get("expected_safeguards", []))

    session.flush()
    logger.info("LensConfigs: %d records upserted.", count)
    return count


def _load_cross_theme_rules(session: Session) -> int:
    """Load cross_theme_rules.yaml → CrossThemeRule."""
    data = _read_yaml("cross_theme_rules.yaml")
    rules = data.get("cross_theme_rules")
    if not rules:
        raise ValueError("cross_theme_rules.yaml: missing top-level 'cross_theme_rules' key")

    count = 0
    for r in rules:
        _require_fields(r, ["rule_id", "version", "name", "theme_a", "theme_b",
                            "trigger_condition", "check_prompt",
                            "default_materiality_floor"],
                        "cross_theme_rule")

        theme_a = _resolve_enum(Theme, r["theme_a"], "theme_a", f"rule {r['rule_id']}")
        theme_b = _resolve_enum(Theme, r["theme_b"], "theme_b", f"rule {r['rule_id']}")
        mat = _resolve_enum(Materiality, r["default_materiality_floor"],
                            "default_materiality_floor", f"rule {r['rule_id']}")

        existing = (
            session.query(CrossThemeRule)
            .filter_by(rule_id=r["rule_id"])
            .first()
        )

        if existing:
            logger.info("CrossThemeRule %s already exists – updating.", r["rule_id"])
            existing.version = r["version"]
            existing.name = r["name"]
            existing.theme_a = theme_a
            existing.theme_b = theme_b
            existing.trigger_condition = r["trigger_condition"].strip()
            existing.check_prompt = r["check_prompt"].strip()
            existing.default_materiality_floor = mat
            existing.is_active = r.get("is_active", True)
            existing.owner = r.get("owner")
        else:
            session.add(CrossThemeRule(
                rule_id=r["rule_id"],
                version=r["version"],
                name=r["name"],
                theme_a=theme_a,
                theme_b=theme_b,
                trigger_condition=r["trigger_condition"].strip(),
                check_prompt=r["check_prompt"].strip(),
                default_materiality_floor=mat,
                is_active=r.get("is_active", True),
                owner=r.get("owner"),
            ))
        count += 1

    session.flush()
    logger.info("CrossThemeRules: %d records upserted.", count)
    return count


def _load_playbook_entries(session: Session) -> int:
    """Load playbook_v1.yaml → PlaybookEntry.

    Business key: the 'id' field from YAML is used to detect duplicates.
    Since PlaybookEntry has no dedicated business-key column, we store
    the YAML id as the SQLAlchemy primary key (id column) for seed data.
    """
    data = _read_yaml("playbook_v1.yaml")
    entries = data.get("playbook_entries")
    if not entries:
        raise ValueError("playbook_v1.yaml: missing top-level 'playbook_entries' key")

    count = 0
    for e in entries:
        _require_fields(e, ["id", "version", "theme", "risk_pattern",
                            "standard_position", "alt_wordings",
                            "bidder_questions", "applicable_when"],
                        "playbook_entry")

        theme = _resolve_enum(Theme, e["theme"], "theme", f"playbook {e['id']}")

        existing = session.get(PlaybookEntry, e["id"])

        if existing:
            logger.info("PlaybookEntry %s already exists – updating.", e["id"])
            existing.version = e["version"]
            existing.theme = theme
            existing.risk_pattern = e["risk_pattern"].strip()
            existing.standard_position = e["standard_position"].strip()
            existing.alt_wordings = e["alt_wordings"]
            existing.bidder_questions = e["bidder_questions"]
            existing.applicable_when = e["applicable_when"].strip()
            existing.escalation_note = (
                e["escalation_note"].strip() if e.get("escalation_note") else None
            )
            existing.is_active = e.get("is_active", True)
            existing.owner = e.get("owner")
        else:
            session.add(PlaybookEntry(
                id=e["id"],
                version=e["version"],
                theme=theme,
                risk_pattern=e["risk_pattern"].strip(),
                standard_position=e["standard_position"].strip(),
                alt_wordings=e["alt_wordings"],
                bidder_questions=e["bidder_questions"],
                applicable_when=e["applicable_when"].strip(),
                escalation_note=(
                    e["escalation_note"].strip() if e.get("escalation_note") else None
                ),
                is_active=e.get("is_active", True),
                owner=e.get("owner"),
            ))
        count += 1

    session.flush()
    logger.info("PlaybookEntries: %d records upserted.", count)
    return count


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def load_all_seeds(session: Session) -> dict[str, int]:
    """
    Load all seed files in the correct dependency order.

    Returns a dict mapping seed name → number of records upserted.
    Rolls back the transaction on any error.
    """
    results: dict[str, int] = {}
    loaders = [
        ("provider_baseline", _load_provider_baseline),
        ("lens_configs", _load_lens_configs),
        ("cross_theme_rules", _load_cross_theme_rules),
        ("playbook_entries", _load_playbook_entries),
    ]

    try:
        for name, loader_fn in loaders:
            logger.info("Loading seed: %s ...", name)
            results[name] = loader_fn(session)
            logger.info("Seed %s loaded successfully.", name)

        session.commit()
        logger.info("All seeds committed successfully.")
    except Exception:
        session.rollback()
        logger.exception("Seed loading failed – transaction rolled back.")
        raise

    return results
