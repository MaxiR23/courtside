# api/app/sources/video_channel.py
#
# Video channel adapter: lists the official channel's uploads through the
# official API, 50 per request, paging back once per highlights run until every
# due game's full game highlights are found by title or a page holds a video
# older than the oldest due game (rule E of docs/source-rules.md), and takes the largest 16:9 thumbnail the API
# lists for it that the image host serves, or the largest served one when none
# is 16:9. Builds the embed and the search link from templates. The URLs and the key come from Settings; the key
# goes only in a request header. Provider data never leaves this module.
#
# SEE: docs/adr/0007-backend-runtime-and-data-pipeline.md,
# docs/adr/0015-highlights-source.md,
# docs/adr/0020-source-rules.md, api/app/sources/team_players.py

import datetime as dt
import re
from collections.abc import Sequence
from urllib.parse import quote_plus

import httpx
from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    HttpUrl,
    TypeAdapter,
    ValidationError,
)
from pydantic.alias_generators import to_camel

from app.feeds.games import FeedModel, Highlight, NonEmptyStr
from app.settings import Settings
from app.sources.http import SourceClient, SourceError, get_json, is_served
from app.sources.scoreboard import ScoreboardGame

SOURCE = "video_channel"
LABEL = "full game highlights"
PAGE_SIZE = 50
KEY_HEADER = "X-Goog-Api-Key"
_HTTP_URL = TypeAdapter(HttpUrl)


class ChannelVideo(FeedModel):
    """An upload of the official channel, as listed by the official video API. Never reaches the feed."""

    video_id: NonEmptyStr
    title: NonEmptyStr
    channel: NonEmptyStr
    # The best thumbnail the image host serves, or None when it serves none.
    thumbnail_url: str | None
    # The thumbnails the API lists, best first; checked only once matched.
    thumbnail_candidates: tuple[str, ...] = ()


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


class _ProviderThumbnail(_ProviderModel):
    # Optional so one bad thumbnail never rejects the whole page.
    url: str | None = None
    width: int | None = None
    height: int | None = None


class _ProviderSnippet(_ProviderModel):
    published_at: AwareDatetime
    channel_title: str
    title: str
    resource_id: _ProviderResource
    # Keyed by size name; a removed or private video lists none.
    thumbnails: dict[str, _ProviderThumbnail] = {}


class _ProviderItem(_ProviderModel):
    snippet: _ProviderSnippet


class _ProviderPage(_ProviderModel):
    items: list[_ProviderItem]
    next_page_token: str | None = None


def _is_sized(thumbnail: _ProviderThumbnail) -> bool:
    return (thumbnail.width or 0) > 0 and (thumbnail.height or 0) > 0


def _is_http_url(url: str | None) -> bool:
    if not url:
        return False
    try:
        _HTTP_URL.validate_python(url)
    except ValidationError:
        return False
    return True


def _is_wide(thumbnail: _ProviderThumbnail) -> bool:
    if not _is_sized(thumbnail) or thumbnail.width is None or thumbnail.height is None:
        return False
    return thumbnail.width * 9 == thumbnail.height * 16


def _area(thumbnail: _ProviderThumbnail) -> int:
    if not _is_sized(thumbnail):
        return 0
    return (thumbnail.width or 0) * (thumbnail.height or 0)


def _ranked_thumbnails(thumbnails: dict[str, _ProviderThumbnail]) -> list[str]:
    """Return the thumbnail URLs best first: 16:9 before any other shape,
    then larger first. A thumbnail without a size ranks last and one without
    a URL that is not a valid HTTP URL is skipped."""
    usable = [t for t in thumbnails.values() if _is_http_url(t.url)]
    usable.sort(key=lambda t: (_is_wide(t), _area(t)), reverse=True)
    return [t.url for t in usable if t.url]


async def _first_served(client: httpx.AsyncClient, urls: list[str]) -> str | None:
    """Return the first URL the image host serves. The API lists sizes the
    host answers with a placeholder and a 404, so each one is checked."""
    for url in urls:
        if await is_served(client, url, source=SOURCE):
            return url
    return None


def _invalid(error: ValidationError) -> SourceError:
    return SourceError(
        SOURCE,
        f"invalid payload: {error.error_count()} errors, first at {_location(error)}",
    )


