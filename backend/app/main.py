"""FastAPI entry point."""

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__, sessions
from app.api import upload
from app.config import get_settings

logger = logging.getLogger("churnlens")
CLEANUP_INTERVAL_S = 10 * 60


async def _cleanup_loop() -> None:
    while True:
        try:
            deleted = await asyncio.to_thread(sessions.cleanup_expired)
            if deleted:
                logger.info("deleted %d expired sessions", len(deleted))
        except Exception:
            logger.exception("session cleanup failed")
        await asyncio.sleep(CLEANUP_INTERVAL_S)


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    task = asyncio.create_task(_cleanup_loop())
    try:
        yield
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="ChurnLens API", version=__version__, lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.FRONTEND_ORIGIN],
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    app.include_router(upload.router)
    return app


app = create_app()
