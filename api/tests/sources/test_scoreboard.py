# api/tests/sources/test_scoreboard.py
#
# Tests for the scoreboard adapter.
#
# Tested:
# - Maps a recorded day with scheduled, live and final games to contract types
# - Maps each provider status, and leaves scores and clock empty outside live and final
# - Normalizes the clock, converts the start time to UTC and appends overtime periods
# - Maps a team outside the league to a guest side with the source code, name and city, and keeps a guest code outside the usual pattern as it is
# - Raises the source error on a guest code equal to a league code, an unknown status, a payload missing a field, a naive start time, a live game without a clock, an empty team name or city, a timeout, an error status and a missing URL
# - Maps a team without an abbreviation to a guest side with a null code, its name and city, or to a league side by its provider id
# - Skips a game with a side that has neither a code nor a name, and keeps the other games in provider order
# - ScoreboardGame uses the same field types as the contract Game
# - Marks a game with the Cup round of its note, and leaves any other note or none unmarked
# - Reuses a fetched day for thirty seconds
# - Marks the play-in and playoff games of a day with their postseason mark and each stake of a recorded day, and leaves a regular game unmarked
# - A malformed series object, an unknown series competitor id, a missing note and an unknown competition type each give a null mark, log the event id only and still build the day
# - The lenient mark shapes read the field names the strict postseason shapes read
# - The playoffs adapter path reads the same mark as the core path and logs no unreadable mark warning
# - Maps an All-Star day: the All-Star games carry the round mark with the suffix dropped, their sides are guests read by code or name with no All-Star flag and a null city even with a location, and the league game keeps its city, score and no mark
# - Skips silently an All-Star game with a side that has neither a code nor a name (both, one, or empty strings) and keeps the other games, and marks the Championship when its sides have a code or a name
# - Treats an unreadable season or competition type as not All-Star, and leaves a regular game with no All-Star flag unaffected
# - Skips with one log line by event id an All-Star event without a line score, without a clock, with a league code, with a provider-key side without a city, with a note that is not an All-Star note or with an unknown status, and keeps the rest of the day
# - Still raises the source error for an event with no competition
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
import logging
from collections.abc import Iterator
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import httpx
import pytest
import respx
from pydantic import BaseModel

from app.feeds.games import CupRound, Game, GameStatus, PostseasonStage, Stakes
from app.settings import Settings
from app.sources import postseason_scoreboard, scoreboard
from app.sources.http import SourceClient, SourceError, create_client
from app.sources.scoreboard import ScoreboardGame, fetch_games
from app.storage.state import StateStore

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
    with TemporaryDirectory() as directory:
        store = StateStore(Path(directory))
        store.migrate()
        async with create_client(store) as client:
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
    assert "Courtside TV" in [g.broadcast for g in games]


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


def guest_side(game: Payload, index: int = 0) -> None:
    team = game["competitions"][0]["competitors"][index]["team"]
    team["abbreviation"] = "HCM"
    team["name"] = "Mariners"
    team["location"] = "Harbor City"


@pytest.mark.anyio
async def test_maps_a_team_outside_the_league_to_a_guest_side_with_the_source_code_name_and_city(
    mock: respx.MockRouter, settings: Settings
) -> None:
    game = event(load("day.json"), "STATUS_FINAL")
    guest_side(game)
    mock.get(URL).respond(json=only(game))

    [mapped] = await fetch(settings)

    sides = (mapped.away, mapped.home)
    [guest] = [side for side in sides if side.guest]
    [league] = [side for side in sides if not side.guest]
    assert (guest.code, guest.name, guest.city) == ("HCM", "Mariners", "Harbor City")
    assert league.code is not None and len(league.code) == 3


@pytest.mark.anyio
async def test_maps_a_day_with_a_guest_game_and_a_league_game(
    mock: respx.MockRouter, settings: Settings
) -> None:
    day = load("day.json")
    guest = event(day, "STATUS_FINAL")
    guest["id"] = "guest-game"
    guest_side(guest)
    league = event(day, "STATUS_FINAL")
    mock.get(URL).respond(json=only(league, guest))

    games = await fetch(settings)

    assert [g.id for g in games] == [league["id"], "guest-game"]
    assert [(g.away.guest, g.home.guest) for g in games] == [
        (False, False),
        (False, True),
    ]


