# api/tests/sources/test_scoreboard.py
#
# Tests for the scoreboard adapter.
#
# Tested:
# - Maps a recorded day with scheduled, live and final games to contract types
# - Maps each provider status, and leaves scores and clock empty outside live and final
# - Normalizes the clock, converts the start time to UTC and appends overtime periods
# - Raises the source error on an unknown team, an unknown status, a payload missing a field, a naive start time, a live game without a clock, an empty team name or city, a timeout, an error status and a missing URL
# - ScoreboardGame uses the same field types as the contract Game
#
# What is covered:
# - A valid response mapped, an invalid payload rejected, upstream failures handled
# - Happy path, edge cases and error cases of the status, time and line score mapping
#
# The recorded fixtures are trimmed to the fields the adapter reads. day.json
# was assembled from recordings of different days (scheduled and final
# games). The provider has no live game outside a match, so live, delayed,
# postponed and canceled games are built from a recorded game by replacing its status fields.
#
# Run with: cd api && .venv/bin/python -m pytest tests/sources/test_scoreboard.py
#
# SEE: api/app/sources/scoreboard.py

import copy
import datetime as dt
import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx

from app.feeds.games import Game, GameStatus
from app.settings import Settings
from app.sources.http import SourceError, create_client
from app.sources.scoreboard import ScoreboardGame, fetch_games

FIXTURES = Path(__file__).parent / "fixtures" / "scoreboard"
DAY = dt.date(2026, 10, 5)
TEMPLATE = "https://example.com/scoreboard/{date}"
URL = "https://example.com/scoreboard/20261005"

Payload = dict[str, Any]


def load(name: str) -> Payload:
    payload: Payload = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    return payload


def event(payload: Payload, status: str) -> Payload:
    found: Payload = next(
        e for e in payload["events"] if e["status"]["type"]["name"] == status
    )
    return copy.deepcopy(found)


def only(*events: Payload) -> Payload:
    return {"events": list(events)}


def live(payload: Payload, name: str = "STATUS_IN_PROGRESS") -> Payload:
    game = event(payload, "STATUS_FINAL")
    game["status"] = {
        "period": 3,
        "displayClock": "4:12",
        "type": {"name": name},
    }
    for competitor in game["competitions"][0]["competitors"]:
        competitor["linescores"] = competitor["linescores"][:3]
    return game


@pytest.fixture
def settings() -> Settings:
    return Settings(_env_file=None, scoreboard_url=TEMPLATE)  # type: ignore[call-arg]


@pytest.fixture
def mock() -> Iterator[respx.MockRouter]:
    with respx.mock as router:
        yield router


async def fetch(settings: Settings) -> list[ScoreboardGame]:
    async with create_client() as client:
        return await fetch_games(client, DAY, settings)


async def fetch_error(settings: Settings) -> SourceError:
    with pytest.raises(SourceError) as raised:
        await fetch(settings)
    return raised.value


@pytest.mark.anyio
async def test_maps_a_recorded_day_with_scheduled_live_and_final_games(
    mock: respx.MockRouter, settings: Settings
) -> None:
    day = load("day.json")
    day["events"].append(live(day))
    mock.get(URL).respond(json=day)

    games = await fetch(settings)

    assert [g.status for g in games] == [
        GameStatus.SCHEDULED,
        GameStatus.SCHEDULED,
        GameStatus.FINAL,
        GameStatus.FINAL,
        GameStatus.FINAL,
        GameStatus.FINAL,
        GameStatus.LIVE,
    ]
    assert [g.id for g in games[:2]] == [e["id"] for e in day["events"][:2]]
    scheduled, final, in_progress = games[0], games[2], games[-1]
    assert (scheduled.away.code, scheduled.home.code) == ("MEM", "ATL")
    assert scheduled.venue == "State Farm Arena"
    assert scheduled.score is None and scheduled.line_score is None
    assert (final.away.code, final.home.code) == ("DET", "CHA")
    assert (final.away.name, final.away.city) == ("Pistons", "Detroit")
    assert final.score is not None and (final.score.away, final.score.home) == (
        118,
        100,
    )
    assert final.line_score is not None and len(final.line_score.away) == 4
    assert in_progress.period == 3
    assert in_progress.clock == "4:12"
    assert in_progress.line_score is not None and len(in_progress.line_score.home) == 3


@pytest.mark.anyio
async def test_requests_the_url_built_from_the_template_and_the_day(
    mock: respx.MockRouter, settings: Settings
) -> None:
    route = mock.get(URL).respond(json=only())

    assert await fetch(settings) == []
    assert route.call_count == 1


