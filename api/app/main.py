from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.jobs.games import GamesJob
from app.jobs.highlights import HighlightsJob
from app.jobs.scheduler import Scheduler
from app.jobs.stars import StarsJob
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
        stars_job = StarsJob(settings, store, client)
        # The highlights job reads the final games of the games job, built below.
        highlights_job = HighlightsJob(
            settings, store, client, final_games=lambda: games_job.final_games()
        )
        games_job = GamesJob(
            settings,
            store,
            client,
            stars=stars_job.stars_of,
            highlights=highlights_job.highlights_of,
            highlights_search_url=highlights_job.search_url_of,
        )
        scheduler = Scheduler([stars_job, games_job, highlights_job], store)
        app.state.scheduler = scheduler
        try:
            if run_jobs:
                scheduler.start()
            yield
        finally:
            try:
                await scheduler.stop()
            finally:
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
