# api/tests/jobs/test_news_recap_feed.py
#
# Tests for the news game recap kind.
#
# Tested:
# - With News off every id is unknown, serving raises UnknownFeedError and no request is sent
# - An English final game reads the summary once and serves the recap with the game's sides and score; a later request after a day sends nothing
# - A game whose summary has no article is marked and never read again for that language
# - A game that is not final serves an empty feed with no read
# - A recap an archived list stored is served without a summary read
# - Spanish serves the Spanish recap, else the English one (two summary reads at most), else an empty feed
# - A Spanish game feed holding the English recap is rebuilt every 15 minutes until the Spanish side is settled (recap archived or game marked); a Spanish recap is kept for good
# - A failed read leaves no mark and serves the archive; the next request after 15 minutes reads again
# - A final game of a stored day (a past game) is known and read; an unknown game is unknown with no read; a request before the days are loaded is not ready
# - A game with an archived recap is known even when the site holds no game
#
# What is covered:
# - Feed kind: success publishes a valid feed, failure keeps the archive, off answers unknown
#
# The recap adapter runs for real against respx routes, so route calls are real source requests.
#
# Run with: cd api && .venv/bin/python -m pytest tests/jobs/test_news_recap_feed.py
#
# SEE: api/app/jobs/news_recap_feed.py

import asyncio
import datetime as dt
from collections.abc import Iterator
from pathlib import Path
from typing import Any, cast

import httpx
import pytest
import respx

from app.feeds.days import PastGame
from app.feeds.games import GameStatus, LineScore, Score
from app.feeds.news import NewsKind, NewsLanguage
from app.feeds.news_article import NewsArticleFeed
from app.jobs.games import GamesJob
from app.jobs.news_recap_feed import KIND, NewsRecapFeeds
from app.jobs.on_demand import (
    FeedCache,
    FeedKind,
    FeedUnavailableError,
    IdStatus,
    UnknownFeedError,
)
from app.jobs.past_game_detail_feed import KIND as PAST_KIND
from app.jobs.past_game_detail_feed import PastGameDetailFeeds
from app.settings import Settings
from app.sources.http import create_client
from app.sources.scoreboard import ScoreboardGame
from app.storage.state import StateStore
from tests.jobs.test_news_feed import NOW, load, note
from tests.jobs.test_past_game_detail_feed import past_game

DETAIL = "https://example.com/summary/{game_id}"
MINUTE = dt.timedelta(minutes=1)
DAY = dt.timedelta(days=1)
EN = NewsLanguage.EN
ES = NewsLanguage.ES
START = dt.datetime(2026, 9, 1, 23, 0, tzinfo=dt.UTC)


def game(game_id: str, status: GameStatus = GameStatus.FINAL) -> ScoreboardGame:
    data: dict[str, Any] = {
        "id": game_id,
        "away": {"code": "NYK", "name": "Knicks", "city": "New York"},
        "home": {"code": "BOS", "name": "Celtics", "city": "Boston"},
        "status": status,
        "start_time": START,
        "venue": "Arena",
    }
    if status is GameStatus.FINAL:
        data["line_score"] = LineScore(away=[20, 20], home=[22, 21])
        data["score"] = Score(away=40, home=43)
    return ScoreboardGame.model_validate(data)


