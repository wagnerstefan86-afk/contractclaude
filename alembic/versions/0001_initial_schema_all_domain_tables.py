"""initial schema - all domain tables

Revision ID: 0001
Revises:
Create Date: 2026-04-04 17:15:07.130188

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0001'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- Independent tables (no FKs) ---

    op.create_table(
        'contract_packages',
        sa.Column('name', sa.String(300), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        'cross_theme_rules',
        sa.Column('rule_id', sa.String(50), nullable=False, unique=True),
        sa.Column('version', sa.String(20), nullable=False),
        sa.Column('name', sa.String(300), nullable=False),
        sa.Column('theme_a', sa.String(40), nullable=False),
        sa.Column('theme_b', sa.String(40), nullable=False),
        sa.Column('trigger_condition', sa.Text(), nullable=False),
        sa.Column('check_prompt', sa.Text(), nullable=False),
        sa.Column('default_materiality_floor', sa.String(10), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('owner', sa.String(200), nullable=True),
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        'lens_configs',
        sa.Column('lens_id', sa.String(50), nullable=False, unique=True),
        sa.Column('version', sa.String(20), nullable=False),
        sa.Column('theme', sa.String(40), nullable=False),
        sa.Column('prompt_template_id', sa.String(100), nullable=False),
        sa.Column('segment_filter', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('include_neighbor_context', sa.Boolean(), nullable=False),
        sa.Column('max_segments_per_call', sa.Integer(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('owner', sa.String(200), nullable=True),
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        'playbook_entries',
        sa.Column('version', sa.String(20), nullable=False),
        sa.Column('theme', sa.String(40), nullable=False),
        sa.Column('risk_pattern', sa.Text(), nullable=False),
        sa.Column('standard_position', sa.Text(), nullable=False),
        sa.Column('alt_wordings', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('bidder_questions', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('applicable_when', sa.Text(), nullable=False),
        sa.Column('escalation_note', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('owner', sa.String(200), nullable=True),
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_playbook_entries_theme', 'playbook_entries', ['theme'])

    op.create_table(
        'provider_baselines',
        sa.Column('version', sa.String(20), nullable=False),
        sa.Column('valid_from', sa.String(10), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # --- Tables with FK to contract_packages ---

    op.create_table(
        'analysis_runs',
        sa.Column('package_id', sa.String(36), sa.ForeignKey('contract_packages.id'), nullable=False),
        sa.Column('status', sa.String(10), nullable=False),
        sa.Column('config_snapshot', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_analysis_runs_package_id', 'analysis_runs', ['package_id'])

    op.create_table(
        'documents',
        sa.Column('package_id', sa.String(36), sa.ForeignKey('contract_packages.id'), nullable=False),
        sa.Column('filename', sa.String(500), nullable=False),
        sa.Column('doc_type', sa.String(50), nullable=True),
        sa.Column('language', sa.String(10), nullable=True),
        sa.Column('page_count', sa.Integer(), nullable=True),
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_documents_package_id', 'documents', ['package_id'])

    # --- Tables with FK to provider_baselines ---

    op.create_table(
        'baseline_certifications',
        sa.Column('baseline_id', sa.String(36), sa.ForeignKey('provider_baselines.id'), nullable=False),
        sa.Column('standard', sa.String(100), nullable=False),
        sa.Column('scope', sa.Text(), nullable=False),
        sa.Column('valid_until', sa.String(10), nullable=True),
        sa.Column('covers_all_services', sa.Boolean(), nullable=False),
        sa.Column('excluded_services', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_baseline_certifications_baseline_id', 'baseline_certifications', ['baseline_id'])

    op.create_table(
        'baseline_service_profiles',
        sa.Column('baseline_id', sa.String(36), sa.ForeignKey('provider_baselines.id'), nullable=False),
        sa.Column('service_type', sa.String(30), nullable=False),
        sa.Column('delivery_model', sa.String(20), nullable=False),
        sa.Column('tenant_model', sa.String(20), nullable=False),
        sa.Column('baseline_controls', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_baseline_service_profiles_baseline_id', 'baseline_service_profiles', ['baseline_id'])

    op.create_table(
        'baseline_standard_positions',
        sa.Column('baseline_id', sa.String(36), sa.ForeignKey('provider_baselines.id'), nullable=False),
        sa.Column('theme', sa.String(40), nullable=False),
        sa.Column('accepted', sa.Text(), nullable=False),
        sa.Column('not_accepted', sa.Text(), nullable=False),
        sa.Column('escalation_threshold', sa.Text(), nullable=False),
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_baseline_standard_positions_baseline_id', 'baseline_standard_positions', ['baseline_id'])
    op.create_index('ix_baseline_standard_positions_theme', 'baseline_standard_positions', ['theme'])

    # --- Tables with FK to lens_configs ---

    op.create_table(
        'expected_safeguards',
        sa.Column('lens_config_id', sa.String(36), sa.ForeignKey('lens_configs.id'), nullable=False),
        sa.Column('safeguard_key', sa.String(100), nullable=False),
        sa.Column('label', sa.String(300), nullable=False),
        sa.Column('maps_to_limit_field', sa.String(100), nullable=True),
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_expected_safeguards_lens_config_id', 'expected_safeguards', ['lens_config_id'])

    # --- Tables with FK to documents ---

    op.create_table(
        'document_precedence_rules',
        sa.Column('package_id', sa.String(36), sa.ForeignKey('contract_packages.id'), nullable=False),
        sa.Column('higher_doc_id', sa.String(36), sa.ForeignKey('documents.id'), nullable=False),
        sa.Column('lower_doc_id', sa.String(36), sa.ForeignKey('documents.id'), nullable=False),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_document_precedence_rules_package_id', 'document_precedence_rules', ['package_id'])

    op.create_table(
        'segments',
        sa.Column('document_id', sa.String(36), sa.ForeignKey('documents.id'), nullable=False),
        sa.Column('segment_index', sa.Integer(), nullable=False),
        sa.Column('segment_type', sa.String(20), nullable=False),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('heading', sa.String(500), nullable=True),
        sa.Column('page_number', sa.Integer(), nullable=True),
        sa.Column('routing_tier', sa.String(30), nullable=True),
        sa.Column('deterministic_flags', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('routed_themes', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_segments_document_id', 'segments', ['document_id'])

    # --- Tables with FK to analysis_runs ---

    op.create_table(
        'cross_theme_finding_candidates',
        sa.Column('rule_id', sa.String(36), sa.ForeignKey('cross_theme_rules.id'), nullable=False),
        sa.Column('run_id', sa.String(36), sa.ForeignKey('analysis_runs.id'), nullable=False),
        sa.Column('result', sa.String(30), nullable=False),
        sa.Column('rationale', sa.Text(), nullable=True),
        sa.Column('confidence', sa.String(10), nullable=True),
        sa.Column('materiality', sa.String(10), nullable=False),
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_cross_theme_finding_candidates_rule_id', 'cross_theme_finding_candidates', ['rule_id'])
    op.create_index('ix_cross_theme_finding_candidates_run_id', 'cross_theme_finding_candidates', ['run_id'])

    op.create_table(
        'run_steps',
        sa.Column('run_id', sa.String(36), sa.ForeignKey('analysis_runs.id'), nullable=False),
        sa.Column('step_type', sa.String(20), nullable=False),
        sa.Column('step_index', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(10), nullable=False),
        sa.Column('input_summary', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('output_summary', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_run_steps_run_id', 'run_steps', ['run_id'])

    # --- Tables with FK to segments ---

    op.create_table(
        'obligations',
        sa.Column('segment_id', sa.String(36), sa.ForeignKey('segments.id'), nullable=False),
        sa.Column('theme', sa.String(40), nullable=False),
        sa.Column('obligation_type', sa.String(10), nullable=False),
        sa.Column('direction', sa.String(20), nullable=False),
        sa.Column('summary', sa.Text(), nullable=False),
        sa.Column('verbatim_quote', sa.Text(), nullable=True),
        sa.Column('materiality', sa.String(10), nullable=False),
        sa.Column('confidence', sa.String(10), nullable=True),
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_obligations_segment_id', 'obligations', ['segment_id'])
    op.create_index('ix_obligations_theme', 'obligations', ['theme'])

    # --- Tables with FK to analysis_runs + playbook_entries ---

    op.create_table(
        'findings',
        sa.Column('run_id', sa.String(36), sa.ForeignKey('analysis_runs.id'), nullable=False),
        sa.Column('theme', sa.String(40), nullable=False),
        sa.Column('title', sa.String(500), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('severity', sa.String(10), nullable=False),
        sa.Column('materiality', sa.String(10), nullable=False),
        sa.Column('status', sa.String(10), nullable=False),
        sa.Column('playbook_entry_id', sa.String(36), sa.ForeignKey('playbook_entries.id'), nullable=True),
        sa.Column('recommendation', sa.Text(), nullable=True),
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_findings_run_id', 'findings', ['run_id'])
    op.create_index('ix_findings_theme', 'findings', ['theme'])

    # --- Tables with FK to obligations ---

    op.create_table(
        'obligation_limits',
        sa.Column('obligation_id', sa.String(36), sa.ForeignKey('obligations.id'), nullable=False, unique=True),
        sa.Column('frequency_limit', sa.Text(), nullable=True),
        sa.Column('time_limit', sa.Text(), nullable=True),
        sa.Column('cost_limit', sa.Text(), nullable=True),
        sa.Column('scope_limit', sa.Text(), nullable=True),
        sa.Column('other_limits', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_obligation_limits_obligation_id', 'obligation_limits', ['obligation_id'])

    op.create_table(
        'obligation_relations',
        sa.Column('obligation_a_id', sa.String(36), sa.ForeignKey('obligations.id'), nullable=False),
        sa.Column('obligation_b_id', sa.String(36), sa.ForeignKey('obligations.id'), nullable=False),
        sa.Column('relation_type', sa.String(20), nullable=False),
        sa.Column('rationale', sa.Text(), nullable=True),
        sa.Column('confidence', sa.String(10), nullable=True),
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_obligation_relations_obligation_a_id', 'obligation_relations', ['obligation_a_id'])
    op.create_index('ix_obligation_relations_obligation_b_id', 'obligation_relations', ['obligation_b_id'])

    # --- Tables with FK to findings ---

    op.create_table(
        'evidences',
        sa.Column('finding_id', sa.String(36), sa.ForeignKey('findings.id'), nullable=False),
        sa.Column('obligation_id', sa.String(36), sa.ForeignKey('obligations.id'), nullable=True),
        sa.Column('segment_id', sa.String(36), sa.ForeignKey('segments.id'), nullable=True),
        sa.Column('quote', sa.Text(), nullable=True),
        sa.Column('rationale', sa.Text(), nullable=True),
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_evidences_finding_id', 'evidences', ['finding_id'])

    op.create_table(
        'missing_safeguards',
        sa.Column('finding_id', sa.String(36), sa.ForeignKey('findings.id'), nullable=False),
        sa.Column('safeguard_key', sa.String(100), nullable=False),
        sa.Column('label', sa.String(300), nullable=False),
        sa.Column('explanation', sa.Text(), nullable=True),
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_missing_safeguards_finding_id', 'missing_safeguards', ['finding_id'])

    op.create_table(
        'review_decisions',
        sa.Column('finding_id', sa.String(36), sa.ForeignKey('findings.id'), nullable=False, unique=True),
        sa.Column('decision', sa.String(10), nullable=False),
        sa.Column('reviewer', sa.String(200), nullable=False),
        sa.Column('comment', sa.Text(), nullable=True),
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_review_decisions_finding_id', 'review_decisions', ['finding_id'])


def downgrade() -> None:
    # Drop in reverse dependency order
    op.drop_table('review_decisions')
    op.drop_table('missing_safeguards')
    op.drop_table('evidences')
    op.drop_table('obligation_relations')
    op.drop_table('obligation_limits')
    op.drop_table('findings')
    op.drop_table('obligations')
    op.drop_table('run_steps')
    op.drop_table('cross_theme_finding_candidates')
    op.drop_table('segments')
    op.drop_table('document_precedence_rules')
    op.drop_table('expected_safeguards')
    op.drop_table('baseline_standard_positions')
    op.drop_table('baseline_service_profiles')
    op.drop_table('baseline_certifications')
    op.drop_table('documents')
    op.drop_table('analysis_runs')
    op.drop_table('provider_baselines')
    op.drop_table('playbook_entries')
    op.drop_table('lens_configs')
    op.drop_table('cross_theme_rules')
    op.drop_table('contract_packages')
