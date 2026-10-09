# api/tests/sources/test_video_channel.py
#
# Tests for the video channel adapter.
#
# Tested:
# - Returns the matching video from the first page with one request, with the channel from the item
# - Asks for fifty videos per request, with the key in a header and never in the URL
# - Pages back with the next page token until it finds the video
# - Takes the largest 16:9 thumbnail, even over a larger 4:3 one; falls back to the largest one when none is 16:9, ranks a thumbnail without a size last, skips one without a URL, and has none when the API lists none with a URL
# - Skips a listed thumbnail the image host does not serve and takes the next one, and has none when the host serves none
# - Checks only the matched video's thumbnails, best first, with HEAD requests, stopping at the first served one and never sending the key
# - Raises the source error when the image host times out, marked as a failed request
# - Stops paging at the page with a video older than the game, and at the first page when the game started after its oldest video
# - Returns none when the uploads run out
# - Raises the source error on a body that is not JSON, a missing items list, a missing video id, a missing title, a missing or bad published time and an empty title
# - Raises the source error on a timeout, an error status, a missing URL and a missing or empty key, never with the key or the URL in the reason
# - Marks a timeout and an error status as a failed request; an invalid payload, a missing URL and a missing key are not
# - Never writes the key to any log record
# - Matches a title with both teams, the label and the date, in any letter case
# - Does not match a title missing the label, a team or the date, nor a player clip that says only highlights
# - Does not take a team name inside a longer word
# - Finds the first matching video in order, and none when no title matches
# - Builds the highlight with the video's thumbnail and the embed template, keeping the title and channel, and raises the source error when the video has no thumbnail, the template is missing or the result is invalid
# - Builds the search URL from the template with the encoded teams, label and date, and none when the template is missing
# - Two lookups of one run list each page once, and a lookup lists again the pages listed before its run
# - Never stores the key in the source cache
# - Lists until every game is matched, each page once, and checks no thumbnail
# - Lists back to the oldest game of the listing
# - Lists the ranked thumbnail candidates of every upload
# - Checks the thumbnail of one video best first
# - A listing raises the failed request of a later page
# - A listing that fails on a later page carries the uploads of the pages read
#
# What is covered:
# - A valid response mapped, an invalid payload rejected, upstream failures handled
# - Paging (page size, token, both stops), key handling (header, error, log)
# - Thumbnail check against the image host (served, not served, timeout)
# - Pure logic: matching (happy path, each missing part, word boundary), thumbnail choice, URL building
#
# The fixtures are minimal pages of the official uploads listing. No test makes a real request.
#
# Run with: cd api && .venv/bin/python -m pytest tests/sources/test_video_channel.py
#
# SEE: api/app/sources/video_channel.py

import datetime as dt
import logging
import sqlite3
from collections.abc import Iterator
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import httpx
import pytest
import respx

from app.feeds.games import GameStatus, GameTeam
from app.settings import Settings
from app.sources.http import SourceClient, SourceError, create_client
from app.sources.scoreboard import ScoreboardGame
from app.sources.video_channel import (
    ChannelVideo,
    ListingError,
    check_thumbnail,
    find_video,
    list_uploads,
    lookup_video,
    matches,
    search_url,
    to_highlight,
)
from app.storage.state import STATE_FILE, StateStore

FIXTURES = Path(__file__).parent / "fixtures" / "video_channel"
SOURCE_URL = "https://example.com/uploads?list=example"
KEY = "test-key-value"
DAY = dt.date(2026, 10, 4)
# Before the fixed clock START the client reads, so every cached page counts as listed in the run.
LISTED_SINCE = dt.datetime(2026, 1, 1, tzinfo=dt.UTC)
START = dt.datetime(2026, 10, 5, 2, 0, tzinfo=dt.UTC)
TITLE = "WARRIORS at CLIPPERS | PRESEASON FULL GAME HIGHLIGHTS | October 4, 2026"


