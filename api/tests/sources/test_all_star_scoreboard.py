# api/tests/sources/test_all_star_scoreboard.py
#
# Tests for the All-Star view of the scoreboard adapter.
#
# Tested:
# - Maps the All-Star games of a day: the note, the sides with code and name, a null city when there is no location, the score, the period and the status text of a final game, and the tip-off time in UTC
# - Ignores a regular game
# - A day with no events is an empty list
# - A side that is not an All-Star team is null in a scheduled game and raises the source error in a live or final game
# - A live game keeps the status text and the period as sent and normalizes the clock like the games feed
# - Raises the source error on an invalid payload, an unknown status, a live game with no score and a missing URL
# - Raises the source error on an upstream 500 and on a timeout
# - Shares one request per day with the games function of the scoreboard adapter
#
# What is covered:
# - Happy path, edge cases and error cases of the All-Star mapping
#
# The fixtures are invented: clubs, arena and notes are made up, and every URL
# uses example.com.
#
# Run with: cd api && .venv/bin/python -m pytest tests/sources/test_all_star_scoreboard.py
#
# SEE: api/app/sources/all_star_scoreboard.py

import datetime as dt
import json
from collections.abc import Iterator
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import httpx
import pytest
import respx

from app.feeds.games import GameStatus
from app.settings import Settings
from app.sources.all_star_scoreboard import (
    AllStarScoreboardGame,
    fetch_all_star_games,
)
from app.sources.http import SourceClient, SourceError, create_client
from app.sources.scoreboard import fetch_games
from app.storage.state import StateStore

FIXTURES = Path(__file__).parent / "fixtures" / "all_star_scoreboard"
DAY = dt.date(2027, 2, 14)
TEMPLATE = "https://example.com/scoreboard/{date}"
URL = "https://example.com/scoreboard/20270214"

Payload = dict[str, Any]


def load(name: str) -> Payload:
    payload: Payload = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    return payload


@pytest.fixture
def settings() -> Settings:
    return Settings(_env_file=None, scoreboard_url=TEMPLATE)  # type: ignore[call-arg]


@pytest.fixture
def mock() -> Iterator[respx.MockRouter]:
    with respx.mock as router:
        yield router


def clocked(tmp_path: Path, clock: list[dt.datetime]) -> SourceClient:
    store = StateStore(tmp_path)
    store.migrate()
    return create_client(store, clock=lambda: clock[0])


async def fetch(settings: Settings) -> list[AllStarScoreboardGame]:
    with TemporaryDirectory() as directory:
        store = StateStore(Path(directory))
        store.migrate()
        async with create_client(store) as client:
            return await fetch_all_star_games(client, DAY, settings)


@pytest.mark.anyio
async def test_maps_the_all_star_games_of_a_day(
    mock: respx.MockRouter, settings: Settings
) -> None:
    mock.get(URL).respond(json=load("day.json"))

    games = await fetch(settings)

    assert [g.id for g in games] == ["9001", "9002", "9003"]
    first = games[0]
    assert first.note == "NBA All-Star - Round Robin"
    assert first.venue == "Example Arena"
    assert first.start_time == dt.datetime(2027, 2, 15, 1, 0, tzinfo=dt.UTC)
    assert first.status is GameStatus.FINAL
    assert first.status_text == "Final"
    assert first.period == 1
    assert first.clock is None
    assert first.score is not None
    assert (first.score.away, first.score.home) == (21, 18)
    assert first.away is not None and first.home is not None
    assert (first.away.code, first.away.name) == ("STR", "Team Stripes")
    assert (first.home.code, first.home.name) == ("WAV", "Team Waves")
    assert first.away.city is None
    assert games[1].away is not None and games[1].away.city == "Example City"
    assert games[2].note == "NBA All-Star - Championship"
    assert games[2].period == 2 and games[2].status_text == "Final/OT"


@pytest.mark.anyio
async def test_ignores_a_regular_game(
    mock: respx.MockRouter, settings: Settings
) -> None:
    payload = load("day.json")
    mock.get(URL).respond(json=payload)

    games = await fetch(settings)

    assert "8001" not in [g.id for g in games]


@pytest.mark.anyio
async def test_ignores_an_all_star_competition_outside_the_regular_season(
    mock: respx.MockRouter, settings: Settings
) -> None:
    payload = load("day.json")
    payload["events"][1]["season"]["type"] = 3
    mock.get(URL).respond(json=payload)

    games = await fetch(settings)

    assert [g.id for g in games] == ["9002", "9003"]


@pytest.mark.anyio
async def test_a_day_with_no_events_is_an_empty_list(
    mock: respx.MockRouter, settings: Settings
) -> None:
    mock.get(URL).respond(json=load("empty.json"))

    assert await fetch(settings) == []


@pytest.mark.anyio
async def test_a_scheduled_game_whose_sides_are_not_all_star_teams_has_null_sides(
    mock: respx.MockRouter, settings: Settings
) -> None:
    payload = load("tbd.json")
    payload["events"][0]["competitions"][0]["type"] = {"abbreviation": "ALLSTAR"}
    mock.get(URL).respond(json=payload)

    games = await fetch(settings)

    assert len(games) == 1
    game = games[0]
    assert game.status is GameStatus.SCHEDULED
    assert game.away is None and game.home is None
    assert game.score is None and game.period is None and game.clock is None
    assert game.status_text == "Scheduled"


