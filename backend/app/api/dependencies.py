from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.database.models import Actor
from app.database.session import get_db_session


def get_current_actor(
    session: Annotated[Session, Depends(get_db_session)],
    x_actor_id: Annotated[str | None, Header(alias="X-Actor-Id")] = None,
) -> Actor:
    if x_actor_id is None:
        raise HTTPException(status_code=401, detail="X-Actor-Id header is required")
    try:
        actor_id = UUID(x_actor_id)
    except ValueError as error:
        raise HTTPException(status_code=401, detail="X-Actor-Id is invalid") from error

    actor = session.get(Actor, actor_id)
    if actor is None:
        raise HTTPException(status_code=401, detail="actor is unknown")
    return actor


CurrentActor = Annotated[Actor, Depends(get_current_actor)]
DatabaseSession = Annotated[Session, Depends(get_db_session)]