@pytest.mark.anyio
async def test_keeps_provider_order_and_maps_the_teams_that_differ(
    mock: respx.MockRouter, settings: Settings
) -> None:
    day = load("day.json")
    mock.get(URL).respond(json=day)

    games = await fetch(settings)

    boston = next(g for g in games if g.home.code == "BOS")
    new_york = next(g for g in games if g.home.code == "NYK")
    assert boston.away.code == "NOP"
    assert new_york.home.name == "Knicks"


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("provider", "expected"),
    [
        ("STATUS_SCHEDULED", GameStatus.SCHEDULED),
        ("STATUS_DELAYED", GameStatus.DELAYED),
        ("STATUS_POSTPONED", GameStatus.POSTPONED),
        ("STATUS_CANCELED", GameStatus.CANCELED),
    ],
)
async def test_maps_each_provider_status_of_a_game_not_played(
    mock: respx.MockRouter, settings: Settings, provider: str, expected: GameStatus
) -> None:
    game = event(load("day.json"), "STATUS_SCHEDULED")
    game["status"]["type"]["name"] = provider
    mock.get(URL).respond(json=only(game))

    (mapped,) = await fetch(settings)

    assert mapped.status == expected


@pytest.mark.anyio
@pytest.mark.parametrize(
    "provider", ["STATUS_IN_PROGRESS", "STATUS_HALFTIME", "STATUS_END_PERIOD"]
)
async def test_maps_every_in_progress_status_to_live(
    mock: respx.MockRouter, settings: Settings, provider: str
) -> None:
    mock.get(URL).respond(json=only(live(load("day.json"), provider)))

    (mapped,) = await fetch(settings)

    assert mapped.status == GameStatus.LIVE


@pytest.mark.anyio
@pytest.mark.parametrize(
    "provider", ["STATUS_DELAYED", "STATUS_POSTPONED", "STATUS_CANCELED"]
)
async def test_leaves_scores_and_clock_empty_for_a_game_that_is_not_live_or_final(
    mock: respx.MockRouter, settings: Settings, provider: str
) -> None:
    game = live(load("day.json"))
    game["status"]["type"]["name"] = provider
    mock.get(URL).respond(json=only(game))

    (mapped,) = await fetch(settings)

    assert mapped.period is None
    assert mapped.clock is None
    assert mapped.line_score is None
    assert mapped.score is None


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("provider_clock", "expected"),
    [("4:12", "4:12"), ("12:00", "12:00"), ("45.3", "0:45"), ("5.0", "0:05")],
)
async def test_normalizes_the_clock_to_minutes_and_seconds(
    mock: respx.MockRouter, settings: Settings, provider_clock: str, expected: str
) -> None:
    game = live(load("day.json"))
    game["status"]["displayClock"] = provider_clock
    mock.get(URL).respond(json=only(game))

    (mapped,) = await fetch(settings)

    assert mapped.clock == expected


@pytest.mark.anyio
async def test_converts_the_start_time_to_utc(
    mock: respx.MockRouter, settings: Settings
) -> None:
    game = event(load("day.json"), "STATUS_SCHEDULED")
    game["date"] = "2026-10-05T19:00-04:00"
    mock.get(URL).respond(json=only(game))

    (mapped,) = await fetch(settings)

    assert mapped.start_time == dt.datetime(2026, 10, 5, 23, 0, tzinfo=dt.UTC)
    assert mapped.start_time.utcoffset() == dt.timedelta(0)


@pytest.mark.anyio
async def test_maps_an_empty_broadcast_to_none_and_keeps_a_named_one(
    mock: respx.MockRouter, settings: Settings
) -> None:
    mock.get(URL).respond(json=load("day.json"))

    games = await fetch(settings)

    assert games[0].broadcast is None
    assert "Prime Video" in [g.broadcast for g in games]


@pytest.mark.anyio
async def test_appends_overtime_periods_to_the_line_score(
    mock: respx.MockRouter, settings: Settings
) -> None:
    mock.get(URL).respond(json=load("overtime.json"))

    (mapped,) = await fetch(settings)

    assert mapped.status == GameStatus.FINAL
    assert mapped.line_score is not None
    assert len(mapped.line_score.away) == 5
    assert len(mapped.line_score.home) == 5
    assert mapped.score is not None
    assert sum(mapped.line_score.home) == mapped.score.home


