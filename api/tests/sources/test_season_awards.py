# api/tests/sources/test_season_awards.py
#
# Tests for the season awards adapter.
#
# Tested:
# - Maps each listed award name to its code and team number, ignoring case
# - Keeps the winners of a team award in order, and a winner with no team link has a null team
# - Skips an award with no winners without a log
# - Skips an unknown award name with winners and logs its name only
# - Maps an empty list of awards to no awards
# - Raises the source error on a link without an id, an unknown team id, an invalid payload, a timeout, an error status and a missing URL
# - Reuses a read for one hour
#
# What is covered:
# - Valid responses mapped, invalid payloads rejected, upstream failures handled
#
# The fixtures are made-up payloads of the shape docs/api/playoffs.md documents.
#
# Run with: cd api && .venv/bin/python -m pytest tests/sources/test_season_awards.py
#
# SEE: api/app/sources/season_awards.py

import datetime as dt
import json
import logging
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx

from app.feeds.playoffs import AwardCode
from app.settings import Settings
from app.sources.http import SourceError, create_client
from app.sources.season_awards import AWARDS, SeasonAwards, fetch_season_awards
from app.storage.state import StateStore

FIXTURES = Path(__file__).parent / "fixtures" / "season_awards"
TEMPLATE = "https://example.com/{season}/awards"
URL = "https://example.com/2027/awards"

Payload = dict[str, Any]


def load(name: str) -> Payload:
    payload: Payload = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    return payload


@pytest.fixture
def settings() -> Settings:
    return Settings(_env_file=None, season_awards_url=TEMPLATE)  # type: ignore[call-arg]


@pytest.fixture
def mock() -> Iterator[respx.MockRouter]:
    with respx.mock as router:
        yield router


async def awards(settings: Settings, tmp_path: Path) -> SeasonAwards:
    store = StateStore(tmp_path)
    store.migrate()
    async with create_client(store) as client:
        return await fetch_season_awards(client, 2027, settings)


@pytest.mark.anyio
async def test_maps_each_listed_award_name_to_its_code_and_team_number(
    mock: respx.MockRouter, settings: Settings, tmp_path: Path
) -> None:
    route = mock.get(URL).respond(json=load("awards.json"))

    result = await awards(settings, tmp_path)

    assert route.call_count == 1
    assert [(a.code, a.team) for a in result.awards] == [
        (AwardCode.MVP, None),
        (AwardCode.DPOY, None),
        (AwardCode.ROY, None),
        (AwardCode.SIXTH_MAN, None),
        (AwardCode.MIP, None),
        (AwardCode.CPOY, None),
        (AwardCode.FINALS_MVP, None),
        (AwardCode.EAST_FINALS_MVP, None),
        (AwardCode.WEST_FINALS_MVP, None),
        (AwardCode.ALL_STAR_MVP, None),
        (AwardCode.CUP_MVP, None),
        (AwardCode.CUP_ALL_TOURNAMENT, None),
        (AwardCode.ALL_NBA, 1),
        (AwardCode.ALL_NBA, 2),
        (AwardCode.ALL_NBA, 3),
        (AwardCode.ALL_ROOKIE, 1),
        (AwardCode.ALL_ROOKIE, 2),
        (AwardCode.ALL_DEFENSIVE, 1),
        (AwardCode.ALL_DEFENSIVE, 2),
        (AwardCode.TWYMAN_STOKES, None),
    ]


def test_the_table_has_a_lower_case_name_for_every_award_code() -> None:
    assert all(name == name.casefold() for name in AWARDS)
    assert {code for code, _ in AWARDS.values()} == set(AwardCode)


@pytest.mark.anyio
async def test_keeps_the_winners_of_a_team_award_in_order_with_their_teams(
    mock: respx.MockRouter, settings: Settings, tmp_path: Path
) -> None:
    mock.get(URL).respond(json=load("awards.json"))

    result = await awards(settings, tmp_path)

    first_team = next(
        a for a in result.awards if a.code is AwardCode.ALL_NBA and a.team == 1
    )
    assert [w.player_id for w in first_team.winners] == ["31", "32", "33", "34", "35"]
    assert [w.team_code for w in first_team.winners] == [
        "ATL",
        "BOS",
        "NOP",
        "CHI",
        "CLE",
    ]


