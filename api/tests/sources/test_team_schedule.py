# api/tests/sources/test_team_schedule.py
#
# Tests for the team schedule adapter.
#
# Tested:
# - Maps the last five completed games newest first with both scores
# - Marks home games and results from the side of the requested team
# - Dates games on the US Eastern day
# - Lists a completed game against a guest team with the guest's code
# - Returns no last games when no game is completed
# - Maps the arena of each completed game by game id
# - Requests the schedule URL built from the template and the provider team code, including a code that differs from the standard one
# - Raises the source error when the team is missing from a game, on a game without a score, an unknown team code, an invalid payload, a timeout, an error status and a missing URL
# - Reuses a team's schedule for one hour
# - Maps a recorded regular season with notes, broadcasts, venues and scores
# - Maps unplayed games without scores
# - Marks playoff games from the playoffs season type
# - Requests the season and the season type in the URL's query and keeps the template's own query
# - Maps an empty playoff schedule to no games
# - Raises the source error on an invalid season schedule payload, a played game without a score, a team missing from a game, a timeout, an error status and a missing URL for a season schedule
# - Reuses a season schedule for one hour
#
# What is covered:
# - A valid response mapped, an invalid payload rejected, upstream failures handled
#
# The fixtures are a recorded schedule trimmed to the fields the adapter
# reads: schedule.json keeps seven completed games, the four games of one
# season series among them, and schedule-preseason.json keeps two games not
# yet played, without scores.
#
# Run with: cd api && .venv/bin/python -m pytest tests/sources/test_team_schedule.py
#
# SEE: api/app/sources/team_schedule.py

import datetime as dt
import json
from collections.abc import Iterator
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import httpx
import pytest
import respx

from app.feeds.game_detail import GameResult
from app.settings import Settings
from app.sources.http import SourceClient, SourceError, create_client
from app.sources.team_schedule import (
    SeasonSchedule,
    TeamSchedule,
    fetch_season_schedule,
    fetch_team_schedule,
)
from app.storage.state import StateStore

FIXTURES = Path(__file__).parent / "fixtures" / "team_schedule"
TEMPLATE = "https://example.com/teams/{team}/schedule"
URL = "https://example.com/teams/BOS/schedule"

Payload = dict[str, Any]


def load(name: str = "schedule.json") -> Payload:
    payload: Payload = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    return payload


def event(payload: Payload, game_id: str) -> Payload:
    found: Payload = next(e for e in payload["events"] if e["id"] == game_id)
    return found


@pytest.fixture
def settings() -> Settings:
    return Settings(_env_file=None, team_schedule_url=TEMPLATE)  # type: ignore[call-arg]


@pytest.fixture
def mock() -> Iterator[respx.MockRouter]:
    with respx.mock as router:
        yield router


async def fetch(settings: Settings, team_code: str = "BOS") -> TeamSchedule:
    with TemporaryDirectory() as directory:
        store = StateStore(Path(directory))
        store.migrate()
        async with create_client(store) as client:
            return await fetch_team_schedule(client, team_code, settings)


async def fetch_error(settings: Settings, team_code: str = "BOS") -> SourceError:
    with pytest.raises(SourceError) as raised:
        await fetch(settings, team_code)
    return raised.value


async def fetch_error_of(
    mock: respx.MockRouter, settings: Settings, payload: Any
) -> SourceError:
    mock.get(URL).respond(json=payload)
    return await fetch_error(settings)


@pytest.mark.anyio
async def test_maps_the_last_five_completed_games_newest_first_with_both_scores(
    mock: respx.MockRouter, settings: Settings
) -> None:
    mock.get(URL).respond(json=load())

    schedule = await fetch(settings)

    games = schedule.last_games
    assert [g.date.isoformat() for g in games] == [
        "2026-04-12",
        "2025-11-23",
        "2025-11-09",
        "2025-11-07",
        "2025-10-26",
    ]
    assert [g.opponent for g in games] == ["ORL", "ORL", "ORL", "ORL", "DET"]
    assert [(g.team_score, g.opponent_score) for g in games] == [
        (113, 108),
        (138, 129),
        (111, 107),
        (110, 123),
        (113, 119),
    ]


@pytest.mark.anyio
async def test_lists_a_completed_game_against_a_guest_among_the_last_games_with_the_guest_code(
    mock: respx.MockRouter, settings: Settings
) -> None:
    payload = load()
    latest = max(payload["events"], key=lambda e: e["date"])
    for competitor in latest["competitions"][0]["competitors"]:
        if competitor["team"]["abbreviation"] != "BOS":
            competitor["team"]["abbreviation"] = "HCM"
    mock.get(URL).respond(json=payload)

    schedule = await fetch(settings)

    assert [g.opponent for g in schedule.last_games] == [
        "HCM",
        "ORL",
        "ORL",
        "ORL",
        "DET",
    ]


