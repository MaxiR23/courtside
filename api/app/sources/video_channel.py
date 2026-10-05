# api/app/sources/video_channel.py
#
# Video channel adapter: reads the channel's public feed, finds the full game
# highlights of a game by its title and builds the highlight and the search
# link from templates. The URLs come from Settings. Provider data never leaves
# this module.
#
# SEE: docs/adr/0007-backend-runtime-and-data-pipeline.md, api/app/sources/team_players.py

import datetime as dt
import re
from urllib.parse import quote_plus
from xml.etree import ElementTree

import httpx
from pydantic import ValidationError

from app.feeds.games import FeedModel, Highlight, NonEmptyStr
from app.settings import Settings
from app.sources.http import SourceError, get_text
from app.sources.scoreboard import ScoreboardGame

SOURCE = "video_channel"
LABEL = "full game highlights"


class ChannelVideo(FeedModel):
    """A video of the channel feed. Never reaches the feed."""

    video_id: NonEmptyStr
    title: NonEmptyStr
    channel: NonEmptyStr


def _title_date(day: dt.date) -> str:
    return f"{day:%B} {day.day}, {day.year}"


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _child_text(element: ElementTree.Element, name: str) -> str | None:
    for child in element:
        if _local(child.tag) == name:
            return child.text
    return None


def _author(element: ElementTree.Element) -> str | None:
    for child in element:
        if _local(child.tag) == "author":
            return _child_text(child, "name")
    return None


def _location(error: ValidationError) -> str:
    return ".".join(str(part) for part in error.errors()[0]["loc"])


async def fetch_videos(
    client: httpx.AsyncClient, settings: Settings
) -> list[ChannelVideo]:
    """Return the videos of the channel feed in feed order, or raise SourceError."""
    if settings.video_channel_feed_url is None:
        raise SourceError(SOURCE, "video channel feed URL is not configured")
    text = await get_text(client, settings.video_channel_feed_url, source=SOURCE)
    try:
        root = ElementTree.fromstring(text)
    except ElementTree.ParseError:
        raise SourceError(SOURCE, "response is not valid XML") from None
    if _local(root.tag) != "feed":
        raise SourceError(SOURCE, "invalid payload: not a feed")
    feed_author = _author(root)
    videos: list[ChannelVideo] = []
    for entry in root:
        if _local(entry.tag) != "entry":
            continue
        try:
            videos.append(
                ChannelVideo.model_validate(
                    {
                        "video_id": _child_text(entry, "videoId"),
                        "title": _child_text(entry, "title"),
                        "channel": _author(entry) or feed_author,
                    }
                )
            )
        except ValidationError as error:
            raise SourceError(
                SOURCE,
                f"invalid payload: {error.error_count()} errors, "
                f"first at {_location(error)}",
            ) from None
    return videos


def _has_word(title: str, words: str) -> bool:
    pattern = r"(?<!\w)" + re.escape(words) + r"(?!\w)"
    return re.search(pattern, title, re.IGNORECASE) is not None


def matches(title: str, game: ScoreboardGame, day: dt.date) -> bool:
    """True when the title names both teams, the label and the date of the day."""
    return (
        _has_word(title, game.away.name)
        and _has_word(title, game.home.name)
        and _has_word(title, LABEL)
        and _has_word(title, _title_date(day))
    )


def find_video(
    videos: list[ChannelVideo], game: ScoreboardGame, day: dt.date
) -> ChannelVideo | None:
    """Return the first video in feed order whose title matches the game."""
    for video in videos:
        if matches(video.title, game, day):
            return video
    return None


def to_highlight(video: ChannelVideo, settings: Settings) -> Highlight:
    """Build the feed's highlight from a video, or raise SourceError."""
    if settings.video_thumbnail_url is None:
        raise SourceError(SOURCE, "video thumbnail URL is not configured")
    if settings.video_embed_url is None:
        raise SourceError(SOURCE, "video embed URL is not configured")
    try:
        return Highlight.model_validate(
            {
                "title": video.title,
                "channel": video.channel,
                "thumbnail_url": settings.video_thumbnail_url.format(
                    video_id=video.video_id
                ),
                "embed_url": settings.video_embed_url.format(video_id=video.video_id),
            }
        )
    except ValidationError as error:
        first = error.errors()[0]
        raise SourceError(
            SOURCE,
            f"video {video.video_id} is invalid: {first['type']} at {_location(error)}",
        ) from None


def search_url(game: ScoreboardGame, day: dt.date, settings: Settings) -> str | None:
    """Return the search link for the game's highlights, or None when not set."""
    if settings.highlights_search_url is None:
        return None
    query = f"{game.away.name} {game.home.name} {LABEL} {_title_date(day)}"
    return settings.highlights_search_url.format(query=quote_plus(query))