@pytest.mark.anyio
async def test_maps_a_team_without_an_abbreviation_to_a_guest_side_with_a_null_code(
    mock: respx.MockRouter, settings: Settings
) -> None:
    game = event(load("day.json"), "STATUS_FINAL")
    guest_side(game)
    team = game["competitions"][0]["competitors"][0]["team"]
    del team["abbreviation"]
    team["id"] = "90001"
    mock.get(URL).respond(json=only(game))

    [mapped] = await fetch(settings)

    [guest] = [side for side in (mapped.away, mapped.home) if side.guest]
    assert (guest.code, guest.name, guest.city) == (None, "Mariners", "Harbor City")


@pytest.mark.anyio
async def test_maps_a_team_without_an_abbreviation_to_a_league_side_by_its_provider_id(
    mock: respx.MockRouter, settings: Settings
) -> None:
    game = event(load("day.json"), "STATUS_FINAL")
    team = game["competitions"][0]["competitors"][0]["team"]
    del team["abbreviation"]
    team["id"] = "9"
    mock.get(URL).respond(json=only(game))

    [mapped] = await fetch(settings)

    sides = [side for side in (mapped.away, mapped.home) if side.code == "GSW"]
    assert [side.guest for side in sides] == [False]


@pytest.mark.anyio
async def test_skips_a_game_with_a_side_that_has_neither_a_code_nor_a_name(
    mock: respx.MockRouter, settings: Settings
) -> None:
    day = load("day.json")
    nobody = event(day, "STATUS_FINAL")
    nobody["id"] = "nobody"
    team = nobody["competitions"][0]["competitors"][0]["team"]
    del team["abbreviation"]
    del team["name"]
    first = event(day, "STATUS_FINAL")
    last = event(day, "STATUS_FINAL")
    last["id"] = "last"
    mock.get(URL).respond(json=only(first, nobody, last))

    games = await fetch(settings)

    assert [g.id for g in games] == [first["id"], "last"]


@pytest.mark.anyio
async def test_raises_the_source_error_on_a_guest_code_equal_to_a_league_code(
    mock: respx.MockRouter, settings: Settings
) -> None:
    game = event(load("day.json"), "STATUS_FINAL")
    game["competitions"][0]["competitors"][0]["team"]["abbreviation"] = "GSW"
    mock.get(URL).respond(json=only(game))

    error = await fetch_error(settings)

    assert error.reason == "guest team code 'GSW' is a league team code"


@pytest.mark.anyio
async def test_keeps_a_guest_code_outside_the_usual_pattern_as_it_is(
    mock: respx.MockRouter, settings: Settings
) -> None:
    game = event(load("day.json"), "STATUS_FINAL")
    game["competitions"][0]["competitors"][0]["team"]["abbreviation"] = "harbor city"
    mock.get(URL).respond(json=only(game))

    [fetched] = await fetch(settings)

    assert fetched.home.code == "harbor city"
    assert fetched.home.guest is True


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
    ("field", "location"), [("name", "home.name"), ("location", "home")]
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


def clocked(tmp_path: Path, clock: list[dt.datetime]) -> SourceClient:
    store = StateStore(tmp_path)
    store.migrate()
    return create_client(store, clock=lambda: clock[0])


@pytest.mark.anyio
async def test_reuses_a_fetched_day_for_thirty_seconds(
    mock: respx.MockRouter, settings: Settings, tmp_path: Path
) -> None:
    start = dt.datetime(2026, 1, 10, 12, 0, tzinfo=dt.UTC)
    clock = [start]
    route = mock.get(URL).respond(json=load("day.json"))
    async with clocked(tmp_path, clock) as client:
        await fetch_games(client, DAY, settings)
        clock[0] = start + dt.timedelta(seconds=30) - dt.timedelta(seconds=1)
        await fetch_games(client, DAY, settings)
        assert route.call_count == 1
        clock[0] = start + dt.timedelta(seconds=30)
        await fetch_games(client, DAY, settings)

    assert route.call_count == 2


@pytest.mark.anyio
async def test_marks_a_game_with_the_cup_round_of_its_note(
    mock: respx.MockRouter, settings: Settings
) -> None:
    mock.get(URL).respond(json=load("cup.json"))

    games = await fetch(settings)

    assert [g.cup.stage if g.cup else None for g in games] == [
        CupRound.GROUP,
        CupRound.QUARTERFINALS,
        CupRound.SEMIFINALS,
        CupRound.CHAMPIONSHIP,
        None,
        None,
        CupRound.SEMIFINALS,
    ]