@pytest.mark.anyio
async def test_marks_home_games_and_results_from_the_team_side(
    mock: respx.MockRouter, settings: Settings
) -> None:
    mock.get(URL).respond(json=load())

    games = (await fetch(settings)).last_games

    assert [g.is_home for g in games] == [True, True, False, False, False]
    assert [g.result for g in games] == [
        GameResult.WIN,
        GameResult.WIN,
        GameResult.WIN,
        GameResult.LOSS,
        GameResult.LOSS,
    ]


@pytest.mark.anyio
async def test_dates_games_on_the_us_eastern_day(
    mock: respx.MockRouter, settings: Settings
) -> None:
    payload = load()
    assert event(payload, "401809510")["date"] == "2025-11-08T00:00Z"
    mock.get(URL).respond(json=payload)

    games = (await fetch(settings)).last_games

    assert games[3].date.isoformat() == "2025-11-07"


@pytest.mark.anyio
async def test_returns_no_last_games_when_none_is_completed(
    mock: respx.MockRouter, settings: Settings
) -> None:
    mock.get(URL).respond(json=load("schedule-preseason.json"))

    schedule = await fetch(settings)

    assert schedule.last_games == []
    assert schedule.arenas == {}


@pytest.mark.anyio
async def test_maps_the_arena_of_each_completed_game_by_game_id(
    mock: respx.MockRouter, settings: Settings
) -> None:
    mock.get(URL).respond(json=load())

    arenas = (await fetch(settings)).arenas

    assert len(arenas) == 7
    assert arenas["401811041"] == "TD Garden"
    assert arenas["401809510"] == "Kia Center"
    assert arenas["401809945"] == "Madison Square Garden"


@pytest.mark.anyio
async def test_requests_the_schedule_url_built_from_the_provider_team_code(
    mock: respx.MockRouter, settings: Settings
) -> None:
    payload = load()
    for e in payload["events"]:
        for competitor in e["competitions"][0]["competitors"]:
            if competitor["team"]["abbreviation"] == "BOS":
                competitor["team"]["abbreviation"] = "GS"
    route = mock.get("https://example.com/teams/GS/schedule").respond(json=payload)

    schedule = await fetch(settings, "GSW")

    assert route.call_count == 1
    assert len(schedule.last_games) == 5


@pytest.mark.anyio
async def test_raises_the_source_error_when_the_team_is_missing_from_a_game(
    mock: respx.MockRouter, settings: Settings
) -> None:
    payload = load()
    competitors = event(payload, "401811041")["competitions"][0]["competitors"]
    competitors[0]["team"]["abbreviation"] = "MIA"

    error = await fetch_error_of(mock, settings, payload)

    assert error.reason == "team BOS is missing from game 401811041"


@pytest.mark.anyio
async def test_raises_the_source_error_on_a_completed_game_without_a_score(
    mock: respx.MockRouter, settings: Settings
) -> None:
    payload = load()
    del event(payload, "401811041")["competitions"][0]["competitors"][0]["score"]

    error = await fetch_error_of(mock, settings, payload)

    assert error.reason == "game 401811041 has no score"


@pytest.mark.anyio
async def test_raises_the_source_error_on_an_unknown_team_code(
    settings: Settings,
) -> None:
    with respx.mock:
        error = await fetch_error(settings, "XXX")

    assert error.reason == "unknown team code 'XXX'"


@pytest.mark.anyio
@pytest.mark.parametrize("payload", [{}, {"events": 3}, {"events": [{"id": "1"}]}])
async def test_raises_the_source_error_on_an_invalid_payload(
    mock: respx.MockRouter, settings: Settings, payload: Any
) -> None:
    error = await fetch_error_of(mock, settings, payload)

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
async def test_raises_the_source_error_when_the_schedule_url_is_not_configured() -> (
    None
):
    unset = Settings(_env_file=None, team_schedule_url=None)  # type: ignore[call-arg]
    with respx.mock:
        error = await fetch_error(unset)

    assert error.reason == "team schedule URL is not configured"


def clocked(tmp_path: Path, clock: list[dt.datetime]) -> SourceClient:
    store = StateStore(tmp_path)
    store.migrate()
    return create_client(store, clock=lambda: clock[0])


