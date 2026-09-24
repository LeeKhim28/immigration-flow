from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.api.dependencies import DatabaseSession
from app.core.config import get_settings
from app.domains.demo.service import DemoSessionService

router = APIRouter(prefix="/api/v1/demo", tags=["demo"])


class DemoSessionResponse(BaseModel):
    applicant_actor_id: UUID
    officer_actor_id: UUID
    case_id: UUID
    case_number: str


def _require_demo_mode() -> None:
    if not get_settings().demo_mode:
        raise HTTPException(status_code=404, detail="not found")


@router.post("/session", response_model=DemoSessionResponse)
def get_or_create_demo_session(session: DatabaseSession) -> DemoSessionResponse:
    _require_demo_mode()
    demo = DemoSessionService.get_or_create(session)
    return DemoSessionResponse(
        applicant_actor_id=demo.applicant_actor_id,
        officer_actor_id=demo.officer_actor_id,
        case_id=demo.case_id,
        case_number=demo.case_number,
    )


@router.delete("/session", response_model=DemoSessionResponse)
def reset_demo_session(session: DatabaseSession) -> DemoSessionResponse:
    _require_demo_mode()
    demo = DemoSessionService.reset(session)
    return DemoSessionResponse(
        applicant_actor_id=demo.applicant_actor_id,
        officer_actor_id=demo.officer_actor_id,
        case_id=demo.case_id,
        case_number=demo.case_number,
    )
