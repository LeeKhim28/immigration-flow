from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Integer, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.database.enums import (
    ApplicabilityBasis,
    ApprovalDecision,
    KnowledgeSourceStatus,
    KnowledgeSyncStatus,
    RequirementSupportType,
    RuleSetVersionStatus,
    ServiceType,
)


class KnowledgeSyncRun(Base):
    __tablename__ = "knowledge_sync_run"
    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    git_commit_sha: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[KnowledgeSyncStatus] = mapped_column(Text, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    validation_summary: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    error_summary: Mapped[str | None] = mapped_column(Text)


class KnowledgeSource(Base):
    __tablename__ = "knowledge_source"
    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    source_code: Mapped[str] = mapped_column(Text, nullable=False)
    canonical_url: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    authority: Mapped[str] = mapped_column(Text, nullable=False)
    jurisdiction: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str] = mapped_column(Text, nullable=False)
    topics: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    source_type: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[KnowledgeSourceStatus] = mapped_column(Text, nullable=False)


class SourceRevision(Base):
    __tablename__ = "source_revision"
    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    knowledge_source_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("knowledge_source.id", ondelete="RESTRICT"),
        nullable=False,
    )
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    effective_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    effective_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    normalized_content_hash: Mapped[str] = mapped_column(Text, nullable=False)
    repository_snapshot_reference: Mapped[str] = mapped_column(Text, nullable=False)
    git_commit_sha: Mapped[str] = mapped_column(Text, nullable=False)
    knowledge_sync_run_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("knowledge_sync_run.id", ondelete="RESTRICT"),
        nullable=False,
    )


class Requirement(Base):
    __tablename__ = "requirement"
    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    requirement_code: Mapped[str] = mapped_column(Text, nullable=False)
    service_type: Mapped[ServiceType] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(Text, nullable=False)


class RequirementVersion(Base):
    __tablename__ = "requirement_version"
    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    requirement_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("requirement.id", ondelete="RESTRICT"),
        nullable=False,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    stage: Mapped[str] = mapped_column(Text, nullable=False)
    responsible_actor: Mapped[str] = mapped_column(Text, nullable=False)
    level: Mapped[str] = mapped_column(Text, nullable=False)
    statement: Mapped[str] = mapped_column(Text, nullable=False)
    condition_document: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    machine_handling: Mapped[str] = mapped_column(Text, nullable=False)
    effective_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    effective_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fingerprint: Mapped[str] = mapped_column(Text, nullable=False)
    git_commit_sha: Mapped[str] = mapped_column(Text, nullable=False)
    knowledge_sync_run_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("knowledge_sync_run.id", ondelete="RESTRICT"),
        nullable=False,
    )


class RequirementSource(Base):
    __tablename__ = "requirement_source"
    requirement_version_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("requirement_version.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    source_revision_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("source_revision.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    locator: Mapped[str] = mapped_column(Text, primary_key=True)
    support_type: Mapped[RequirementSupportType] = mapped_column(Text, nullable=False)


class RuleSet(Base):
    __tablename__ = "rule_set"

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    rule_set_code: Mapped[str] = mapped_column(Text, nullable=False)
    service_type: Mapped[ServiceType] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)


class RuleSetVersion(Base):
    __tablename__ = "rule_set_version"

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    rule_set_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("rule_set.id", ondelete="RESTRICT"), nullable=False
    )
    semantic_version: Mapped[str] = mapped_column(Text, nullable=False)
    scope_document: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    outcome_contract: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    default_outcome: Mapped[str] = mapped_column(Text, nullable=False)
    dataset_snapshots: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    effective_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    applicability_basis: Mapped[ApplicabilityBasis] = mapped_column(Text, nullable=False)
    submission_cutoff_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    transition_policy: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    status: Mapped[RuleSetVersionStatus] = mapped_column(Text, nullable=False)
    supersedes_rule_set_version_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("rule_set_version.id", ondelete="RESTRICT")
    )
    knowledge_sync_run_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("knowledge_sync_run.id", ondelete="RESTRICT"),
        nullable=False,
    )
    fingerprint: Mapped[str] = mapped_column(Text, nullable=False)
    git_commit_sha: Mapped[str] = mapped_column(Text, nullable=False)


class RuleDefinition(Base):
    __tablename__ = "rule_definition"

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    rule_code: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)


class RuleVersion(Base):
    __tablename__ = "rule_version"

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    rule_definition_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("rule_definition.id", ondelete="RESTRICT"),
        nullable=False,
    )
    rule_set_version_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("rule_set_version.id", ondelete="RESTRICT"),
        nullable=False,
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=False)
    condition_document: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    outcome: Mapped[str] = mapped_column(Text, nullable=False)
    finding_code: Mapped[str] = mapped_column(Text, nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    task_type: Mapped[str | None] = mapped_column(Text)
    supplemental_source_codes: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    fingerprint: Mapped[str] = mapped_column(Text, nullable=False)
    git_commit_sha: Mapped[str] = mapped_column(Text, nullable=False)
    knowledge_sync_run_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("knowledge_sync_run.id", ondelete="RESTRICT"),
        nullable=False,
    )


class RuleRequirement(Base):
    __tablename__ = "rule_requirement"

    rule_version_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("rule_version.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    requirement_version_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("requirement_version.id", ondelete="RESTRICT"),
        primary_key=True,
    )


class ApprovalEvent(Base):
    __tablename__ = "approval_event"

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    rule_set_version_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("rule_set_version.id", ondelete="RESTRICT"),
        nullable=False,
    )
    decision: Mapped[ApprovalDecision] = mapped_column(Text, nullable=False)
    decided_by_actor_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("actor.id", ondelete="RESTRICT"), nullable=False
    )
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
