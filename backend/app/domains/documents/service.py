from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.database.enums import ActorType, CaseStatus, DocumentStatus, DocumentType
from app.database.models import (
    Actor,
    ApplicantProfile,
    AuditEvent,
    CaseEvent,
    Document,
    DocumentVersion,
    ImmigrationCase,
)
from app.domains.cases.service import CaseWorkflowError


@dataclass(frozen=True)
class DocumentMetadataCommand:
    document_type: DocumentType
    storage_reference: str
    content_hash: str
    mime_type: str
    size_bytes: int
    captured_at: datetime


def record_document_metadata(
    session: Session,
    actor: Actor,
    case_id: UUID,
    command: DocumentMetadataCommand,
) -> tuple[Document, DocumentVersion]:
    if actor.actor_type is not ActorType.APPLICANT:
        raise CaseWorkflowError(403, "actor is not permitted for this action")
    case = session.get(ImmigrationCase, case_id)
    if case is None:
        raise CaseWorkflowError(404, "case was not found")
    profile = session.get(ApplicantProfile, case.applicant_profile_id)
    if profile is None or profile.actor_id != actor.id:
        raise CaseWorkflowError(403, "actor does not own the case")
    if case.status is not CaseStatus.DRAFT:
        raise CaseWorkflowError(409, "documents can only be recorded for a draft case")

    document = Document(
        case_id=case.id,
        document_type=command.document_type,
        owner_actor_id=actor.id,
        status=DocumentStatus.ACTIVE,
    )
    session.add(document)
    session.flush()
    version = DocumentVersion(
        document_id=document.id,
        version_number=1,
        storage_reference=command.storage_reference,
        content_hash=command.content_hash,
        mime_type=command.mime_type,
        size_bytes=command.size_bytes,
        captured_at=command.captured_at,
        created_by_actor_id=actor.id,
    )
    session.add(version)
    session.flush()
    occurred_at = datetime.now(UTC)
    session.add_all(
        [
            CaseEvent(
                case_id=case.id,
                event_type="DOCUMENT_METADATA_RECORDED",
                event_payload={
                    "document_type": command.document_type.value,
                    "version_number": 1,
                },
                occurred_at=occurred_at,
                actor_id=actor.id,
            ),
            AuditEvent(
                case_id=case.id,
                actor_id=actor.id,
                action="DOCUMENT_METADATA_RECORDED",
                entity_type="DOCUMENT_VERSION",
                entity_id=version.id,
                after_summary={
                    "document_type": command.document_type.value,
                    "version_number": 1,
                },
                occurred_at=occurred_at,
            ),
        ]
    )
    session.commit()
    session.refresh(document)
    session.refresh(version)
    return document, version