@pytest.fixture(autouse=True)
def no_network() -> Iterator[None]:
    with respx.mock:
        yield


@pytest.fixture(autouse=True)
def image_host(no_network: None) -> ImageHost:
    return ImageHost()


class ImageHost:
    """Serves every thumbnail under example.com/thumbs except the missing ones,
    which get a 404, as the real host does, and times out when told to.
    Records the requests."""

    def __init__(self) -> None:
        self.missing: set[str] = set()
        self.timeout = False
        self.requests: list[httpx.Request] = []
        respx.head(url__startswith="https://example.com/thumbs/").mock(
            side_effect=self._serve
        )

    def _serve(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.timeout:
            raise httpx.ReadTimeout("slow")
        return httpx.Response(404 if str(request.url) in self.missing else 200)


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
        away=GameTeam(code=codes[away], name=away, city="City"),
        home=GameTeam(code=codes[home], name=home, city="City"),
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
    with TemporaryDirectory() as directory:
        store = StateStore(Path(directory))
        store.migrate()
        async with create_client(store, clock=lambda: START) as client:
            return await lookup_video(
                client, game, day, settings or configured(), LISTED_SINCE
            )


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
    assert found.thumbnail_url == "https://example.com/thumbs/vid-full/maxres.jpg"
    assert len(seen) == 2
    assert "pageToken" not in seen[0].url.params
    assert seen[1].url.params["pageToken"] == "page-2"


@pytest.mark.anyio
async def test_checks_only_the_matched_video_thumbnails_best_first_and_stops_at_the_first_served(
    image_host: ImageHost,
) -> None:
    serve_pages()
    image_host.missing.add("https://example.com/thumbs/vid-full/maxres.jpg")

    found = await lookup(make_game(), DAY)

    assert found is not None
    assert found.thumbnail_url == "https://example.com/thumbs/vid-full/medium.jpg"
    assert [(r.method, str(r.url)) for r in image_host.requests] == [
        ("HEAD", "https://example.com/thumbs/vid-full/maxres.jpg"),
        ("HEAD", "https://example.com/thumbs/vid-full/medium.jpg"),
    ]
    assert all("x-goog-api-key" not in r.headers for r in image_host.requests)


@pytest.mark.anyio
async def test_raises_the_source_error_when_the_image_host_times_out(
    image_host: ImageHost,
) -> None:
    serve_pages()
    image_host.timeout = True

    with pytest.raises(SourceError) as raised:
        await lookup(make_game(), DAY)

    assert raised.value.reason == "request timed out"
    assert raised.value.request_failed is True


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


def thumbnail(name: str, width: int | None, height: int | None) -> dict[str, Any]:
    size = {"width": width, "height": height}
    return {
        "url": f"https://example.com/thumbs/{name}.jpg",
        **{k: v for k, v in size.items() if v is not None},
    }


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("missing", "expected"),
    [
        ({"fhd"}, "https://example.com/thumbs/maxres.jpg"),
        ({"fhd", "maxres", "standard"}, "https://example.com/thumbs/high.jpg"),
        ({"fhd", "maxres", "standard", "high"}, None),
    ],
)
async def test_skips_a_thumbnail_the_image_host_does_not_serve(
    image_host: ImageHost, missing: set[str], expected: str | None
) -> None:
    image_host.missing.update(f"https://example.com/thumbs/{n}.jpg" for n in missing)
    thumbnails = {
        "fhd": thumbnail("fhd", 1920, 1080),
        "maxres": thumbnail("maxres", 1280, 720),
        "standard": thumbnail("standard", 640, 480),
        "high": thumbnail("high", 480, 360),
    }

    assert await thumbnail_of(thumbnails) == expected