class ListingError(SourceError):
    """A listing that failed after reading some pages. Carries the uploads of
    the pages read before the failure, so a caller can keep a match found on
    them. A failed request (`request_failed`) means the listing is unusable."""

    def __init__(self, error: SourceError, uploads: list[ChannelVideo]) -> None:
        super().__init__(
            error.source,
            error.reason,
            status_code=error.status_code,
            request_failed=error.request_failed,
        )
        self.uploads = uploads


async def _read_page(
    client: SourceClient,
    settings: Settings,
    key: str,
    token: str | None,
    listed_since: dt.datetime,
) -> _ProviderPage:
    assert settings.highlights_source_url is not None
    params: dict[str, str | int] = {"maxResults": PAGE_SIZE}
    if token is not None:
        params["pageToken"] = token
    body = await get_json(
        client,
        settings.highlights_source_url,
        source=SOURCE,
        fresh=listed_since,
        params=params,
        headers={KEY_HEADER: key},
    )
    try:
        return _ProviderPage.model_validate(body)
    except ValidationError as error:
        raise _invalid(error) from None


async def list_uploads(
    client: SourceClient,
    games: Sequence[tuple[ScoreboardGame, dt.date]],
    settings: Settings,
    listed_since: dt.datetime,
) -> list[ChannelVideo]:
    """Page back through the channel's uploads once for every game, newest
    first, 50 per request, and return every upload read, with its ranked
    thumbnail candidates and no thumbnail checked. Stops after the first page
    where every game has a matching title among the uploads listed so far, or
    a page holds a video published before the start of the oldest game, or
    the uploads run out. Every page is fetched at or after `listed_since`,
    the start of the highlights run (rule E). Raises SourceError; a failure
    after the first page raises ListingError, which carries the uploads read."""
    if settings.highlights_source_url is None:
        raise SourceError(SOURCE, "highlights source URL is not configured")
    key = settings.highlights_source_key
    if key is None or not key.get_secret_value():
        raise SourceError(SOURCE, "highlights source key is not configured")
    if not games:
        return []
    oldest = min(game.start_time for game, _ in games)
    listed: list[ChannelVideo] = []
    token: str | None = None
    while True:
        try:
            page = await _read_page(
                client, settings, key.get_secret_value(), token, listed_since
            )
            videos = [
                ChannelVideo(
                    video_id=item.snippet.resource_id.video_id,
                    title=item.snippet.title,
                    channel=item.snippet.channel_title,
                    thumbnail_url=None,
                    thumbnail_candidates=tuple(
                        _ranked_thumbnails(item.snippet.thumbnails)
                    ),
                )
                for item in page.items
            ]
        except ValidationError as error:
            raise ListingError(_invalid(error), listed) from None
        except SourceError as error:
            raise ListingError(error, listed) from None
        listed.extend(videos)
        if all(find_video(listed, game, day) is not None for game, day in games):
            return listed
        older = any(item.snippet.published_at < oldest for item in page.items)
        if page.next_page_token is None or older:
            return listed
        token = page.next_page_token


async def check_thumbnail(
    client: httpx.AsyncClient, video: ChannelVideo
) -> ChannelVideo:
    """Return the video with the first of its thumbnail candidates the image
    host serves, or None when it serves none. Raises SourceError on a timeout
    or transport failure."""
    served = await _first_served(client, list(video.thumbnail_candidates))
    return video.model_copy(update={"thumbnail_url": served})


async def lookup_video(
    client: SourceClient,
    game: ScoreboardGame,
    day: dt.date,
    settings: Settings,
    listed_since: dt.datetime,
) -> ChannelVideo | None:
    """List the uploads for one game and return the video whose title matches
    it, with its thumbnail checked, or None. Raises SourceError."""
    uploads = await list_uploads(client, [(game, day)], settings, listed_since)
    found = find_video(uploads, game, day)
    return None if found is None else await check_thumbnail(client, found)


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
    if video.thumbnail_url is None:
        raise SourceError(SOURCE, f"video {video.video_id} has no thumbnail")
    if settings.video_embed_url is None:
        raise SourceError(SOURCE, "video embed URL is not configured")
    try:
        return Highlight.model_validate(
            {
                "title": video.title,
                "channel": video.channel,
                "thumbnail_url": video.thumbnail_url,
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
