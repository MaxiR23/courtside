# api/tests/sources/test_player_gamelog.py
#
# Tests for the player game log adapter.
#
# Tested:
# - Maps the recorded regular season and postseason games with their stats
# - Keeps preseason games, marked preseason, as a third season type
# - Maps an opponent without an abbreviation to a guest with a null code, its name and city, and an unknown abbreviation to a guest with that code
# - Skips an event whose opponent has neither a code nor a name
# - Validates only the events a matched season type references: an invalid event nothing references does not fail the log
# - Takes the season label from the season type names
# - Maps an All-Star game with no opponent
# - Maps the team and opponent scores from the home and away sides
# - Raises the source error on a stat line whose labels are missing a column, an event the log does not describe, an event of an invalid shape that a season type references and a malformed stat
# - Raises the source error on an invalid payload, a timeout, an error status and a missing URL
# - Reuses a game log for one hour
#
# What is covered:
# - A valid response mapped, an invalid payload rejected, upstream failures handled
#
# The fixtures are recorded responses trimmed to the fields the adapter reads.
#
# Run with: cd api && .venv/bin/python -m pytest tests/sources/test_player_gamelog.py
#
# SEE: api/app/sources/player_gamelog.py

import datetime as dt
import json
from collections.abc import Iterator
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import httpx
import pytest
import respx

from app.settings import Settings
from app.sources.http import SourceError, create_client
from app.sources.player_gamelog import PlayerGameLog, fetch_player_gamelog
from app.storage.state import StateStore

FIXTURES = Path(__file__).parent / "fixtures" / "player_gamelog"
TEMPLATE = "https://example.com/athletes/{player_id}/gamelog"
URL = "https://example.com/athletes/4278073/gamelog"

Payload = dict[str, Any]


def load(name: str = "gamelog-2026.json") -> Payload:
    payload: Payload = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    return payload


@pytest.fixture
def settings() -> Settings:
    return Settings(_env_file=None, player_gamelog_url=TEMPLATE)  # type: ignore[call-arg]


@pytest.fixture
def mock() -> Iterator[respx.MockRouter]:
    with respx.mock as router:
        yield router


async def fetch(settings: Settings) -> PlayerGameLog:
    with TemporaryDirectory() as directory:
        store = StateStore(Path(directory))
        store.migrate()
        async with create_client(store) as client:
            return await fetch_player_gamelog(client, "4278073", settings)


async def fetch_error(settings: Settings) -> SourceError:
    with pytest.raises(SourceError) as raised:
        await fetch(settings)
    return raised.value


@pytest.mark.anyio
async def test_maps_the_recorded_regular_season_and_postseason_games_with_their_stats(
    mock: respx.MockRouter, settings: Settings
) -> None:
    mock.get(URL).respond(json=load())

    log = await fetch(settings)

    games = {game.game_id: game for game in log.games}
    assert len(games) == 11
    game = games["401873203"]
    assert game.start_time == dt.datetime(2026, 5, 31, 0, 0, tzinfo=dt.UTC)
    assert game.opponent is not None
    assert (game.opponent.code, game.is_home, game.won) == ("SAS", True, False)
    assert (game.team_score, game.opponent_score) == (103, 111)
    assert game.note == "West Finals - Game 7"
    assert game.playoffs is True
    assert (game.minutes, game.field_goals, game.field_goal_pct) == (
        "43",
        "12-21",
        57.1,
    )
    assert (game.three_points, game.three_point_pct) == ("2-5", 40.0)
    assert (game.free_throws, game.free_throw_pct) == ("9-11", 81.8)
    assert (game.rebounds, game.assists, game.blocks, game.steals) == (4, 9, 1, 3)
    assert (game.fouls, game.turnovers, game.points) == (1, 3, 35)
    assert games["401809995"].playoffs is False
    assert games["401809995"].note is None


@pytest.mark.anyio
async def test_keeps_preseason_games_marked_as_preseason(
    mock: respx.MockRouter, settings: Settings
) -> None:
    mock.get(URL).respond(json=load())

    log = await fetch(settings)

    games = {game.game_id: game for game in log.games}
    assert games["401812735"].preseason is True
    assert games["401812735"].playoffs is False
    assert [g.game_id for g in log.games if g.preseason] == ["401812735"]


