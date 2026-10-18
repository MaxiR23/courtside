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
# - With by_id_first a side whose abbreviation names another franchise maps to the code of its provider id; without it the abbreviation wins
# - fetch_postseason_schedule maps a team's postseason schedule: a final game with its competition type, series, note, period, score, arena and broadcast, with no line score, and a scheduled game; both resolve their sides by provider id (ADR 0058)
# - fetch_postseason_schedule skips a game with a side that has neither a code nor a name, rejects an in-play game, a final game without a score and an invalid payload, and raises on an error status, an unknown team code and a missing URL
# - fetch_postseason_schedule names the sides of a payload without name keys from the display name and the location, and codes them from the provider id whatever the abbreviation
# - ScheduleGame does not require a line score of a final game, and still requires a score
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

import httpx
import pytest
import respx

from app.feeds.games import GameStatus
from app.settings import Settings
from app.sources.http import SourceClient, SourceError, create_client
from app.sources.postseason_scoreboard import (
    PostseasonGame,
    ScheduleGame,
    fetch_postseason_games,
    fetch_postseason_schedule,
)
from app.sources.scoreboard import fetch_games
from app.sources.team_schedule import season_schedule_url
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


@pytest.mark.anyio
async def test_by_id_first_maps_a_side_to_the_code_of_its_provider_id(
    mock: respx.MockRouter, settings: Settings
) -> None:
    payload = load("playoffs.json")
    team = payload["events"][0]["competitions"][0]["competitors"][0]["team"]
    assert team["id"] == "5"
    team["abbreviation"] = "DEN"
    mock.get(URL).respond(json=payload)

    with TemporaryDirectory() as directory:
        store = StateStore(Path(directory))
        store.migrate()
        async with create_client(store) as client:
            by_abbreviation = await fetch_postseason_games(client, DAY, settings)
            by_id = await fetch_postseason_games(
                client, DAY, settings, by_id_first=True
            )

    assert by_abbreviation[0].game.home.code == "DEN"
    assert by_id[0].game.home.code == "CLE"
    assert by_id[0].game.home.guest is False
    assert mock.calls.call_count == 1


SCHEDULE_FIXTURES = Path(__file__).parent / "fixtures" / "team_schedule"
SCHEDULE_TEMPLATE = "https://example.com/teams/{team}/schedule"
SCHEDULE_URL = "https://example.com/teams/OKC/schedule?season=2004&seasontype=3"


def load_schedule() -> Payload:
    payload: Payload = json.loads(
        (SCHEDULE_FIXTURES / "past-postseason.json").read_text(encoding="utf-8")
    )
    return payload


@pytest.fixture
def schedule_settings() -> Settings:
    return Settings(_env_file=None, team_schedule_url=SCHEDULE_TEMPLATE)  # type: ignore[call-arg]


async def fetch_schedule(settings: Settings, team: str = "OKC") -> list[PostseasonGame]:
    with TemporaryDirectory() as directory:
        store = StateStore(Path(directory))
        store.migrate()
        async with create_client(store) as client:
            return await fetch_postseason_schedule(client, team, 2004, settings)


@pytest.mark.anyio
async def test_maps_a_final_postseason_schedule_game_with_its_type_series_note_and_no_line_score(
    mock: respx.MockRouter, schedule_settings: Settings
) -> None:
    mock.get(SCHEDULE_URL).respond(json=load_schedule())

    games = {g.game.id: g for g in await fetch_schedule(schedule_settings)}

    final = games["pg1"]
    assert isinstance(final.game, ScheduleGame)
    assert final.game.status is GameStatus.FINAL
    assert (final.game.home.code, final.game.away.code) == ("OKC", "MEM")
    assert (final.game.home.name, final.game.home.city) == ("Harbor Gulls", "Seattle")
    assert final.game.line_score is None
    assert (final.game.score.home, final.game.score.away) == (101, 95)  # type: ignore[union-attr]
    assert (final.game.venue, final.game.broadcast) == ("Harbor Arena", "Courtside TV")
    assert final.game.start_time == dt.datetime(2004, 5, 3, 1, 0, tzinfo=dt.UTC)
    assert (final.season_type, final.competition_type) == (3, "QTR")
    assert final.note == "West 1st Round - Game 6" and final.period == 4
    assert final.series is not None
    assert (final.series.summary, final.series.completed) == (
        "SEA wins series 4-2",
        True,
    )
    assert final.series.total_games == 7
    assert final.series.wins == {"OKC": 4, "MEM": 2}


@pytest.mark.anyio
async def test_maps_a_scheduled_game_with_no_score_period_or_line_score_and_a_game_without_type_or_series(
    mock: respx.MockRouter, schedule_settings: Settings
) -> None:
    mock.get(SCHEDULE_URL).respond(json=load_schedule())

    games = {g.game.id: g for g in await fetch_schedule(schedule_settings)}

    scheduled = games["pg2"]
    assert scheduled.game.status is GameStatus.SCHEDULED
    assert scheduled.game.score is None and scheduled.game.line_score is None
    assert scheduled.period is None and scheduled.series is not None
    assert scheduled.series.wins == {"OKC": 3, "MEM": 2}
    bare = games["pg4"]
    assert (bare.competition_type, bare.series, bare.note) == (None, None, None)
    assert bare.period == 5


