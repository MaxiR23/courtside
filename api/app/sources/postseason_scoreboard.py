# api/app/sources/postseason_scoreboard.py
#
# Postseason view of the scoreboard (ADR 0032).
#
# Reads the same day as app.sources.scoreboard, from the same URL with the same
# freshness, so both share one cached response. It adds what the playoffs feed
# needs and a game of the games feed does not carry: the season type, the
# competition type, the first note, the period of a game in play or final and
# the series object (summary, completion, total games and wins per team). The
# side fields are mapped by the scoreboard adapter. With by_id_first, a past
# season's sides resolve by provider id first (ADR 0046). Its results never
# reach a core feed, and removing the playoffs section removes this module.
#
# A series competitor with an unknown team id fails the read for a live or
# final game and is left out of the wins of any other game, because a side
# still undecided can carry a placeholder id.
#
# A past season is also read from the schedule of a team (fetch_postseason_schedule,
# ADR 0058): its games carry the competition type and the series object, and
# the provider sends no line score there, so ScheduleGame does not require one
# (the exception ADR 0051 makes for untimed All-Star games). A schedule game is
# final or scheduled; any other state fails the read.
#
# SEE: docs/api/playoffs.md, docs/adr/0032-playoffs-feed.md, docs/adr/0058-bounded-past-competition-reads.md

import datetime as dt
from typing import Annotated

from pydantic import (
    Field,
    NonNegativeInt,
    PositiveInt,
    ValidationError,
    model_validator,
)
from pydantic.alias_generators import to_camel

from app.feeds.games import (
    REQUIRED_BY_STATUS,
    FeedModel,
    GameStatus,
    NonEmptyStr,
    TeamCode,
    required_fields,
)
from app.settings import Settings
from app.sources import team_schedule
from app.sources.http import SourceClient, SourceError, get_json
from app.sources.scoreboard import (
    DATE_FORMAT,
    FRESH_FOR,
    SOURCE,
    ScoreboardGame,
    _map_event,
    _ProviderCompetition,
    _ProviderEvent,
    _ProviderModel,
    _ProviderScoreboard,
)
from app.sources.season_types import POSTSEASON
from app.sources.teams import TEAM_IDS, team_code_of_id, to_opponent


class _ProviderCompetitionType(_ProviderModel):
    abbreviation: str | None = None


class _ProviderSeriesCompetitor(_ProviderModel):
    id: str
    wins: int


class _ProviderSeries(_ProviderModel):
    summary: str | None = None
    completed: bool = False
    total_competitions: int | None = None
    competitors: list[_ProviderSeriesCompetitor] = Field(default_factory=list)


class _PostseasonCompetition(_ProviderCompetition):
    type: _ProviderCompetitionType | None = None
    series: _ProviderSeries | None = None


class _ProviderSeason(_ProviderModel):
    type: int | None = None


class _PostseasonEvent(_ProviderEvent):
    competitions: list[_PostseasonCompetition]  # type: ignore[assignment]
    season: _ProviderSeason | None = None


class _PostseasonScoreboard(_ProviderScoreboard):
    events: list[_PostseasonEvent]  # type: ignore[assignment]


class SeriesState(FeedModel):
    """The series object of a postseason game. Never reaches a feed."""

    summary: NonEmptyStr | None
    completed: bool
    total_games: PositiveInt | None
    wins: dict[TeamCode, NonNegativeInt]


class ScheduleGame(ScoreboardGame):
    """A postseason game read from a team's schedule, which sends no line score."""

    @model_validator(mode="after")
    def _require_fields_of_status(self) -> ScheduleGame:
        required = required_fields(
            REQUIRED_BY_STATUS, self.status, all_star=self.all_star is not None
        )
        missing = [
            to_camel(name)
            for name in required
            if name != "line_score"
            and name in type(self).model_fields
            and getattr(self, name) is None
        ]
        if missing:
            raise ValueError(f"a {self.status} game requires {', '.join(missing)}")
        return self


class PostseasonGame(FeedModel):
    """A scoreboard game with its postseason fields. Never reaches a feed."""

    # A schedule game is a ScoreboardGame that needs no line score; the union
    # keeps its validator from asking for one.
    game: ScoreboardGame | ScheduleGame
    season_type: int | None
    competition_type: NonEmptyStr | None
    note: NonEmptyStr | None
    period: PositiveInt | None
    series: SeriesState | None


def _series_state(series: _ProviderSeries | None, in_play: bool) -> SeriesState | None:
    if series is None:
        return None
    return SeriesState(
        summary=series.summary or None,
        completed=series.completed,
        total_games=series.total_competitions or None,
        wins={
            team_code_of_id(competitor.id, source=SOURCE): competitor.wins
            for competitor in series.competitors
            if in_play or competitor.id in TEAM_IDS
        },
    )


