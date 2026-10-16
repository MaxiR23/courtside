# api/tests/sources/test_season_awards.py
#
# Tests for the season awards adapter.
#
# Tested:
# - Maps each listed award name to its code and team number, ignoring case; the conference finals MVPs and the Twyman-Stokes award are named as the provider sends them (NBA Eastern Conference Finals MVP, NBA Western Conference Finals MVP, Twyman-Stokes Teammate of the Year Award)
# - Keeps the winners of a team award in order, and a winner with no team link has a null team
# - Skips an award with no winners without a log
# - Skips an unknown award name with winners and logs its name only
# - Maps the paged index and its award documents, including the All-Star MVP and its winner, and a winner whose team link is not a league team (an All-Star side) has a null team
# - Maps an empty index to no awards without reading a document
# - Raises the source error on a link without an id, an invalid index, an invalid award document, a missing award document, a timeout, an error status and a missing URL
# - Reuses the index and the documents for one hour
#
# What is covered:
# - Valid responses mapped, invalid payloads rejected, upstream failures handled
#
# The fixtures are a made-up paged index and award documents of the shape
# docs/api/playoffs.md documents.
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


def load(name: str) -> Any:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def serve(
    mock: respx.MockRouter,
    index: Any = None,
    documents: list[Payload] | None = None,
) -> respx.Route:
    """Register the index and each award document, and return the index route."""
    route = mock.get(URL).respond(json=load("index.json") if index is None else index)
    for document in load("awards.json") if documents is None else documents:
        mock.get(document["$ref"]).respond(json=document)
    return route


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
    route = serve(mock)

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


@pytest.mark.anyio
async def test_maps_the_all_star_mvp_and_its_winner_from_the_index_and_its_award_documents(
    mock: respx.MockRouter, settings: Settings, tmp_path: Path
) -> None:
    serve(mock)

    result = await awards(settings, tmp_path)

    mvp = next(a for a in result.awards if a.code is AwardCode.ALL_STAR_MVP)
    assert mvp.team is None
    assert [(w.player_id, w.team_code) for w in mvp.winners] == [("10", None)]
    requested = [str(call.request.url) for call in mock.calls]
    assert requested == [URL, *(i["$ref"] for i in load("index.json")["items"])]


def test_the_table_has_a_lower_case_name_for_every_award_code() -> None:
    assert all(name == name.casefold() for name in AWARDS)
    assert {code for code, _ in AWARDS.values()} == set(AwardCode)


@pytest.mark.anyio
async def test_keeps_the_winners_of_a_team_award_in_order_with_their_teams(
    mock: respx.MockRouter, settings: Settings, tmp_path: Path
) -> None:
    serve(mock)

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
    serve(mock)

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
    serve(mock)

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
    serve(mock)

    with caplog.at_level(logging.WARNING):
        result = await awards(settings, tmp_path)

    assert "season awards: unknown award 'Best Example Award'" in caplog.text
    assert "99" not in caplog.text
    assert len(result.awards) == 20


@pytest.mark.anyio
async def test_maps_an_empty_list_of_awards_to_no_awards(
    mock: respx.MockRouter, settings: Settings, tmp_path: Path
) -> None:
    serve(mock, load("empty.json"), [])

    assert (await awards(settings, tmp_path)).awards == []


@pytest.mark.anyio
async def test_raises_the_source_error_on_a_link_without_an_id(
    mock: respx.MockRouter, settings: Settings, tmp_path: Path
) -> None:
    documents = load("awards.json")
    documents[0]["winners"][0]["athlete"]["$ref"] = "https://example.com/v2/x"
    serve(mock, documents=documents)

    with pytest.raises(SourceError) as raised:
        await awards(settings, tmp_path)

    assert raised.value.reason == "athlete link has no athlete id"


@pytest.mark.anyio
async def test_a_winner_whose_team_link_is_not_a_league_team_has_a_null_team(
    mock: respx.MockRouter, settings: Settings, tmp_path: Path
) -> None:
    documents = load("awards.json")
    documents[0]["winners"][0]["team"]["$ref"] = "https://example.com/v2/teams/999"
    serve(mock, documents=documents)

    result = await awards(settings, tmp_path)

    assert result.awards[0].winners[0].team_code is None
    assert len(result.awards) == 20


@pytest.mark.anyio
@pytest.mark.parametrize(
    "payload",
    [[], {}, {"items": 3}, {"items": [{}]}],
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
    "document",
    [[], {}, {"winners": []}, {"name": "MVP", "winners": [{}]}],
    ids=str,
)
async def test_raises_the_source_error_on_an_invalid_award_document(
    mock: respx.MockRouter, settings: Settings, tmp_path: Path, document: Any
) -> None:
    serve(mock)
    mock.get(load("awards.json")[0]["$ref"]).respond(json=document)

    with pytest.raises(SourceError) as raised:
        await awards(settings, tmp_path)

    assert raised.value.reason.startswith("invalid award payload: ")


@pytest.mark.anyio
async def test_raises_the_source_error_on_a_missing_award_document(
    mock: respx.MockRouter, settings: Settings, tmp_path: Path
) -> None:
    serve(mock)
    mock.get(load("awards.json")[0]["$ref"]).respond(status_code=404)

    with pytest.raises(SourceError) as raised:
        await awards(settings, tmp_path)

    assert raised.value.reason == "responded with status 404"


@pytest.mark.anyio
async def test_raises_the_source_error_on_a_timeout_of_an_award_document(
    mock: respx.MockRouter, settings: Settings, tmp_path: Path
) -> None:
    serve(mock)
    mock.get(load("awards.json")[0]["$ref"]).mock(side_effect=httpx.ReadTimeout("slow"))

    with pytest.raises(SourceError) as raised:
        await awards(settings, tmp_path)

    assert raised.value.reason == "request timed out"


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
    route = serve(mock)
    first = load("awards.json")[0]["$ref"]

    def document_calls() -> int:
        return sum(str(call.request.url) == first for call in mock.calls)

    store = StateStore(tmp_path)
    store.migrate()
    async with create_client(store, clock=lambda: clock[0]) as client:
        await fetch_season_awards(client, 2027, settings)
        clock[0] = start + dt.timedelta(hours=1) - dt.timedelta(seconds=1)
        await fetch_season_awards(client, 2027, settings)
        assert (route.call_count, document_calls()) == (1, 1)
        clock[0] = start + dt.timedelta(hours=1)
        await fetch_season_awards(client, 2027, settings)

    assert (route.call_count, document_calls()) == (2, 2)