@pytest.mark.anyio
async def test_skips_a_schedule_game_with_a_side_that_has_neither_a_code_nor_a_name(
    mock: respx.MockRouter, schedule_settings: Settings
) -> None:
    mock.get(SCHEDULE_URL).respond(json=load_schedule())

    games = await fetch_schedule(schedule_settings)

    assert [g.game.id for g in games] == ["pg1", "pg2", "pg4"]


@pytest.mark.anyio
async def test_rejects_an_in_play_game_and_a_final_game_without_a_score(
    mock: respx.MockRouter, schedule_settings: Settings
) -> None:
    payload = load_schedule()
    payload["events"][1]["competitions"][0]["status"]["type"]["state"] = "in"
    mock.get(SCHEDULE_URL).respond(json=payload)
    with pytest.raises(SourceError, match="game pg2 is neither final nor scheduled"):
        await fetch_schedule(schedule_settings)

    payload = load_schedule()
    for competitor in payload["events"][0]["competitions"][0]["competitors"]:
        del competitor["score"]
    mock.get(SCHEDULE_URL).respond(json=payload)
    with pytest.raises(SourceError, match="game pg1 has no score"):
        await fetch_schedule(schedule_settings)


@pytest.mark.anyio
async def test_rejects_a_schedule_game_without_one_home_and_one_away_side(
    mock: respx.MockRouter, schedule_settings: Settings
) -> None:
    payload = load_schedule()
    for competitor in payload["events"][0]["competitions"][0]["competitors"]:
        competitor["homeAway"] = "home"
    mock.get(SCHEDULE_URL).respond(json=payload)

    with pytest.raises(SourceError, match="game pg1 needs one home and one away"):
        await fetch_schedule(schedule_settings)


@pytest.mark.anyio
async def test_raises_the_source_error_on_an_invalid_schedule_payload_an_error_status_an_unknown_team_and_a_missing_url(
    mock: respx.MockRouter, schedule_settings: Settings
) -> None:
    mock.get(SCHEDULE_URL).respond(json={"events": 3})
    with pytest.raises(SourceError, match="invalid payload"):
        await fetch_schedule(schedule_settings)

    mock.get(SCHEDULE_URL).mock(return_value=httpx.Response(500))
    with pytest.raises(SourceError):
        await fetch_schedule(schedule_settings)

    with pytest.raises(SourceError, match="unknown team code"):
        await fetch_schedule(schedule_settings, "XXX")

    unset = Settings(_env_file=None)  # type: ignore[call-arg]
    with pytest.raises(SourceError, match="team schedule URL is not configured"):
        await fetch_schedule(unset)


@pytest.mark.anyio
async def test_a_postseason_schedule_without_name_keys_names_its_sides_from_the_display_name(
    mock: respx.MockRouter, schedule_settings: Settings
) -> None:
    payload: Payload = json.loads(
        (SCHEDULE_FIXTURES / "det-2005-playoffs.json").read_text(encoding="utf-8")
    )
    url = season_schedule_url("DET", 2005, schedule_settings, playoffs=True)

    async def read(body: Payload) -> list[PostseasonGame]:
        mock.get(url).respond(json=body)
        with TemporaryDirectory() as directory:
            store = StateStore(Path(directory))
            store.migrate()
            async with create_client(store) as client:
                return await fetch_postseason_schedule(
                    client, "DET", 2005, schedule_settings
                )

    (item,) = await read(payload)
    game = item.game
    assert game.id == "250423008"
    assert (game.home.code, game.home.name, game.home.city, game.home.guest) == (
        "DET",
        "Pistons",
        "Detroit",
        False,
    )
    assert (game.away.code, game.away.name, game.away.city, game.away.guest) == (
        "PHI",
        "76ers",
        "Philadelphia",
        False,
    )

    competitors = payload["events"][0]["competitions"][0]["competitors"]
    competitors[0]["team"]["abbreviation"] = "SEA"
    competitors[1]["team"]["abbreviation"] = "VAN"
    (renamed,) = await read(payload)
    assert (renamed.game.home.code, renamed.game.away.code) == ("DET", "PHI")


def test_a_schedule_game_does_not_require_a_line_score_but_still_requires_a_score() -> (
    None
):
    base: Payload = {
        "id": "x",
        "away": {"code": "MEM", "name": "Pines", "city": "Vancouver"},
        "home": {"code": "OKC", "name": "Gulls", "city": "Seattle"},
        "status": "final",
        "start_time": dt.datetime(2004, 5, 3, tzinfo=dt.UTC),
        "venue": "Harbor Arena",
        "score": {"away": 90, "home": 100},
    }

    assert ScheduleGame.model_validate(base).line_score is None
    with pytest.raises(ValueError, match="requires score"):
        ScheduleGame.model_validate({**base, "score": None})
