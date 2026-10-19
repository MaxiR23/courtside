# api/tests/jobs/test_highlights_search.py
#
# Tests for the on-demand highlights search.
#
# Tested:
# - With a match it stores the highlight and the next request serves it
# - It skips a match without a served thumbnail and takes the next
# - Without a match it stores a mark and never searches that game again
# - Past the daily cap it neither searches nor marks
# - A query the source cache holds still runs and saves or marks but is not counted against the daily cap; an uncached one counts one
# - A search that loses the race for the last slot neither searches nor marks
# - The cap survives a new search over the same store
# - A mark starts no search
# - Without the search API URL, the key or the embed URL no search runs
# - At most one search per target is in flight
# - The request returns before the search ends
# - A failed search request leaves no mark and logs the target
# - A failed thumbnail check request leaves no mark; another thumbnail error skips the result
# - The game query is away, home, full game highlights and the date
# - A target of another kind saves through its own function
#
# What is covered:
# - Job-like: a success stores, a failure keeps the state and leaves no mark
#
# The search and the thumbnail check are fakes passed to the search, the client clock
# is frozen and every test runs in an empty respx mock: a real request fails.
#
# Run with: cd api && .venv/bin/python -m pytest tests/jobs/test_highlights_search.py
#
# SEE: api/app/jobs/highlights_search.py

import asyncio
import datetime as dt
import logging
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx

from app.feeds.games import GameStatus, GameTeam, Highlight
from app.jobs.highlights import HighlightsJob
from app.jobs.highlights_search import GAME, HighlightsSearch, SearchTarget
from app.settings import Settings
from app.sources.http import SourceError, create_client
from app.sources.scoreboard import ScoreboardGame
from app.sources.video_channel import ChannelVideo
from app.storage.state import StateStore

# 21:00 US Eastern (EDT) on 2026-10-04.
START = dt.datetime(2026, 10, 5, 1, 0, tzinfo=dt.UTC)
NOW = dt.datetime(2026, 10, 12, 16, 0, tzinfo=dt.UTC)
TODAY = dt.date(2026, 10, 12)
GULLS, OWLS = "Harbor City Gulls", "Example Town Owls"
TITLE = f"{GULLS} at {OWLS} | FULL GAME HIGHLIGHTS | October 4, 2026"


def video(
    video_id: str, title: str = TITLE, thumbnail: str | None = None
) -> ChannelVideo:
    return ChannelVideo(
        video_id=video_id,
        title=title,
        channel="Example Channel",
        published_at=NOW,
        thumbnail_url=None,
        thumbnail_candidates=(f"https://example.com/thumbs/{video_id}.jpg",),
    )


class FakeSearch:
    def __init__(self) -> None:
        self.results: list[ChannelVideo] = [video("v1")]
        self.error: SourceError | None = None
        self.queries: list[str] = []
        self.gate: asyncio.Event | None = None
        self.unserved: set[str] = set()
        self.thumbnail_errors: dict[str, SourceError] = {}

    async def search(
        self, client: httpx.AsyncClient, settings: Settings, query: str
    ) -> list[ChannelVideo]:
        self.queries.append(query)
        if self.gate is not None:
            await self.gate.wait()
        if self.error is not None:
            raise self.error
        return list(self.results)

    async def check_thumbnail(
        self, client: httpx.AsyncClient, found: ChannelVideo
    ) -> ChannelVideo:
        if found.video_id in self.thumbnail_errors:
            raise self.thumbnail_errors[found.video_id]
        if found.video_id in self.unserved:
            return found
        return found.model_copy(update={"thumbnail_url": found.thumbnail_candidates[0]})


@pytest.fixture(autouse=True)
def no_network() -> Iterator[None]:
    with respx.mock:
        yield


@pytest.fixture
def fake() -> FakeSearch:
    return FakeSearch()


@pytest.fixture
def store(tmp_path: Path) -> StateStore:
    state = StateStore(tmp_path)
    state.migrate()
    return state


def make_settings(tmp_path: Path, **values: Any) -> Settings:
    defaults: dict[str, Any] = {
        "highlights_search_api_url": "https://example.com/search",
        "highlights_source_key": "test-key-value",
        "video_embed_url": "https://example.com/e/{video_id}",
    }
    return Settings(_env_file=None, data_dir=tmp_path, **{**defaults, **values})  # type: ignore[call-arg]


class Kit:
    def __init__(
        self,
        tmp_path: Path,
        store: StateStore,
        fake: FakeSearch,
        cached: bool | None = None,
        **values: Any,
    ) -> None:
        self.store = store
        self.settings = make_settings(tmp_path, **values)
        self.client = create_client(store, clock=lambda: NOW)
        self.highlights = HighlightsJob(
            self.settings, store, self.client, final_games=list
        )
        self.search = HighlightsSearch(
            self.settings,
            store,
            self.client,
            self.highlights,
            search=fake.search,
            check_thumbnail=fake.check_thumbnail,
            **({} if cached is None else {"is_cached": lambda *_: cached}),
        )

    def request(self) -> None:
        self.search.request_game("g1", GULLS, OWLS, START)