@pytest.mark.anyio
@pytest.mark.parametrize("status", ["STATUS_IN_PROGRESS", "STATUS_FINAL"])
async def test_raises_the_source_error_on_a_game_in_play_with_a_side_that_is_not_a_team(
    mock: respx.MockRouter, settings: Settings, status: str
) -> None:
    payload = load("live.json")
    event = payload["events"][0]
    event["status"]["type"]["name"] = status
    event["competitions"][0]["competitors"][0]["team"]["isAllStar"] = False
    mock.get(URL).respond(json=payload)

    with pytest.raises(SourceError) as raised:
        await fetch(settings)

    assert raised.value.reason == "game 9020 is in play with a side with no team"


@pytest.mark.anyio
async def test_a_live_game_keeps_the_status_text_and_period_and_normalizes_the_clock(
    mock: respx.MockRouter, settings: Settings
) -> None:
    mock.get(URL).respond(json=load("live.json"))

    games = await fetch(settings)

    game = games[0]
    assert game.status is GameStatus.LIVE
    assert game.status_text == "Q2 8.3"
    assert game.period == 2
    assert game.clock == "0:08"
    assert game.score is not None
    assert (game.score.away, game.score.home) == (12, 9)
    assert game.note is not None and game.note.endswith("Untimed")


@pytest.mark.anyio
async def test_a_live_game_keeps_a_clock_that_is_already_minutes_and_seconds(
    mock: respx.MockRouter, settings: Settings
) -> None:
    payload = load("live.json")
    payload["events"][0]["status"]["displayClock"] = "4:12"
    mock.get(URL).respond(json=payload)

    assert (await fetch(settings))[0].clock == "4:12"


@pytest.mark.anyio
async def test_raises_the_source_error_on_a_live_game_with_no_score(
    mock: respx.MockRouter, settings: Settings
) -> None:
    payload = load("live.json")
    del payload["events"][0]["competitions"][0]["competitors"][0]["score"]
    mock.get(URL).respond(json=payload)

    with pytest.raises(SourceError) as raised:
        await fetch(settings)

    assert raised.value.reason == "game 9020 is in play with no score"


@pytest.mark.anyio
async def test_raises_the_source_error_on_an_unknown_status(
    mock: respx.MockRouter, settings: Settings
) -> None:
    payload = load("live.json")
    payload["events"][0]["status"]["type"]["name"] = "STATUS_UNKNOWN"
    mock.get(URL).respond(json=payload)

    with pytest.raises(SourceError) as raised:
        await fetch(settings)

    assert raised.value.reason == "unknown game status 'STATUS_UNKNOWN'"


@pytest.mark.anyio
async def test_raises_the_source_error_on_a_game_without_one_home_and_one_away_team(
    mock: respx.MockRouter, settings: Settings
) -> None:
    payload = load("live.json")
    payload["events"][0]["competitions"][0]["competitors"].pop()
    mock.get(URL).respond(json=payload)

    with pytest.raises(SourceError) as raised:
        await fetch(settings)

    assert raised.value.reason == "game 9020 needs one home and one away team"


@pytest.mark.anyio
async def test_raises_the_source_error_on_an_invalid_payload(
    mock: respx.MockRouter, settings: Settings
) -> None:
    mock.get(URL).respond(json={"events": [{"id": "1"}]})

    with pytest.raises(SourceError) as raised:
        await fetch(settings)

    assert raised.value.reason.startswith("invalid payload: ")


@pytest.mark.anyio
async def test_raises_the_source_error_when_the_url_is_not_configured() -> None:
    unset = Settings(_env_file=None)  # type: ignore[call-arg]
    with respx.mock, pytest.raises(SourceError) as raised:
        await fetch(unset)

    assert raised.value.reason == "scoreboard URL is not configured"


@pytest.mark.anyio
async def test_raises_the_source_error_on_an_error_status(
    mock: respx.MockRouter, settings: Settings
) -> None:
    mock.get(URL).respond(status_code=500)

    with pytest.raises(SourceError) as raised:
        await fetch(settings)

    assert raised.value.reason == "responded with status 500"


@pytest.mark.anyio
async def test_raises_the_source_error_when_the_request_times_out(
    mock: respx.MockRouter, settings: Settings
) -> None:
    mock.get(URL).mock(side_effect=httpx.ReadTimeout("slow"))

    with pytest.raises(SourceError) as raised:
        await fetch(settings)

    assert raised.value.reason == "request timed out"


@pytest.mark.anyio
async def test_the_games_and_all_star_functions_share_one_request_for_a_day(
    mock: respx.MockRouter, settings: Settings, tmp_path: Path
) -> None:
    clock = [dt.datetime(2027, 2, 14, 12, 0, tzinfo=dt.UTC)]
    payload = load("day.json")
    for event in payload["events"]:
        event["status"] = {"type": {"name": "STATUS_SCHEDULED"}}
        for competitor in event["competitions"][0]["competitors"]:
            competitor["team"]["location"] = "Example City"
            competitor.pop("score", None)
    route = mock.get(URL).respond(json=payload)
    async with clocked(tmp_path, clock) as client:
        await fetch_games(client, DAY, settings)
        games = await fetch_all_star_games(client, DAY, settings)

    assert route.call_count == 1
    assert len(games) == 3
