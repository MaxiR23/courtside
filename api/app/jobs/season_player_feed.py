# api/app/jobs/season_player_feed.py
#
# Player feed of a past season (ADR 0043): the player feed's shape for one player
# in one season. The builder is a pure function from the data the adapters
# fetched to the feed; it reads no clock and no source and reuses the
# conversions of the player feed builder. The game log, the last five games and
# the All-Star year are those of the season's game log; the summary is the
# season's per game stats row with null ranks (the bio takes no season); the
# averages and the milestones are the season's rows and the career's; the season
# rows and the awards are the career's. The age is on February 1 of the end
# year. The injury, the next game and the live block are null, and the season
# label is set. The team is the one of the season's newest game, named as it
# was that season, and null for a season with no game log. The number is the
# jersey of that team's box scores of the season (SeasonRosters), else null,
# never the athlete's. The opponents of the game log are named by that season's
# team object, and every game of the log has detail available: its date is
# registered so its past game detail can be built (ADR 0053).
#
# SeasonPlayerFeeds is the feed kind of the on-demand cache: the id is
# {season}-{player id}, the feed is stored at feeds/season-players/{id}.json only
# when requested. A season is valid from 1994 to the season before the current
# one (past_season_status). A player is known from a current roster or from a
# stored past roster or box score (503 until the rosters are all fetched). A feed
# is built once and kept (rule G): it is never deleted, and rebuilt only when its
# build version is not the current one (ADR 0053).
#
# SEE: docs/api/player.md, docs/adr/0043-season-feeds-and-franchise-names.md,
# api/app/jobs/player_feed.py

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
    FetchAwards,
    FetchDraft,
    FetchStats,
    PlayerBuildError,
    _average_row,
    _birthplace,
    _counts,
    all_star_year,
    awards,
    game_log,
    height,
    percentage,
    season_split,
    weight,
)
from app.jobs.season_rosters import SeasonRosters
from app.jobs.season_standings_feed import past_season_status
from app.jobs.stars import StarsJob
from app.jobs.team_feed import (
    FetchDivisionStandings,
    age_on,
    eastern_date,
    season_label,
)
from app.jobs.team_names import TeamNamesFeeds, season_named
from app.settings import Settings
from app.sources import (
    division_standings,
    player_draft,
    player_gamelog,
    player_overview,
    player_stats,
)
from app.sources.division_standings import DivisionStandings
from app.sources.http import SourceClient
from app.sources.player_draft import DraftPick, PlayerAthlete
from app.sources.player_gamelog import GameLogGame, PlayerGameLog
from app.sources.player_overview import ProviderAward
from app.sources.player_stats import PlayerStats, StatLine
from app.sources.teams import TEAM_CODES, TEAM_IDS
from app.storage.state import StateStore

