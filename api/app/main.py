import datetime as dt
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.jobs.all_star_edition_videos import AllStarEditionVideos
from app.jobs.all_star_feed import AllStarFeeds
from app.jobs.calendar_feed import KIND as CALENDARS_KIND
from app.jobs.calendar_feed import CalendarFeeds
from app.jobs.cup_feed import CupFeeds
from app.jobs.cup_matchup_feed import CupMatchupFeeds
from app.jobs.cup_team_marks import CupTeamMarks
from app.jobs.cup_titles import CupTitles
from app.jobs.day_feed import KIND as DAYS_KIND
from app.jobs.day_feed import DayFeeds
from app.jobs.game_detail_feed import GameDetailFeeds
from app.jobs.games import GamesJob
from app.jobs.highlights import HighlightsJob
from app.jobs.highlights_search import HighlightsSearch
from app.jobs.on_demand import FeedCache
from app.jobs.past_game_detail_feed import KIND as PAST_GAMES_KIND
from app.jobs.past_game_detail_feed import PastGameDetailFeeds
from app.jobs.past_player_ids import PastPlayerIds
from app.jobs.player_feed import PlayerFeeds
from app.jobs.player_identities import PlayerIdentities
from app.jobs.playoffs_feed import PlayoffsFeeds
from app.jobs.playoffs_finals_feed import PlayoffsFinalsFeeds
from app.jobs.playoffs_titles import PlayoffsTitles
from app.jobs.presence import Presence
from app.jobs.scheduler import Scheduler
from app.jobs.search_feed import SearchFeeds
from app.jobs.season_all_star_feed import KIND as SEASON_ALL_STAR_KIND
from app.jobs.season_all_star_feed import SeasonAllStarFeeds
from app.jobs.season_cup_feed import KIND as SEASON_CUP_KIND
from app.jobs.season_cup_feed import SeasonCupFeeds
from app.jobs.season_cup_matchup_feed import KIND as SEASON_CUP_MATCHUPS_KIND
from app.jobs.season_cup_matchup_feed import SeasonCupMatchupFeeds
from app.jobs.season_player_feed import KIND as SEASON_PLAYERS_KIND
from app.jobs.season_player_feed import SeasonPlayerFeeds
from app.jobs.season_playoffs_feed import KIND as SEASON_PLAYOFFS_KIND
from app.jobs.season_playoffs_feed import SeasonPlayoffsFeeds
from app.jobs.season_playoffs_feed import stored_player_ids as playoffs_player_ids
from app.jobs.season_playoffs_finals_feed import KIND as SEASON_FINALS_KIND
from app.jobs.season_playoffs_finals_feed import SeasonPlayoffsFinalsFeeds
from app.jobs.season_playoffs_finals_feed import stored_player_ids as finals_player_ids
from app.jobs.season_standings_feed import SeasonStandingsFeeds
from app.jobs.season_team_feed import KIND as SEASON_TEAMS_KIND
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

# The kept kinds deleted when not served in 90 days (ADR 0063).
PRUNED_KINDS = (
    DAYS_KIND,
    PAST_GAMES_KIND,
    SEASON_PLAYERS_KIND,
    SEASON_TEAMS_KIND,
    SEASON_PLAYOFFS_KIND,
    SEASON_FINALS_KIND,
    SEASON_CUP_KIND,
    SEASON_CUP_MATCHUPS_KIND,
    SEASON_ALL_STAR_KIND,
    CALENDARS_KIND,
)


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

        def daily_cleanup(now: dt.datetime) -> None:
            # The player ids of the stored feeds are kept before any is deleted.
            past_ids.save_stored()
            feed_cache.prune_unserved(PRUNED_KINDS, now)

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
        highlights_search = HighlightsSearch(settings, store, client, highlights_job)
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
            daily_cleanup=daily_cleanup,
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
            search=highlights_search,
            attempts_over=highlights_job.attempts_over,
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
        past_ids = PastPlayerIds(
            settings.data_dir,
            store,
            named=(
                (SEASON_PLAYOFFS_KIND, playoffs_player_ids),
                (SEASON_FINALS_KIND, finals_player_ids),
            ),
        )
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
            cup_marks=CupTeamMarks(cup_feeds),
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
            names=team_names,
            past_ids=past_ids,
        )
        SeasonStandingsFeeds(settings, store, client, feed_cache, stars_job, team_names)
        SeasonTeamFeeds(
            settings,
            store,
            client,
            feed_cache,
            stars_job,
            team_names,
        )
        SeasonPlayerFeeds(
            settings,
            store,
            client,
            feed_cache,
            stars_job,
            past_ids,
            team_names,
        )
        season_cups = SeasonCupFeeds(
            settings, store, client, feed_cache, stars_job, team_names
        )
        season_cup_matchups = SeasonCupMatchupFeeds(
            settings, store, client, feed_cache, stars_job, season_cups
        )
        player_identities = PlayerIdentities(settings, store, client)
        season_playoffs = SeasonPlayoffsFeeds(
            settings,
            store,
            client,
            feed_cache,
            stars_job,
            team_names,
            player_identities,
        )
        season_playoffs_finals = SeasonPlayoffsFinalsFeeds(
            settings,
            store,
            client,
            feed_cache,
            stars_job,
            season_playoffs,
        )
        edition_videos = AllStarEditionVideos(store, highlights_search, client.clock)
        AllStarFeeds(
            settings,
            store,
            client,
            feed_cache,
            games_job,
            stars_job,
            edition_videos=edition_videos,
        )
        season_all_star = SeasonAllStarFeeds(
            settings,
            store,
            client,
            feed_cache,
            stars_job,
            edition_videos=edition_videos,
        )
        calendar_feeds = CalendarFeeds(settings, store, client, feed_cache, stars_job)
        DayFeeds(
            settings,
            store,
            client,
            feed_cache,
            games_job,
            team_names,
            on_publish=lambda day_id, feed: past_details.index_day(day_id, feed),
        )
        past_details = PastGameDetailFeeds(
            settings, store, client, feed_cache, search=highlights_search
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
