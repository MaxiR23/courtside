# api/tests/sources/test_video_channel.py
#
# Tests for the video channel adapter.
#
# Tested:
# - Returns the matching video from the first page with one request, with the channel from the item
# - Asks for fifty videos per request, with the key in a header and never in the URL
# - Pages back with the next page token until it finds the video
# - Stops paging at the page with a video older than the game, and at the first page when the game started after its oldest video
# - Returns none when the uploads run out
# - Raises the source error on a body that is not JSON, a missing items list, a missing video id, a missing title, a missing or bad published time and an empty title
# - Raises the source error on a timeout, an error status, a missing URL and a missing or empty key, never with the key or the URL in the reason
# - Never writes the key to any log record
# - Matches a title with both teams, the label and the date, in any letter case
# - Does not match a title missing the label, a team or the date, nor a player clip that says only highlights
# - Does not take a team name inside a longer word
# - Finds the first matching video in order, and none when no title matches
# - Builds the highlight from the templates and keeps the title and channel, and raises the source error when a template is missing or the result is invalid
# - Builds the search URL from the template with the encoded teams, label and date, and none when the template is missing
#
# What is covered:
# - A valid response mapped, an invalid payload rejected, upstream failures handled
# - Paging (page size, token, both stops), key handling (header, error, log)
# - Pure logic: matching (happy path, each missing part, word boundary), URL building
#
# The fixtures are minimal pages of the official uploads listing. No test makes a real request.
#
# Run with: cd api && .venv/bin/python -m pytest tests/sources/test_video_channel.py
#
# SEE: api/app/sources/video_channel.py

import datetime as dt
import logging
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx

from app.feeds.games import GameStatus, Team
from app.settings import Settings
from app.sources.http import SourceError, create_client
from app.sources.scoreboard import ScoreboardGame
from app.sources.video_channel import (
    ChannelVideo,
    find_video,
    lookup_video,
    matches,
    search_url,
    to_highlight,
)

FIXTURES = Path(__file__).parent / "fixtures" / "video_channel"
SOURCE_URL = "https://example.com/uploads?list=example"
KEY = "test-key-value"
DAY = dt.date(2026, 10, 4)
START = dt.datetime(2026, 10, 5, 2, 0, tzinfo=dt.UTC)
TITLE = "WARRIORS at CLIPPERS | PRESEASON FULL GAME HIGHLIGHTS | October 4, 2026"


@pytest.fixture(autouse=True)
def no_network() -> Iterator[None]:
    with respx.mock:
        yield


def make_game(away: str = "Warriors", home: str = "Clippers") -> ScoreboardGame:
    codes = {
        "Warriors": "GSW",
        "Clippers": "LAC",
        "Nets": "BKN",
        "Jazz": "UTA",
        "Nuggets": "DEN",
    }
    return ScoreboardGame(
        id="g1",
        away=Team(code=codes[away], name=away, city="City"),
        home=Team(code=codes[home], name=home, city="City"),
        status=GameStatus.SCHEDULED,
        start_time=START,
        venue="Arena",
    )


def make_settings(**values: Any) -> Settings:
    return Settings(_env_file=None, **values)  # type: ignore[call-arg]


def page(name: str) -> str:
    return (FIXTURES / f"uploads-{name}.json").read_text(encoding="utf-8")


def configured() -> Settings:
    return make_settings(highlights_source_url=SOURCE_URL, highlights_source_key=KEY)


def serve_pages() -> list[httpx.Request]:
    """Serve page 1 without a token and page 2 for page-2. Records the requests."""
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        token = request.url.params.get("pageToken")
        return httpx.Response(
            200, text=page("page-2" if token == "page-2" else "page-1")
        )

    respx.get("https://example.com/uploads").mock(side_effect=handler)
    return seen


async def lookup(
    game: ScoreboardGame, day: dt.date, settings: Settings | None = None
) -> ChannelVideo | None:
    async with create_client() as client:
        return await lookup_video(client, game, day, settings or configured())


async def lookup_error(
    effect: httpx.Response | Exception, settings: Settings | None = None
) -> SourceError:
    route = respx.get("https://example.com/uploads")
    if isinstance(effect, Exception):
        route.mock(side_effect=effect)
    else:
        route.mock(return_value=effect)
    with pytest.raises(SourceError) as raised:
        await lookup(make_game(), DAY, settings)
    return raised.value


@pytest.mark.anyio
async def test_returns_the_matching_video_from_the_first_page_with_one_request() -> (
    None
):
    seen = serve_pages()

    found = await lookup(make_game("Jazz", "Nuggets"), DAY)

    assert found is not None
    assert found.video_id == "vid-other-game"
    assert found.channel == "Example Channel"
    assert len(seen) == 1