@pytest.mark.anyio
async def test_takes_the_season_label_from_the_season_type_names(
    mock: respx.MockRouter, settings: Settings
) -> None:
    mock.get(URL).respond(json=load())

    assert (await fetch(settings)).season == "2025-26"


@pytest.mark.anyio
async def test_gives_no_season_and_no_games_without_a_matching_season_type(
    mock: respx.MockRouter, settings: Settings
) -> None:
    payload = load()
    payload["seasonTypes"] = [
        {**payload["seasonTypes"][0], "displayName": "2025-26 Summer League"}
    ]
    mock.get(URL).respond(json=payload)

    log = await fetch(settings)

    assert (log.season, log.games) == (None, [])


@pytest.mark.anyio
async def test_maps_an_all_star_game_with_no_opponent(
    mock: respx.MockRouter, settings: Settings
) -> None:
    payload = load()
    payload["events"]["401809995"]["eventNote"] = "NBA All-Star - Championship"
    del payload["events"]["401809995"]["opponent"]
    mock.get(URL).respond(json=payload)

    log = await fetch(settings)

    game = next(game for game in log.games if game.game_id == "401809995")
    assert game.opponent is None
    assert game.note == "NBA All-Star - Championship"


@pytest.mark.anyio
async def test_maps_the_team_and_opponent_scores_from_the_home_and_away_sides(
    mock: respx.MockRouter, settings: Settings
) -> None:
    mock.get(URL).respond(json=load())

    log = await fetch(settings)

    games = {game.game_id: game for game in log.games}
    home = games["401873201"]
    away = games["401811018"]
    assert (home.is_home, home.team_score, home.opponent_score) == (True, 127, 114)
    assert (away.is_home, away.team_score, away.opponent_score) == (False, 128, 110)


@pytest.mark.anyio
async def test_raises_the_source_error_on_a_stat_line_with_a_missing_column(
    mock: respx.MockRouter, settings: Settings
) -> None:
    payload = load()
    payload["seasonTypes"][0]["categories"][0]["events"][0]["stats"].pop()
    mock.get(URL).respond(json=payload)

    error = await fetch_error(settings)

    assert (
        error.reason == "invalid payload: 1 errors, first at stats of event 401873203"
    )


@pytest.mark.anyio
async def test_raises_the_source_error_on_labels_missing_a_column(
    mock: respx.MockRouter, settings: Settings
) -> None:
    payload = load()
    payload["labels"][0] = "XX"
    mock.get(URL).respond(json=payload)

    error = await fetch_error(settings)

    assert error.reason.startswith("invalid payload: ")


@pytest.mark.anyio
async def test_raises_the_source_error_on_an_event_the_log_does_not_describe(
    mock: respx.MockRouter, settings: Settings
) -> None:
    payload = load()
    del payload["events"]["401873203"]
    mock.get(URL).respond(json=payload)

    error = await fetch_error(settings)

    assert error.reason == "invalid payload: 1 errors, first at events.401873203"


@pytest.mark.anyio
async def test_maps_an_unknown_opponent_abbreviation_to_a_guest_with_that_code(
    mock: respx.MockRouter, settings: Settings
) -> None:
    payload = load()
    payload["events"]["401873203"]["opponent"]["abbreviation"] = "XXX"
    mock.get(URL).respond(json=payload)

    log = await fetch(settings)

    opponent = {g.game_id: g for g in log.games}["401873203"].opponent
    assert opponent is not None
    assert (opponent.code, opponent.guest) == ("XXX", True)


@pytest.mark.anyio
async def test_maps_a_preseason_game_against_an_opponent_without_an_abbreviation(
    mock: respx.MockRouter, settings: Settings
) -> None:
    payload = load()
    payload["events"]["401812735"]["opponent"] = {
        "id": "90001",
        "displayName": "Harbor City Mariners",
        "name": "Mariners",
        "location": "Harbor City",
    }
    mock.get(URL).respond(json=payload)

    log = await fetch(settings)

    game = {g.game_id: g for g in log.games}["401812735"]
    assert game.preseason is True
    assert game.opponent is not None
    assert (game.opponent.code, game.opponent.name, game.opponent.city) == (
        None,
        "Mariners",
        "Harbor City",
    )
    assert game.opponent.guest is True