def a_game() -> ScoreboardGame:
    return ScoreboardGame(
        id="g1",
        away=GameTeam(code="GSW", name=GULLS, city="Harbor City"),
        home=GameTeam(code="LAC", name=OWLS, city="Example Town"),
        status=GameStatus.FINAL,
        start_time=START,
        venue="Arena",
        line_score={"away": [20], "home": [18]},  # type: ignore[arg-type]
        score={"away": 20, "home": 18},  # type: ignore[arg-type]
    )


async def drain() -> None:
    for _ in range(30):
        await asyncio.sleep(0)


@pytest.mark.anyio
async def test_with_a_match_it_stores_the_highlight_and_the_next_request_serves_it(
    tmp_path: Path, store: StateStore, fake: FakeSearch
) -> None:
    kit = Kit(tmp_path, store, fake)
    assert kit.highlights.highlights_of(a_game()) == []

    kit.request()
    await drain()

    served = kit.highlights.highlights_of(a_game())
    assert [str(h.embed_url) for h in served] == ["https://example.com/e/v1"]
    assert str(served[0].thumbnail_url) == "https://example.com/thumbs/v1.jpg"
    assert store.highlights()["g1"] == served[0]
    assert not store.highlight_searched(GAME, "g1")
    assert store.highlight_searches_on(TODAY) == 1


@pytest.mark.anyio
async def test_it_skips_a_match_without_a_served_thumbnail_and_takes_the_next(
    tmp_path: Path, store: StateStore, fake: FakeSearch
) -> None:
    fake.results = [
        video("clip", "Player Scores 30 For The Example Town Owls | October 4, 2026"),
        video("unserved"),
        video("broken"),
        video("v2"),
    ]
    fake.unserved = {"unserved"}
    fake.thumbnail_errors = {"broken": SourceError("video_channel", "no host")}
    kit = Kit(tmp_path, store, fake)

    kit.request()
    await drain()

    assert [str(h.embed_url) for h in kit.highlights.highlights_of(a_game())] == [
        "https://example.com/e/v2"
    ]


@pytest.mark.anyio
async def test_without_a_match_it_stores_a_mark_and_never_searches_that_game_again(
    tmp_path: Path, store: StateStore, fake: FakeSearch
) -> None:
    fake.results = [video("clip", "Player Scores 30 | October 4, 2026")]
    kit = Kit(tmp_path, store, fake)

    kit.request()
    await drain()
    kit.request()
    await drain()

    assert store.highlight_searched(GAME, "g1")
    assert kit.highlights.highlights_of(a_game()) == []
    assert len(fake.queries) == 1
    assert store.highlight_searches_on(TODAY) == 1


@pytest.mark.anyio
async def test_past_the_daily_cap_it_neither_searches_nor_marks(
    tmp_path: Path, store: StateStore, fake: FakeSearch
) -> None:
    kit = Kit(tmp_path, store, fake, highlights_search_daily_cap=1)
    assert store.take_highlight_search(TODAY, 1)

    kit.request()
    await drain()

    assert fake.queries == []
    assert not store.highlight_searched(GAME, "g1")
    assert store.highlight_searches_on(TODAY) == 1
    assert kit.highlights.highlights_of(a_game()) == []


@pytest.mark.anyio
async def test_a_query_held_by_the_source_cache_runs_without_using_the_daily_cap(
    tmp_path: Path, store: StateStore, fake: FakeSearch
) -> None:
    kit = Kit(tmp_path, store, fake, cached=True)

    kit.request()
    await drain()

    assert len(fake.queries) == 1
    assert kit.highlights.highlights_of(a_game()) != []
    assert store.highlight_searches_on(TODAY) == 0


@pytest.mark.anyio
async def test_a_cached_query_without_a_match_still_marks_and_is_not_counted(
    tmp_path: Path, store: StateStore, fake: FakeSearch
) -> None:
    fake.results = []
    kit = Kit(tmp_path, store, fake, cached=True)

    kit.request()
    await drain()

    assert store.highlight_searched(GAME, "g1")
    assert store.highlight_searches_on(TODAY) == 0


@pytest.mark.anyio
async def test_a_query_missing_from_the_source_cache_counts_one(
    tmp_path: Path, store: StateStore, fake: FakeSearch
) -> None:
    kit = Kit(tmp_path, store, fake, cached=False)

    kit.request()
    await drain()

    assert len(fake.queries) == 1
    assert store.highlight_searches_on(TODAY) == 1


@pytest.mark.anyio
async def test_a_search_that_loses_the_race_for_the_last_slot_neither_searches_nor_marks(
    tmp_path: Path, store: StateStore, fake: FakeSearch
) -> None:
    kit = Kit(tmp_path, store, fake, highlights_search_daily_cap=1)
    fake.gate = asyncio.Event()
    kit.request()
    kit.search.request(
        SearchTarget(GAME, "g2", "other query", lambda title: True, lambda h: None)
    )
    await drain()
    fake.gate.set()
    await drain()

    assert len(fake.queries) == 1
    assert store.highlight_searches_on(TODAY) == 1
    assert not store.highlight_searched(GAME, "g2")