@pytest.mark.anyio
async def test_leaves_a_game_without_notes_unmarked(
    mock: respx.MockRouter, settings: Settings
) -> None:
    mock.get(URL).respond(json=load("day.json"))

    assert all(game.cup is None for game in await fetch(settings))


@pytest.mark.anyio
async def test_marks_the_play_in_and_playoff_games_of_a_day_with_their_postseason_mark(
    mock: respx.MockRouter, settings: Settings
) -> None:
    mock.get(URL).respond(json=load("play-in.json"))
    play_in = await fetch(settings)
    mock.get(URL).respond(json=load("playoffs.json"))
    playoffs = await fetch(settings)

    first, second = play_in[0].postseason, play_in[1].postseason
    assert first is not None and second is not None
    assert (first.conference, first.play_in, first.stakes) == (
        "east",
        "seven_eight",
        None,
    )
    assert (second.conference, second.play_in, second.stakes) == (
        "west",
        "nine_ten",
        Stakes.ELIMINATION,
    )
    round_one, semifinal, finals = (g.postseason for g in playoffs)
    assert round_one is not None and semifinal is not None and finals is not None
    assert (round_one.round, round_one.conference, round_one.number) == (1, "east", 1)
    assert round_one.summary == "CLE leads series 1-0" and round_one.stakes is None
    assert semifinal.summary is None and semifinal.stakes is None
    assert (finals.stage, finals.number, finals.stakes) == (
        PostseasonStage.FINALS,
        6,
        Stakes.CLINCHED,
    )


@pytest.mark.anyio
async def test_marks_each_stake_of_a_recorded_postseason_day(
    mock: respx.MockRouter, settings: Settings
) -> None:
    mock.get(URL).respond(json=load("postseason-marks.json"))

    games = {g.id: g for g in await fetch(settings)}

    game_7, live_game, final_game, play_in = (
        games[i].postseason for i in ("7001", "7002", "7003", "7004")
    )
    assert game_7 is not None and game_7.stakes is Stakes.GAME_7
    assert (game_7.round, game_7.conference, game_7.number) == (3, "west", 7)
    assert live_game is not None and live_game.stakes is Stakes.CAN_CLINCH
    assert final_game is not None and final_game.stakes is Stakes.CAN_CLINCH
    assert final_game.number == 5
    assert play_in is not None and play_in.stakes is Stakes.ELIMINATION


@pytest.mark.anyio
async def test_leaves_a_postseason_game_with_an_unreadable_mark_unmarked_and_keeps_the_day(
    mock: respx.MockRouter, settings: Settings
) -> None:
    payload = load("postseason-marks.json")
    mock.get(URL).respond(json=payload)

    games = await fetch(settings)

    assert [g.id for g in games] == [e["id"] for e in payload["events"]]
    unmarked = {g.id for g in games if g.postseason is None}
    assert unmarked == {"7005", "7006", "7007", "7008", "7009", games[-1].id}


@pytest.mark.anyio
async def test_leaves_a_regular_game_unmarked(
    mock: respx.MockRouter, settings: Settings
) -> None:
    mock.get(URL).respond(json=load("day.json"))

    assert all(game.postseason is None for game in await fetch(settings))


async def unreadable_mark(
    mock: respx.MockRouter,
    settings: Settings,
    caplog: pytest.LogCaptureFixture,
    event_id: str,
) -> None:
    payload = load("postseason-marks.json")
    mock.get(URL).respond(json=payload)

    with caplog.at_level(logging.WARNING, logger="app.sources.scoreboard"):
        games = await fetch(settings)

    assert [g.id for g in games] == [e["id"] for e in payload["events"]]
    game = next(g for g in games if g.id == event_id)
    assert game.postseason is None
    assert (game.venue, game.status) == ("Example Arena", GameStatus.SCHEDULED)
    warned = [r for r in caplog.records if event_id in r.getMessage()]
    assert len(warned) == 1
    assert warned[0].getMessage() == (
        f"scoreboard: event {event_id} has an unreadable postseason mark"
    )


@pytest.mark.anyio
async def test_a_malformed_series_object_gives_a_null_mark_and_the_day_still_builds(
    mock: respx.MockRouter, settings: Settings, caplog: pytest.LogCaptureFixture
) -> None:
    await unreadable_mark(mock, settings, caplog, "7007")


