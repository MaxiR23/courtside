# api/app/sources/team_schedule.py
#
# Team schedule adapter: fetches one team's schedule from the provider and
# maps its completed games to the contract's last games, newest first, and to
# the arena of each completed game by game id. It also fetches a team's whole
# schedule of one season and season type (regular season or playoffs), with
# each game's note, broadcast, arena and score, adding the season and the
# season type to the URL's own query. The provider URL comes from Settings.
# Provider data never leaves this module.
#
# An opponent is a league team, a guest with a code, or a guest without one. A
# game whose opponent has neither a code nor a name is skipped. The team
# schedule validates only its completed events; the season schedule validates
# every event (ADR 0026).
#
# SEE: docs/api/game-detail.md, api/app/sources/team_players.py

import datetime as dt
from typing import Annotated, Any, Literal
from zoneinfo import ZoneInfo

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    NonNegativeInt,
    ValidationError,
)
from pydantic.alias_generators import to_camel

from app.feeds.game_detail import GameResult, LastGame
from app.feeds.games import FeedModel, NonEmptyStr, UtcDatetime
from app.feeds.opponent import Opponent
from app.settings import Settings
from app.sources.http import SourceClient, SourceError, get_json, with_query
from app.sources.teams import TEAM_CODES, side_of, to_opponent

SOURCE = "team_schedule"
FRESH_FOR = dt.timedelta(hours=1)
EASTERN = ZoneInfo("America/New_York")
LAST_GAMES = 5
PROVIDER_CODES: dict[str, str] = {
    code: provider for provider, code in TEAM_CODES.items()
}


class _ProviderModel(BaseModel):
    model_config = ConfigDict(
        extra="ignore", alias_generator=to_camel, validate_by_name=True
    )


class _ProviderTeam(_ProviderModel):
    abbreviation: str | None = None
    id: str | None = None
    name: str | None = None
    location: str | None = None


class _ProviderScore(_ProviderModel):
    value: float


class _ProviderCompetitor(_ProviderModel):
    home_away: str
    winner: bool = False
    team: _ProviderTeam
    score: _ProviderScore | None = None


class _ProviderAddress(_ProviderModel):
    city: str | None = None


class _ProviderVenue(_ProviderModel):
    full_name: str
    address: _ProviderAddress | None = None


class _ProviderNote(_ProviderModel):
    headline: str | None = None


class _ProviderMedia(_ProviderModel):
    short_name: str | None = None


class _ProviderBroadcast(_ProviderModel):
    media: _ProviderMedia | None = None


class _ProviderStatusType(_ProviderModel):
    state: str
    completed: bool


class _ProviderStatus(_ProviderModel):
    type: _ProviderStatusType


class _ProviderCompetition(_ProviderModel):
    venue: _ProviderVenue
    status: _ProviderStatus
    competitors: list[_ProviderCompetitor]
    notes: list[_ProviderNote] = []
    broadcasts: list[_ProviderBroadcast] = []


class _ProviderEvent(_ProviderModel):
    id: str
    date: AwareDatetime
    competitions: Annotated[list[_ProviderCompetition], Field(min_length=1)]


class _ProviderSchedule(_ProviderModel):
    events: list[_ProviderEvent]


class _ProviderCompetitionState(_ProviderModel):
    status: _ProviderStatus


class _ProviderEventState(_ProviderModel):
    competitions: Annotated[list[_ProviderCompetitionState], Field(min_length=1)]


class _ProviderRawSchedule(_ProviderModel):
    # Events stay raw: only the completed ones are validated in full.
    events: list[dict[str, Any]]


class TeamSchedule(FeedModel):
    """A team's completed games: the last five for the feed, and the arena of
    each completed game by game id, for the season series. Never reaches the feed."""

    last_games: Annotated[list[LastGame], Field(max_length=LAST_GAMES)]
    arenas: dict[NonEmptyStr, NonEmptyStr]


class ScheduledGame(FeedModel):
    """One game of a season schedule, from the requested team's side. Never
    reaches a feed."""

    game_id: NonEmptyStr
    start_time: UtcDatetime
    opponent: Opponent
    is_home: bool
    state: Literal["pre", "in", "post"]
    completed: bool
    won: bool | None = None
    team_score: NonNegativeInt | None = None
    opponent_score: NonNegativeInt | None = None
    note: NonEmptyStr | None = None
    broadcast: NonEmptyStr | None = None
    arena: NonEmptyStr
    city: NonEmptyStr | None = None
    playoffs: bool


class SeasonSchedule(FeedModel):
    """A team's games of one season and season type, in the provider's order.
    Never reaches a feed."""

    games: list[ScheduledGame]


def _provider_code(team_code: str) -> str:
    try:
        return PROVIDER_CODES[team_code]
    except KeyError:
        raise SourceError(SOURCE, f"unknown team code {team_code!r}") from None


def _location(error: ValidationError) -> str:
    return ".".join(str(part) for part in error.errors()[0]["loc"])


def _team_and_opponent(
    team_code: str, event: _ProviderEvent
) -> tuple[_ProviderCompetitor, _ProviderCompetitor]:
    competitors = event.competitions[0].competitors
    matches = [
        c
        for c in competitors
        if side_of(c.team.abbreviation, c.team.id, source=SOURCE)[0] == team_code
    ]
    if len(competitors) != 2 or len(matches) != 1:
        raise SourceError(SOURCE, f"team {team_code} is missing from game {event.id}")
    team = matches[0]
    return team, next(c for c in competitors if c is not team)


