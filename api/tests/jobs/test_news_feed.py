# api/tests/jobs/test_news_feed.py
#
# Tests for the news list kind (league, team and player pages).
#
# Tested:
# - With News off every id is unknown, serving raises UnknownFeedError and no request is sent
# - Ids: only en or es, the three scopes, a page that is a positive integer without a leading zero and one of the 30 lower-case team codes parse
# - League, team and player pages in English and Spanish return the expected notes from the fixtures
# - A team page reads that team's list; a player page reads his current team's list, returns only notes naming him and adds an archived note naming him that the list lacks
# - A player on no roster and named by no note is unknown, and not ready before the rosters; a player named by an archived note is known
# - Freshness: a second page and a repeated team page within 15 minutes send no new list read; a request at 14:59 sends none; a request at 15:00 serves the stored page and sends exactly one read
# - A failed read (500 or timeout) serves the archived notes and stores the feed; with an empty archive it serves an empty first page
# - Paging: page 2 is unknown until the archive holds more than 12 notes, and hasMore is set on page 1 only
# - No link: the only URL-like strings in a served body are photo URLs
# - A build sends at most one read
#
# What is covered:
# - Feed kind: success publishes a valid feed, failure serves the archive, off answers unknown
#
# The list adapter runs for real against respx routes, so route calls are real source requests.
#
# Run with: cd api && .venv/bin/python -m pytest tests/jobs/test_news_feed.py
#
# SEE: api/app/jobs/news_feed.py

import asyncio
import datetime as dt
import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any, cast

import httpx
import pytest
import respx

from app.feeds.news import PAGE_SIZE, NewsFeed, NewsLanguage, NewsNote
from app.jobs.news_feed import KIND, NewsFeeds, NewsScope, parse_id
from app.jobs.on_demand import (
    FeedCache,
    FeedUnavailableError,
    IdStatus,
    UnknownFeedError,
)
from app.jobs.stars import StarsJob
from app.settings import Settings
from app.sources.http import create_client
from app.storage.feeds import read_by_id
from app.storage.state import StateStore

FIXTURES = Path(__file__).parents[1] / "sources" / "fixtures" / "news"
NEWS = "https://example.com/news"
DETAIL = "https://example.com/summary/{game_id}"
NOW = dt.datetime(2026, 11, 3, 15, 0, tzinfo=dt.UTC)
MINUTE = dt.timedelta(minutes=1)

EN = NewsLanguage.EN
ES = NewsLanguage.ES


def load(name: str) -> Any:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def note(note_id: str, hour: int, *, day: int = 2, **more: Any) -> NewsNote:
    return NewsNote.model_validate(
        {
            "id": note_id,
            "language": "en",
            "kind": "news",
            "headline": f"Headline {note_id}",
            "description": None,
            "published": dt.datetime(2026, 10, day, hour, 0, tzinfo=dt.UTC),
            "photo": None,
            "teams": [],
            "players": [],
            "game_id": None,
        }
        | more
    )


class StubStars:
    def __init__(self) -> None:
        self.teams = {"111": "BOS"}
        self.ready = True

    def player_team(self, player_id: str) -> str | None:
        return self.teams.get(player_id)

    def rosters_ready(self) -> bool:
        return self.ready