@pytest.mark.anyio
async def test_raises_the_source_error_on_an_unknown_team_code(
    mock: respx.MockRouter, settings: Settings
) -> None:
    game = event(load("day.json"), "STATUS_FINAL")
    game["competitions"][0]["competitors"][0]["team"]["abbreviation"] = "ZZZ"
    mock.get(URL).respond(json=only(game))

    error = await fetch_error(settings)

    assert error.reason == "unknown team code 'ZZZ'"


@pytest.mark.anyio
async def test_raises_the_source_error_on_an_unknown_status(
    mock: respx.MockRouter, settings: Settings
) -> None:
    game = event(load("day.json"), "STATUS_FINAL")
    game["status"]["type"]["name"] = "STATUS_UNHEARD_OF"
    mock.get(URL).respond(json=only(game))

    error = await fetch_error(settings)

    assert error.reason == "unknown game status 'STATUS_UNHEARD_OF'"


@pytest.mark.anyio
@pytest.mark.parametrize("payload", [{}, {"events": [{"id": "1"}]}, {"events": 3}, []])
async def test_raises_the_source_error_on_a_payload_missing_a_used_field(
    mock: respx.MockRouter, settings: Settings, payload: object
) -> None:
    mock.get(URL).respond(json=payload)

    error = await fetch_error(settings)

    assert error.reason.startswith("invalid payload: ")


@pytest.mark.anyio
async def test_raises_the_source_error_on_a_start_time_without_a_timezone(
    mock: respx.MockRouter, settings: Settings
) -> None:
    game = event(load("day.json"), "STATUS_SCHEDULED")
    game["date"] = "2026-10-05T19:00:00"
    mock.get(URL).respond(json=only(game))

    error = await fetch_error(settings)

    assert error.reason.startswith("invalid payload: ")


@pytest.mark.anyio
async def test_raises_the_source_error_on_a_live_game_without_a_clock(
    mock: respx.MockRouter, settings: Settings
) -> None:
    game = live(load("day.json"))
    game["status"]["displayClock"] = ""
    mock.get(URL).respond(json=only(game))

    error = await fetch_error(settings)

    assert error.reason.startswith(f"game {game['id']} is invalid")


@pytest.mark.anyio
async def test_raises_the_source_error_on_a_final_game_without_a_score(
    mock: respx.MockRouter, settings: Settings
) -> None:
    game = event(load("day.json"), "STATUS_FINAL")
    for competitor in game["competitions"][0]["competitors"]:
        del competitor["score"]
    mock.get(URL).respond(json=only(game))

    error = await fetch_error(settings)

    assert error.reason.startswith(f"game {game['id']} is invalid")


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("field", "location"), [("name", "home.name"), ("location", "home.city")]
)
async def test_raises_the_source_error_on_an_empty_team_name_or_city(
    mock: respx.MockRouter, settings: Settings, field: str, location: str
) -> None:
    game = event(load("day.json"), "STATUS_FINAL")
    for competitor in game["competitions"][0]["competitors"]:
        if competitor["homeAway"] == "home":
            competitor["team"][field] = ""
    mock.get(URL).respond(json=only(game))

    error = await fetch_error(settings)

    assert error.reason.startswith(f"game {game['id']} is invalid")
    assert error.reason.endswith(f"at {location}")


@pytest.mark.anyio
async def test_raises_the_source_error_when_the_request_times_out(
    mock: respx.MockRouter, settings: Settings
) -> None:
    mock.get(URL).mock(side_effect=httpx.ReadTimeout("slow"))

    error = await fetch_error(settings)

    assert error.reason == "request timed out"


@pytest.mark.anyio
async def test_raises_the_source_error_on_an_error_status(
    mock: respx.MockRouter, settings: Settings
) -> None:
    mock.get(URL).respond(status_code=500)

    error = await fetch_error(settings)

    assert error.reason == "responded with status 500"


@pytest.mark.anyio
async def test_raises_the_source_error_when_the_url_is_not_configured() -> None:
    unset = Settings(_env_file=None, scoreboard_url=None)  # type: ignore[call-arg]
    with respx.mock:
        error = await fetch_error(unset)

    assert error.reason == "scoreboard URL is not configured"


def test_scoreboard_game_fields_match_the_contract_game() -> None:
    for name, field in ScoreboardGame.model_fields.items():
        assert name in Game.model_fields
        assert field.annotation == Game.model_fields[name].annotation
        assert field.metadata == Game.model_fields[name].metadata
