# api/app/jobs/season_player_feed.py
#
# Player feed of a past season (ADR 0043): the player feed's shape for one player
# in one season. The builder is a pure function from the data the adapters
# fetched to the feed; it reads no clock and no source and reuses the
# conversions of the player feed builder. The game log, the last five games and
# the All-Star year are those of the season's game log; the summary, the
# averages and the milestones are the season's rows of the two career stats reads
# (regular season and playoffs), with null ranks (the bio takes no season); the
# season rows are the career's. The age is on February 1 of the end year. The
# injury, the next game and the live block are null, and the season label is set.
# The number, the draft and the awards are null (ADR 0059). The team is the one of
# the season's newest game, named as the stored franchise names name it for that
# season, and null without a stored list or a run holding the season; it is named
# again when served, once the list is stored. The opponents of the game log are
# named from the game log payload with the season code of the stored franchise
# names, and every game of the log has detail available: its date is registered
# so its past game detail can be built (ADR 0053). The season code of each team of
# a season row is set when the feed is served, from the stored franchise names
# (ADR 0055). The build declares a read budget of READ_BUDGET source reads: the
# athlete, the game log and the two career stats (ADR 0059).
#
# SeasonPlayerFeeds is the feed kind of the on-demand cache: the id is
# {season}-{player id}, the feed is stored at feeds/season-players/{id}.json only
# when requested. A season is valid from 1994 to the season before the current
# one (past_season_status). A player is known from a current roster, a stored past
# roster or box score, or a player named by a stored past playoffs or Finals
# feed. An id none of them knows answers 503 until the rosters are all fetched,
# then 404. A feed is built once and kept (rule G): it is deleted with its build
# row when not served in 90 days and rebuilt on its next request (ADR 0063), and
# rebuilt otherwise only when its build version is not the current one (ADR 0053).
#
# SEE: docs/api/player.md, docs/adr/0043-season-feeds-and-franchise-names.md,
# api/app/jobs/player_feed.py

import asyncio
import datetime as dt
import re
from collections.abc import Awaitable, Callable, Mapping
from typing import Any

from pydantic import ValidationError

from app.feeds.games import Team
from app.feeds.player import PastPlayerFeed
from app.jobs.on_demand import (
    FeedCache,
    FeedKind,
    IdStatus,
    is_current_build,
    with_build_version,
)
from app.jobs.past_player_ids import PastPlayerIds
from app.jobs.player_feed import (
    FetchAthlete,
    FetchStats,
    PlayerBuildError,
    _average_row,
    _birthplace,
    _counts,
    all_star_year,
    game_log,
    height,
    percentage,
    season_split,
    weight,
)
from app.jobs.season_standings_feed import past_season_status
from app.jobs.stars import StarsJob
from app.jobs.team_feed import age_on, eastern_date, season_label
from app.jobs.team_names import (
    SeasonIdentity,
    TeamNamesFeeds,
    career_team_codes,
    payload_names,
    season_named,
    with_career_codes,
)
from app.settings import Settings
from app.sources import player_draft, player_gamelog, player_stats
from app.sources.http import ReadBudget, SourceClient, within_budget
from app.sources.player_draft import PlayerAthlete
from app.sources.player_gamelog import GameLogGame, PlayerGameLog
from app.sources.player_stats import PlayerStats, StatLine
from app.sources.teams import TEAM_CODES, TEAM_IDS
from app.storage.state import StateStore

KIND = "season-players"
READ_BUDGET = 4
_ID = re.compile(r"([0-9]{4})-([A-Za-z0-9]+)")

FetchSeasonGameLog = Callable[..., Awaitable[PlayerGameLog]]


def _season_line(stats: PlayerStats, label: str) -> StatLine | None:
    return next((line for line in stats.per_game if line.season == label), None)


def _summary(line: StatLine | None, label: str) -> dict[str, Any] | None:
    if line is None:
        return None
    return {
        "season": label,
        "points": {"value": round(line.points, 1), "rank": None},
        "rebounds": {"value": round(line.rebounds, 1), "rank": None},
        "assists": {"value": round(line.assists, 1), "rank": None},
        "field_goal_pct": {"value": percentage(line.field_goal_pct), "rank": None},
    }


