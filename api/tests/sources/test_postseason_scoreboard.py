# api/tests/sources/test_postseason_scoreboard.py
#
# Tests for the postseason view of the scoreboard adapter.
#
# Tested:
# - Maps the postseason fields of a game: season type, competition type, note, period of a final game and series object (summary, completion, total games, wins per standard code), and none of them for a regular game
# - Returns an empty list for a day with no games and skips a game with a side that has no team
# - Raises the source error on a series competitor with an unknown team id of a final game, an invalid payload and a missing URL
# - Leaves a series competitor with an unknown team id out of the wins of a scheduled game
# - Shares one request per day with the games function of the scoreboard adapter
#
# What is covered:
# - Happy path, edge cases and error cases of the postseason mapping
#
# The recorded fixtures are the ones of the scoreboard adapter, trimmed to the
# fields the adapters read.
#
# Run with: cd api && .venv/bin/python -m pytest tests/sources/test_postseason_scoreboard.py
#
# SEE: api/app/sources/postseason_scoreboard.py

import datetime as dt
import json
from collections.abc import Iterator
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import pytest
import respx

from app.feeds.games import GameStatus
from app.settings import Settings
from app.sources.http import SourceClient, SourceError, create_client
from app.sources.postseason_scoreboard import PostseasonGame, fetch_postseason_games
from app.sources.scoreboard import fetch_games
from app.storage.state import StateStore

FIXTURES = Path(__file__).parent / "fixtures" / "scoreboard"
DAY = dt.date(2026, 10, 5)
TEMPLATE = "https://example.com/scoreboard/{date}"
URL = "https://example.com/scoreboard/20261005"

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


async def fetch_postseason(settings: Settings) -> list[PostseasonGame]:
    with TemporaryDirectory() as directory:
        store = StateStore(Path(directory))
        store.migrate()
        async with create_client(store) as client:
            return await fetch_postseason_games(client, DAY, settings)


@pytest.mark.anyio
async def test_maps_the_season_type_competition_type_and_note_of_a_play_in_game(
    mock: respx.MockRouter, settings: Settings
) -> None:
    mock.get(URL).respond(json=load("play-in.json"))

    games = await fetch_postseason(settings)

    assert [g.game.id for g in games] == ["5001", "5002"]
    first = games[0]
    assert first.season_type == 5
    assert first.competition_type is None
    assert first.note == "NBA Play-In - East - 7th Place vs 8th Place"
    assert first.series is None
    assert first.game.status is GameStatus.FINAL


@pytest.mark.anyio
async def test_maps_the_series_object_of_a_playoff_game_to_standard_codes(
    mock: respx.MockRouter, settings: Settings
) -> None:
    mock.get(URL).respond(json=load("playoffs.json"))

    games = await fetch_postseason(settings)

    assert [g.competition_type for g in games] == ["RD16", "QTR", "FINAL"]
    first, second, third = games
    assert first.series is not None
    assert first.series.summary == "CLE leads series 1-0"
    assert first.series.completed is False
    assert first.series.total_games == 7
    assert first.series.wins == {"CLE": 1, "ORL": 0}
    assert second.series is not None and second.series.summary is None
    assert third.series is not None and third.series.completed is True
    assert third.series.wins == {"CLE": 4, "DEN": 2}


@pytest.mark.anyio
async def test_keeps_the_period_of_a_final_overtime_game_and_none_before_the_game(
    mock: respx.MockRouter, settings: Settings
) -> None:
    mock.get(URL).respond(json=load("playoffs.json"))

    games = await fetch_postseason(settings)

    assert [g.period for g in games] == [5, None, 4]


@pytest.mark.anyio
async def test_a_regular_game_has_no_postseason_fields(
    mock: respx.MockRouter, settings: Settings
) -> None:
    mock.get(URL).respond(json=load("day.json"))

    games = await fetch_postseason(settings)

    assert games
    assert all(g.season_type is None and g.series is None for g in games)
    assert all(g.competition_type is None and g.note is None for g in games)


@pytest.mark.anyio
async def test_a_day_with_no_games_is_an_empty_list(
    mock: respx.MockRouter, settings: Settings
) -> None:
    mock.get(URL).respond(json=load("postseason-empty.json"))

    assert await fetch_postseason(settings) == []


@pytest.mark.anyio
async def test_skips_a_game_with_a_side_that_has_no_team(
    mock: respx.MockRouter, settings: Settings
) -> None:
    payload = load("playoffs.json")
    payload["events"][0]["competitions"][0]["competitors"][0]["team"] = {}
    mock.get(URL).respond(json=payload)

    games = await fetch_postseason(settings)

    assert [g.game.id for g in games] == ["6002", "6003"]


@pytest.mark.anyio
async def test_raises_the_source_error_on_a_final_game_series_competitor_with_an_unknown_team_id(
    mock: respx.MockRouter, settings: Settings
) -> None:
    payload = load("playoffs.json")
    payload["events"][0]["competitions"][0]["series"]["competitors"][0]["id"] = "999"
    mock.get(URL).respond(json=payload)

    with pytest.raises(SourceError) as raised:
        await fetch_postseason(settings)

    assert raised.value.reason == "unknown team id '999'"


@pytest.mark.anyio
async def test_leaves_an_unknown_series_competitor_out_of_the_wins_of_a_scheduled_game(
    mock: respx.MockRouter, settings: Settings
) -> None:
    payload = load("playoffs.json")
    competitors = payload["events"][1]["competitions"][0]["series"]["competitors"]
    competitors[0]["id"] = "999"
    mock.get(URL).respond(json=payload)

    games = await fetch_postseason(settings)

    scheduled = games[1]
    assert scheduled.game.status is GameStatus.SCHEDULED
    assert scheduled.series is not None
    assert len(scheduled.series.wins) == len(competitors) - 1
    assert "999" not in scheduled.series.wins


@pytest.mark.anyio
async def test_raises_the_source_error_on_an_invalid_payload(
    mock: respx.MockRouter, settings: Settings
) -> None:
    mock.get(URL).respond(json={"events": [{"id": "1"}]})

    with pytest.raises(SourceError) as raised:
        await fetch_postseason(settings)

    assert raised.value.reason.startswith("invalid payload: ")


@pytest.mark.anyio
async def test_raises_the_source_error_when_the_url_is_not_configured() -> None:
    unset = Settings(_env_file=None)  # type: ignore[call-arg]
    with respx.mock, pytest.raises(SourceError) as raised:
        await fetch_postseason(unset)

    assert raised.value.reason == "scoreboard URL is not configured"


@pytest.mark.anyio
async def test_the_games_and_postseason_functions_share_one_request_for_a_day(
    mock: respx.MockRouter, settings: Settings, tmp_path: Path
) -> None:
    clock = [dt.datetime(2027, 4, 20, 12, 0, tzinfo=dt.UTC)]
    route = mock.get(URL).respond(json=load("playoffs.json"))
    async with clocked(tmp_path, clock) as client:
        await fetch_games(client, DAY, settings)
        await fetch_postseason_games(client, DAY, settings)

    assert route.call_count == 1
