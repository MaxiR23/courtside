# api/app/sources/postseason_scoreboard.py
#
# Postseason view of the scoreboard (ADR 0032).
#
# Reads the same day as app.sources.scoreboard, from the same URL with the same
# freshness, so both share one cached response. It adds what the playoffs feed
# needs and a game of the games feed does not carry: the season type, the
# competition type, the first note, the period of a game in play or final and
# the series object (summary, completion, total games and wins per team). The
# side fields are mapped by the scoreboard adapter. Its results never reach a
# core feed, and removing the playoffs section removes this module.
#
# A series competitor with an unknown team id fails the read for a live or
# final game and is left out of the wins of any other game, because a side
# still undecided can carry a placeholder id.
#
# SEE: docs/api/playoffs.md, docs/adr/0032-playoffs-feed.md

import datetime as dt

from pydantic import Field, NonNegativeInt, PositiveInt, ValidationError

from app.feeds.games import FeedModel, GameStatus, NonEmptyStr, TeamCode
from app.settings import Settings
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
from app.sources.teams import TEAM_IDS, team_code_of_id


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


class PostseasonGame(FeedModel):
    """A scoreboard game with its postseason fields. Never reaches a feed."""

    game: ScoreboardGame
    season_type: int | None
    competition_type: NonEmptyStr | None
    note: NonEmptyStr | None
    period: PositiveInt | None
    series: SeriesState | None


def _series(competition: _PostseasonCompetition, in_play: bool) -> SeriesState | None:
    series = competition.series
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
            series=_series(competition, in_play),
        )
    except ValidationError as error:
        first = error.errors()[0]
        location = ".".join(str(part) for part in first["loc"])
        raise SourceError(
            SOURCE, f"game {event.id} is invalid: {first['type']} at {location}"
        ) from None


async def fetch_postseason_games(
    client: SourceClient, day: dt.date, settings: Settings
) -> list[PostseasonGame]:
    """Return the games of a US Eastern day with their postseason fields, in
    provider order, or raise SourceError."""
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
        game = _map_event(event)
        if game is not None:
            games.append(_postseason_game(event, game))
    return games
