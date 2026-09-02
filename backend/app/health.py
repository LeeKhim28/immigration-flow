import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database.session import get_db_session

router = APIRouter(tags=["health"])
logger = logging.getLogger(__name__)


@router.get("/health")
def process_health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/database")
def database_health(session: Annotated[Session, Depends(get_db_session)]) -> dict[str, str]:
    try:
        session.execute(select(1))
    except SQLAlchemyError as error:
        logger.warning("database health check failed: %s", type(error).__name__)
        raise HTTPException(status_code=503, detail="database unavailable") from error
    return {"status": "ok"}
