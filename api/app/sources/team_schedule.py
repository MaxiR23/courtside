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
# A season schedule also carries the names its payload gives the league teams
# (SeasonSchedule.teams, ADR 0058).
#
# A side's name is read by side_name, for every team schedule read, current and
# past (the opponents, SeasonSchedule.teams and the past postseason schedule):
# the team's name; when it sends none, its display name without the location
# and one space it starts with (an exact, case-sensitive match), or the whole
# display name when it does not start with them or nothing is left; with
# neither, null. An empty string counts as absent. The short display name is
# not used.
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
    PositiveInt,
    ValidationError,
)
from pydantic.alias_generators import to_camel

from app.feeds.game_detail import GameResult, LastGame
from app.feeds.games import FeedModel, NonEmptyStr, UtcDatetime
from app.feeds.opponent import Opponent
from app.settings import Settings
from app.sources.http import SourceClient, SourceError, get_json, with_query
from app.sources.teams import (
    LEAGUE_CODES,
    TEAM_CODES,
    TEAM_IDS,
    SeasonTeamName,
    side_of,
    to_opponent,
)

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
    display_name: str | None = None
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
    period: int = 0


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
    period: PositiveInt | None = None


class SeasonSchedule(FeedModel):
    """A team's games of one season and season type, in the provider's order.
    Never reaches a feed."""

    games: list[ScheduledGame]
    # Each league team the payload names, by standard code: the first one seen
    # wins (ADR 0058).
    teams: dict[str, SeasonTeamName] = Field(default_factory=dict)


def _provider_code(team_code: str) -> str:
    try:
        return PROVIDER_CODES[team_code]
    except KeyError:
        raise SourceError(SOURCE, f"unknown team code {team_code!r}") from None


def _location(error: ValidationError) -> str:
    return ".".join(str(part) for part in error.errors()[0]["loc"])


def side_name(
    name: str | None, display_name: str | None, location: str | None
) -> str | None:
    """Return the name of a team schedule side: its name, else its display
    name without the location and one space it starts with, else its whole
    display name; null with neither. An empty string counts as absent."""
    if name:
        return name
    if not display_name:
        return None
    prefix = f"{location} " if location else None
    if prefix and display_name.startswith(prefix):
        rest = display_name[len(prefix) :]
        if rest.strip():
            return rest
    return display_name


def _code_of(competitor: _ProviderCompetitor, by_id_first: bool) -> str | None:
    team = competitor.team
    if by_id_first and team.id in TEAM_IDS:
        return TEAM_CODES[TEAM_IDS[team.id]]
    return side_of(team.abbreviation, team.id, source=SOURCE)[0]


def _team_and_opponent(
    team_code: str, event: _ProviderEvent, by_id_first: bool = False
) -> tuple[_ProviderCompetitor, _ProviderCompetitor]:
    competitors = event.competitions[0].competitors
    matches = [c for c in competitors if _code_of(c, by_id_first) == team_code]
    if len(competitors) != 2 or len(matches) != 1:
        raise SourceError(SOURCE, f"team {team_code} is missing from game {event.id}")
    team = matches[0]
    return team, next(c for c in competitors if c is not team)


def _opponent_of(
    competitor: _ProviderCompetitor, by_id_first: bool = False
) -> dict[str, Any] | None:
    team = competitor.team
    return to_opponent(
        team.abbreviation,
        team.id,
        side_name(team.name, team.display_name, team.location),
        team.location,
        source=SOURCE,
        by_id_first=by_id_first,
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
    team_code: str, event: _ProviderEvent, *, playoffs: bool, by_id_first: bool = False
) -> dict[str, Any] | None:
    competition = event.competitions[0]
    team, opponent = _team_and_opponent(team_code, event, by_id_first)
    opponent_team = _opponent_of(opponent, by_id_first)
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
        "period": (
            competition.status.period
            if played and competition.status.period > 0
            else None
        ),
    }


def season_schedule_url(
    team_code: str, season: int, settings: Settings, *, playoffs: bool
) -> str:
    """Return the URL of one team's schedule of a season (its end year) and
    season type, or raise SourceError."""
    if settings.team_schedule_url is None:
        raise SourceError(SOURCE, "team schedule URL is not configured")
    provider_code = _provider_code(team_code)
    return with_query(
        settings.team_schedule_url.format(team=provider_code),
        {"season": season, "seasontype": 3 if playoffs else 2},
    )


def _team_names(
    events: list[_ProviderEvent], by_id_first: bool
) -> dict[str, dict[str, str]]:
    names: dict[str, dict[str, str]] = {}
    for event in events:
        for competitor in event.competitions[0].competitors:
            team = competitor.team
            code = _code_of(competitor, by_id_first)
            name = side_name(team.name, team.display_name, team.location)
            if (
                code in LEAGUE_CODES
                and code not in names
                and team.abbreviation
                and name
                and team.location
            ):
                names[code] = {
                    "abbreviation": team.abbreviation,
                    "name": name,
                    "location": team.location,
                }
    return names


async def fetch_season_schedule(
    client: SourceClient,
    team_code: str,
    season: int,
    settings: Settings,
    *,
    playoffs: bool,
    by_id_first: bool = False,
) -> SeasonSchedule:
    """Return one team's games of a season (its end year) and season type, or
    raise SourceError. With by_id_first, a past season matches the teams by
    provider id before the abbreviation (ADR 0043)."""
    url = season_schedule_url(team_code, season, settings, playoffs=playoffs)
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
            _scheduled_game(
                team_code, event, playoffs=playoffs, by_id_first=by_id_first
            )
            for event in schedule.events
        )
        return SeasonSchedule.model_validate(
            {
                "games": [game for game in games if game is not None],
                "teams": _team_names(schedule.events, by_id_first),
            }
        )
    except ValidationError as error:
        first = error.errors()[0]
        raise SourceError(
            SOURCE,
            f"team schedule is invalid: {first['type']} at {_location(error)}",
        ) from None
