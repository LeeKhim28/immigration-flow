from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.database.enums import (
    ApplicabilityBasis,
    KnowledgeSourceStatus,
    KnowledgeSyncStatus,
    RequirementSupportType,
    RuleSetVersionStatus,
    ServiceType,
)
from app.database.models import (
    KnowledgeSource,
    KnowledgeSyncRun,
    Requirement,
    RequirementSource,
    RequirementVersion,
    RuleDefinition,
    RuleRequirement,
    RuleSet,
    RuleSetVersion,
    RuleVersion,
    SourceRevision,
)
from app.knowledge.fingerprints import (
    canonical_fingerprint,
    requirement_fingerprint,
    rule_fingerprint,
    rule_set_fingerprint,
)
from app.knowledge.repository import KnowledgeBundle, load_knowledge_bundle

SHA_PATTERN = re.compile(r"^[0-9a-f]{40,64}$")


@dataclass(frozen=True, slots=True)
class SyncResult:
    run_id: UUID
    status: KnowledgeSyncStatus
    source_count: int = 0
    requirement_count: int = 0
    rule_count: int = 0
    reused: bool = False


class KnowledgeSynchronizer:
    def __init__(self, session_factory: Callable[[], Session] | None = None) -> None:
        self._session_factory = session_factory

    def sync(self, root: Path, expected_git_sha: str) -> SyncResult:
        if not root.is_dir() or not (root / ".git").exists():
            raise ValueError("repository root is invalid")
        if SHA_PATTERN.fullmatch(expected_git_sha) is None:
            raise ValueError("git SHA must be lowercase hexadecimal with 40 to 64 characters")
        bundle = load_knowledge_bundle(root, expected_git_sha)
        factory = self._session_factory or _default_session_factory
        now = datetime.now(UTC)

        started = factory()
        try:
            started.execute(
                text("SELECT pg_advisory_xact_lock(hashtextextended(:sha, 0))"),
                {"sha": expected_git_sha},
            )
            existing = started.scalar(
                select(KnowledgeSyncRun).where(
                    KnowledgeSyncRun.git_commit_sha == expected_git_sha,
                    KnowledgeSyncRun.status == KnowledgeSyncStatus.SUCCEEDED,
                )
            )
            if existing is not None:
                started.rollback()
                return SyncResult(existing.id, KnowledgeSyncStatus.SUCCEEDED, reused=True)
            run = KnowledgeSyncRun(
                git_commit_sha=expected_git_sha,
                status=KnowledgeSyncStatus.STARTED,
                started_at=now,
            )
            started.add(run)
            started.commit()
            run_id = run.id
        finally:
            started.close()

        session = factory()
        try:
            session.execute(
                text("SELECT pg_advisory_xact_lock(hashtextextended(:sha, 0))"),
                {"sha": expected_git_sha},
            )
            counts = _import_bundle(session, bundle, run_id, now)
            current_run = session.get(KnowledgeSyncRun, run_id)
            if current_run is None:
                raise RuntimeError("sync run disappeared")
            current_run.status = KnowledgeSyncStatus.SUCCEEDED
            current_run.completed_at = now
            current_run.validation_summary = dict(counts)
            session.commit()
            return SyncResult(
                run_id,
                KnowledgeSyncStatus.SUCCEEDED,
                counts["source_count"],
                counts["requirement_count"],
                counts["rule_count"],
            )
        except Exception as error:
            session.rollback()
            failed = factory()
            try:
                failed_run = failed.get(KnowledgeSyncRun, run_id)
                if failed_run is not None:
                    failed_run.status = KnowledgeSyncStatus.FAILED
                    failed_run.completed_at = datetime.now(UTC)
                    failed_run.error_summary = _safe_error(error)
                    failed.commit()
            finally:
                failed.close()
            raise
        finally:
            session.close()


def _default_session_factory() -> Session:
    from app.core.config import get_settings
    from app.database.session import _get_session_factory

    return _get_session_factory(get_settings().database_url)()


