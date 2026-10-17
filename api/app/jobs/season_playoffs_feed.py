# api/app/jobs/season_playoffs_feed.py
#
# Playoffs feed of a past season (ADR 0046): the playoffs feed's shape, built by
# the playoffs feed builder from the sources of that season, with the
# scoreboard days resolving the sides by provider id first as the past season
# feeds do (ADR 0043). The names of leaders and award winners come from that
# season's box-score rosters (SeasonRosters, ADR 0053); a failed roster read fails
# the build. A season before 2021 has no play-in, so that window is not read and the play-in
# block is null. Leaders, awards and the champion's record are null only when the
# source answers 404; any other failed read fails the build, because the feed is
# kept for good. A team info that fails only nulls its colors. A past playoffs
# feed is stored only when it builds as complete: a postseason that is not
# complete, or whose rounds cannot be derived, fails the build, logs the reason
# and stores nothing. Game detail is never available. Its league sides are named by
# that season's team object and carry the season code and the historical flag
# (ADR 0054).
#
# SeasonPlayoffsFeeds is the feed kind of the on-demand cache: the id is the
# season's end year, the feed is stored at feeds/season-playoffs/{season}.json
# only when requested. A season is valid from 1994 to the season before the
# current one (past_season_status). The current season is resolved before the
# cache (target) to the current playoffs feed (ADR 0042). A feed is built once
# and kept (rule G): it is never deleted, and rebuilt only when its build version
# is not the current one (ADR 0053).
#
# SEE: docs/api/playoffs.md, docs/adr/0046-season-playoffs-feeds.md,
# api/app/jobs/playoffs_feed.py

import asyncio
import datetime as dt
import functools
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from pydantic import ValidationError

from app.feeds.playoffs import PlayoffsFeed, PlayoffsState
from app.jobs import playoffs_feed
from app.jobs.on_demand import (
    FeedCache,
    FeedKind,
    IdStatus,
    is_current_build,
    with_build_version,
)
from app.jobs.playoffs_feed import (
    CODES,
    FetchAwards,
    FetchLeaders,
    FetchRecord,
    FetchSeasonType,
    PlayoffsBuildError,
    PlayoffsSources,
    build_playoffs_feed,
    finals_winner,
    postseason_days,
)
from app.jobs.season_rosters import SeasonRosters
from app.jobs.season_standings_feed import past_season_status
from app.jobs.stars import StarsJob
from app.jobs.team_feed import FetchInfo, eastern_date
from app.jobs.team_names import TeamNamesFeeds
from app.settings import Settings
from app.sources import (
    division_standings,
    postseason_leaders,
    postseason_scoreboard,
    season_awards,
    season_types,
    team_info,
    team_postseason,
)
from app.sources.game_detail import BoxScoreRosterEntry
from app.sources.http import SourceClient, SourceError
from app.sources.postseason_scoreboard import PostseasonGame
from app.sources.season_types import PLAY_IN, POSTSEASON
from app.sources.team_info import TeamInfo
from app.sources.team_players import RosterEntry
from app.storage.feeds import read_by_id
from app.storage.state import StateStore

logger = logging.getLogger(__name__)

KIND = "season-playoffs"
FIRST_PLAY_IN_SEASON = 2021
NOT_FOUND = 404

FetchSeasonGames = Callable[..., Awaitable[list[PostseasonGame]]]


async def none_on_404[T](read: Awaitable[T]) -> T | None:
    """The result of a read, or none when the source answers 404; any other
    failure is raised."""
    try:
        return await read
    except SourceError as error:
        if error.status_code == NOT_FOUND:
            return None
        raise