@pytest.mark.anyio
async def test_asks_for_fifty_videos_per_request_with_the_key_in_a_header_never_in_the_url() -> (
    None
):
    seen = serve_pages()

    await lookup(make_game(), DAY)

    assert len(seen) == 2
    for request in seen:
        assert request.url.params["maxResults"] == "50"
        assert request.url.params["list"] == "example"
        assert request.headers["x-goog-api-key"] == KEY
        assert KEY not in str(request.url)


@pytest.mark.anyio
async def test_pages_back_with_the_next_page_token_until_it_finds_the_video() -> None:
    seen = serve_pages()

    found = await lookup(make_game(), DAY)

    assert found is not None
    assert found.video_id == "vid-full"
    assert found.title == TITLE
    assert len(seen) == 2
    assert "pageToken" not in seen[0].url.params
    assert seen[1].url.params["pageToken"] == "page-2"


@pytest.mark.anyio
async def test_stops_paging_at_the_page_with_a_video_older_than_the_game() -> None:
    seen = serve_pages()

    found = await lookup(make_game(), dt.date(2026, 10, 3))

    assert found is None
    assert len(seen) == 2


@pytest.mark.anyio
async def test_stops_at_the_first_page_when_the_game_started_after_its_oldest_video() -> (
    None
):
    seen = serve_pages()
    game = make_game().model_copy(
        update={"start_time": dt.datetime(2026, 10, 5, 6, 30, tzinfo=dt.UTC)}
    )

    found = await lookup(game, dt.date(2026, 10, 3))

    assert found is None
    assert len(seen) == 1


@pytest.mark.anyio
async def test_returns_none_when_the_uploads_run_out() -> None:
    body = {
        "items": [
            {
                "snippet": {
                    "publishedAt": "2026-10-05T07:00:00Z",
                    "channelTitle": "C",
                    "title": "T",
                    "resourceId": {"videoId": "v"},
                }
            }
        ]
    }
    route = respx.get("https://example.com/uploads").respond(json=body)

    assert await lookup(make_game(), DAY) is None
    assert route.call_count == 1


def item(**snippet: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "publishedAt": "2026-10-05T07:00:00Z",
        "channelTitle": "C",
        "title": "T",
        "resourceId": {"videoId": "v"},
    }
    base.update(snippet)
    return {"snippet": {k: v for k, v in base.items() if v is not None}}


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("response", "reason"),
    [
        (httpx.Response(200, text="not json"), "response is not JSON"),
        (httpx.Response(200, json={}), "invalid payload: 1 errors, first at items"),
        (
            httpx.Response(200, json={"items": [item(resourceId={})]}),
            "invalid payload: 1 errors, first at items.0.snippet.resourceId.videoId",
        ),
        (
            httpx.Response(200, json={"items": [item(title=None)]}),
            "invalid payload: 1 errors, first at items.0.snippet.title",
        ),
        (
            httpx.Response(200, json={"items": [item(publishedAt=None)]}),
            "invalid payload: 1 errors, first at items.0.snippet.publishedAt",
        ),
        (
            httpx.Response(200, json={"items": [item(publishedAt="soon")]}),
            "invalid payload: 1 errors, first at items.0.snippet.publishedAt",
        ),
        (
            httpx.Response(200, json={"items": [item(title="")]}),
            "invalid payload: 1 errors, first at title",
        ),
    ],
)
async def test_raises_the_source_error_on_an_invalid_payload(
    response: httpx.Response, reason: str
) -> None:
    error = await lookup_error(response)

    assert error.source == "video_channel"
    assert error.reason == reason


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("effect", "reason"),
    [
        (httpx.ReadTimeout("slow"), "request timed out"),
        (httpx.Response(503), "responded with status 503"),
    ],
)
async def test_raises_the_source_error_on_an_upstream_failure(
    effect: httpx.Response | Exception, reason: str
) -> None:
    error = await lookup_error(effect)

    assert error.reason == reason
    assert KEY not in str(error)
    assert SOURCE_URL not in str(error)


@pytest.mark.anyio
async def test_raises_the_source_error_when_the_source_url_is_missing() -> None:
    with pytest.raises(SourceError) as raised:
        await lookup(make_game(), DAY, make_settings(highlights_source_key=KEY))

    assert raised.value.reason == "highlights source URL is not configured"


@pytest.mark.anyio
@pytest.mark.parametrize("key", [None, ""])
async def test_raises_the_source_error_when_the_key_is_missing_or_empty(
    key: str | None,
) -> None:
    route = respx.get("https://example.com/uploads")
    settings = make_settings(
        highlights_source_url=SOURCE_URL, highlights_source_key=key
    )

    with pytest.raises(SourceError) as raised:
        await lookup(make_game(), DAY, settings)

    assert raised.value.reason == "highlights source key is not configured"
    assert route.call_count == 0