class RecapKit:
    """A feed cache and the recap kind over one client and one clock, with the real
    recap adapter reading counted respx routes."""

    def __init__(self, path: Path, *, enabled: bool = True) -> None:
        self.path = path
        self.clock = [NOW]
        self.store = StateStore(path)
        self.store.migrate()
        self.settings = Settings(  # type: ignore[call-arg]
            _env_file=None,
            data_dir=path,
            news_enabled=enabled,
            news_url="https://example.com/news",
            game_detail_url=DETAIL,
        )
        self.client = create_client(self.store, clock=lambda: self.clock[0])
        self.cache = FeedCache(path, self.store, clock=lambda: self.clock[0])
        self.loaded: dict[str, ScoreboardGame] = {}
        self.past: dict[str, PastGame] = {}
        self.days_loaded = True
        self.summaries: dict[str, Any] = {}
        self.requests: list[httpx.URL] = []
        self.cache.register(
            FeedKind(
                PAST_KIND,
                NewsArticleFeed,
                check=lambda game_id: (
                    IdStatus.KNOWN if game_id in self.past else IdStatus.UNKNOWN
                ),
                build=self.never,
                is_fresh=lambda feed, built_at, now: True,
                keep=lambda game_id: True,
            )
        )
        respx.get(url__startswith="https://example.com/summary/").mock(
            side_effect=self.answer
        )
        self.feeds = NewsRecapFeeds(
            self.settings,
            self.store,
            self.client,
            self.cache,
            cast(GamesJob, self),
            cast(PastGameDetailFeeds, self),
        )

    async def never(self, feed_id: str) -> NewsArticleFeed:
        raise AssertionError("the past kind is not built here")

    # The games job and the past game kind, as the recap kind reads them.
    def loaded_game(self, game_id: str) -> ScoreboardGame | None:
        return self.loaded.get(game_id)

    def shown_games(self) -> list[ScoreboardGame] | None:
        return list(self.loaded.values()) if self.days_loaded else None

    def past_game(self, game_id: str) -> PastGame | None:
        return self.past.get(game_id)

    def answer(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request.url)
        language = "es" if request.url.params.get("lang") == "es" else "en"
        body = self.summaries.get(language, "no-article")
        if body == "500":
            return httpx.Response(500)
        name = {
            "recap": f"summary-recap-{language}.json",
            "no-article": "summary-no-article.json",
        }[body]
        return httpx.Response(200, json=load(name))

    async def serve(
        self, feed_id: str, at: dt.datetime | None = None
    ) -> NewsArticleFeed:
        if at is not None:
            self.clock[0] = at
        body = await self.cache.serve(KIND, feed_id)
        await self.settle()
        return NewsArticleFeed.model_validate_json(body)

    async def settle(self) -> None:
        while self.cache.in_flight:
            await next(iter(self.cache.in_flight.values()))
            await asyncio.sleep(0)
        await asyncio.sleep(0)


@pytest.fixture(autouse=True)
def no_network() -> Iterator[None]:
    with respx.mock:
        yield


@pytest.fixture
def kit(tmp_path: Path) -> RecapKit:
    kit = RecapKit(tmp_path)
    kit.loaded["401"] = game("401")
    return kit


@pytest.mark.anyio
async def test_with_news_off_every_id_is_unknown_and_no_request_is_sent(
    tmp_path: Path,
) -> None:
    kit = RecapKit(tmp_path, enabled=False)
    kit.loaded["401"] = game("401")

    for feed_id in ("en-401", "es-401"):
        assert kit.feeds.check(feed_id) is IdStatus.UNKNOWN
        with pytest.raises(UnknownFeedError):
            await kit.cache.serve(KIND, feed_id)

    assert kit.requests == []


@pytest.mark.anyio
async def test_an_english_final_game_reads_the_summary_once_and_serves_the_recap_with_its_game(
    kit: RecapKit,
) -> None:
    kit.summaries["en"] = "recap"

    feed = await kit.serve("en-401")

    assert feed.note is not None
    assert (feed.note.id, feed.note.kind) == ("recap-401", NewsKind.RECAP)
    assert feed.note.published == START
    assert feed.note.teams == ["NYK", "BOS"]
    assert feed.game is not None
    assert (feed.game.id, feed.game.away.code, feed.game.home.code) == (
        "401",
        "NYK",
        "BOS",
    )
    assert feed.game.score == Score(away=40, home=43)
    assert len(kit.requests) == 1

    again = await kit.serve("en-401", NOW + DAY)

    assert again.note == feed.note
    assert len(kit.requests) == 1


@pytest.mark.anyio
async def test_a_game_with_no_article_is_marked_and_never_read_again(
    kit: RecapKit,
) -> None:
    feed = await kit.serve("en-401")

    assert (feed.note, feed.game) == (None, None)
    assert len(kit.requests) == 1
    assert kit.store.news_recap_missing("401", EN) is True
    assert kit.store.news_recap_missing("401", ES) is False

    await kit.serve("en-401", NOW + 16 * MINUTE)
    await kit.serve("en-401", NOW + DAY)

    assert len(kit.requests) == 1