async def thumbnail_of(thumbnails: dict[str, Any] | None) -> str | None:
    """Look up a page with one matching video listing these thumbnails."""
    respx.get("https://example.com/uploads").respond(
        json={"items": [item(title=TITLE, thumbnails=thumbnails)]}
    )
    found = await lookup(make_game(), DAY)
    assert found is not None
    return found.thumbnail_url


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("thumbnails", "expected"),
    [
        (
            {
                "default": thumbnail("default", 120, 90),
                "medium": thumbnail("medium", 320, 180),
                "high": thumbnail("high", 480, 360),
                "standard": thumbnail("standard", 640, 480),
                "maxres": thumbnail("maxres", 1280, 720),
            },
            "https://example.com/thumbs/maxres.jpg",
        ),
        (
            {
                "medium": thumbnail("medium", 320, 180),
                "standard": thumbnail("standard", 640, 480),
            },
            "https://example.com/thumbs/medium.jpg",
        ),
        (
            {
                "default": thumbnail("default", 120, 90),
                "standard": thumbnail("standard", 640, 480),
                "high": thumbnail("high", 480, 360),
            },
            "https://example.com/thumbs/standard.jpg",
        ),
        (
            {
                "unsized": thumbnail("unsized", None, None),
                "default": thumbnail("default", 120, 90),
            },
            "https://example.com/thumbs/default.jpg",
        ),
        (
            {"unsized": thumbnail("unsized", None, None)},
            "https://example.com/thumbs/unsized.jpg",
        ),
        (
            {
                "maxres": {"width": 1280, "height": 720},
                "high": thumbnail("high", 480, 360),
            },
            "https://example.com/thumbs/high.jpg",
        ),
        ({"maxres": {"url": "", "width": 1280, "height": 720}}, None),
        (
            {
                "standard": thumbnail("standard", 640, 480),
                "zero": thumbnail("zero", 0, 0),
            },
            "https://example.com/thumbs/standard.jpg",
        ),
        (
            {
                "standard": thumbnail("standard", 640, 480),
                "neg": thumbnail("neg", -16, -9),
            },
            "https://example.com/thumbs/standard.jpg",
        ),
        ({}, None),
        (None, None),
    ],
)
async def test_takes_the_largest_wide_thumbnail_and_falls_back_to_the_largest(
    thumbnails: dict[str, Any] | None, expected: str | None
) -> None:
    assert await thumbnail_of(thumbnails) == expected


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("invalid", "expected"),
    [
        (["not a url", "//host/x.jpg"], "https://example.com/thumbs/high.jpg"),
        (["not a url", "//host/x.jpg"], None),
    ],
)
async def test_skips_a_listed_thumbnail_url_that_is_not_valid(
    image_host: ImageHost, invalid: list[str], expected: str | None
) -> None:
    thumbnails: dict[str, Any] = {
        f"bad{i}": {"url": url, "width": 1920, "height": 1080}
        for i, url in enumerate(invalid)
    }
    if expected is not None:
        thumbnails["high"] = thumbnail("high", 480, 360)

    assert await thumbnail_of(thumbnails) == expected
    assert [str(r.url) for r in image_host.requests] == (
        [] if expected is None else [expected]
    )


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
    assert error.request_failed is False


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
    assert error.request_failed is True
    assert KEY not in str(error)
    assert SOURCE_URL not in str(error)


@pytest.mark.anyio
async def test_raises_the_source_error_when_the_source_url_is_missing() -> None:
    with pytest.raises(SourceError) as raised:
        await lookup(make_game(), DAY, make_settings(highlights_source_key=KEY))

    assert raised.value.reason == "highlights source URL is not configured"
    assert raised.value.request_failed is False


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
    assert raised.value.request_failed is False
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
        ChannelVideo(
            video_id="a", title="Something else", channel="C", thumbnail_url=None
        ),
        ChannelVideo(video_id="b", title=TITLE, channel="C", thumbnail_url=None),
        ChannelVideo(video_id="c", title=TITLE, channel="C", thumbnail_url=None),
    ]

    found = find_video(videos, make_game(), DAY)
    assert found is not None and found.video_id == "b"
    assert find_video(videos, make_game(), dt.date(2026, 10, 9)) is None
    assert find_video([], make_game(), DAY) is None


