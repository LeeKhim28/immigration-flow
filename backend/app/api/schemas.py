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


class RequirementSourceResponse(BaseModel):
    title: str
    canonical_url: str
    locator: str
    reviewed_at: datetime | None


class ChecklistRequirementResponse(BaseModel):
    requirement_code: str
    statement: str
    machine_handling: str
    status: str
    sources: list[RequirementSourceResponse]


class CaseChecklistResponse(BaseModel):
    rule_set_version: str
    requirements: list[ChecklistRequirementResponse]


class NamedReferenceResponse(BaseModel):
    id: UUID
    name: str
    code: str


class ReadinessSummaryResponse(BaseModel):
    outcome: str
    finding_count: int


class OfficerQueueItemResponse(BaseModel):
    id: UUID
    case_number: str
    status: CaseStatus
    stage: CaseStage
    submitted_at: datetime
    institution: NamedReferenceResponse
    readiness: ReadinessSummaryResponse


class CaseDetailResponse(BaseModel):
    id: UUID
    case_number: str
    applicant_profile_id: UUID
    status: CaseStatus
    stage: CaseStage
    synthetic: bool
    institution: NamedReferenceResponse
    programme: NamedReferenceResponse
    nationality_code: str
    passport_expires_at: datetime
    rule_set_version: str | None


class TimelineEntryResponse(BaseModel):
    id: UUID
    event_type: str
    occurred_at: datetime


class CaseTimelineResponse(BaseModel):
    events: list[TimelineEntryResponse]


class EvaluationFindingResponse(BaseModel):
    id: UUID
    outcome: str
    code: str
    message: str


class EvaluationResponse(BaseModel):
    id: UUID
    outcome: str
    trigger: str
    evaluated_at: datetime
    supersedes_evaluation_id: UUID | None
    rule_set_version: str
    findings: list[EvaluationFindingResponse]


class CaseEvaluationHistoryResponse(BaseModel):
    evaluations: list[EvaluationResponse]
