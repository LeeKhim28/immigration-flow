from uuid import UUID

from fastapi import APIRouter, HTTPException

from app.api.dependencies import CurrentActor, DatabaseSession
from app.api.schemas import CaseDetailResponse, CaseEvaluationHistoryResponse, CaseResponse
from app.database.enums import CaseStatus
from app.domains.cases.queries import get_case_evaluations, get_officer_case_detail
from app.domains.cases.service import (
    CaseWorkflowError,
    list_officer_cases,
    start_case_processing,
)

router = APIRouter(prefix="/api/v1/officer", tags=["officer"])


@router.get("/cases/{case_id}")
def get_case_detail(
    case_id: UUID,
    session: DatabaseSession,
    actor: CurrentActor,
) -> dict[str, object]:
    try:
        detail = CaseDetailResponse.model_validate(
            get_officer_case_detail(session, actor, case_id), from_attributes=True
        )
        evaluations = CaseEvaluationHistoryResponse.model_validate(
            {"evaluations": get_case_evaluations(session, actor, case_id, officer=True)},
            from_attributes=True,
        )
    except CaseWorkflowError as error:
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error
    return {**detail.model_dump(mode="json"), **evaluations.model_dump(mode="json")}


@router.get("/cases", response_model=list[CaseResponse])
def list_cases(
    session: DatabaseSession,
    actor: CurrentActor,
    status: CaseStatus = CaseStatus.SUBMITTED,
) -> list[CaseResponse]:
    try:
        cases = list_officer_cases(session, actor, status)
    except CaseWorkflowError as error:
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error
    return [CaseResponse.model_validate(case) for case in cases]


@router.post("/cases/{case_id}/start-processing", response_model=CaseResponse)
def start_processing(
    case_id: UUID,
    session: DatabaseSession,
    actor: CurrentActor,
) -> CaseResponse:
    try:
        case = start_case_processing(session, actor, case_id)
    except CaseWorkflowError as error:
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error
    return CaseResponse.model_validate(case)