def video_with(thumbnail_url: str | None) -> ChannelVideo:
    return ChannelVideo(
        video_id="abc", title="T", channel="C", thumbnail_url=thumbnail_url
    )


EMBED = make_settings(video_embed_url="https://example.com/e/{video_id}")


def test_builds_the_highlight_with_the_video_thumbnail_and_the_embed_template() -> None:
    highlight = to_highlight(video_with("https://example.com/t/abc.jpg"), EMBED)

    assert highlight.title == "T"
    assert highlight.channel == "C"
    assert str(highlight.thumbnail_url) == "https://example.com/t/abc.jpg"
    assert str(highlight.embed_url) == "https://example.com/e/abc"


@pytest.mark.parametrize(
    ("video", "settings", "reason"),
    [
        (video_with(None), EMBED, "video abc has no thumbnail"),
        (
            video_with("https://example.com/t/abc.jpg"),
            make_settings(),
            "video embed URL is not configured",
        ),
    ],
)
def test_raises_the_source_error_without_a_thumbnail_or_the_embed_template(
    video: ChannelVideo, settings: Settings, reason: str
) -> None:
    with pytest.raises(SourceError) as raised:
        to_highlight(video, settings)

    assert raised.value.reason == reason


def test_raises_the_source_error_when_the_highlight_is_invalid() -> None:
    with pytest.raises(SourceError) as raised:
        to_highlight(video_with("not a url"), EMBED)

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


def clocked(tmp_path: Path, clock: list[dt.datetime]) -> SourceClient:
    store = StateStore(tmp_path)
    store.migrate()
    return create_client(store, clock=lambda: clock[0])


@pytest.mark.anyio
async def test_two_lookups_of_one_run_list_each_page_once(tmp_path: Path) -> None:
    seen = serve_pages()
    start = dt.datetime(2026, 10, 5, 12, 0, tzinfo=dt.UTC)
    second = make_game().model_copy(update={"id": "g2"})
    async with clocked(tmp_path, [start]) as client:
        await lookup_video(client, make_game(), DAY, configured(), start)
        await lookup_video(client, second, DAY, configured(), start)

    assert [r.url.params.get("pageToken") for r in seen] == [None, "page-2"]


@pytest.mark.anyio
async def test_a_lookup_lists_again_the_pages_listed_before_its_run(
    tmp_path: Path,
) -> None:
    seen = serve_pages()
    start = dt.datetime(2026, 10, 5, 12, 0, tzinfo=dt.UTC)
    later = start + dt.timedelta(minutes=10)
    clock = [start]
    async with clocked(tmp_path, clock) as client:
        await lookup_video(client, make_game(), DAY, configured(), start)
        clock[0] = later
        await lookup_video(client, make_game(), DAY, configured(), later)

    assert len(seen) == 4


@pytest.mark.anyio
async def test_the_key_header_is_never_stored(tmp_path: Path) -> None:
    serve_pages()
    store = StateStore(tmp_path)
    store.migrate()
    async with create_client(store, clock=lambda: START) as client:
        await lookup_video(client, make_game(), DAY, configured(), LISTED_SINCE)

    with closing(sqlite3.connect(tmp_path / STATE_FILE)) as connection:
        stored = connection.execute("SELECT url, body FROM source_cache").fetchall()
    assert len(stored) == 2
    assert KEY not in str(stored)


async def listing(
    games: list[tuple[ScoreboardGame, dt.date]], tmp_path: Path
) -> list[ChannelVideo]:
    async with clocked(tmp_path, [START]) as client:
        return await list_uploads(client, games, configured(), LISTED_SINCE)


def second_game(away: str, home: str, **values: Any) -> ScoreboardGame:
    return make_game(away, home).model_copy(update={"id": "g2", **values})


