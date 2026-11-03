# api/tests/sources/test_news.py
#
# Tests for the news adapter.
#
# Tested:
# - Maps a recorded English list to notes: keeps headline news, story and recap
#   and drops preview, media and premium notes
# - Keeps dStory and drops media in the Spanish list
# - Marks Recap and BasketballRecap notes as recaps and the rest as news
# - Takes the first header image, else the first image, else none; keeps a null credit
# - Trims a leading dash and the spaces from the description
# - Maps team codes from team ids (an unknown id is skipped), players with names
#   and the game id of the event category
# - Converts the published time to UTC
# - Keeps no link: the provider's link URL appears nowhere in the notes
# - Merges the Spanish parameters into the URL's own query, and sends none in English
# - Adds the team to the query in lower case
# - Reads the summary recap from the game detail URL, Spanish with its parameters
# - Returns no recap for a summary with no article, a non-recap type or a premium one
# - Names the recap recap-{gameId} with the given time and teams and no players
# - Raises the source error on a list without articles, a timeout, an error status
#   and an unset URL (with no request); skips one invalid article and keeps the rest
#
# What is covered:
# - A valid response mapped, an invalid payload rejected, upstream failures handled
#
# The fixtures are invented: teams, players and headlines are made up, every URL
# is on example.com, and the articles carry links so the tests can prove they are
# dropped.
#
# Run with: cd api && .venv/bin/python -m pytest tests/sources/test_news.py
#
# SEE: api/app/sources/news.py

import datetime as dt
import json
from collections.abc import Iterator
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import httpx
import pytest
import respx

from app.feeds.news import NewsKind, NewsLanguage, NewsNote
from app.settings import Settings
from app.sources.http import SourceError, create_client
from app.sources.news import fetch_game_recap, fetch_news_list
from app.storage.state import StateStore

FIXTURES = Path(__file__).parent / "fixtures" / "news"
URL = "https://example.com/news?sport=x"
DETAIL = "https://example.com/summary/{game_id}"
Payload = dict[str, Any]
EN = NewsLanguage.EN
ES = NewsLanguage.ES
START = dt.datetime(2026, 11, 3, 0, 0, tzinfo=dt.UTC)


def load(name: str) -> Payload:
    payload: Payload = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    return payload


@pytest.fixture
def settings() -> Settings:
    return Settings(  # type: ignore[call-arg]
        _env_file=None, news_url=URL, game_detail_url=DETAIL
    )


@pytest.fixture
def mock() -> Iterator[respx.MockRouter]:
    with respx.mock as router:
        yield router


async def listing(
    settings: Settings, language: NewsLanguage = EN, team: str | None = None
) -> list[NewsNote]:
    with TemporaryDirectory() as directory:
        store = StateStore(Path(directory))
        store.migrate()
        async with create_client(store) as client:
            return await fetch_news_list(client, settings, language, team)


async def recap(settings: Settings, language: NewsLanguage = EN) -> NewsNote | None:
    with TemporaryDirectory() as directory:
        store = StateStore(Path(directory))
        store.migrate()
        async with create_client(store) as client:
            return await fetch_game_recap(
                client,
                settings,
                "401",
                language,
                published=START,
                teams=["BOS", "NYK"],
            )


def english_route(mock: respx.MockRouter) -> respx.Route:
    return mock.get(
        "https://example.com/news", params={"sport": "x", "limit": "50"}
    ).respond(json=load("list-en.json"))


def by_id(notes: list[NewsNote]) -> dict[str, NewsNote]:
    return {note.id: note for note in notes}


@pytest.mark.anyio
async def test_maps_an_english_list_and_drops_the_types_it_does_not_keep(
    mock: respx.MockRouter, settings: Settings
) -> None:
    english_route(mock)

    notes = await listing(settings)

    assert [note.id for note in notes] == ["9001", "9002", "9003", "9007"]
    assert {note.language for note in notes} == {EN}


@pytest.mark.anyio
async def test_keeps_dstory_and_drops_media_in_the_spanish_list(
    mock: respx.MockRouter, settings: Settings
) -> None:
    mock.get("https://example.com/news").respond(json=load("list-es.json"))

    notes = await listing(settings, ES)

    assert [note.id for note in notes] == ["8001"]
    assert notes[0].language is ES