@pytest.mark.anyio
async def test_a_game_that_is_not_final_serves_an_empty_feed_with_no_read(
    kit: RecapKit,
) -> None:
    kit.loaded["402"] = game("402", GameStatus.SCHEDULED)

    feed = await kit.serve("en-402")

    assert (feed.note, feed.game) == (None, None)
    assert kit.requests == []
    assert kit.store.news_recap_missing("402", EN) is False


@pytest.mark.anyio
async def test_a_recap_a_list_stored_is_served_without_a_summary_read(
    kit: RecapKit,
) -> None:
    kit.store.add_news_notes(
        [note("9003", 4, kind="recap", game_id="401", teams=["BOS"])], NOW
    )

    feed = await kit.serve("en-401")

    assert feed.note is not None and feed.note.id == "9003"
    assert feed.game is not None
    assert kit.requests == []


@pytest.mark.anyio
async def test_spanish_serves_the_spanish_recap(kit: RecapKit) -> None:
    kit.summaries["es"] = "recap"

    feed = await kit.serve("es-401")

    assert feed.note is not None and feed.note.language is ES
    assert [r.params.get("lang") for r in kit.requests] == ["es"]


@pytest.mark.anyio
async def test_spanish_falls_back_to_the_english_recap_with_two_reads_at_most(
    kit: RecapKit,
) -> None:
    kit.summaries["en"] = "recap"

    feed = await kit.serve("es-401")

    assert feed.note is not None and feed.note.language is EN
    assert [r.params.get("lang") for r in kit.requests] == ["es", None]
    assert kit.store.news_recap_missing("401", ES) is True
    assert kit.store.news_recap_missing("401", EN) is False


@pytest.mark.anyio
async def test_spanish_with_no_recap_in_either_language_is_empty(kit: RecapKit) -> None:
    feed = await kit.serve("es-401")

    assert (feed.note, feed.game) == (None, None)
    assert len(kit.requests) == 2
    assert kit.store.news_recap_missing("401", ES) is True
    assert kit.store.news_recap_missing("401", EN) is True


@pytest.mark.anyio
async def test_a_failed_read_leaves_no_mark_and_the_next_request_reads_again(
    kit: RecapKit,
) -> None:
    kit.summaries["en"] = "500"

    feed = await kit.serve("en-401")

    assert feed.note is None
    assert kit.store.news_recap_missing("401", EN) is False

    kit.summaries["en"] = "recap"
    # The stale feed is served at once and rebuilt in the background.
    await kit.serve("en-401", NOW + 16 * MINUTE)
    rebuilt = await kit.serve("en-401", NOW + 17 * MINUTE)

    assert rebuilt.note is not None
    assert len(kit.requests) == 2


@pytest.mark.anyio
async def test_a_failed_spanish_read_serves_the_archived_english_recap(
    kit: RecapKit,
) -> None:
    kit.summaries["es"] = "500"
    kit.store.add_news_notes(
        [note("9003", 4, kind="recap", game_id="401", teams=["BOS"])], NOW
    )

    feed = await kit.serve("es-401")

    assert feed.note is not None and feed.note.id == "9003"
    assert kit.store.news_recap_missing("401", ES) is False
    assert len(kit.requests) == 1


@pytest.mark.anyio
async def test_a_spanish_feed_that_fell_back_to_english_reads_spanish_again_later(
    kit: RecapKit,
) -> None:
    kit.summaries["es"] = "500"
    kit.store.add_news_notes(
        [note("9003", 4, kind="recap", game_id="401", teams=["BOS"])], NOW
    )
    first = await kit.serve("es-401")
    assert first.note is not None and first.note.language is EN

    kit.summaries["es"] = "recap"
    # The stale feed is served at once and rebuilt in the background.
    await kit.serve("es-401", NOW + 16 * MINUTE)
    rebuilt = await kit.serve("es-401", NOW + 17 * MINUTE)

    assert rebuilt.note is not None and rebuilt.note.language is ES
    assert len(kit.requests) == 2


