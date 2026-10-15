# api/app/sources/scoreboard.py
#
# Scoreboard adapter: fetches the games of one US Eastern day from the
# provider and maps them to contract types. The provider URL comes from
# Settings. Provider data never leaves this module.
#
# A team outside the 30 is a guest side with the provider's code when it sends
# one. A side with neither a code nor a name is not a team: its game is skipped
# (ADR 0026). A game whose note names a Cup round carries the Cup mark. A play-in
# or playoff game carries the postseason mark (ADR 0035). The postseason fields are
# read leniently: an unreadable or inconsistent value only leaves that game's
# mark null, logged by event id, and never fails the event or its day. An
# All-Star game (regular season type 2, competition type ALLSTAR) carries the
# All-Star mark; its sides are guests without a city. A side is a team when it
# has a code or a name, as for any game, and no All-Star flag is read (ADR
# 0039). An All-Star event that cannot be
# mapped (its note, status, sides or required fields) is skipped with a log line
# by event id: it never fails the day (ADR 0038).
#
# The past-day path, fetch_past_games, reads the same payload as fetch_games but
# resolves a side by its team id first and skips any event that cannot be mapped,
# with a log line by event id, instead of failing the day (ADR 0040).
#
# SEE: docs/api/games.md, docs/adr/0007-backend-runtime-and-data-pipeline.md

import datetime as dt
import logging
import re
from typing import Any

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    PositiveInt,
    ValidationError,
    model_validator,
)
from pydantic.alias_generators import to_camel

from app.feeds.games import (
    REQUIRED_BY_STATUS,
    FeedModel,
    GameAllStar,
    GameCup,
    GamePostseason,
    GameStatus,
    GameTeam,
    LineScore,
    NonEmptyStr,
    Score,
    UtcDatetime,
)
from app.settings import Settings
from app.sources.all_star_mark import all_star_mark, is_an_all_star_game
from app.sources.cup import cup_round
from app.sources.http import SourceClient, SourceError, get_json
from app.sources.postseason_mark import postseason_mark
from app.sources.season_types import PLAY_IN, POSTSEASON
from app.sources.teams import TEAM_CODES, TEAM_IDS, to_opponent

logger = logging.getLogger(__name__)

SOURCE = "scoreboard"
FRESH_FOR = dt.timedelta(seconds=30)
DATE_FORMAT = "%Y%m%d"

STATUSES: dict[str, GameStatus] = {
    "STATUS_SCHEDULED": GameStatus.SCHEDULED,
    "STATUS_IN_PROGRESS": GameStatus.LIVE,
    "STATUS_HALFTIME": GameStatus.LIVE,
    "STATUS_END_PERIOD": GameStatus.LIVE,
    "STATUS_FINAL": GameStatus.FINAL,
    "STATUS_DELAYED": GameStatus.DELAYED,
    "STATUS_POSTPONED": GameStatus.POSTPONED,
    "STATUS_CANCELED": GameStatus.CANCELED,
}

_CLOCK = re.compile(r"^\d{1,2}:\d{2}$")
_SECONDS = re.compile(r"^(\d{1,2})(?:\.\d)?$")


class _ProviderModel(BaseModel):
    model_config = ConfigDict(
        extra="ignore", alias_generator=to_camel, validate_by_name=True
    )


class _ProviderTeam(_ProviderModel):
    abbreviation: str | None = None
    id: str | None = None
    name: str | None = None
    location: str | None = None


class _ProviderPeriod(_ProviderModel):
    period: int
    value: float


class _ProviderCompetitor(_ProviderModel):
    home_away: str
    score: str | None = None
    linescores: list[_ProviderPeriod] | None = None
    team: _ProviderTeam


class _ProviderVenue(_ProviderModel):
    full_name: str | None = None


class _ProviderType(_ProviderModel):
    name: str


class _ProviderStatus(_ProviderModel):
    period: int = 0
    display_clock: str | None = None
    type: _ProviderType


class _ProviderNote(_ProviderModel):
    headline: str | None = None


class _ProviderCompetition(_ProviderModel):
    venue: _ProviderVenue | None = None
    broadcast: str | None = None
    notes: list[_ProviderNote] = []
    competitors: list[_ProviderCompetitor]
    # Raw postseason values, read leniently for the mark (ADR 0035).
    type: Any = None
    series: Any = None


class _ProviderEvent(_ProviderModel):
    id: str
    date: AwareDatetime
    status: _ProviderStatus
    competitions: list[_ProviderCompetition]
    season: Any = None


class _MarkCompetitionType(_ProviderModel):
    abbreviation: str | None = None


class _MarkSeriesCompetitor(_ProviderModel):
    id: str | None = None
    wins: int | None = None


class _MarkSeries(_ProviderModel):
    summary: str | None = None
    competitors: list[_MarkSeriesCompetitor] | None = None