@pytest.mark.anyio
async def test_reuses_a_team_schedule_for_one_hour(
    mock: respx.MockRouter, settings: Settings, tmp_path: Path
) -> None:
    start = dt.datetime(2026, 1, 10, 12, 0, tzinfo=dt.UTC)
    clock = [start]
    route = mock.get(URL).respond(json=load())
    async with clocked(tmp_path, clock) as client:
        await fetch_team_schedule(client, "BOS", settings)
        clock[0] = start + dt.timedelta(hours=1) - dt.timedelta(seconds=1)
        await fetch_team_schedule(client, "BOS", settings)
        assert route.call_count == 1
        clock[0] = start + dt.timedelta(hours=1)
        await fetch_team_schedule(client, "BOS", settings)

    assert route.call_count == 2


QUERY_TEMPLATE = "https://example.com/teams/{team}/schedule?lang=en"


def season_url(team: str, season: int, season_type: int) -> str:
    return (
        f"https://example.com/teams/{team}/schedule"
        f"?lang=en&season={season}&seasontype={season_type}"
    )


@pytest.fixture
def query_settings() -> Settings:
    return Settings(_env_file=None, team_schedule_url=QUERY_TEMPLATE)  # type: ignore[call-arg]


async def fetch_season(
    settings: Settings,
    team_code: str = "OKC",
    season: int = 2026,
    *,
    playoffs: bool = False,
) -> SeasonSchedule:
    with TemporaryDirectory() as directory:
        store = StateStore(Path(directory))
        store.migrate()
        async with create_client(store) as client:
            return await fetch_season_schedule(
                client, team_code, season, settings, playoffs=playoffs
            )


async def season_error(
    mock: respx.MockRouter, settings: Settings, payload: Any
) -> SourceError:
    mock.get(season_url("OKC", 2026, 2)).respond(json=payload)
    with pytest.raises(SourceError) as raised:
        await fetch_season(settings)
    return raised.value


@pytest.mark.anyio
async def test_maps_a_recorded_regular_season_with_notes_broadcasts_venues_and_scores(
    mock: respx.MockRouter, query_settings: Settings
) -> None:
    mock.get(season_url("OKC", 2026, 2)).respond(json=load("okc-2026-regular.json"))

    schedule = await fetch_season(query_settings)

    games = {game.game_id: game for game in schedule.games}
    assert len(schedule.games) == 7
    opener = games["401809243"]
    assert opener.start_time == dt.datetime(2025, 10, 21, 23, 30, tzinfo=dt.UTC)
    assert (opener.opponent, opener.is_home, opener.state) == ("HOU", True, "post")
    assert (opener.completed, opener.won) == (True, True)
    assert (opener.team_score, opener.opponent_score) == (125, 124)
    assert opener.note is None
    assert opener.broadcast == "Courtside TV"
    assert (opener.arena, opener.city, opener.playoffs) == (
        "Paycom Center",
        "Oklahoma City",
        False,
    )
    road_loss = games["401811037"]
    assert (road_loss.is_home, road_loss.won) == (False, False)
    assert (road_loss.team_score, road_loss.opponent_score) == (107, 127)
    assert games["401809780"].note == "NBA Cup - Group Play"
    assert games["401809838"].note == "NBA Cup - Semifinals"


@pytest.mark.anyio
async def test_maps_unplayed_games_without_scores(
    mock: respx.MockRouter, query_settings: Settings
) -> None:
    mock.get(season_url("OKC", 2027, 2)).respond(json=load("okc-2027-regular.json"))

    schedule = await fetch_season(query_settings, season=2027)

    games = {game.game_id: game for game in schedule.games}
    unplayed = games["401909090"]
    assert (unplayed.state, unplayed.completed, unplayed.won) == ("pre", False, None)
    assert (unplayed.team_score, unplayed.opponent_score) == (None, None)
    assert (unplayed.opponent, unplayed.is_home) == ("SAS", False)
    assert unplayed.broadcast == "Courtside TV"
    assert games["401909865"].broadcast is None


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("team", "fixture", "provider_code"),
    [("OKC", "okc-2026-playoffs.json", "OKC"), ("SAS", "sas-2026-playoffs.json", "SA")],
)
async def test_marks_playoff_games_from_the_playoffs_season_type(
    mock: respx.MockRouter,
    query_settings: Settings,
    team: str,
    fixture: str,
    provider_code: str,
) -> None:
    mock.get(season_url(provider_code, 2026, 3)).respond(json=load(fixture))

    schedule = await fetch_season(query_settings, team, playoffs=True)

    assert schedule.games
    assert all(game.playoffs for game in schedule.games)
    notes = [game.note for game in schedule.games]
    assert "West Finals - Game 7" in notes
    assert ("NBA Finals - Game 1" in notes) is (team == "SAS")


