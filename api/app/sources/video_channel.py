# api/app/sources/video_channel.py
#
# Video channel adapter: lists the official channel's uploads through the
# official API, 50 per request, paging back per game until it finds the game's
# full game highlights by title, builds the highlight and the search link from
# templates. The URLs and the key come from Settings; the key goes only in a
# request header. Provider data never leaves this module.
#
# SEE: docs/adr/0007-backend-runtime-and-data-pipeline.md,
# docs/adr/0015-highlights-source.md, api/app/sources/team_players.py

import datetime as dt
import re
from urllib.parse import quote_plus

import httpx
from pydantic import AwareDatetime, BaseModel, ConfigDict, ValidationError
from pydantic.alias_generators import to_camel

from app.feeds.games import FeedModel, Highlight, NonEmptyStr
from app.settings import Settings
from app.sources.http import SourceError, get_json
from app.sources.scoreboard import ScoreboardGame

SOURCE = "video_channel"
LABEL = "full game highlights"
PAGE_SIZE = 50
KEY_HEADER = "X-Goog-Api-Key"


class ChannelVideo(FeedModel):
    """A video of the channel feed. Never reaches the feed."""

    video_id: NonEmptyStr
    title: NonEmptyStr
    channel: NonEmptyStr


def _title_date(day: dt.date) -> str:
    return f"{day:%B} {day.day}, {day.year}"


def _location(error: ValidationError) -> str:
    return ".".join(str(part) for part in error.errors()[0]["loc"])


class _ProviderModel(BaseModel):
    model_config = ConfigDict(
        extra="ignore", alias_generator=to_camel, validate_by_name=True
    )


class _ProviderResource(_ProviderModel):
    video_id: str


class _ProviderSnippet(_ProviderModel):
    published_at: AwareDatetime
    channel_title: str
    title: str
    resource_id: _ProviderResource


class _ProviderItem(_ProviderModel):
    snippet: _ProviderSnippet


class _ProviderPage(_ProviderModel):
    items: list[_ProviderItem]
    next_page_token: str | None = None


def _invalid(error: ValidationError) -> SourceError:
    return SourceError(
        SOURCE,
        f"invalid payload: {error.error_count()} errors, first at {_location(error)}",
    )


async def lookup_video(
    client: httpx.AsyncClient,
    game: ScoreboardGame,
    day: dt.date,
    settings: Settings,
) -> ChannelVideo | None:
    """Page back through the channel's uploads, newest first, 50 per request,
    and return the first video whose title matches the game. None once a
    page holds a video published before the game's start or the uploads
    run out. Raises SourceError."""
    if settings.highlights_source_url is None:
        raise SourceError(SOURCE, "highlights source URL is not configured")
    key = settings.highlights_source_key
    if key is None or not key.get_secret_value():
        raise SourceError(SOURCE, "highlights source key is not configured")
    token: str | None = None
    while True:
        params: dict[str, str | int] = {"maxResults": PAGE_SIZE}
        if token is not None:
            params["pageToken"] = token
        body = await get_json(
            client,
            settings.highlights_source_url,
            source=SOURCE,
            params=params,
            headers={KEY_HEADER: key.get_secret_value()},
        )
        try:
            page = _ProviderPage.model_validate(body)
            videos = [
                ChannelVideo(
                    video_id=item.snippet.resource_id.video_id,
                    title=item.snippet.title,
                    channel=item.snippet.channel_title,
                )
                for item in page.items
            ]
        except ValidationError as error:
            raise _invalid(error) from None
        found = find_video(videos, game, day)
        if found is not None:
            return found
        older = any(item.snippet.published_at < game.start_time for item in page.items)
        if page.next_page_token is None or older:
            return None
        token = page.next_page_token


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
