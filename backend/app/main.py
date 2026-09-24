import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.applicant import router as applicant_router
from app.api.demo import router as demo_router
from app.api.officer import router as officer_router
from app.core.config import get_settings
from app.health import router as health_router
from app.knowledge.activation import ActivationCoordinator
from app.knowledge.scheduler import run_activation_poll


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    stop = asyncio.Event()
    settings = get_settings()
    if settings.knowledge_activation_poll_seconds > 0:
        poll_task = asyncio.create_task(
            run_activation_poll(
                stop,
                settings.knowledge_activation_poll_seconds,
                ActivationCoordinator,
            )
        )
    else:
        poll_task = None
    try:
        yield
    finally:
        stop.set()
        if poll_task is not None:
            await poll_task


def create_app() -> FastAPI:
    app = FastAPI(title="ImmigrationFlow API", version="0.1.0", lifespan=lifespan)
    app.include_router(health_router)
    app.include_router(demo_router)
    app.include_router(applicant_router)
    app.include_router(officer_router)
    return app


app = create_app()