class NewsKit:
    """A feed cache and the news list kind over one client and one clock, with the
    real list adapter reading counted respx routes."""

    def __init__(self, path: Path, *, enabled: bool = True) -> None:
        self.path = path
        self.clock = [NOW]
        self.store = StateStore(path)
        self.store.migrate()
        self.settings = Settings(  # type: ignore[call-arg]
            _env_file=None,
            data_dir=path,
            news_enabled=enabled,
            news_url=NEWS,
            game_detail_url=DETAIL,
        )
        self.client = create_client(self.store, clock=lambda: self.clock[0])
        self.cache = FeedCache(path, self.store, clock=lambda: self.clock[0])
        self.stars = StubStars()
        self.requests: list[httpx.URL] = []
        self.failure: str | None = None
        respx.get(url__startswith=NEWS).mock(side_effect=self.answer)
        self.feeds = NewsFeeds(
            self.settings,
            self.store,
            self.client,
            self.cache,
            cast(StarsJob, self.stars),
        )

    def answer(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request.url)
        if self.failure == "timeout":
            raise httpx.ReadTimeout("slow")
        if self.failure == "500":
            return httpx.Response(500)
        spanish = request.url.params.get("lang") == "es"
        return httpx.Response(
            200, json=load("list-es.json" if spanish else "list-en.json")
        )

    async def serve(self, feed_id: str, at: dt.datetime | None = None) -> NewsFeed:
        if at is not None:
            self.clock[0] = at
        body = await self.cache.serve(KIND, feed_id)
        await self.settle()
        return NewsFeed.model_validate_json(body)

    async def settle(self) -> None:
        while self.cache.in_flight:
            await next(iter(self.cache.in_flight.values()))
            await asyncio.sleep(0)
        await asyncio.sleep(0)

    def fill(self, count: int) -> None:
        """Archive `count` older English notes."""
        self.store.add_news_notes(
            [note(f"old{n}", n % 24, day=1 + n // 24) for n in range(count)], NOW
        )


@pytest.fixture(autouse=True)
def no_network() -> Iterator[None]:
    with respx.mock:
        yield


@pytest.fixture
def kit(tmp_path: Path) -> NewsKit:
    return NewsKit(tmp_path)


def ids(feed: NewsFeed) -> list[str]:
    return [item.id for item in feed.notes]


@pytest.mark.parametrize(
    ("feed_id", "expected"),
    [
        ("en-league-1", NewsScope(EN, None, None, 1)),
        ("es-league-12", NewsScope(ES, None, None, 12)),
        ("en-team-bos-2", NewsScope(EN, "BOS", None, 2)),
        ("es-player-111-3", NewsScope(ES, None, "111", 3)),
    ],
)
def test_parses_the_three_scopes(feed_id: str, expected: NewsScope) -> None:
    assert parse_id(feed_id) == expected


@pytest.mark.parametrize(
    "feed_id",
    [
        "fr-league-1",
        "EN-league-1",
        "en-league-0",
        "en-league-01",
        "en-league-1.5",
        "en-league-123456789",
        "en-league",
        "en-team-BOS-1",
        "en-team-xxx-1",
        "en-team-bos",
        "en-player--1",
        "en-player-1-1-1",
        "en-player-a/b-1",
        "",
    ],
)
def test_rejects_an_id_that_is_not_a_news_page(feed_id: str) -> None:
    assert parse_id(feed_id) is None


@pytest.mark.anyio
async def test_with_news_off_every_id_is_unknown_and_no_request_is_sent(
    tmp_path: Path,
) -> None:
    kit = NewsKit(tmp_path, enabled=False)

    for feed_id in ("en-league-1", "es-team-bos-1", "en-player-111-1"):
        assert kit.feeds.check(feed_id) is IdStatus.UNKNOWN
        with pytest.raises(UnknownFeedError):
            await kit.cache.serve(KIND, feed_id)

    assert kit.requests == []


@pytest.mark.anyio
async def test_serves_the_league_page_in_english(kit: NewsKit) -> None:
    feed = await kit.serve("en-league-1")

    assert ids(feed) == ["9001", "9002", "9003", "9007"]
    assert (feed.page, feed.has_more) == (1, False)
    assert len(kit.requests) == 1
    assert kit.requests[0].params["limit"] == "50"
    assert "lang" not in kit.requests[0].params


@pytest.mark.anyio
async def test_serves_the_league_page_in_spanish(kit: NewsKit) -> None:
    feed = await kit.serve("es-league-1")

    assert ids(feed) == ["8001"]
    assert feed.notes[0].language is ES
    assert kit.requests[0].params["lang"] == "es"
    assert kit.requests[0].params["region"] == "us"


@pytest.mark.anyio
async def test_spanish_pages_list_an_archived_english_recap_without_a_spanish_one(
    kit: NewsKit,
) -> None:
    await kit.serve("en-league-1")

    feed = await kit.serve("es-league-1")

    assert ids(feed) == ["8001", "9003"]
    assert feed.notes[1].language is EN


@pytest.mark.anyio
async def test_serves_a_team_page_from_that_teams_list(kit: NewsKit) -> None:
    feed = await kit.serve("en-team-bos-1")

    assert kit.requests[0].params["team"] == "bos"
    assert ids(feed) == ["9001", "9002", "9003"]


@pytest.mark.anyio
async def test_serves_a_player_page_with_only_the_notes_naming_him(
    kit: NewsKit,
) -> None:
    feed = await kit.serve("en-player-111-1")

    assert kit.requests[0].params["team"] == "bos"
    assert ids(feed) == ["9001"]


@pytest.mark.anyio
async def test_a_player_page_adds_an_archived_note_the_list_lacks(kit: NewsKit) -> None:
    kit.store.add_news_notes(
        [note("old1", 5, players=[{"player_id": "111", "name": "Ana Lee"}])], NOW
    )

    feed = await kit.serve("en-player-111-1")

    assert ids(feed) == ["9001", "old1"]


@pytest.mark.anyio
async def test_a_player_on_no_roster_and_named_by_no_note_is_unknown(
    kit: NewsKit,
) -> None:
    assert kit.feeds.check("en-player-999-1") is IdStatus.UNKNOWN
    with pytest.raises(UnknownFeedError):
        await kit.cache.serve(KIND, "en-player-999-1")
    assert kit.requests == []


@pytest.mark.anyio
async def test_a_player_page_is_not_ready_before_the_rosters(kit: NewsKit) -> None:
    kit.stars.ready = False

    assert kit.feeds.check("en-player-999-1") is IdStatus.NOT_READY
    with pytest.raises(FeedUnavailableError):
        await kit.cache.serve(KIND, "en-player-999-1")
    assert kit.feeds.check("en-player-111-1") is IdStatus.KNOWN


@pytest.mark.anyio
async def test_a_player_named_by_an_archived_note_is_known_without_a_roster(
    kit: NewsKit,
) -> None:
    kit.store.add_news_notes(
        [note("old1", 5, players=[{"player_id": "999", "name": "Cy Dunn"}])], NOW
    )

    feed = await kit.serve("en-player-999-1")

    assert ids(feed) == ["old1"]
    assert kit.requests == []


@pytest.mark.anyio
async def test_a_second_page_and_a_repeated_team_page_within_15_minutes_send_no_new_read(
    kit: NewsKit,
) -> None:
    kit.fill(PAGE_SIZE)
    await kit.serve("en-league-1")
    await kit.serve("en-team-bos-1")
    reads = len(kit.requests)

    second = await kit.serve("en-league-2", NOW + 5 * MINUTE)
    await kit.serve("en-team-bos-1", NOW + 6 * MINUTE)
    await kit.serve("en-league-1", NOW + 7 * MINUTE)

    assert reads == 2
    assert len(kit.requests) == 2
    assert second.page == 2


@pytest.mark.anyio
async def test_a_request_at_14_59_sends_no_read_and_one_at_15_00_sends_exactly_one(
    kit: NewsKit,
) -> None:
    await kit.serve("en-league-1")
    assert len(kit.requests) == 1

    await kit.serve("en-league-1", NOW + 14 * MINUTE + dt.timedelta(seconds=59))
    assert len(kit.requests) == 1

    stored = await kit.serve("en-league-1", NOW + 15 * MINUTE)
    assert len(kit.requests) == 2
    assert ids(stored) == ["9001", "9002", "9003", "9007"]


@pytest.mark.anyio
@pytest.mark.parametrize("failure", ["500", "timeout"])
async def test_a_failed_read_serves_the_archive_and_stores_the_feed(
    kit: NewsKit, failure: str
) -> None:
    kit.store.add_news_notes([note("old1", 5), note("old2", 6)], NOW)
    kit.failure = failure

    feed = await kit.serve("en-league-1")

    assert ids(feed) == ["old2", "old1"]
    assert read_by_id(kit.path, KIND, "en-league-1") is not None


@pytest.mark.anyio
async def test_a_failed_read_with_an_empty_archive_serves_an_empty_first_page(
    kit: NewsKit,
) -> None:
    kit.failure = "500"

    feed = await kit.serve("en-league-1")

    assert (feed.page, feed.has_more, feed.notes) == (1, False, [])


@pytest.mark.anyio
async def test_page_2_is_unknown_until_the_archive_holds_more_than_12_notes(
    kit: NewsKit,
) -> None:
    kit.fill(PAGE_SIZE - 1)
    kit.store.add_news_notes([note("old-last", 0, day=1)], NOW)
    assert kit.store.count_news_notes(EN) == PAGE_SIZE
    assert kit.feeds.check("en-league-2") is IdStatus.UNKNOWN

    first = await kit.serve("en-league-1")

    # The list adds four notes: 16 in all, so a second page now exists.
    assert len(first.notes) == PAGE_SIZE
    assert first.has_more is True
    assert kit.feeds.check("en-league-2") is IdStatus.KNOWN
    second = await kit.serve("en-league-2")
    assert (second.page, second.has_more, len(second.notes)) == (2, False, 4)
    assert kit.feeds.check("en-league-3") is IdStatus.UNKNOWN


@pytest.mark.anyio
async def test_a_served_body_holds_no_url_but_photo_urls(kit: NewsKit) -> None:
    body = await kit.cache.serve(KIND, "en-league-1")
    await kit.settle()

    def urls(value: Any, path: str = "") -> list[tuple[str, str]]:
        if isinstance(value, dict):
            return [u for k, v in value.items() for u in urls(v, f"{path}.{k}")]
        if isinstance(value, list):
            return [u for item in value for u in urls(item, path)]
        if isinstance(value, str) and "://" in value:
            return [(path, value)]
        return []

    found = urls(json.loads(body))
    assert found
    assert {path for path, _ in found} == {".notes.photo.url"}
    assert "example.com/story" not in body.decode()


@pytest.mark.anyio
async def test_a_build_sends_at_most_one_read(kit: NewsKit) -> None:
    await kit.serve("en-team-bos-1")

    assert len(kit.requests) == 1
