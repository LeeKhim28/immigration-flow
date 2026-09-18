from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.api.dependencies import CurrentActor, DatabaseSession
from app.api.schemas import (
    CaseResponse,
    DraftStudentPassCaseRequest,
    SubmissionResponse,
    SubmitCaseRequest,
)
from app.domains.cases.service import (
    CaseWorkflowError,
    DraftStudentPassCaseCommand,
    create_student_pass_draft,
    submit_case_to_immigration,
)

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