@pytest.mark.anyio
async def test_a_winner_without_a_team_link_has_a_null_team(
    mock: respx.MockRouter, settings: Settings, tmp_path: Path
) -> None:
    mock.get(URL).respond(json=load("awards.json"))

    result = await awards(settings, tmp_path)

    second_team = next(
        a for a in result.awards if a.code is AwardCode.ALL_NBA and a.team == 2
    )
    assert second_team.winners[-1].team_code is None


@pytest.mark.anyio
async def test_skips_an_award_with_no_winners_without_a_log(
    mock: respx.MockRouter,
    settings: Settings,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    mock.get(URL).respond(json=load("awards.json"))

    with caplog.at_level(logging.WARNING):
        await awards(settings, tmp_path)

    assert "Coach of the Year" not in caplog.text


@pytest.mark.anyio
async def test_skips_an_unknown_award_with_winners_and_logs_its_name_only(
    mock: respx.MockRouter,
    settings: Settings,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    mock.get(URL).respond(json=load("awards.json"))

    with caplog.at_level(logging.WARNING):
        result = await awards(settings, tmp_path)

    assert "season awards: unknown award 'Best Example Award'" in caplog.text
    assert "99" not in caplog.text
    assert len(result.awards) == 20


@pytest.mark.anyio
async def test_maps_an_empty_list_of_awards_to_no_awards(
    mock: respx.MockRouter, settings: Settings, tmp_path: Path
) -> None:
    mock.get(URL).respond(json=load("empty.json"))

    assert (await awards(settings, tmp_path)).awards == []


@pytest.mark.anyio
async def test_raises_the_source_error_on_a_link_without_an_id(
    mock: respx.MockRouter, settings: Settings, tmp_path: Path
) -> None:
    payload = load("awards.json")
    payload["awards"][0]["winners"][0]["athlete"]["$ref"] = "https://example.com/v2/x"
    mock.get(URL).respond(json=payload)

    with pytest.raises(SourceError) as raised:
        await awards(settings, tmp_path)

    assert raised.value.reason == "athlete link has no athlete id"


@pytest.mark.anyio
async def test_raises_the_source_error_on_an_unknown_team_id(
    mock: respx.MockRouter, settings: Settings, tmp_path: Path
) -> None:
    payload = load("awards.json")
    payload["awards"][0]["winners"][0]["team"]["$ref"] = (
        "https://example.com/v2/teams/999"
    )
    mock.get(URL).respond(json=payload)

    with pytest.raises(SourceError) as raised:
        await awards(settings, tmp_path)

    assert raised.value.reason == "unknown team id '999'"


@pytest.mark.anyio
@pytest.mark.parametrize(
    "payload",
    [[], {}, {"awards": 3}, {"awards": [{"name": "MVP", "winners": [{}]}]}],
    ids=str,
)
async def test_raises_the_source_error_on_an_invalid_payload(
    mock: respx.MockRouter, settings: Settings, tmp_path: Path, payload: Any
) -> None:
    mock.get(URL).respond(json=payload)

    with pytest.raises(SourceError) as raised:
        await awards(settings, tmp_path)

    assert raised.value.reason.startswith("invalid payload: ")


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
    mock: respx.MockRouter,
    settings: Settings,
    tmp_path: Path,
    fails: Any,
    reason: str,
) -> None:
    fails(mock.get(URL))

    with pytest.raises(SourceError) as raised:
        await awards(settings, tmp_path)

    assert raised.value.reason == reason


@pytest.mark.anyio
async def test_raises_the_source_error_when_the_url_is_not_configured(
    tmp_path: Path,
) -> None:
    unset = Settings(_env_file=None)  # type: ignore[call-arg]
    with respx.mock, pytest.raises(SourceError) as raised:
        await awards(unset, tmp_path)

    assert raised.value.reason == "season awards URL is not configured"


@pytest.mark.anyio
async def test_reuses_a_read_for_one_hour(
    mock: respx.MockRouter, settings: Settings, tmp_path: Path
) -> None:
    start = dt.datetime(2027, 6, 1, 12, 0, tzinfo=dt.UTC)
    clock = [start]
    route = mock.get(URL).respond(json=load("awards.json"))
    store = StateStore(tmp_path)
    store.migrate()
    async with create_client(store, clock=lambda: clock[0]) as client:
        await fetch_season_awards(client, 2027, settings)
        clock[0] = start + dt.timedelta(hours=1) - dt.timedelta(seconds=1)
        await fetch_season_awards(client, 2027, settings)
        assert route.call_count == 1
        clock[0] = start + dt.timedelta(hours=1)
        await fetch_season_awards(client, 2027, settings)

    assert route.call_count == 2