def _opponent_of(competitor: _ProviderCompetitor) -> dict[str, Any] | None:
    team = competitor.team
    return to_opponent(
        team.abbreviation, team.id, team.name, team.location, source=SOURCE
    )


def _last_game(team_code: str, event: _ProviderEvent) -> dict[str, Any] | None:
    team, opponent = _team_and_opponent(team_code, event)
    opponent_team = _opponent_of(opponent)
    if opponent_team is None:
        return None
    if team.score is None or opponent.score is None:
        raise SourceError(SOURCE, f"game {event.id} has no score")
    return {
        "date": event.date.astimezone(EASTERN).date(),
        "opponent": opponent_team,
        "is_home": team.home_away == "home",
        "result": GameResult.WIN if team.winner else GameResult.LOSS,
        "team_score": int(team.score.value),
        "opponent_score": int(opponent.score.value),
    }


async def fetch_team_schedule(
    client: SourceClient, team_code: str, settings: Settings
) -> TeamSchedule:
    """Return the completed games of one team, or raise SourceError."""
    if settings.team_schedule_url is None:
        raise SourceError(SOURCE, "team schedule URL is not configured")
    provider_code = _provider_code(team_code)
    url = settings.team_schedule_url.format(team=provider_code)
    body = await get_json(client, url, source=SOURCE, fresh=FRESH_FOR)
    try:
        raw = _ProviderRawSchedule.model_validate(body)
    except ValidationError as error:
        raise SourceError(
            SOURCE,
            f"invalid payload: {error.error_count()} errors, first at {_location(error)}",
        ) from None

    # Only completed events are used, so only they are validated in full.
    completed: list[_ProviderEvent] = []
    for index, raw_event in enumerate(raw.events):
        try:
            state = _ProviderEventState.model_validate(raw_event)
            status = state.competitions[0].status.type
            if not (status.completed and status.state == "post"):
                continue
            completed.append(_ProviderEvent.model_validate(raw_event))
        except ValidationError as error:
            raise SourceError(
                SOURCE,
                f"invalid payload: {error.error_count()} errors, first at"
                f" events.{index}.{_location(error)}",
            ) from None
    newest_first = sorted(completed, key=lambda event: event.date, reverse=True)
    try:
        last_games: list[dict[str, Any]] = []
        for event in newest_first:
            if len(last_games) == LAST_GAMES:
                break
            game = _last_game(team_code, event)
            if game is not None:
                last_games.append(game)
        return TeamSchedule.model_validate(
            {
                "last_games": last_games,
                "arenas": {
                    event.id: event.competitions[0].venue.full_name
                    for event in completed
                },
            }
        )
    except ValidationError as error:
        first = error.errors()[0]
        raise SourceError(
            SOURCE,
            f"team schedule is invalid: {first['type']} at {_location(error)}",
        ) from None


def _scheduled_game(
    team_code: str, event: _ProviderEvent, *, playoffs: bool
) -> dict[str, Any] | None:
    competition = event.competitions[0]
    team, opponent = _team_and_opponent(team_code, event)
    opponent_team = _opponent_of(opponent)
    if opponent_team is None:
        return None
    played = (
        competition.status.type.completed and competition.status.type.state == "post"
    )
    if played and (team.score is None or opponent.score is None):
        raise SourceError(SOURCE, f"game {event.id} has no score")
    return {
        "game_id": event.id,
        "start_time": event.date,
        "opponent": opponent_team,
        "is_home": team.home_away == "home",
        "state": competition.status.type.state,
        "completed": competition.status.type.completed,
        "won": team.winner if played else None,
        "team_score": int(team.score.value) if played and team.score else None,
        "opponent_score": (
            int(opponent.score.value) if played and opponent.score else None
        ),
        "note": next((n.headline for n in competition.notes if n.headline), None),
        "broadcast": next(
            (
                b.media.short_name
                for b in competition.broadcasts
                if b.media and b.media.short_name
            ),
            None,
        ),
        "arena": competition.venue.full_name,
        "city": (competition.venue.address.city if competition.venue.address else None),
        "playoffs": playoffs,
    }


async def fetch_season_schedule(
    client: SourceClient,
    team_code: str,
    season: int,
    settings: Settings,
    *,
    playoffs: bool,
) -> SeasonSchedule:
    """Return one team's games of a season (its end year) and season type, or
    raise SourceError."""
    if settings.team_schedule_url is None:
        raise SourceError(SOURCE, "team schedule URL is not configured")
    provider_code = _provider_code(team_code)
    url = with_query(
        settings.team_schedule_url.format(team=provider_code),
        {"season": season, "seasontype": 3 if playoffs else 2},
    )
    body = await get_json(client, url, source=SOURCE, fresh=FRESH_FOR)
    try:
        schedule = _ProviderSchedule.model_validate(body)
    except ValidationError as error:
        raise SourceError(
            SOURCE,
            f"invalid payload: {error.error_count()} errors, first at {_location(error)}",
        ) from None
    try:
        games = (
            _scheduled_game(team_code, event, playoffs=playoffs)
            for event in schedule.events
        )
        return SeasonSchedule.model_validate(
            {"games": [game for game in games if game is not None]}
        )
    except ValidationError as error:
        first = error.errors()[0]
        raise SourceError(
            SOURCE,
            f"team schedule is invalid: {first['type']} at {_location(error)}",
        ) from None
