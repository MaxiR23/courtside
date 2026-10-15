from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.jobs.all_star_discovery import AllStarDiscovery
from app.jobs.all_star_edition_videos import AllStarEditionVideos
from app.jobs.all_star_feed import AllStarFeeds
from app.jobs.calendar_feed import CalendarFeeds
from app.jobs.cup_backfill_games import cup_backfill_games
from app.jobs.cup_feed import CupFeeds
from app.jobs.cup_matchup_feed import CupMatchupFeeds
from app.jobs.cup_titles import CupTitles
from app.jobs.day_feed import DayFeeds
from app.jobs.game_detail_feed import GameDetailFeeds
from app.jobs.games import GamesJob
from app.jobs.highlights import HighlightsJob
from app.jobs.highlights_backfill import HighlightsBackfill
from app.jobs.on_demand import FeedCache
from app.jobs.past_game_detail_feed import PastGameDetailFeeds
from app.jobs.past_player_ids import PastPlayerIds
from app.jobs.player_feed import PlayerFeeds
from app.jobs.playoffs_backfill_games import playoffs_backfill_games
from app.jobs.playoffs_feed import PlayoffsFeeds
from app.jobs.playoffs_finals_feed import PlayoffsFinalsFeeds
from app.jobs.playoffs_titles import PlayoffsTitles
from app.jobs.presence import Presence
from app.jobs.scheduler import Scheduler
from app.jobs.search_feed import SearchFeeds
from app.jobs.season_all_star_feed import SeasonAllStarFeeds
from app.jobs.season_cup_feed import SeasonCupFeeds
from app.jobs.season_cup_matchup_feed import SeasonCupMatchupFeeds
from app.jobs.season_player_feed import SeasonPlayerFeeds
from app.jobs.season_playoffs_feed import SeasonPlayoffsFeeds
from app.jobs.season_playoffs_finals_feed import SeasonPlayoffsFinalsFeeds
from app.jobs.season_standings_feed import SeasonStandingsFeeds
from app.jobs.season_team_feed import SeasonTeamFeeds
from app.jobs.standings_feed import StandingsFeeds
from app.jobs.stars import StarsJob
from app.jobs.team_feed import TeamFeeds
from app.jobs.team_names import TeamNamesFeeds
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
        StandingsFeeds(settings, store, client, feed_cache, games_job)
        SearchFeeds(settings, store, client, feed_cache, games_job, stars_job)
        cup_feeds = CupFeeds(settings, store, client, feed_cache, games_job, stars_job)
        CupMatchupFeeds(
            settings, store, client, feed_cache, games_job, stars_job, cup_feeds
        )
        playoffs_feeds = PlayoffsFeeds(
            settings, store, client, feed_cache, games_job, stars_job
        )
        past_ids = PastPlayerIds(settings.data_dir)
        team_names = TeamNamesFeeds(settings, store, client, feed_cache, stars_job)
        team_feeds = TeamFeeds(
            settings,
            store,
            client,
            feed_cache,
            games_job,
            names=team_names,
            title_providers=(
                CupTitles(store, cup_feeds),
                PlayoffsTitles(store, playoffs_feeds),
            ),
        )
        PlayoffsFinalsFeeds(
            settings,
            store,
            client,
            feed_cache,
            games_job,
            stars_job,
            playoffs_feeds,
        )
        player_feeds = PlayerFeeds(
            settings,
            store,
            client,
            feed_cache,
            games_job,
            stars_job,
            team_feeds,
            past_ids=past_ids,
        )
        SeasonStandingsFeeds(settings, store, client, feed_cache, stars_job)
        SeasonTeamFeeds(settings, store, client, feed_cache, stars_job, team_names)
        SeasonPlayerFeeds(settings, store, client, feed_cache, stars_job, past_ids)
        season_cups = SeasonCupFeeds(settings, store, client, feed_cache, stars_job)
        season_cup_matchups = SeasonCupMatchupFeeds(
            settings, store, client, feed_cache, stars_job, season_cups
        )
        season_playoffs = SeasonPlayoffsFeeds(
            settings, store, client, feed_cache, stars_job
        )
        season_playoffs_finals = SeasonPlayoffsFinalsFeeds(
            settings, store, client, feed_cache, stars_job, season_playoffs
        )
        all_star_discovery = AllStarDiscovery(settings, store, client, stars_job)
        AllStarFeeds(
            settings,
            store,
            client,
            feed_cache,
            games_job,
            stars_job,
            all_star_discovery,
        )
        season_all_star = SeasonAllStarFeeds(
            settings, store, client, feed_cache, stars_job
        )
        calendar_feeds = CalendarFeeds(settings, store, client, feed_cache, stars_job)
        DayFeeds(settings, store, client, feed_cache)
        PastGameDetailFeeds(settings, store, client, feed_cache)
        highlights_backfill = HighlightsBackfill(
            settings,
            store,
            client,
            highlights_job,
            final_games=lambda: games_job.final_games(),
            game_sources=(
                lambda: cup_backfill_games(settings.data_dir),
                lambda: playoffs_backfill_games(settings.data_dir),
            ),
            editions=AllStarEditionVideos(store),
        )
        # The stars job runs in its own task so its fetches never delay the live refresh,
        # and so does the All-Star discovery; the highlights backfill runs in a third
        # task so its pages never delay the live refresh or the stars.
        stars_scheduler = Scheduler([stars_job, all_star_discovery], store)
        backfill_scheduler = Scheduler([highlights_backfill], store)
        scheduler = Scheduler([games_job, highlights_job], store)
        app.state.scheduler = scheduler
        app.state.stars_scheduler = stars_scheduler
        app.state.backfill_scheduler = backfill_scheduler
        app.state.presence = presence
        app.state.games_job = games_job
        app.state.feed_cache = feed_cache
        app.state.player_feeds = player_feeds
        app.state.calendar_feeds = calendar_feeds
        app.state.season_cup_feeds = season_cups
        app.state.season_cup_matchup_feeds = season_cup_matchups
        app.state.season_playoffs_feeds = season_playoffs
        app.state.season_playoffs_finals_feeds = season_playoffs_finals
        app.state.season_all_star_feeds = season_all_star
        try:
            if run_jobs:
                stars_scheduler.start()
                scheduler.start()
                backfill_scheduler.start()
            yield
        finally:
            try:
                await scheduler.stop()
            finally:
                try:
                    await stars_scheduler.stop()
                finally:
                    try:
                        await backfill_scheduler.stop()
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
