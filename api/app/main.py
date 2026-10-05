from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.jobs.games import GamesJob
from app.jobs.scheduler import Scheduler
from app.log import configure_logging
from app.routers import feeds, health
from app.settings import Settings, get_settings
from app.sources.http import create_client
from app.storage.state import StateStore


def create_app(settings: Settings | None = None, *, run_jobs: bool = True) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        configure_logging()
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        store = StateStore(settings.data_dir)
        store.create_tables()
        client = create_client()
        scheduler = Scheduler([GamesJob(settings, store, client)], store)
        app.state.scheduler = scheduler
        try:
            if run_jobs:
                scheduler.start()
            yield
        finally:
            await scheduler.stop()
            await client.aclose()

    app = FastAPI(lifespan=lifespan)
    app.state.settings = settings
    app.add_middleware(
        CORSMiddleware, allow_origins=settings.cors_origins, allow_methods=["GET"]
    )
    app.include_router(health.router)
    app.include_router(feeds.router)
    return app


app = create_app()