@pytest.mark.anyio
async def test_an_unknown_series_competitor_id_gives_a_null_mark_and_the_day_still_builds(
    mock: respx.MockRouter, settings: Settings, caplog: pytest.LogCaptureFixture
) -> None:
    await unreadable_mark(mock, settings, caplog, "7008")


@pytest.mark.anyio
async def test_a_postseason_game_without_a_note_gives_a_null_mark_and_the_day_still_builds(
    mock: respx.MockRouter, settings: Settings, caplog: pytest.LogCaptureFixture
) -> None:
    await unreadable_mark(mock, settings, caplog, "7009")


@pytest.mark.anyio
async def test_an_unknown_competition_type_gives_a_null_mark_and_the_day_still_builds(
    mock: respx.MockRouter, settings: Settings, caplog: pytest.LogCaptureFixture
) -> None:
    await unreadable_mark(mock, settings, caplog, "7005")


@pytest.mark.anyio
async def test_a_regular_season_game_logs_nothing_for_the_mark(
    mock: respx.MockRouter, settings: Settings, caplog: pytest.LogCaptureFixture
) -> None:
    mock.get(URL).respond(json=load("day.json"))

    with caplog.at_level(logging.WARNING, logger="app.sources.scoreboard"):
        await fetch(settings)

    assert caplog.records == []


def test_the_lenient_mark_reads_every_field_the_strict_postseason_shapes_read() -> None:
    pairs: list[tuple[type[BaseModel], type[BaseModel]]] = [
        (
            scoreboard._MarkCompetitionType,
            postseason_scoreboard._ProviderCompetitionType,
        ),
        (
            scoreboard._MarkSeriesCompetitor,
            postseason_scoreboard._ProviderSeriesCompetitor,
        ),
        (scoreboard._MarkSeries, postseason_scoreboard._ProviderSeries),
        (scoreboard._MarkSeason, postseason_scoreboard._ProviderSeason),
    ]
    used = {"abbreviation", "type", "summary", "competitors", "id", "wins"}

    for lenient, strict in pairs:
        read = used & set(strict.model_fields)
        assert read <= set(lenient.model_fields)
        assert read
    postseason_competition = postseason_scoreboard._PostseasonCompetition
    postseason_event = postseason_scoreboard._PostseasonEvent
    assert {"type", "series"} <= set(postseason_competition.model_fields)
    assert {"type", "series"} <= set(scoreboard._ProviderCompetition.model_fields)
    assert "season" in postseason_event.model_fields
    assert "season" in scoreboard._ProviderEvent.model_fields


@pytest.mark.parametrize("name", ["playoffs.json", "play-in.json"])
def test_the_playoffs_adapter_path_reads_the_same_mark_as_the_core_path_and_logs_nothing(
    name: str, caplog: pytest.LogCaptureFixture
) -> None:
    payload = load(name)
    core = scoreboard._ProviderScoreboard.model_validate(payload)
    strict = postseason_scoreboard._PostseasonScoreboard.model_validate(payload)
    assert len(core.events) == len(strict.events) > 0

    with caplog.at_level(logging.WARNING, logger="app.sources.scoreboard"):
        expected = [scoreboard._map_event(event) for event in core.events]
        caplog.clear()
        actual = [scoreboard._map_event(event) for event in strict.events]

    assert caplog.records == []
    assert all(game is not None and game.postseason for game in actual)
    assert [g.postseason for g in actual if g] == [g.postseason for g in expected if g]


def all_star_event(payload: Payload, event_id: str) -> Payload:
    found: Payload = next(e for e in payload["events"] if e["id"] == event_id)
    return found


def all_star_sides(game: Payload) -> list[Payload]:
    sides: list[Payload] = game["competitions"][0]["competitors"]
    return sides


@pytest.mark.anyio
async def test_maps_an_all_star_day_with_marks_and_guest_sides(
    mock: respx.MockRouter, settings: Settings
) -> None:
    payload = load("all-star.json")
    mock.get(URL).respond(json=payload)

    games = {g.id: g for g in await fetch(settings)}

    assert list(games) == ["9100", "9101", "9102"]
    for event_id in ("9101", "9102"):
        sides = all_star_sides(all_star_event(payload, event_id))
        assert all(s["team"]["location"] for s in sides)
    robin, semi = games["9101"], games["9102"]
    assert robin.all_star is not None
    assert (robin.all_star.round_label, robin.all_star.championship) == (
        "Round Robin",
        False,
    )
    assert semi.all_star is not None
    assert (semi.all_star.round_label, semi.all_star.championship) == (
        "Semifinals",
        False,
    )
    for side in (robin.home, robin.away, semi.home, semi.away):
        assert side.guest is True
        assert side.city is None
    assert (robin.away.code, robin.away.name) == ("STR", "Team Stripes")
    assert (robin.home.code, robin.home.name) == ("WAV", "Team Waves")
    assert robin.score is not None
    assert (robin.score.away, robin.score.home) == (21, 18)