def _average(line: StatLine | None, *, with_season: bool) -> dict[str, Any] | None:
    if line is None or not line.games_played:
        return None
    values = _average_row(line)
    return {**values, "season": line.season} if with_season else values


def _milestones(
    season_stats: PlayerStats, career: PlayerStats, label: str
) -> dict[str, Any] | None:
    line = next((m for m in season_stats.misc if m.season == label), None)
    if line is None or career.career_misc is None:
        return None
    return {
        "season": label,
        "current": _counts(line),
        "career": _counts(career.career_misc),
    }


def newest_team_id(log: PlayerGameLog) -> str | None:
    """The provider team id of the newest game that is neither an All-Star nor a
    preseason game and has a team of the 30."""
    games: list[GameLogGame] = [
        game
        for game in log.games
        if game.opponent is not None and not game.preseason and game.team_id in TEAM_IDS
    ]
    if not games:
        return None
    return max(games, key=lambda game: game.start_time).team_id


def build_season_player_feed(
    player_id: str,
    season: int,
    athlete: PlayerAthlete,
    team: Team | None,
    log: PlayerGameLog,
    career_regular: PlayerStats,
    career_playoffs: PlayerStats,
    opponent_names: Mapping[str, SeasonIdentity] | None = None,
) -> PastPlayerFeed:
    """Build the player feed of a past season, or raise PlayerBuildError."""
    entry = athlete.entry
    if entry.position_name is None:
        raise PlayerBuildError(f"player {player_id} has no position")
    label = season_label(season)
    seasons = {
        "regular": season_split(career_regular),
        "playoffs": season_split(career_playoffs),
    }
    rows = seasons["regular"]["per_game"]
    named = opponent_names or {}
    log = log.model_copy(
        update={
            "games": [
                game
                if game.opponent is None
                else game.model_copy(
                    update={"opponent": season_named(game.opponent, named)}
                )
                for game in log.games
            ]
        }
    )
    log_feed, recent = game_log(log, frozenset(game.game_id for game in log.games))
    try:
        return PastPlayerFeed.model_validate(
            {
                "id": entry.player_id,
                "first_name": entry.first_name,
                "last_name": entry.last_name,
                "number": None,
                "position": entry.position_name,
                "team": team,
                "photo_url": entry.headshot_url,
                "injury": None,
                "profile": {
                    "height": height(entry.height_inches, entry.display_height)
                    if entry.height_inches
                    else None,
                    "weight": weight(entry.weight_lb) if entry.weight_lb else None,
                    "birth_date": entry.birth_date,
                    "age": age_on(entry.birth_date, dt.date(season, 2, 1))
                    if entry.birth_date
                    else None,
                    "birthplace": _birthplace(entry),
                    "college": entry.college,
                    "draft": None,
                    "seasons": len(rows) if rows else None,
                    "debut_season": rows[-1]["season"] if rows else None,
                },
                "summary": _summary(_season_line(career_regular, label), label),
                "next_game": None,
                "live": None,
                "last_games": recent,
                "averages": {
                    "regular": _average(
                        _season_line(career_regular, label), with_season=True
                    ),
                    "playoffs": _average(
                        _season_line(career_playoffs, label), with_season=True
                    ),
                    "career": _average(
                        career_regular.career_per_game, with_season=False
                    ),
                },
                "seasons": seasons,
                "milestones": _milestones(career_regular, career_regular, label),
                "game_log": log_feed,
                "awards": None,
                "all_star_year": all_star_year(log_feed),
                "active": athlete.active,
                "season_label": label,
            }
        )
    except ValidationError as error:
        location = ".".join(str(part) for part in error.errors()[0]["loc"])
        raise PlayerBuildError(
            f"invalid feed: {error.error_count()} errors, first at {location}"
        ) from None


