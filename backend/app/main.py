from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.config import get_settings
from app.logging import configure_logging, get_logger
from app.routers import health, jobs, matching, outreach, shortlist, stream


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(env=settings.env, level=settings.log_level)
    log = get_logger()
    log.info("startup", env=settings.env, version=__version__)
    yield
    log.info("shutdown")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Recruiter Agent",
        version=__version__,
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(jobs.router)
    app.include_router(matching.router)
    app.include_router(outreach.router)
    app.include_router(stream.router)
    app.include_router(shortlist.router)
    return app


app = create_app()
