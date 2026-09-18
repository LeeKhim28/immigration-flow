from __future__ import annotations

import asyncio
from collections.abc import Callable

from app.knowledge.activation import ActivationCoordinator


async def run_activation_poll(
    stop: asyncio.Event,
    interval_seconds: int,
    coordinator_factory: Callable[[], ActivationCoordinator],
) -> None:
    if interval_seconds <= 0:
        return
    while not stop.is_set():
        await asyncio.to_thread(_run_once, coordinator_factory)
        try:
            await asyncio.wait_for(stop.wait(), timeout=interval_seconds)
        except TimeoutError:
            continue


def _run_once(factory: Callable[[], ActivationCoordinator]) -> None:
    from datetime import UTC, datetime

    from app.database.session import get_db_session

    session = next(get_db_session())
    try:
        factory().activate_due(session, datetime.now(UTC))
    finally:
        session.close()
