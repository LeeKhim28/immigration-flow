from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.database.enums import (
    ApplicantLocation,
    ApplicationType,
    CaseStage,
    CaseStatus,
    DocumentType,
    InstitutionType,
    SubmissionChannel,
)


class DraftStudentPassCaseRequest(BaseModel):
    case_number: str = Field(min_length=1, max_length=100, pattern=r".*\S.*")
    applicant_profile_id: UUID
    application_type: ApplicationType
    institution_id: UUID
    programme_id: UUID
    institution_type: InstitutionType
    region_code: str = Field(min_length=1, max_length=32, pattern=r".*\S.*")
    applicant_location: ApplicantLocation
    nationality_code: str = Field(min_length=2, max_length=3, pattern=r"^[A-Z]+$")
    passport_expires_at: datetime


class CaseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    case_number: str
    applicant_profile_id: UUID
    status: CaseStatus
    stage: CaseStage


class SubmitCaseRequest(BaseModel):
    channel: SubmissionChannel


class SubmissionResponse(BaseModel):
    id: UUID
    case_id: UUID
    status: CaseStatus
    submitted_at: datetime
    accepted_at: datetime | None


class RecordDocumentMetadataRequest(BaseModel):
    document_type: DocumentType
    storage_reference: str = Field(min_length=1, pattern=r"^metadata-only://")
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    mime_type: str = Field(min_length=1, max_length=255)
    size_bytes: int = Field(ge=0)
    captured_at: datetime


class DocumentMetadataResponse(BaseModel):
    id: UUID
    case_id: UUID
    document_type: DocumentType
    version_number: int
    storage_reference: str
