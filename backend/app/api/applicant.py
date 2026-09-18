from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.api.dependencies import CurrentActor, DatabaseSession
from app.api.schemas import (
    CaseChecklistResponse,
    CaseResponse,
    ChecklistRequirementResponse,
    DocumentMetadataResponse,
    DraftStudentPassCaseRequest,
    RecordDocumentMetadataRequest,
    SubmissionResponse,
    SubmitCaseRequest,
)
from app.domains.cases.service import (
    CaseWorkflowError,
    DraftStudentPassCaseCommand,
    create_student_pass_draft,
    get_case_checklist,
    submit_case_to_immigration,
)
from app.domains.documents.service import DocumentMetadataCommand, record_document_metadata

router = APIRouter(prefix="/api/v1/applicant", tags=["applicant"])


@router.post("/cases", response_model=CaseResponse, status_code=status.HTTP_201_CREATED)
def create_case(
    request: DraftStudentPassCaseRequest,
    session: DatabaseSession,
    actor: CurrentActor,
) -> CaseResponse:
    try:
        case = create_student_pass_draft(
            session,
            actor,
            DraftStudentPassCaseCommand(**request.model_dump()),
        )
    except CaseWorkflowError as error:
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error
    return CaseResponse.model_validate(case)


@router.post(
    "/cases/{case_id}/submit",
    response_model=SubmissionResponse,
    status_code=status.HTTP_201_CREATED,
)
def submit_case(
    case_id: UUID,
    request: SubmitCaseRequest,
    session: DatabaseSession,
    actor: CurrentActor,
) -> SubmissionResponse:
    try:
        case, submission = submit_case_to_immigration(
            session,
            actor,
            case_id,
            request.channel,
        )
    except CaseWorkflowError as error:
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error
    return SubmissionResponse(
        id=submission.id,
        case_id=case.id,
        status=case.status,
        submitted_at=submission.submitted_at,
        accepted_at=submission.accepted_at,
    )


@router.post(
    "/cases/{case_id}/documents",
    response_model=DocumentMetadataResponse,
    status_code=status.HTTP_201_CREATED,
)
def record_document(
    case_id: UUID,
    request: RecordDocumentMetadataRequest,
    session: DatabaseSession,
    actor: CurrentActor,
) -> DocumentMetadataResponse:
    try:
        document, version = record_document_metadata(
            session,
            actor,
            case_id,
            DocumentMetadataCommand(**request.model_dump()),
        )
    except CaseWorkflowError as error:
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error
    return DocumentMetadataResponse(
        id=version.id,
        case_id=document.case_id,
        document_type=document.document_type,
        version_number=version.version_number,
        storage_reference=version.storage_reference,
    )


@router.get("/cases/{case_id}/checklist", response_model=CaseChecklistResponse)
def get_checklist(
    case_id: UUID,
    session: DatabaseSession,
    actor: CurrentActor,
) -> CaseChecklistResponse:
    try:
        checklist = get_case_checklist(session, actor, case_id)
    except CaseWorkflowError as error:
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error
    return CaseChecklistResponse(
        rule_set_version=checklist.rule_set_version,
        requirements=[
            ChecklistRequirementResponse(
                requirement_code=item.requirement_code,
                statement=item.statement,
                machine_handling=item.machine_handling,
                status=item.status,
            )
            for item in checklist.requirements
        ],
    )