KIND = "season-players"
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
    standings_now: DivisionStandings,
    draft: DraftPick | None,
    provided_awards: list[ProviderAward],
    log: PlayerGameLog,
    career_regular: PlayerStats,
    career_playoffs: PlayerStats,
    season_regular: PlayerStats,
    season_playoffs: PlayerStats,
    jersey: str | None = None,
    opponent_names: Mapping[str, tuple[str, str]] | None = None,
) -> PastPlayerFeed:
    """Build the player feed of a past season, or raise PlayerBuildError."""
    entry = athlete.entry
    if entry.position_name is None:
        raise PlayerBuildError(f"player {player_id} has no position")
    label = season_label(season)
    drafted = None
    if draft is not None:
        drafting = standings_now.teams.get(draft.team_code)
        if drafting is None:
            raise PlayerBuildError(f"team {draft.team_code} has no standing")
        drafted = {
            "year": draft.year,
            "round": draft.round,
            "pick": draft.pick,
            "team_name": drafting.display_name,
        }
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
                "number": jersey,
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
                    "draft": drafted,
                    "seasons": len(rows) if rows else None,
                    "debut_season": rows[-1]["season"] if rows else None,
                },
                "summary": _summary(_season_line(season_regular, label), label),
                "next_game": None,
                "live": None,
                "last_games": recent,
                "averages": {
                    "regular": _average(
                        _season_line(season_regular, label), with_season=True
                    ),
                    "playoffs": _average(
                        _season_line(season_playoffs, label), with_season=True
                    ),
                    "career": _average(
                        career_regular.career_per_game, with_season=False
                    ),
                },
                "seasons": seasons,
                "milestones": _milestones(season_regular, career_regular, label),
                "game_log": log_feed,
                "awards": awards(provided_awards),
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
        rosters: SeasonRosters,
        *,
        fetch_player_athlete: FetchAthlete = player_draft.fetch_player_athlete,
        fetch_division_standings: FetchDivisionStandings = (
            division_standings.fetch_division_standings
        ),
        fetch_player_draft: FetchDraft = player_draft.fetch_player_draft,
        fetch_player_awards: FetchAwards = player_overview.fetch_player_awards,
        fetch_player_gamelog: FetchSeasonGameLog = player_gamelog.fetch_player_gamelog,
        fetch_player_stats: FetchStats = player_stats.fetch_player_stats,
    ) -> None:
        self._settings = settings
        self._store = store
        self._client = client
        self._stars = stars
        self._past_ids = past_ids
        self._names = names
        self._rosters = rosters
        self._fetch_player_athlete = fetch_player_athlete
        self._fetch_division_standings = fetch_division_standings
        self._fetch_player_draft = fetch_player_draft
        self._fetch_player_awards = fetch_player_awards
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
        if not self._stars.rosters_ready():
            return IdStatus.NOT_READY
        return IdStatus.KNOWN if self._past_ids.known(match[2]) else IdStatus.UNKNOWN

    async def _team(self, log: PlayerGameLog, season: int) -> Team | None:
        team_id = newest_team_id(log)
        if team_id is None:
            return None
        code = TEAM_CODES[TEAM_IDS[team_id]]
        found = await self._names.season_identity(code, season)
        if found is None:
            return None
        return Team(code=code, name=found[0], city=found[1])

    async def build(self, feed_id: str) -> PastPlayerFeed:
        match = _ID.fullmatch(feed_id)
        if match is None:
            raise PlayerBuildError(f"{feed_id} is not a season and a player")
        season, player_id = int(match[1]), match[2]
        client, settings = self._client, self._settings
        athlete = await self._fetch_player_athlete(client, player_id, settings)
        standings = await self._fetch_division_standings(client, settings)
        draft = await self._fetch_player_draft(client, player_id, settings)
        provided = await self._fetch_player_awards(client, player_id, settings)
        log = await self._fetch_player_gamelog(
            client, player_id, settings, season=season
        )
        career_regular = await self._fetch_player_stats(
            client, player_id, settings, playoffs=False
        )
        career_playoffs = await self._fetch_player_stats(
            client, player_id, settings, playoffs=True
        )
        season_regular = await self._fetch_player_stats(
            client, player_id, settings, playoffs=False, season=season
        )
        season_playoffs = await self._fetch_player_stats(
            client, player_id, settings, playoffs=True, season=season
        )
        team_id = newest_team_id(log)
        jersey = None
        if team_id is not None:
            roster = await self._rosters.roster(TEAM_CODES[TEAM_IDS[team_id]], season)
            jersey = next((e.jersey for e in roster if e.player_id == player_id), None)
        codes = sorted(
            {
                game.opponent.code
                for game in log.games
                if game.opponent is not None
                and not game.opponent.guest
                and game.opponent.code is not None
            }
        )
        opponent_names = await self._names.season_names(codes, season)
        self._store.set_past_game_dates(
            {game.game_id: eastern_date(game.start_time) for game in log.games}
        )
        return with_build_version(
            build_season_player_feed(
                player_id,
                season,
                athlete,
                await self._team(log, season),
                standings,
                draft,
                provided,
                log,
                career_regular,
                career_playoffs,
                season_regular,
                season_playoffs,
                jersey,
                opponent_names,
            )
        )

    def is_fresh(
        self, feed: PastPlayerFeed, built_at: dt.datetime, now: dt.datetime
    ) -> bool:
        return is_current_build(feed)

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
        )