class _MarkSeason(_ProviderModel):
    type: int | None = None


class _ProviderScoreboard(_ProviderModel):
    events: list[_ProviderEvent]


class ScoreboardGame(FeedModel):
    """A game as the scoreboard knows it: a `Game` without stars and detail."""

    id: NonEmptyStr
    away: GameTeam
    home: GameTeam
    status: GameStatus
    start_time: UtcDatetime
    venue: NonEmptyStr
    broadcast: NonEmptyStr | None = None
    period: PositiveInt | None = None
    clock: NonEmptyStr | None = None
    line_score: LineScore | None = None
    score: Score | None = None
    cup: GameCup | None = None
    postseason: GamePostseason | None = None
    all_star: GameAllStar | None = None

    @model_validator(mode="after")
    def _require_fields_of_status(self) -> ScoreboardGame:
        required = REQUIRED_BY_STATUS.get(self.status, ())
        missing = [
            to_camel(name)
            for name in required
            if name in type(self).model_fields and getattr(self, name) is None
        ]
        if missing:
            raise ValueError(f"a {self.status} game requires {', '.join(missing)}")
        return self


def _normalize_clock(display_clock: str | None) -> str | None:
    """Return the clock as M:SS: the provider sends 4:12, or seconds under a minute."""
    if display_clock is None:
        return None
    value = display_clock.strip()
    if _CLOCK.match(value):
        return value
    seconds = _SECONDS.match(value)
    if seconds:
        return f"0:{int(seconds.group(1)):02d}"
    return None


def _team(
    competitor: _ProviderCompetitor, *, all_star: bool, by_id_first: bool = False
) -> dict[str, Any] | None:
    team = competitor.team
    # An All-Star team's location repeats its name: it is not a city (ADR 0039).
    location = None if all_star else team.location
    return to_opponent(
        team.abbreviation,
        team.id,
        team.name,
        location,
        source=SOURCE,
        by_id_first=by_id_first,
    )


def _points(competitor: _ProviderCompetitor) -> list[int]:
    periods = sorted(competitor.linescores or [], key=lambda p: p.period)
    return [int(p.value) for p in periods]


def _cup(competition: _ProviderCompetition) -> dict[str, Any] | None:
    """The Cup mark of a game: the round of the first note that is a Cup note."""
    for note in competition.notes:
        stage = cup_round(note.headline)
        if stage is not None:
            return {"stage": stage}
    return None


def _first_note(competition: _ProviderCompetition) -> str | None:
    return next((n.headline for n in competition.notes if n.headline), None)


def _series_wins(series: _MarkSeries | None) -> dict[str, int] | None:
    """Wins by standard code, or None without a series. Raises on a competitor
    that is not a league team with a win count."""
    if series is None or not series.competitors:
        return None
    wins: dict[str, int] = {}
    for competitor in series.competitors:
        if competitor.id is None or competitor.wins is None or competitor.wins < 0:
            raise ValueError("a series competitor needs an id and wins")
        wins[TEAM_CODES[TEAM_IDS[competitor.id]]] = competitor.wins
    return wins


def _postseason(event: _ProviderEvent, game: ScoreboardGame) -> GamePostseason | None:
    """The postseason mark of a game, or None. Never raises: an unreadable or
    inconsistent value is logged by event id and leaves the mark null."""
    mark: GamePostseason | None = None
    season_type: int | None = None
    try:
        competition = event.competitions[0]
        season = (
            None
            if event.season is None
            else _MarkSeason.model_validate(event.season, from_attributes=True)
        )
        season_type = season.type if season else None
        if season_type not in (PLAY_IN, POSTSEASON):
            return None
        kind = (
            None
            if competition.type is None
            else _MarkCompetitionType.model_validate(
                competition.type, from_attributes=True
            )
        )
        series = (
            None
            if competition.series is None
            else _MarkSeries.model_validate(competition.series, from_attributes=True)
        )
        mark = postseason_mark(
            season_type=season_type,
            competition_type=kind.abbreviation if kind else None,
            note=_first_note(competition),
            summary=series.summary if series else None,
            wins=_series_wins(series),
            status=game.status,
            away=game.away.code,
            home=game.home.code,
            score=game.score,
        )
    except ValidationError, ValueError, TypeError, KeyError:
        mark = None
    if mark is None:
        logger.warning(
            "scoreboard: event %s has an unreadable postseason mark", event.id
        )
    return mark


def _is_an_all_star_event(event: _ProviderEvent) -> bool:
    """Whether the event is the All-Star game. Never raises: an unreadable season
    or competition type is not All-Star."""
    try:
        competition = event.competitions[0]
        season = (
            None
            if event.season is None
            else _MarkSeason.model_validate(event.season, from_attributes=True)
        )
        kind = (
            None
            if competition.type is None
            else _MarkCompetitionType.model_validate(
                competition.type, from_attributes=True
            )
        )
        return is_an_all_star_game(
            season.type if season else None, kind.abbreviation if kind else None
        )
    except ValidationError, ValueError, TypeError, IndexError:
        return False