@pytest.mark.anyio
async def test_a_game_the_site_gets_later_reads_spanish_after_15_minutes(
    kit: RecapKit,
) -> None:
    del kit.loaded["401"]
    kit.summaries["es"] = "recap"
    kit.store.add_news_notes(
        [note("9003", 4, kind="recap", game_id="401", teams=["BOS"])], NOW
    )
    first = await kit.serve("es-401")
    assert first.note is not None and first.note.language is EN
    assert kit.requests == []

    kit.past["401"] = past_game("401")
    await kit.serve("es-401", NOW + 16 * MINUTE)
    rebuilt = await kit.serve("es-401", NOW + 17 * MINUTE)

    assert rebuilt.note is not None and rebuilt.note.language is ES
    assert len(kit.requests) == 1


@pytest.mark.anyio
async def test_an_english_recap_is_kept_once_the_spanish_side_is_settled(
    kit: RecapKit,
) -> None:
    kit.summaries["es"] = "no-article"
    kit.store.add_news_notes(
        [note("9003", 4, kind="recap", game_id="401", teams=["BOS"])], NOW
    )
    first = await kit.serve("es-401")
    assert first.note is not None and first.note.language is EN
    assert kit.store.news_recap_missing("401", ES) is True
    sent = len(kit.requests)

    await kit.serve("es-401", NOW + 16 * MINUTE)
    again = await kit.serve("es-401", NOW + 17 * MINUTE)

    assert again.note is not None and again.note.language is EN
    assert len(kit.requests) == sent


@pytest.mark.anyio
async def test_a_spanish_recap_is_kept_for_good(kit: RecapKit) -> None:
    kit.summaries["es"] = "recap"
    first = await kit.serve("es-401")
    assert first.note is not None and first.note.language is ES

    await kit.serve("es-401", NOW + 16 * MINUTE)
    again = await kit.serve("es-401", NOW + 17 * MINUTE)

    assert again.note is not None and again.note.language is ES
    assert len(kit.requests) == 1


@pytest.mark.anyio
async def test_a_final_game_of_a_stored_day_is_known_and_read(kit: RecapKit) -> None:
    kit.past["1"] = past_game("1")
    kit.summaries["en"] = "recap"

    assert kit.feeds.check("en-1") is IdStatus.KNOWN
    feed = await kit.serve("en-1")

    assert feed.note is not None and feed.note.id == "recap-1"
    assert feed.game is not None and feed.game.id == "1"
    assert len(kit.requests) == 1


@pytest.mark.anyio
async def test_an_unknown_game_is_unknown_with_no_read(kit: RecapKit) -> None:
    assert kit.feeds.check("en-999") is IdStatus.UNKNOWN
    with pytest.raises(UnknownFeedError):
        await kit.cache.serve(KIND, "en-999")
    for bad in ("fr-401", "en-", "en-a/b", "401"):
        assert kit.feeds.check(bad) is IdStatus.UNKNOWN
    assert kit.requests == []


@pytest.mark.anyio
async def test_a_request_before_the_days_are_loaded_is_not_ready(kit: RecapKit) -> None:
    kit.days_loaded = False

    assert kit.feeds.check("en-999") is IdStatus.NOT_READY
    with pytest.raises(FeedUnavailableError):
        await kit.cache.serve(KIND, "en-999")
    assert kit.feeds.check("en-401") is IdStatus.KNOWN
    assert kit.requests == []


@pytest.mark.anyio
async def test_a_game_with_an_archived_recap_is_known_without_a_site_game(
    kit: RecapKit,
) -> None:
    kit.store.add_news_notes(
        [note("9003", 4, kind="recap", game_id="500", teams=["BOS"])], NOW
    )

    feed = await kit.serve("en-500")

    assert feed.note is not None and feed.note.id == "9003"
    assert feed.game is None
    assert kit.requests == []