@pytest.mark.anyio
async def test_uses_the_display_name_of_an_opponent_without_a_name(
    mock: respx.MockRouter, settings: Settings
) -> None:
    payload = load()
    payload["events"]["401812735"]["opponent"] = {
        "id": "90001",
        "displayName": "Harbor City Mariners",
    }
    mock.get(URL).respond(json=payload)

    log = await fetch(settings)

    opponent = {g.game_id: g for g in log.games}["401812735"].opponent
    assert opponent is not None and opponent.name == "Harbor City Mariners"


@pytest.mark.anyio
async def test_skips_an_event_whose_opponent_has_neither_a_code_nor_a_name(
    mock: respx.MockRouter, settings: Settings
) -> None:
    payload = load()
    payload["events"]["401812735"]["opponent"] = {"id": "90001"}
    mock.get(URL).respond(json=payload)

    log = await fetch(settings)

    assert len(log.games) == 10
    assert "401812735" not in {g.game_id for g in log.games}


@pytest.mark.anyio
async def test_does_not_validate_an_event_that_no_season_type_references(
    mock: respx.MockRouter, settings: Settings
) -> None:
    payload = load()
    payload["events"]["999"] = {"id": "999"}
    mock.get(URL).respond(json=payload)

    log = await fetch(settings)

    assert len(log.games) == 11


@pytest.mark.anyio
async def test_raises_the_source_error_on_an_invalid_event_a_season_type_references(
    mock: respx.MockRouter, settings: Settings
) -> None:
    payload = load()
    payload["events"]["401812735"] = {"id": "401812735"}
    mock.get(URL).respond(json=payload)

    error = await fetch_error(settings)

    assert error.reason.startswith("invalid payload: ")
    assert "first at events.401812735." in error.reason


@pytest.mark.anyio
async def test_raises_the_source_error_on_a_malformed_stat(
    mock: respx.MockRouter, settings: Settings
) -> None:
    payload = load()
    payload["seasonTypes"][0]["categories"][0]["events"][0]["stats"][1] = "12/21"
    mock.get(URL).respond(json=payload)

    error = await fetch_error(settings)

    assert error.reason.startswith("player 4278073 is invalid: ")
    assert error.reason.endswith("games.0.field_goals")


@pytest.mark.anyio
@pytest.mark.parametrize(
    "payload",
    [{}, {"labels": 3}, {"labels": [], "seasonTypes": [{"categories": []}]}],
    ids=str,
)
async def test_raises_the_source_error_on_an_invalid_payload(
    mock: respx.MockRouter, settings: Settings, payload: Any
) -> None:
    mock.get(URL).respond(json=payload)

    error = await fetch_error(settings)

    assert error.source == "player_gamelog"
    assert error.reason.startswith("invalid payload: ")


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("fails", "reason"),
    [
        (
            lambda route: route.mock(side_effect=httpx.ReadTimeout("slow")),
            "request timed out",
        ),
        (lambda route: route.respond(status_code=500), "responded with status 500"),
    ],
    ids=["timeout", "error status"],
)
async def test_raises_the_source_error_on_a_timeout_and_an_error_status(
    mock: respx.MockRouter, settings: Settings, fails: Any, reason: str
) -> None:
    fails(mock.get(URL))

    error = await fetch_error(settings)

    assert error.reason == reason


@pytest.mark.anyio
async def test_raises_the_source_error_when_the_url_is_not_configured() -> None:
    unset = Settings(_env_file=None, player_gamelog_url=None)  # type: ignore[call-arg]
    with respx.mock:
        error = await fetch_error(unset)

    assert error.reason == "player game log URL is not configured"


@pytest.mark.anyio
async def test_reuses_a_game_log_for_one_hour(
    mock: respx.MockRouter, settings: Settings, tmp_path: Path
) -> None:
    start = dt.datetime(2026, 1, 10, 12, 0, tzinfo=dt.UTC)
    clock = [start]
    route = mock.get(URL).respond(json=load())
    store = StateStore(tmp_path)
    store.migrate()
    async with create_client(store, clock=lambda: clock[0]) as client:
        await fetch_player_gamelog(client, "4278073", settings)
        clock[0] = start + dt.timedelta(hours=1) - dt.timedelta(seconds=1)
        await fetch_player_gamelog(client, "4278073", settings)
        assert route.call_count == 1
        clock[0] = start + dt.timedelta(hours=1)
        await fetch_player_gamelog(client, "4278073", settings)

    assert route.call_count == 2
