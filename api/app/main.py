from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.jobs.game_detail_feed import GameDetailFeeds
from app.jobs.games import GamesJob
from app.jobs.highlights import HighlightsJob
from app.jobs.on_demand import FeedCache
from app.jobs.player_feed import PlayerFeeds
from app.jobs.presence import Presence
from app.jobs.scheduler import Scheduler
from app.jobs.standings_feed import StandingsFeeds
from app.jobs.stars import StarsJob
from app.jobs.team_feed import TeamFeeds
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
        store.migrate()
        client = create_client(store)
        presence = Presence()
        feed_cache = FeedCache(settings.data_dir, store)
        # The stars and highlights jobs read the final games of the games job, built below.
        stars_job = StarsJob(
            settings,
            store,
            client,
            final_games=lambda: games_job.final_games(),
            after_run=lambda: player_feeds.after_stars_run(),
        )
        highlights_job = HighlightsJob(
            settings, store, client, final_games=lambda: games_job.final_games()
        )
        games_job = GamesJob(
            settings,
            store,
            client,
            stars=stars_job.stars_of,
            stars_ready=stars_job.has_every_star,
            highlights=highlights_job.highlights_of,
            highlights_search_url=highlights_job.search_url_of,
            present=presence.present,
            after_run=lambda: detail_feeds.after_games_run(),
        )
        detail_feeds = GameDetailFeeds(
            settings,
            store,
            client,
            feed_cache,
            games_job,
            stars=stars_job.stars_of,
            highlights=highlights_job.highlights_of,
            highlights_search_url=highlights_job.search_url_of,
        )
        team_feeds = TeamFeeds(settings, store, client, feed_cache, games_job)
        StandingsFeeds(settings, store, client, feed_cache, games_job)
        player_feeds = PlayerFeeds(
            settings, store, client, feed_cache, games_job, stars_job, team_feeds
        )
        # The stars job runs in its own task so its fetches never delay the live refresh.
        stars_scheduler = Scheduler([stars_job], store)
        scheduler = Scheduler([games_job, highlights_job], store)
        app.state.scheduler = scheduler
        app.state.stars_scheduler = stars_scheduler
        app.state.presence = presence
        app.state.games_job = games_job
        app.state.feed_cache = feed_cache
        app.state.player_feeds = player_feeds
        try:
            if run_jobs:
                stars_scheduler.start()
                scheduler.start()
            yield
        finally:
            try:
                await scheduler.stop()
            finally:
                try:
                    await stars_scheduler.stop()
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