def _import_bundle(
    session: Session, bundle: KnowledgeBundle, run_id: UUID, now: datetime
) -> dict[str, int]:
    sources = _records(bundle.registry, "sources")
    requirements = _records(bundle.requirements, "requirements")
    rules = _records(bundle.rule_set, "rules")
    source_rows: dict[str, KnowledgeSource] = {}
    revision_rows: dict[str, SourceRevision] = {}
    for source in sources:
        code = _text(source, "id")
        row = session.scalar(select(KnowledgeSource).where(KnowledgeSource.source_code == code))
        if row is None:
            row = KnowledgeSource(
                source_code=code,
                canonical_url=_text(source, "canonical_url"),
                title=_text(source, "title"),
                authority=_text(source, "authority"),
                jurisdiction=_text(source, "jurisdiction"),
                language=_text(source, "language"),
                topics=_text_list(source.get("topics", [])),
                source_type=_text(source, "source_type"),
                status=KnowledgeSourceStatus.REVIEWED,
            )
            session.add(row)
            session.flush()
        source_rows[code] = row
        content_hash = canonical_fingerprint(source)
        revision = session.scalar(
            select(SourceRevision).where(
                SourceRevision.knowledge_source_id == row.id,
                SourceRevision.normalized_content_hash == content_hash,
            )
        )
        if revision is None:
            revision = SourceRevision(
                knowledge_source_id=row.id,
                retrieved_at=_date(source.get("retrieved_at"), now),
                reviewed_at=_date(source.get("reviewed_at"), now),
                effective_from=_date(source.get("effective_from"), now),
                effective_to=_date(source.get("effective_to"), now),
                normalized_content_hash=content_hash,
                repository_snapshot_reference=f"data/official-sources/registry.yaml#{code}",
                git_commit_sha=bundle.git_commit_sha,
                knowledge_sync_run_id=run_id,
            )
            session.add(revision)
            session.flush()
        revision_rows[code] = revision

    requirement_rows: dict[str, RequirementVersion] = {}
    for record in requirements:
        code = _text(record, "id")
        requirement = session.scalar(
            select(Requirement).where(Requirement.requirement_code == code)
        )
        if requirement is None:
            requirement = Requirement(
                requirement_code=code,
                service_type=ServiceType.STUDENT_PASS,
                category=_text(record, "category"),
            )
            session.add(requirement)
            session.flush()
        provenance = [item for item in _mapping_list(record.get("sources", []))]
        fingerprint = requirement_fingerprint(record, provenance)
        version = session.scalar(
            select(RequirementVersion).where(RequirementVersion.fingerprint == fingerprint)
        )
        if version is None:
            version = RequirementVersion(
                requirement_id=requirement.id,
                version_number=int(
                    float(str(bundle.requirements.get("version", "1.0.0")).split(".")[0])
                ),
                stage=_text(record, "stage"),
                responsible_actor=_text(record, "actor"),
                level=_text(record, "level"),
                statement=_text(record, "statement"),
                condition_document=record.get("condition", "always"),
                machine_handling=_text(record, "machine_handling"),
                fingerprint=fingerprint,
                git_commit_sha=bundle.git_commit_sha,
                knowledge_sync_run_id=run_id,
            )
            session.add(version)
            session.flush()
            for citation in provenance:
                source_code = _text(citation, "source_id")
                session.add(
                    RequirementSource(
                        requirement_version_id=version.id,
                        source_revision_id=revision_rows[source_code].id,
                        locator=_text(citation, "locator"),
                        support_type=RequirementSupportType.PRIMARY,
                    )
                )
            session.flush()
        requirement_rows[code] = version

    release_id = _text(bundle.rule_set, "rule_set_id")
    rule_set = session.scalar(select(RuleSet).where(RuleSet.rule_set_code == release_id))
    if rule_set is None:
        rule_set = RuleSet(
            rule_set_code=release_id, service_type=ServiceType.STUDENT_PASS, name=release_id
        )
        session.add(rule_set)
        session.flush()
    rule_fingerprints: list[str] = []
    release_fingerprint = rule_set_fingerprint(
        bundle.rule_set, [canonical_fingerprint(rule) for rule in rules]
    )
    release = session.scalar(
        select(RuleSetVersion).where(RuleSetVersion.fingerprint == release_fingerprint)
    )
    if release is None:
        effective_at = _date(bundle.rule_set.get("effective_from"), now) or now
        release = RuleSetVersion(
            rule_set_id=rule_set.id,
            semantic_version=_text(bundle.rule_set, "version"),
            scope_document=bundle.rule_set.get("scope", {}),
            outcome_contract=bundle.rule_set.get("outcome_contract", []),
            default_outcome=_text(bundle.rule_set, "default_outcome"),
            dataset_snapshots={"datasets": list(bundle.datasets)},
            published_at=now,
            effective_at=effective_at,
            applicability_basis=ApplicabilityBasis.IMMIGRATION_SUBMISSION_DATE,
            submission_cutoff_at=effective_at,
            transition_policy={"re_evaluate_after_effective": True},
            status=RuleSetVersionStatus.DRAFT,
            knowledge_sync_run_id=run_id,
            fingerprint=release_fingerprint,
            git_commit_sha=bundle.git_commit_sha,
        )
        session.add(release)
        session.flush()
        for rule in rules:
            rule_id = _text(rule, "id")
            definition = session.scalar(
                select(RuleDefinition).where(RuleDefinition.rule_code == rule_id)
            )
            if definition is None:
                definition = RuleDefinition(rule_code=rule_id, name=_text(rule, "description"))
                session.add(definition)
                session.flush()
            req_ids = _text_list(rule.get("requirement_ids", []))
            req_versions = [requirement_rows[item] for item in req_ids]
            fingerprint = rule_fingerprint(rule, [{"id": item.id.hex} for item in req_versions])
            rule_fingerprints.append(fingerprint)
            then = _mapping(rule.get("then", {}))
            rule_version = RuleVersion(
                rule_definition_id=definition.id,
                rule_set_version_id=release.id,
                description=_text(rule, "description"),
                priority=_integer(rule.get("priority", 0)),
                condition_document=_mapping(rule.get("when", {})),
                outcome=_text(then, "outcome"),
                finding_code=_text(then, "code"),
                message=_text(then, "message"),
                task_type=_text(then, "create_task") if then.get("create_task") else None,
                supplemental_source_codes=_text_list(rule.get("source_ids", [])),
                fingerprint=fingerprint,
                git_commit_sha=bundle.git_commit_sha,
                knowledge_sync_run_id=run_id,
            )
            session.add(rule_version)
            session.flush()
            for requirement_version in req_versions:
                session.add(
                    RuleRequirement(
                        rule_version_id=rule_version.id,
                        requirement_version_id=requirement_version.id,
                    )
                )
        session.flush()
    return {
        "source_count": len(sources),
        "requirement_count": len(requirements),
        "rule_count": len(rules),
    }


def _records(document: Mapping[str, object], field: str) -> list[dict[str, object]]:
    value = document.get(field) if isinstance(document, dict) else None
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise ValueError(f"knowledge bundle {field} must be a list")
    return [item for item in value if isinstance(item, dict)]


def _text(record: Mapping[str, object], field: str) -> str:
    value = record.get(field)
    if not isinstance(value, str) or not value:
        raise ValueError(f"knowledge bundle field {field} is required")
    return value


def _mapping(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError("knowledge bundle field must be an object")
    return dict(value)


def _mapping_list(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list) or any(not isinstance(item, Mapping) for item in value):
        raise ValueError("knowledge bundle field must be a list of objects")
    return [dict(item) for item in value if isinstance(item, Mapping)]


def _text_list(value: object) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ValueError("knowledge bundle field must be a list of strings")
    return [item for item in value if isinstance(item, str)]


def _integer(value: object) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError("knowledge bundle field must be an integer")
    return value


def _date(value: object, fallback: datetime) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    if isinstance(value, str):
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    return fallback


def _safe_error(error: Exception) -> str:
    message = str(error).replace("\n", " ")
    return message[:500] or error.__class__.__name__
