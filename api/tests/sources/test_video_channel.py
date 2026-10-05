# api/tests/sources/test_video_channel.py
#
# Tests for the video channel adapter.
#
# Tested:
# - Maps a recorded channel feed to videos with id, title and channel, in feed order
# - Reads elements by local name, whatever their namespace
# - Takes the channel from the feed author when an entry has none
# - Raises the source error on a body that is not XML, a root that is not a feed, an entry without a video id, an entry without a title, a timeout, an error status and a missing feed URL, never with the URL in the reason
# - Matches a title with both teams, the label and the date, in any letter case
# - Does not match a title missing the label, a team or the date, nor a player clip that says only highlights
# - Does not take a team name inside a longer word
# - Finds the first matching video in feed order, and none when no title matches
# - Builds the highlight from the templates and keeps the title and channel, and raises the source error when a template is missing or the result is invalid
# - Builds the search URL from the template with the encoded teams, label and date, and none when the template is missing
#
# What is covered:
# - A valid response mapped, an invalid payload rejected, upstream failures handled
# - Pure logic: matching (happy path, each missing part, word boundary), URL building
#
# The fixture is a minimal channel feed in a made-up namespace. No test makes a real request.
#
# Run with: cd api && .venv/bin/python -m pytest tests/sources/test_video_channel.py
#
# SEE: api/app/sources/video_channel.py

import datetime as dt
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
    fetch_videos,
    find_video,
    matches,
    search_url,
    to_highlight,
)

FIXTURE = Path(__file__).parent / "fixtures" / "video_channel" / "feed.xml"
FEED_URL = "https://example.com/feed?key=secret-value"
DAY = dt.date(2026, 10, 4)
START = dt.datetime(2026, 10, 5, 2, 0, tzinfo=dt.UTC)
TITLE = "WARRIORS at CLIPPERS | PRESEASON FULL GAME HIGHLIGHTS | October 4, 2026"


@pytest.fixture(autouse=True)
def no_network() -> Iterator[None]:
    with respx.mock:
        yield


def make_game(away: str = "Warriors", home: str = "Clippers") -> ScoreboardGame:
    codes = {"Warriors": "GSW", "Clippers": "LAC", "Nets": "BKN"}
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


async def fetch(
    settings: Settings, effect: httpx.Response | Exception | None = None
) -> list[ChannelVideo]:
    route = respx.get(FEED_URL)
    if isinstance(effect, Exception):
        route.mock(side_effect=effect)
    else:
        route.mock(return_value=effect or httpx.Response(200, text=FIXTURE.read_text()))
    async with create_client() as client:
        return await fetch_videos(client, settings)


async def fetch_error(
    effect: httpx.Response | Exception, settings: Settings | None = None
) -> SourceError:
    with pytest.raises(SourceError) as raised:
        await fetch(settings or make_settings(video_channel_feed_url=FEED_URL), effect)
    return raised.value


@pytest.mark.anyio
async def test_maps_the_recorded_feed_to_videos_in_feed_order() -> None:
    videos = await fetch(make_settings(video_channel_feed_url=FEED_URL))

    assert [v.video_id for v in videos] == [
        "vid-clip",
        "vid-full",
        "vid-other-game",
        "vid-other-date",
        "vid-hornets",
    ]
    assert videos[1].title == TITLE
    assert videos[1].channel == "Example Channel"


@pytest.mark.anyio
async def test_takes_the_channel_from_the_feed_author_when_an_entry_has_none() -> None:
    videos = await fetch(make_settings(video_channel_feed_url=FEED_URL))

    assert videos[2].video_id == "vid-other-game"
    assert videos[2].channel == "Example Channel"


@pytest.mark.anyio
async def test_reads_elements_by_local_name_whatever_their_namespace() -> None:
    body = (
        '<feed xmlns="urn:a" xmlns:q="urn:b"><entry>'
        "<q:videoId>x1</q:videoId><title>T</title><author><name>C</name></author>"
        "</entry></feed>"
    )

    videos = await fetch(
        make_settings(video_channel_feed_url=FEED_URL), httpx.Response(200, text=body)
    )

    assert videos == [ChannelVideo(video_id="x1", title="T", channel="C")]


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("body", "reason"),
    [
        ("<feed><entry>", "response is not valid XML"),
        ("not xml", "response is not valid XML"),
        ("<rss></rss>", "invalid payload: not a feed"),
        (
            (
                "<feed><author><name>C</name></author>"
                "<entry><title>T</title></entry></feed>"
            ),
            "invalid payload: 1 errors, first at video_id",
        ),
        (
            (
                "<feed><author><name>C</name></author>"
                "<entry><videoId>v</videoId></entry></feed>"
            ),
            "invalid payload: 1 errors, first at title",
        ),
    ],
)
async def test_raises_the_source_error_on_an_invalid_payload(
    body: str, reason: str
) -> None:
    error = await fetch_error(httpx.Response(200, text=body))

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
    error = await fetch_error(effect)

    assert error.reason == reason
    assert "secret-value" not in str(error)


@pytest.mark.anyio
async def test_raises_the_source_error_when_the_feed_url_is_missing() -> None:
    async with create_client() as client:
        with pytest.raises(SourceError) as raised:
            await fetch_videos(client, make_settings())

    assert raised.value.reason == "video channel feed URL is not configured"


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


@pytest.mark.anyio
async def test_finds_the_first_matching_video_in_feed_order_and_none_otherwise() -> (
    None
):
    videos = await fetch(make_settings(video_channel_feed_url=FEED_URL))

    found = find_video(videos, make_game(), DAY)
    assert found is not None and found.video_id == "vid-full"
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