@pytest.mark.anyio
async def test_never_writes_the_key_to_any_log(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG)
    serve_pages()
    await lookup(make_game(), DAY)
    respx.get("https://example.com/uploads").mock(return_value=httpx.Response(503))
    with pytest.raises(SourceError):
        await lookup(make_game(), DAY)

    assert caplog.text
    assert KEY not in caplog.text


def test_matches_a_title_with_both_teams_the_label_and_the_date() -> None:
    assert matches(TITLE, make_game(), DAY)
    assert matches(TITLE.lower(), make_game(), DAY)
    assert matches(TITLE.upper(), make_game(), DAY)


@pytest.mark.parametrize(
    "title",
    [
        "WARRIORS at CLIPPERS | PRESEASON | October 4, 2026",
        "WARRIORS at SPURS | FULL GAME HIGHLIGHTS | October 4, 2026",
        "CLIPPERS | FULL GAME HIGHLIGHTS | October 4, 2026",
        "WARRIORS at CLIPPERS | FULL GAME HIGHLIGHTS | October 3, 2026",
        "WARRIORS at CLIPPERS | FULL GAME HIGHLIGHTS | October 14, 2026",
        (
            "Player Scores 21 For The Clippers Against The Warriors | Highlights | "
            "October 4, 2026"
        ),
    ],
)
def test_does_not_match_a_title_missing_a_part(title: str) -> None:
    assert not matches(title, make_game(), DAY)


def test_does_not_take_a_team_name_inside_a_longer_word() -> None:
    title = "HORNETS at CLIPPERS | FULL GAME HIGHLIGHTS | October 4, 2026"

    assert not matches(title, make_game("Nets", "Clippers"), DAY)
    assert matches(title.replace("HORNETS", "NETS"), make_game("Nets"), DAY)


def test_finds_the_first_matching_video_in_order_and_none_otherwise() -> None:
    videos = [
        ChannelVideo(video_id="a", title="Something else", channel="C"),
        ChannelVideo(video_id="b", title=TITLE, channel="C"),
        ChannelVideo(video_id="c", title=TITLE, channel="C"),
    ]

    found = find_video(videos, make_game(), DAY)
    assert found is not None and found.video_id == "b"
    assert find_video(videos, make_game(), dt.date(2026, 10, 9)) is None
    assert find_video([], make_game(), DAY) is None


def test_builds_the_highlight_from_the_templates() -> None:
    settings = make_settings(
        video_thumbnail_url="https://example.com/t/{video_id}.jpg",
        video_embed_url="https://example.com/e/{video_id}",
    )
    video = ChannelVideo(video_id="abc", title="T", channel="C")

    highlight = to_highlight(video, settings)

    assert highlight.title == "T"
    assert highlight.channel == "C"
    assert str(highlight.thumbnail_url) == "https://example.com/t/abc.jpg"
    assert str(highlight.embed_url) == "https://example.com/e/abc"


@pytest.mark.parametrize(
    ("values", "reason"),
    [
        (
            {"video_embed_url": "https://example.com/e/{video_id}"},
            "video thumbnail URL is not configured",
        ),
        (
            {"video_thumbnail_url": "https://example.com/t/{video_id}"},
            "video embed URL is not configured",
        ),
    ],
)
def test_raises_the_source_error_when_a_highlight_template_is_missing(
    values: dict[str, Any], reason: str
) -> None:
    video = ChannelVideo(video_id="abc", title="T", channel="C")

    with pytest.raises(SourceError) as raised:
        to_highlight(video, make_settings(**values))

    assert raised.value.reason == reason


def test_raises_the_source_error_when_a_template_builds_an_invalid_url() -> None:
    settings = make_settings(
        video_thumbnail_url="not a url {video_id}",
        video_embed_url="https://example.com/e/{video_id}",
    )
    video = ChannelVideo(video_id="abc", title="T", channel="C")

    with pytest.raises(SourceError) as raised:
        to_highlight(video, settings)

    assert raised.value.reason.startswith("video abc is invalid:")


def test_builds_the_search_url_from_the_template_with_encoded_words() -> None:
    settings = make_settings(highlights_search_url="https://example.com/s?q={query}")

    url = search_url(make_game(), DAY, settings)

    assert (
        url
        == "https://example.com/s?q=Warriors+Clippers+full+game+highlights+October+4%2C+2026"
    )


def test_builds_no_search_url_when_the_template_is_missing() -> None:
    assert search_url(make_game(), DAY, make_settings()) is None