def _postseason_game(event: _PostseasonEvent, game: ScoreboardGame) -> PostseasonGame:
    competition = event.competitions[0]
    note = next((n.headline for n in competition.notes if n.headline), None)
    in_play = game.status in (GameStatus.LIVE, GameStatus.FINAL)
    try:
        return PostseasonGame(
            game=game,
            season_type=event.season.type if event.season else None,
            competition_type=(
                competition.type.abbreviation or None if competition.type else None
            ),
            note=note,
            period=(event.status.period or None) if in_play else None,
            series=_series_state(competition.series, in_play),
        )
    except ValidationError as error:
        first = error.errors()[0]
        location = ".".join(str(part) for part in first["loc"])
        raise SourceError(
            SOURCE, f"game {event.id} is invalid: {first['type']} at {location}"
        ) from None


async def fetch_postseason_games(
    client: SourceClient, day: dt.date, settings: Settings, *, by_id_first: bool = False
) -> list[PostseasonGame]:
    """Return the games of a US Eastern day with their postseason fields, in
    provider order, or raise SourceError. With by_id_first the sides resolve by
    provider id first (a past season)."""
    if settings.scoreboard_url is None:
        raise SourceError(SOURCE, "scoreboard URL is not configured")
    url = settings.scoreboard_url.format(date=day.strftime(DATE_FORMAT))
    body = await get_json(client, url, source=SOURCE, fresh=FRESH_FOR)
    try:
        scoreboard = _PostseasonScoreboard.model_validate(body)
    except ValidationError as error:
        first = error.errors()[0]
        location = ".".join(str(part) for part in first["loc"])
        raise SourceError(
            SOURCE,
            f"invalid payload: {error.error_count()} errors, first at {location}",
        ) from None
    games: list[PostseasonGame] = []
    for event in scoreboard.events:
        game = _map_event(event, by_id_first=by_id_first)
        if game is not None:
            games.append(_postseason_game(event, game))
    return games


class _ScheduleCompetition(team_schedule._ProviderCompetition):
    type: _ProviderCompetitionType | None = None
    series: _ProviderSeries | None = None


class _ScheduleEvent(team_schedule._ProviderEvent):
    competitions: Annotated[list[_ScheduleCompetition], Field(min_length=1)]  # type: ignore[assignment]


class _ScheduleSchedule(team_schedule._ProviderModel):
    events: list[_ScheduleEvent]


def _schedule_game(event: _ScheduleEvent) -> PostseasonGame | None:
    competition = event.competitions[0]
    sides = {c.home_away: c for c in competition.competitors}
    if set(sides) != {"home", "away"} or len(competition.competitors) != 2:
        raise SourceError(SOURCE, f"game {event.id} needs one home and one away team")
    teams = {
        name: to_opponent(
            side.team.abbreviation,
            side.team.id,
            side.team.name,
            side.team.location,
            source=SOURCE,
            by_id_first=True,
        )
        for name, side in sides.items()
    }
    if teams["away"] is None or teams["home"] is None:
        return None
    status = competition.status.type
    if status.state == "post" and status.completed:
        game_status = GameStatus.FINAL
    elif status.state == "pre":
        game_status = GameStatus.SCHEDULED
    else:
        raise SourceError(SOURCE, f"game {event.id} is neither final nor scheduled")
    final = game_status is GameStatus.FINAL
    away, home = sides["away"], sides["home"]
    data: dict[str, object] = {
        "id": event.id,
        "away": teams["away"],
        "home": teams["home"],
        "status": game_status,
        "start_time": event.date.astimezone(dt.UTC),
        "venue": competition.venue.full_name,
        "broadcast": next(
            (
                b.media.short_name
                for b in competition.broadcasts
                if b.media and b.media.short_name
            ),
            None,
        ),
    }
    if final:
        if away.score is None or home.score is None:
            raise SourceError(SOURCE, f"game {event.id} has no score")
        data["score"] = {"away": int(away.score.value), "home": int(home.score.value)}
    period = status_period = competition.status.period
    try:
        return PostseasonGame(
            game=ScheduleGame.model_validate(data),
            season_type=POSTSEASON,
            competition_type=(
                competition.type.abbreviation or None if competition.type else None
            ),
            note=next((n.headline for n in competition.notes if n.headline), None),
            period=(period or None) if final and status_period > 0 else None,
            series=_series_state(competition.series, in_play=final),
        )
    except ValidationError as error:
        first = error.errors()[0]
        location = ".".join(str(part) for part in first["loc"])
        raise SourceError(
            SOURCE, f"game {event.id} is invalid: {first['type']} at {location}"
        ) from None


async def fetch_postseason_schedule(
    client: SourceClient, team_code: str, season: int, settings: Settings
) -> list[PostseasonGame]:
    """Return one team's postseason games of a past season (its end year), with
    their postseason fields, in provider order, or raise SourceError. The sides
    resolve by provider id first."""
    url = team_schedule.season_schedule_url(team_code, season, settings, playoffs=True)
    body = await get_json(
        client, url, source=team_schedule.SOURCE, fresh=team_schedule.FRESH_FOR
    )
    try:
        schedule = _ScheduleSchedule.model_validate(body)
    except ValidationError as error:
        first = error.errors()[0]
        location = ".".join(str(part) for part in first["loc"])
        raise SourceError(
            team_schedule.SOURCE,
            f"invalid payload: {error.error_count()} errors, first at {location}",
        ) from None
    games = (_schedule_game(event) for event in schedule.events)
    return [game for game in games if game is not None]