@pytest.mark.anyio
async def test_requests_the_season_and_season_type_in_the_query_and_keeps_the_templates_own(
    mock: respx.MockRouter, query_settings: Settings
) -> None:
    route = mock.get(season_url("BOS", 2026, 3)).respond(json={"events": []})

    await fetch_season(query_settings, "BOS", playoffs=True)

    assert route.calls.last.request.url == httpx.URL(
        "https://example.com/teams/BOS/schedule?lang=en&season=2026&seasontype=3"
    )


@pytest.mark.anyio
async def test_maps_an_empty_playoff_schedule_to_no_games(
    mock: respx.MockRouter, query_settings: Settings
) -> None:
    mock.get(season_url("OKC", 2027, 3)).respond(json={"events": []})

    schedule = await fetch_season(query_settings, season=2027, playoffs=True)

    assert schedule.games == []


@pytest.mark.anyio
@pytest.mark.parametrize("payload", [{}, {"events": 3}, {"events": [{"id": "1"}]}])
async def test_raises_the_source_error_on_an_invalid_season_schedule_payload(
    mock: respx.MockRouter, query_settings: Settings, payload: Any
) -> None:
    error = await season_error(mock, query_settings, payload)

    assert error.reason.startswith("invalid payload: ")


@pytest.mark.anyio
async def test_raises_the_source_error_on_a_played_game_without_a_score(
    mock: respx.MockRouter, query_settings: Settings
) -> None:
    payload = load("okc-2026-regular.json")
    for competitor in payload["events"][0]["competitions"][0]["competitors"]:
        del competitor["score"]

    error = await season_error(mock, query_settings, payload)

    assert error.reason == "game 401809243 has no score"


@pytest.mark.anyio
async def test_raises_the_source_error_on_a_team_missing_from_a_season_game(
    mock: respx.MockRouter, query_settings: Settings
) -> None:
    payload = load("okc-2026-regular.json")
    competitors = payload["events"][0]["competitions"][0]["competitors"]
    competitors[0]["team"]["abbreviation"] = "BOS"

    error = await season_error(mock, query_settings, payload)

    assert error.reason == "team OKC is missing from game 401809243"


@pytest.mark.anyio
async def test_raises_the_source_error_on_an_unknown_state_in_a_season_game(
    mock: respx.MockRouter, query_settings: Settings
) -> None:
    payload = load("okc-2026-regular.json")
    payload["events"][0]["competitions"][0]["status"]["type"]["state"] = "later"

    error = await season_error(mock, query_settings, payload)

    assert error.reason.startswith("team schedule is invalid: ")


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
async def test_raises_the_source_error_on_a_season_schedule_timeout_and_error_status(
    mock: respx.MockRouter, query_settings: Settings, fails: Any, reason: str
) -> None:
    fails(mock.get(season_url("OKC", 2026, 2)))

    with pytest.raises(SourceError) as raised:
        await fetch_season(query_settings)

    assert raised.value.reason == reason


@pytest.mark.anyio
async def test_raises_the_source_error_when_the_season_schedule_url_is_not_configured() -> (
    None
):
    unset = Settings(_env_file=None, team_schedule_url=None)  # type: ignore[call-arg]
    with respx.mock, pytest.raises(SourceError) as raised:
        await fetch_season(unset)

    assert raised.value.reason == "team schedule URL is not configured"


@pytest.mark.anyio
async def test_reuses_a_season_schedule_for_one_hour(
    mock: respx.MockRouter, query_settings: Settings, tmp_path: Path
) -> None:
    start = dt.datetime(2026, 1, 10, 12, 0, tzinfo=dt.UTC)
    clock = [start]
    route = mock.get(season_url("OKC", 2026, 2)).respond(json={"events": []})
    async with clocked(tmp_path, clock) as client:
        for later in (
            start,
            start + dt.timedelta(hours=1) - dt.timedelta(seconds=1),
        ):
            clock[0] = later
            await fetch_season_schedule(
                client, "OKC", 2026, query_settings, playoffs=False
            )
        assert route.call_count == 1
        clock[0] = start + dt.timedelta(hours=1)
        await fetch_season_schedule(client, "OKC", 2026, query_settings, playoffs=False)

    assert route.call_count == 2