@pytest.mark.anyio
async def test_the_cap_survives_a_new_search_over_the_same_store(
    tmp_path: Path, store: StateStore, fake: FakeSearch
) -> None:
    first = Kit(tmp_path, store, fake, highlights_search_daily_cap=1)
    first.request()
    await drain()
    assert len(fake.queries) == 1

    second = Kit(tmp_path, StateStore(tmp_path), fake, highlights_search_daily_cap=1)
    second.search.request_game("g2", GULLS, OWLS, START)
    await drain()

    assert len(fake.queries) == 1


@pytest.mark.anyio
async def test_a_mark_starts_no_search(
    tmp_path: Path, store: StateStore, fake: FakeSearch
) -> None:
    store.mark_highlight_searched(GAME, "g1", NOW)
    kit = Kit(tmp_path, store, fake)

    kit.request()
    await drain()

    assert fake.queries == []
    assert store.highlight_searches_on(TODAY) == 0


@pytest.mark.anyio
@pytest.mark.parametrize(
    "unset",
    ["highlights_search_api_url", "highlights_source_key", "video_embed_url"],
)
async def test_without_the_search_api_url_the_key_or_the_embed_url_no_search_runs(
    tmp_path: Path, store: StateStore, fake: FakeSearch, unset: str
) -> None:
    kit = Kit(tmp_path, store, fake, **{unset: None})

    kit.request()
    await drain()

    assert fake.queries == []
    assert store.highlight_searches_on(TODAY) == 0
    assert not store.highlight_searched(GAME, "g1")


@pytest.mark.anyio
async def test_at_most_one_search_per_target_is_in_flight(
    tmp_path: Path, store: StateStore, fake: FakeSearch
) -> None:
    kit = Kit(tmp_path, store, fake)
    fake.gate = asyncio.Event()

    kit.request()
    kit.request()
    await drain()
    assert fake.queries != [] and len(fake.queries) == 1
    fake.gate.set()
    await drain()

    assert len(fake.queries) == 1
    assert store.highlight_searches_on(TODAY) == 1


@pytest.mark.anyio
async def test_request_returns_before_the_search_ends(
    tmp_path: Path, store: StateStore, fake: FakeSearch
) -> None:
    kit = Kit(tmp_path, store, fake)
    fake.gate = asyncio.Event()

    kit.request()

    assert kit.highlights.highlights_of(a_game()) == []
    assert fake.queries == []
    await drain()
    assert len(fake.queries) == 1
    assert kit.highlights.highlights_of(a_game()) == []
    fake.gate.set()
    await drain()
    assert len(kit.highlights.highlights_of(a_game())) == 1


@pytest.mark.anyio
async def test_a_failed_search_request_leaves_no_mark_and_logs_the_target(
    tmp_path: Path,
    store: StateStore,
    fake: FakeSearch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    fake.error = SourceError("video_channel", "request failed", request_failed=True)
    kit = Kit(tmp_path, store, fake)

    with caplog.at_level(logging.WARNING, logger="app.jobs.highlights_search"):
        kit.request()
        await drain()

    assert not store.highlight_searched(GAME, "g1")
    assert kit.highlights.highlights_of(a_game()) == []
    assert "highlights search: game g1: request failed" in caplog.text
    assert "test-key-value" not in caplog.text


@pytest.mark.anyio
async def test_a_failed_thumbnail_request_leaves_no_mark(
    tmp_path: Path, store: StateStore, fake: FakeSearch
) -> None:
    fake.thumbnail_errors = {
        "v1": SourceError("video_channel", "request failed", request_failed=True)
    }
    kit = Kit(tmp_path, store, fake)

    kit.request()
    await drain()

    assert not store.highlight_searched(GAME, "g1")
    assert kit.highlights.highlights_of(a_game()) == []


@pytest.mark.anyio
async def test_the_game_query_is_away_home_full_game_highlights_and_the_date(
    tmp_path: Path, store: StateStore, fake: FakeSearch
) -> None:
    kit = Kit(tmp_path, store, fake)

    kit.request()
    await drain()

    assert fake.queries == [
        "Harbor City Gulls Example Town Owls full game highlights October 4, 2026"
    ]


@pytest.mark.anyio
async def test_a_target_of_another_kind_saves_through_its_own_function(
    tmp_path: Path, store: StateStore, fake: FakeSearch
) -> None:
    kit = Kit(tmp_path, store, fake)
    saved: list[Highlight] = []

    kit.search.request(
        SearchTarget(
            "edition", "2027", "edition query", lambda title: True, saved.append
        )
    )
    await drain()

    assert len(saved) == 1
    assert store.highlights() == {}
    assert fake.queries == ["edition query"]
