"""FastAPI entry point."""

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app import __version__, sessions
from app.api import chat as chat_api
from app.api import experiments as experiments_api
from app.api import exports as exports_api
from app.api import metrics as metrics_api
from app.api import offers as offers_api
from app.api import predictions as predictions_api
from app.api import results as results_api
from app.api import runs as runs_api
from app.api import telemetry as telemetry_api
from app.api import upload
from app.config import get_settings
from app.graph.builder import build_graph
from app.graph.checkpointer import create_checkpointer
from app.graph.nodes import default_nodes
from app.logging_setup import session_from_path, session_var, setup_logging
from app.ratelimit import RateLimiter
from app.runs import RunManager

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
    setup_logging(settings.LOG_LEVEL)
    app = FastAPI(title="ChurnLens API", version=__version__, lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.FRONTEND_ORIGIN],
        allow_origin_regex=settings.FRONTEND_ORIGIN_REGEX or None,
        allow_methods=["GET", "POST", "PATCH"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def tag_session(request: Request, call_next: Any) -> Any:
        # Every log line written while handling this request carries its session_id.
        token = session_var.set(session_from_path(request.url.path))
        try:
            return await call_next(request)
        finally:
            session_var.reset(token)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    app.state.runs = RunManager(
        lambda: build_graph(nodes=default_nodes(), checkpointer=create_checkpointer())
    )
    app.include_router(upload.router)
    app.include_router(runs_api.router)
    app.include_router(results_api.router)
    app.include_router(predictions_api.router)
    app.include_router(offers_api.router)
    app.include_router(experiments_api.router)
    app.include_router(metrics_api.router)
    app.include_router(telemetry_api.router)
    app.include_router(chat_api.router)
    app.include_router(exports_api.router)
    app.state.chat_limiter = RateLimiter(settings.CHAT_PER_MINUTE)
    app.state.upload_limiter = RateLimiter(settings.UPLOAD_PER_MINUTE)
    app.state.ai_limiter = RateLimiter(settings.AI_PER_MINUTE)
    return app


app = create_app()