@pytest.mark.anyio
async def test_an_all_star_side_with_only_a_name_is_a_guest_without_a_code(
    mock: respx.MockRouter, settings: Settings
) -> None:
    payload = load("all-star.json")
    team = all_star_sides(all_star_event(payload, "9101"))[1]["team"]
    del team["abbreviation"], team["id"]
    mock.get(URL).respond(json=payload)

    robin = next(g for g in await fetch(settings) if g.id == "9101")

    assert robin.away.code is None
    assert robin.away.name == "Team Stripes"
    assert robin.away.guest is True
    assert robin.away.city is None


@pytest.mark.anyio
async def test_the_league_game_of_an_all_star_day_has_no_mark_and_keeps_its_city(
    mock: respx.MockRouter, settings: Settings
) -> None:
    mock.get(URL).respond(json=load("all-star.json"))

    league = (await fetch(settings))[0]

    assert league.all_star is None
    assert (league.home.city, league.away.city) == ("Charlotte", "Detroit")
    assert league.score is not None
    assert (league.score.home, league.score.away) == (100, 118)


@pytest.mark.anyio
@pytest.mark.parametrize("case", ["both sides", "one side", "empty strings"])
async def test_skips_an_all_star_game_with_a_side_without_a_code_or_a_name_and_keeps_the_others(
    mock: respx.MockRouter,
    settings: Settings,
    caplog: pytest.LogCaptureFixture,
    case: str,
) -> None:
    payload = load("all-star.json")
    skipped = "9103"
    if case == "one side":
        skipped = "9101"
        all_star_sides(all_star_event(payload, "9101"))[1]["team"] = {"id": "901"}
    if case == "empty strings":
        for side in all_star_sides(all_star_event(payload, "9103")):
            side["team"] = {"id": "0", "abbreviation": "", "name": ""}
    mock.get(URL).respond(json=payload)

    with caplog.at_level(logging.WARNING, logger="app.sources.scoreboard"):
        games = await fetch(settings)

    expected = [e["id"] for e in payload["events"] if e["id"] != skipped]
    if case == "one side":
        expected = ["9100", "9102"]
    assert [g.id for g in games] == expected
    assert [r for r in caplog.records if r.name == "app.sources.scoreboard"] == []


@pytest.mark.anyio
async def test_marks_the_championship_when_its_sides_have_a_code_or_a_name(
    mock: respx.MockRouter, settings: Settings
) -> None:
    payload = load("all-star.json")
    stripes, waves = all_star_sides(all_star_event(payload, "9101"))
    sides = all_star_sides(all_star_event(payload, "9103"))
    sides[0]["team"] = copy.deepcopy(stripes["team"])
    sides[1]["team"] = copy.deepcopy(waves["team"])
    mock.get(URL).respond(json=payload)

    final = next(g for g in await fetch(settings) if g.id == "9103")

    assert final.all_star is not None
    assert final.all_star.round_label == "Championship"
    assert final.all_star.championship is True


@pytest.mark.anyio
@pytest.mark.parametrize(
    "season", [{"type": "regular"}, "regular", 7], ids=["text", "string", "number"]
)
async def test_an_unreadable_season_is_not_all_star_and_the_day_is_read(
    mock: respx.MockRouter, settings: Settings, season: Any
) -> None:
    payload = load("all-star.json")
    league = all_star_event(payload, "9100")
    league["season"] = season
    mock.get(URL).respond(json=only(league))

    games = await fetch(settings)

    assert [g.id for g in games] == ["9100"]
    assert games[0].all_star is None


@pytest.mark.anyio
async def test_an_unreadable_competition_type_is_not_all_star_and_the_day_is_read(
    mock: respx.MockRouter, settings: Settings
) -> None:
    payload = load("all-star.json")
    league = all_star_event(payload, "9100")
    league["competitions"][0]["type"] = "ALLSTAR"
    mock.get(URL).respond(json=only(league))

    games = await fetch(settings)

    assert [g.id for g in games] == ["9100"]
    assert games[0].all_star is None