class SeasonPlayoffsFeeds:
    def __init__(
        self,
        settings: Settings,
        store: StateStore,
        client: SourceClient,
        cache: FeedCache,
        stars: StarsJob,
        rosters: SeasonRosters,
        names: TeamNamesFeeds,
        *,
        fetch_season_type: FetchSeasonType = season_types.fetch_season_type,
        fetch_postseason_games: FetchSeasonGames = (
            postseason_scoreboard.fetch_postseason_games
        ),
        fetch_division_standings: Any = division_standings.fetch_division_standings,
        fetch_team_info: FetchInfo = team_info.fetch_team_info,
        fetch_postseason_leaders: FetchLeaders = (
            postseason_leaders.fetch_postseason_leaders
        ),
        fetch_season_awards: FetchAwards = season_awards.fetch_season_awards,
        fetch_team_postseason_record: FetchRecord = (
            team_postseason.fetch_team_postseason_record
        ),
    ) -> None:
        self._settings = settings
        self._store = store
        self._client = client
        self._stars = stars
        self._rosters = rosters
        self._names = names
        self._fetch_season_type = fetch_season_type
        self._fetch_postseason_games = fetch_postseason_games
        self._fetch_division_standings = fetch_division_standings
        self._fetch_team_info = fetch_team_info
        self._fetch_postseason_leaders = fetch_postseason_leaders
        self._fetch_season_awards = fetch_season_awards
        self._fetch_team_postseason_record = fetch_team_postseason_record
        cache.register(self.kind())

    def check(self, season: str) -> IdStatus:
        return past_season_status(season, self._stars.current_season())

    def target(self, season: str) -> tuple[str, str]:
        """The (kind, id) a route season maps to: the current season is the
        current playoffs feed."""
        current = self._stars.current_season()
        if current is not None and season == str(current):
            return playoffs_feed.KIND, playoffs_feed.FEED_ID
        return KIND, season

    async def _info(self, code: str) -> TeamInfo | None:
        try:
            return await self._fetch_team_info(self._client, code, self._settings)
        except SourceError:
            return None

    async def _read(self, season: str) -> PlayoffsSources:
        year = int(season)
        client, settings = self._client, self._settings
        play_in_read = (
            self._fetch_season_type(client, year, PLAY_IN, settings)
            if year >= FIRST_PLAY_IN_SEASON
            else _none()
        )
        play_in, postseason, standings, infos, leaders, awards = await asyncio.gather(
            play_in_read,
            self._fetch_season_type(client, year, POSTSEASON, settings),
            self._fetch_division_standings(client, settings, season=year),
            asyncio.gather(*(self._info(code) for code in CODES)),
            none_on_404(self._fetch_postseason_leaders(client, year, settings)),
            none_on_404(self._fetch_season_awards(client, year, settings)),
        )
        read_day = functools.partial(self._fetch_postseason_games, by_id_first=True)
        codes = sorted(standings.teams)
        days, rosters = await asyncio.gather(
            asyncio.gather(
                *(
                    read_day(client, day, settings)
                    for day in postseason_days(play_in, postseason)
                )
            ),
            asyncio.gather(*(self._rosters.roster(code, year) for code in codes)),
        )
        games = [game for day in days for game in day]
        players: dict[str, tuple[str, RosterEntry | BoxScoreRosterEntry]] = {}
        for code, roster in zip(codes, rosters, strict=True):
            for entry in roster:
                known = players.get(entry.player_id)
                # A player traded during the season is on two rosters: the team
                # of his newest game wins (ADR 0053).
                if known is None or _newer(entry, known[1]):
                    players[entry.player_id] = (code, entry)
        winner = finals_winner(games)
        record = (
            None
            if winner is None
            else await none_on_404(
                self._fetch_team_postseason_record(client, winner, year, settings)
            )
        )
        return PlayoffsSources(
            season=year,
            today=eastern_date(client.clock()),
            play_in=play_in,
            postseason=postseason,
            standings=standings,
            colors=dict(zip(CODES, infos, strict=True)),
            games=games,
            players=players,
            leaders=leaders,
            awards=awards,
            champion_record=record,
            past=True,
        )

    async def build(self, season: str) -> PlayoffsFeed:
        try:
            feed = build_playoffs_feed(await self._read(season))
            if feed.state is not PlayoffsState.COMPLETE:
                raise PlayoffsBuildError(f"the {season} postseason is not complete")
        except PlayoffsBuildError as error:
            logger.warning("season playoffs: %s not built: %s", season, error.reason)
            raise
        return with_build_version(await self._names.name_sides(feed, int(season)))

    def stored(self, season: str) -> PlayoffsFeed | None:
        """The stored playoffs feed of a season, or none when missing or invalid."""
        body = read_by_id(self._settings.data_dir, KIND, season)
        if body is None:
            return None
        try:
            return PlayoffsFeed.model_validate_json(body)
        except ValidationError:
            return None

    def is_fresh(
        self, feed: PlayoffsFeed, built_at: dt.datetime, now: dt.datetime
    ) -> bool:
        return is_current_build(feed)

    def keep(self, feed_id: str) -> bool:
        return True

    def kind(self) -> FeedKind[PlayoffsFeed]:
        return FeedKind(
            KIND,
            PlayoffsFeed,
            check=self.check,
            build=self.build,
            is_fresh=self.is_fresh,
            keep=self.keep,
        )


def _newer(
    entry: BoxScoreRosterEntry, known: RosterEntry | BoxScoreRosterEntry
) -> bool:
    last = getattr(known, "last_played", None)
    return entry.last_played is not None and (last is None or entry.last_played > last)


async def _none() -> None:
    return None