@pytest.mark.anyio
async def test_lists_until_every_game_is_matched_each_page_once(
    tmp_path: Path, image_host: ImageHost
) -> None:
    seen = serve_pages()
    games = [
        (make_game("Jazz", "Nuggets"), DAY),
        (second_game("Warriors", "Clippers"), DAY),
    ]

    uploads = await listing(games, tmp_path)

    assert [r.url.params.get("pageToken") for r in seen] == [None, "page-2"]
    assert [v.video_id for v in uploads] == [
        "vid-clip",
        "vid-other-game",
        "vid-full",
        "vid-older",
    ]
    assert all(v.thumbnail_url is None for v in uploads)
    assert image_host.requests == []


@pytest.mark.anyio
async def test_lists_back_to_the_oldest_game_of_the_listing(tmp_path: Path) -> None:
    seen = serve_pages()
    jazz = (make_game("Jazz", "Nuggets"), DAY)
    early = dt.datetime(2026, 10, 5, 1, 0, tzinfo=dt.UTC)
    nets = (second_game("Nets", "Jazz", start_time=early), DAY)

    await listing([jazz], tmp_path)
    assert len(seen) == 1
    seen.clear()
    (tmp_path / "other").mkdir()
    await listing([jazz, nets], tmp_path / "other")

    assert [r.url.params.get("pageToken") for r in seen] == [None, "page-2"]


@pytest.mark.anyio
async def test_lists_the_ranked_thumbnail_candidates_of_every_upload(
    tmp_path: Path,
) -> None:
    serve_pages()
    games = [
        (make_game("Jazz", "Nuggets"), DAY),
        (second_game("Warriors", "Clippers"), DAY),
    ]

    uploads = await listing(games, tmp_path)

    full = next(v for v in uploads if v.video_id == "vid-full")
    assert (
        full.thumbnail_candidates[0] == "https://example.com/thumbs/vid-full/maxres.jpg"
    )


@pytest.mark.anyio
async def test_checks_the_thumbnail_of_one_video_best_first(
    tmp_path: Path, image_host: ImageHost
) -> None:
    first = "https://example.com/thumbs/a/maxres.jpg"
    second = "https://example.com/thumbs/a/high.jpg"
    video = ChannelVideo(
        video_id="a",
        title="t",
        channel="c",
        thumbnail_url=None,
        thumbnail_candidates=(first, second),
    )
    async with clocked(tmp_path, [START]) as client:
        image_host.missing = {first}
        assert (await check_thumbnail(client, video)).thumbnail_url == second
        image_host.missing = {first, second}
        assert (await check_thumbnail(client, video)).thumbnail_url is None
        image_host.missing = set()
        image_host.timeout = True
        with pytest.raises(SourceError) as raised:
            await check_thumbnail(client, video)
    assert raised.value.request_failed is True


def serve_page_one_then(second: httpx.Response) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.params.get("pageToken") == "page-2":
            return second
        return httpx.Response(200, text=page("page-1"))

    respx.get("https://example.com/uploads").mock(side_effect=handler)


@pytest.mark.anyio
async def test_a_listing_raises_the_failed_request_of_a_later_page(
    tmp_path: Path,
) -> None:
    serve_page_one_then(httpx.Response(503))
    games = [
        (make_game("Jazz", "Nuggets"), DAY),
        (second_game("Warriors", "Clippers"), DAY),
    ]

    with pytest.raises(SourceError) as raised:
        await listing(games, tmp_path)

    assert raised.value.request_failed is True


@pytest.mark.anyio
async def test_a_listing_that_fails_on_a_later_page_carries_the_uploads_of_the_pages_read(
    tmp_path: Path,
) -> None:
    serve_page_one_then(httpx.Response(200, text="not json"))
    games = [
        (make_game("Jazz", "Nuggets"), DAY),
        (second_game("Warriors", "Clippers"), DAY),
    ]

    with pytest.raises(ListingError) as raised:
        await listing(games, tmp_path)

    assert raised.value.request_failed is False
    assert [v.video_id for v in raised.value.uploads] == ["vid-clip", "vid-other-game"]