@pytest.mark.anyio
async def test_a_regular_game_without_the_all_star_flag_is_unaffected(
    mock: respx.MockRouter, settings: Settings
) -> None:
    mock.get(URL).respond(json=load("day.json"))

    games = await fetch(settings)

    assert len(games) == 6
    assert all(g.all_star is None for g in games)


async def skipped_all_star(
    mock: respx.MockRouter,
    settings: Settings,
    caplog: pytest.LogCaptureFixture,
    payload: Payload,
    event_id: str,
) -> str:
    mock.get(URL).respond(json=payload)

    with caplog.at_level(logging.WARNING, logger="app.sources.scoreboard"):
        games = await fetch(settings)

    expected = [e["id"] for e in payload["events"] if e["id"] != event_id]
    expected = [i for i in expected if i != "9103"]
    assert [g.id for g in games] == expected
    warned = [r for r in caplog.records if r.name == "app.sources.scoreboard"]
    assert len(warned) == 1
    message = warned[0].getMessage()
    assert message.startswith(f"scoreboard: All-Star event {event_id} skipped: ")
    return message


@pytest.mark.anyio
async def test_skips_a_final_all_star_game_without_a_line_score(
    mock: respx.MockRouter, settings: Settings, caplog: pytest.LogCaptureFixture
) -> None:
    payload = load("all-star.json")
    for side in all_star_sides(all_star_event(payload, "9101")):
        del side["linescores"]

    message = await skipped_all_star(mock, settings, caplog, payload, "9101")

    assert "is invalid: value_error" in message


@pytest.mark.anyio
async def test_skips_a_live_all_star_game_without_a_clock(
    mock: respx.MockRouter, settings: Settings, caplog: pytest.LogCaptureFixture
) -> None:
    payload = load("all-star.json")
    game = all_star_event(payload, "9101")
    game["status"] = {"period": 1, "type": {"name": "STATUS_IN_PROGRESS"}}

    message = await skipped_all_star(mock, settings, caplog, payload, "9101")

    assert "is invalid: value_error" in message


@pytest.mark.anyio
async def test_skips_an_all_star_game_with_a_side_code_the_league_owns(
    mock: respx.MockRouter, settings: Settings, caplog: pytest.LogCaptureFixture
) -> None:
    payload = load("all-star.json")
    team = all_star_sides(all_star_event(payload, "9101"))[0]["team"]
    team["abbreviation"] = "GSW"
    team["id"] = "901"

    message = await skipped_all_star(mock, settings, caplog, payload, "9101")

    assert "is a league team code" in message


@pytest.mark.anyio
async def test_skips_an_all_star_game_with_a_provider_key_side_without_a_city(
    mock: respx.MockRouter, settings: Settings, caplog: pytest.LogCaptureFixture
) -> None:
    payload = load("all-star.json")
    team = all_star_sides(all_star_event(payload, "9101"))[0]["team"]
    team["abbreviation"] = "LAL"
    del team["id"]

    message = await skipped_all_star(mock, settings, caplog, payload, "9101")

    assert "is invalid" in message


@pytest.mark.anyio
async def test_skips_an_all_star_game_whose_note_is_not_an_all_star_note(
    mock: respx.MockRouter, settings: Settings, caplog: pytest.LogCaptureFixture
) -> None:
    payload = load("all-star.json")
    all_star_event(payload, "9101")["competitions"][0]["notes"] = [
        {"headline": "Exhibition"}
    ]

    message = await skipped_all_star(mock, settings, caplog, payload, "9101")

    assert "unreadable All-Star mark" in message


@pytest.mark.anyio
async def test_skips_an_all_star_game_with_an_unknown_status(
    mock: respx.MockRouter, settings: Settings, caplog: pytest.LogCaptureFixture
) -> None:
    payload = load("all-star.json")
    all_star_event(payload, "9101")["status"]["type"]["name"] = "STATUS_UNKNOWN"

    message = await skipped_all_star(mock, settings, caplog, payload, "9101")

    assert "unknown game status" in message


@pytest.mark.anyio
async def test_an_event_without_a_competition_still_raises_the_source_error(
    mock: respx.MockRouter, settings: Settings
) -> None:
    payload = load("all-star.json")
    league = all_star_event(payload, "9100")
    league["competitions"] = []
    mock.get(URL).respond(json=only(league))

    error = await fetch_error(settings)

    assert error.reason == "game 9100 has no competition"