class SeasonPlayerFeeds:
    def __init__(
        self,
        settings: Settings,
        store: StateStore,
        client: SourceClient,
        cache: FeedCache,
        stars: StarsJob,
        past_ids: PastPlayerIds,
        names: TeamNamesFeeds,
        *,
        fetch_player_athlete: FetchAthlete = player_draft.fetch_player_athlete,
        fetch_player_gamelog: FetchSeasonGameLog = player_gamelog.fetch_player_gamelog,
        fetch_player_stats: FetchStats = player_stats.fetch_player_stats,
    ) -> None:
        self._settings = settings
        self._store = store
        self._client = client
        self._stars = stars
        self._past_ids = past_ids
        self._names = names
        self._fetch_player_athlete = fetch_player_athlete
        self._fetch_player_gamelog = fetch_player_gamelog
        self._fetch_player_stats = fetch_player_stats
        cache.register(self.kind())

    def check(self, feed_id: str) -> IdStatus:
        match = _ID.fullmatch(feed_id)
        if match is None:
            return IdStatus.UNKNOWN
        status = past_season_status(match[1], self._stars.current_season())
        if status is not IdStatus.KNOWN:
            return status
        if self._stars.player_team(match[2]) is not None:
            return IdStatus.KNOWN
        if self._past_ids.known_in_season(match[2]):
            return IdStatus.KNOWN
        if not self._stars.rosters_ready():
            return IdStatus.NOT_READY
        return IdStatus.UNKNOWN

    def _team(self, code: str, season: int) -> Team | None:
        """The team of the stored franchise names run that holds the season, or
        none. It reads no source and starts no build."""
        for run in self._names.stored(code) or []:
            if run.from_ <= season and (run.to is None or season <= run.to):
                return Team(
                    code=code.upper(),
                    name=run.name,
                    city=run.location,
                    season_code=run.code,
                )
        return None

    async def build(self, feed_id: str) -> PastPlayerFeed:
        return await within_budget(
            ReadBudget(READ_BUDGET),
            f"season player: {feed_id}",
            lambda: self._build(feed_id),
        )

    async def _build(self, feed_id: str) -> PastPlayerFeed:
        match = _ID.fullmatch(feed_id)
        if match is None:
            raise PlayerBuildError(f"{feed_id} is not a season and a player")
        season, player_id = int(match[1]), match[2]
        client, settings = self._client, self._settings
        athlete, log, career_regular, career_playoffs = await asyncio.gather(
            self._fetch_player_athlete(client, player_id, settings),
            self._fetch_player_gamelog(client, player_id, settings, season=season),
            self._fetch_player_stats(client, player_id, settings, playoffs=False),
            self._fetch_player_stats(client, player_id, settings, playoffs=True),
        )
        self._store.set_past_game_dates(
            {game.game_id: eastern_date(game.start_time) for game in log.games},
            at=client.clock(),
        )
        runs = {
            code: found for code in log.teams if (found := self._names.stored(code))
        }
        team_id = newest_team_id(log)
        team = (
            None
            if team_id is None
            else self._team(TEAM_CODES[TEAM_IDS[team_id]], season)
        )
        return with_build_version(
            build_season_player_feed(
                player_id,
                season,
                athlete,
                team,
                log,
                career_regular,
                career_playoffs,
                payload_names(log.teams, runs),
            )
        )

    def is_fresh(
        self, feed: PastPlayerFeed, built_at: dt.datetime, now: dt.datetime
    ) -> bool:
        return is_current_build(feed)

    def serve_with(self, feed_id: str, feed: PastPlayerFeed) -> PastPlayerFeed:
        # A served page keeps the rows of the details it links (ADR 0063).
        if feed.game_log is not None:
            self._store.touch_past_games(
                (
                    entry.game_id
                    for entry in feed.game_log.entries
                    if entry.detail_available
                ),
                at=self._client.clock(),
            )
        coded = with_career_codes(
            feed, self._names.career_runs(career_team_codes(feed))
        )
        return coded if coded.team is not None else self._named_team(coded)

    def _named_team(self, feed: PastPlayerFeed) -> PastPlayerFeed:
        """The feed with the team its season row names, once the stored names
        hold the season (ADR 0059); it reads no source."""
        label = feed.season_label
        if label is None:
            return feed
        season = int(label[:4]) + 1
        rows = [
            row
            for split in (feed.seasons.regular, feed.seasons.playoffs)
            for row in split.per_game
            if row.season == label
        ]
        if not rows:
            return feed
        team = self._team(rows[0].teams[-1], season)
        return feed if team is None else feed.model_copy(update={"team": team})

    def keep(self, feed_id: str) -> bool:
        return True

    def kind(self) -> FeedKind[PastPlayerFeed]:
        return FeedKind(
            KIND,
            PastPlayerFeed,
            check=self.check,
            build=self.build,
            is_fresh=self.is_fresh,
            keep=self.keep,
            serve_with=self.serve_with,
        )