@pytest.mark.anyio
async def test_marks_recaps_and_news(
    mock: respx.MockRouter, settings: Settings
) -> None:
    english_route(mock)

    notes = by_id(await listing(settings))

    assert notes["9003"].kind is NewsKind.RECAP
    assert notes["9001"].kind is NewsKind.NEWS
    assert notes["9002"].kind is NewsKind.NEWS


@pytest.mark.anyio
async def test_takes_the_header_image_else_the_first_image_else_none(
    mock: respx.MockRouter, settings: Settings
) -> None:
    english_route(mock)

    notes = by_id(await listing(settings))

    header = notes["9001"].photo
    assert header is not None
    assert str(header.url) == "https://example.com/a-wide.jpg"
    assert (header.width, header.height, header.credit) == (1296, 729, "Example Press")
    first = notes["9002"].photo
    assert first is not None
    assert str(first.url) == "https://example.com/b-small.jpg"
    assert first.credit is None
    assert notes["9003"].photo is None
    nameless = notes["9007"].photo
    assert nameless is not None
    assert nameless.credit is None


@pytest.mark.anyio
async def test_trims_a_leading_dash_and_the_spaces_from_the_description(
    mock: respx.MockRouter, settings: Settings
) -> None:
    english_route(mock)

    notes = by_id(await listing(settings))

    assert notes["9001"].headline == "Tigers top Bears in overtime"
    assert notes["9001"].description == "Ana Lee scored 32 as Boston won."


@pytest.mark.anyio
async def test_maps_teams_players_and_the_game(
    mock: respx.MockRouter, settings: Settings
) -> None:
    english_route(mock)

    notes = by_id(await listing(settings))

    assert notes["9001"].teams == ["BOS", "NYK"]
    assert [(p.player_id, p.name) for p in notes["9001"].players] == [
        ("111", "Ana Lee"),
        ("222", "Bo Chen"),
    ]
    assert notes["9001"].game_id == "401"
    assert notes["9002"].teams == ["BOS"]
    assert notes["9007"].game_id is None
    assert notes["9007"].teams == []


@pytest.mark.anyio
async def test_converts_the_published_time_to_utc(
    mock: respx.MockRouter, settings: Settings
) -> None:
    english_route(mock)

    notes = by_id(await listing(settings))

    assert notes["9002"].published == dt.datetime(2026, 11, 3, 1, 0, tzinfo=dt.UTC)
    assert notes["9002"].published.utcoffset() == dt.timedelta(0)


@pytest.mark.anyio
async def test_keeps_no_link(mock: respx.MockRouter, settings: Settings) -> None:
    english_route(mock)

    notes = await listing(settings)

    dumped = json.dumps([note.model_dump(mode="json") for note in notes])
    assert "example.com/story" not in dumped
    assert "links" not in dumped


@pytest.mark.anyio
async def test_merges_the_spanish_parameters_into_the_urls_own_query(
    mock: respx.MockRouter, settings: Settings
) -> None:
    route = mock.get(
        "https://example.com/news?sport=x&limit=50&team=gsw&lang=es&region=us"
    ).respond(json=load("list-es.json"))

    await listing(settings, ES, "GSW")

    assert route.call_count == 1
    assert str(route.calls[0].request.url) == (
        "https://example.com/news?sport=x&limit=50&team=gsw&lang=es&region=us"
    )


@pytest.mark.anyio
async def test_sends_no_language_in_english(
    mock: respx.MockRouter, settings: Settings
) -> None:
    route = english_route(mock)

    await listing(settings)

    assert (
        str(route.calls[0].request.url) == "https://example.com/news?sport=x&limit=50"
    )


@pytest.mark.anyio
async def test_reads_the_english_summary_recap_from_the_game_detail_url(
    mock: respx.MockRouter, settings: Settings
) -> None:
    route = mock.get("https://example.com/summary/401").respond(
        json=load("summary-recap-en.json")
    )

    note = await recap(settings)

    assert route.call_count == 1
    assert str(route.calls[0].request.url) == "https://example.com/summary/401"
    assert note is not None
    assert note.headline == "Tigers outlast Bears"
    assert note.description == "Boston closed on a run."
    assert note.photo is not None