def _read_event(
    event: _ProviderEvent, *, all_star: bool, by_id_first: bool = False
) -> ScoreboardGame | None:
    if not event.competitions:
        raise SourceError(SOURCE, f"game {event.id} has no competition")
    competition = event.competitions[0]
    sides = {c.home_away: c for c in competition.competitors}
    if set(sides) != {"home", "away"} or len(competition.competitors) != 2:
        raise SourceError(SOURCE, f"game {event.id} needs one home and one away team")
    away, home = sides["away"], sides["home"]
    away_team = _team(away, all_star=all_star, by_id_first=by_id_first)
    home_team = _team(home, all_star=all_star, by_id_first=by_id_first)
    if away_team is None or home_team is None:
        return None  # a side that is not a team (ADR 0026, ADR 0039)
    mark = all_star_mark(_first_note(competition)) if all_star else None
    if all_star and mark is None:
        raise SourceError(SOURCE, f"game {event.id} has an unreadable All-Star mark")

    provider_status = event.status.type.name
    if provider_status not in STATUSES:
        raise SourceError(SOURCE, f"unknown game status {provider_status!r}")
    status = STATUSES[provider_status]

    data: dict[str, Any] = {
        "id": event.id,
        "away": away_team,
        "home": home_team,
        "status": status,
        "start_time": event.date.astimezone(dt.UTC),
        "venue": competition.venue.full_name if competition.venue else None,
        "broadcast": competition.broadcast or None,
        "cup": _cup(competition),
        "all_star": mark,
    }
    if status is GameStatus.LIVE:
        data["period"] = event.status.period or None
        data["clock"] = _normalize_clock(event.status.display_clock)
    if status in (GameStatus.LIVE, GameStatus.FINAL):
        away_points, home_points = _points(away), _points(home)
        if away_points and home_points:
            data["line_score"] = {"away": away_points, "home": home_points}
        if away.score is not None and home.score is not None:
            data["score"] = {"away": away.score, "home": home.score}
    try:
        game = ScoreboardGame.model_validate(data)
    except ValidationError as error:
        first = error.errors()[0]
        location = ".".join(str(part) for part in first["loc"])
        raise SourceError(
            SOURCE, f"game {event.id} is invalid: {first['type']} at {location}"
        ) from None
    postseason = _postseason(event, game)
    return game.model_copy(update={"postseason": postseason}) if postseason else game


def _map_event(
    event: _ProviderEvent, *, by_id_first: bool = False
) -> ScoreboardGame | None:
    """Map one event. An All-Star event that cannot be mapped is skipped with a
    log line and never fails the day (ADR 0038); any other event raises."""
    if not _is_an_all_star_event(event):
        return _read_event(event, all_star=False, by_id_first=by_id_first)
    try:
        return _read_event(event, all_star=True, by_id_first=by_id_first)
    except SourceError as error:
        logger.warning(
            "scoreboard: All-Star event %s skipped: %s", event.id, error.reason
        )
        return None


async def _read_scoreboard(
    client: SourceClient, day: dt.date, settings: Settings
) -> _ProviderScoreboard:
    if settings.scoreboard_url is None:
        raise SourceError(SOURCE, "scoreboard URL is not configured")
    url = settings.scoreboard_url.format(date=day.strftime(DATE_FORMAT))
    body = await get_json(client, url, source=SOURCE, fresh=FRESH_FOR)
    try:
        return _ProviderScoreboard.model_validate(body)
    except ValidationError as error:
        first = error.errors()[0]
        location = ".".join(str(part) for part in first["loc"])
        raise SourceError(
            SOURCE,
            f"invalid payload: {error.error_count()} errors, first at {location}",
        ) from None


async def fetch_games(
    client: SourceClient, day: dt.date, settings: Settings
) -> list[ScoreboardGame]:
    """Return the games of a US Eastern day in provider order, or raise SourceError."""
    scoreboard = await _read_scoreboard(client, day, settings)
    games = (_map_event(event) for event in scoreboard.events)
    return [game for game in games if game is not None]


async def fetch_past_games(
    client: SourceClient, day: dt.date, settings: Settings
) -> list[ScoreboardGame]:
    """Return the games of a past US Eastern day in provider order: sides by
    team id first, and an event that cannot be mapped skipped with a log
    line by event id (ADR 0040). Raises SourceError for the payload."""
    scoreboard = await _read_scoreboard(client, day, settings)
    games: list[ScoreboardGame] = []
    for event in scoreboard.events:
        try:
            game = _map_event(event, by_id_first=True)
        except SourceError as error:
            logger.warning(
                "scoreboard: past event %s skipped: %s", event.id, error.reason
            )
            continue
        if game is not None:
            games.append(game)
    return games
