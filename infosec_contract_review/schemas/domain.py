from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


# ---------------------------------------------------------------------------
# Base mixins
# ---------------------------------------------------------------------------

class TimestampOut(BaseModel):
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Packages
# ---------------------------------------------------------------------------

class PackageCreate(BaseModel):
    name: str
    description: str | None = None
    customer_name: str | None = None


class DocumentBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    filename: str
    doc_type: str | None
    language: str | None
    page_count: int | None
    created_at: datetime


class PackageBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    description: str | None
    document_count: int
    created_at: datetime


class PackageDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    description: str | None
    created_at: datetime
    updated_at: datetime
    documents: list[DocumentBrief]


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    package_id: str
    filename: str
    doc_type: str | None
    language: str | None
    page_count: int | None
    created_at: datetime


# ---------------------------------------------------------------------------
# Findings
# ---------------------------------------------------------------------------

class EvidenceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    obligation_id: str | None
    segment_id: str | None
    quote: str | None
    rationale: str | None


class MissingSafeguardOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    safeguard_key: str
    label: str
    explanation: str | None


class FindingBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    run_id: str
    theme: str
    title: str
    severity: str
    materiality: str
    status: str
    created_at: datetime


class FindingDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    run_id: str
    theme: str
    title: str
    description: str
    severity: str
    materiality: str
    status: str
    playbook_entry_id: str | None
    recommendation: str | None
    created_at: datetime
    updated_at: datetime
    evidences: list[EvidenceOut]
    missing_safeguards: list[MissingSafeguardOut]


# ---------------------------------------------------------------------------
# Review
# ---------------------------------------------------------------------------

class ReviewCreate(BaseModel):
    reviewer: str
    decision: str
    comment: str | None = None
    new_materiality: str | None = None
    new_action: str | None = None


class ReviewDecisionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    finding_id: str
    decision: str
    reviewer: str
    comment: str | None
    created_at: datetime


# ---------------------------------------------------------------------------
# Analysis Runs
# ---------------------------------------------------------------------------

class RunBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    package_id: str
    status: str
    created_at: datetime


class RunStepOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    step_type: str
    step_index: int
    status: str
    input_summary: dict | None
    output_summary: dict | None
    error_message: str | None
    created_at: datetime


class RunDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    package_id: str
    status: str
    config_snapshot: dict | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime
    steps: list[RunStepOut]


# ---------------------------------------------------------------------------
# Segments
# ---------------------------------------------------------------------------

class SegmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    document_id: str
    segment_index: int
    segment_type: str
    text: str
    heading: str | None
    page_number: int | None
    routing_tier: str | None
    deterministic_flags: list | None
    routed_themes: list | None


# ---------------------------------------------------------------------------
# Config – read-only responses
# ---------------------------------------------------------------------------

class ExpectedSafeguardOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    safeguard_key: str
    label: str
    maps_to_limit_field: str | None


class LensConfigOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    lens_id: str
    version: str
    theme: str
    prompt_template_id: str
    segment_filter: dict
    include_neighbor_context: bool
    max_segments_per_call: int
    is_active: bool
    owner: str | None
    expected_safeguards: list[ExpectedSafeguardOut]


class CrossThemeRuleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    rule_id: str
    version: str
    name: str
    theme_a: str
    theme_b: str
    trigger_condition: str
    check_prompt: str
    default_materiality_floor: str
    is_active: bool
    owner: str | None


class PlaybookEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    version: str
    theme: str
    risk_pattern: str
    standard_position: str
    alt_wordings: list
    bidder_questions: list
    applicable_when: str
    escalation_note: str | None
    is_active: bool
    owner: str | None


class CertificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    standard: str
    scope: str
    valid_until: str | None
    covers_all_services: bool
    excluded_services: list | None


class StandardPositionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    theme: str
    accepted: str
    not_accepted: str
    escalation_threshold: str


class ServiceProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    service_type: str
    delivery_model: str
    tenant_model: str
    baseline_controls: list


class BaselineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    version: str
    valid_from: str
    is_active: bool
    certifications: list[CertificationOut]
    standard_positions: list[StandardPositionOut]
    service_profiles: list[ServiceProfileOut]