@pytest.mark.anyio
async def test_reads_the_spanish_summary_recap_with_its_parameters(
    mock: respx.MockRouter, settings: Settings
) -> None:
    route = mock.get("https://example.com/summary/401?lang=es&region=us").respond(
        json=load("summary-recap-es.json")
    )

    note = await recap(settings, ES)

    assert route.call_count == 1
    assert note is not None
    assert note.language is ES
    assert note.kind is NewsKind.RECAP


@pytest.mark.anyio
async def test_names_the_summary_recap_after_the_game(
    mock: respx.MockRouter, settings: Settings
) -> None:
    mock.get("https://example.com/summary/401").respond(
        json=load("summary-recap-en.json")
    )

    note = await recap(settings)

    assert note is not None
    assert note.id == "recap-401"
    assert note.game_id == "401"
    assert note.published == START
    assert note.teams == ["BOS", "NYK"]
    assert note.players == []
    assert "example.com/story" not in json.dumps(note.model_dump(mode="json"))


def summary_with(article: Payload) -> Payload:
    return {"header": {}, "article": article}


@pytest.mark.anyio
@pytest.mark.parametrize(
    "body",
    [
        load("summary-no-article.json"),
        summary_with({"type": "Story", "headline": "Not a recap"}),
        summary_with({"type": "Recap", "headline": "Paid", "premium": True}),
        summary_with({"type": "Recap", "headline": "  "}),
        summary_with({"type": "Recap", "headline": 3}),
        summary_with({"type": "Recap", "headline": "x", "images": "bad"}),
    ],
    ids=[
        "no article",
        "not a recap",
        "premium",
        "blank headline",
        "bad headline",
        "bad images",
    ],
)
async def test_returns_no_recap_for_a_summary_without_a_usable_one(
    mock: respx.MockRouter, settings: Settings, body: Payload
) -> None:
    mock.get("https://example.com/summary/401").respond(json=body)

    assert await recap(settings) is None


@pytest.mark.anyio
async def test_skips_one_invalid_article_and_keeps_the_rest(
    mock: respx.MockRouter, settings: Settings
) -> None:
    body = load("list-en.json")
    body["articles"].insert(0, {"id": 1, "type": "Story", "published": "not a time"})
    body["articles"].insert(
        1,
        {
            "id": "a/b",
            "type": "Story",
            "headline": "Bad id",
            "published": "2026-11-03T00:00:00Z",
        },
    )
    body["articles"].insert(
        2,
        {
            "id": 3,
            "type": "Story",
            "headline": "  ",
            "published": "2026-11-03T00:00:00Z",
        },
    )
    mock.get("https://example.com/news").respond(json=body)

    notes = await listing(settings)

    assert [note.id for note in notes] == ["9001", "9002", "9003", "9007"]


@pytest.mark.anyio
@pytest.mark.parametrize("body", [{"items": []}, [], {"articles": "x"}])
async def test_rejects_a_list_without_articles(
    mock: respx.MockRouter, settings: Settings, body: object
) -> None:
    mock.get("https://example.com/news").respond(json=body)

    with pytest.raises(SourceError) as raised:
        await listing(settings)

    assert raised.value.source == "news"
    assert "example.com" not in str(raised.value)


@pytest.mark.anyio
async def test_rejects_a_summary_that_is_not_an_object(
    mock: respx.MockRouter, settings: Settings
) -> None:
    mock.get("https://example.com/summary/401").respond(json=[])

    with pytest.raises(SourceError):
        await recap(settings)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "failure", [httpx.ReadTimeout("slow"), httpx.Response(500)], ids=["timeout", "500"]
)
async def test_raises_the_source_error_on_an_upstream_failure(
    mock: respx.MockRouter, settings: Settings, failure: Any
) -> None:
    route = mock.get("https://example.com/news")
    if isinstance(failure, Exception):
        route.mock(side_effect=failure)
    else:
        route.mock(return_value=failure)

    with pytest.raises(SourceError):
        await listing(settings)


@pytest.mark.anyio
async def test_raises_when_a_url_is_unset_and_sends_no_request(
    mock: respx.MockRouter,
) -> None:
    unset = Settings(_env_file=None)  # type: ignore[call-arg]

    with pytest.raises(SourceError):
        await listing(unset)
    with pytest.raises(SourceError):
        await recap(unset)

    assert len(mock.calls) == 0
