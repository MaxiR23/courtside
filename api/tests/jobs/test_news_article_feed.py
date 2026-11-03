# api/tests/jobs/test_news_article_feed.py
#
# Tests for the news article kind and its shared game helpers.
#
# Tested:
# - An archived note is served with its tags, plus the game's sides and score when the site holds the game, and no game otherwise
# - The game comes from a final game of a stored day when the games job does not hold it
# - The Spanish path serves an English recap and does not serve an English news note
# - A Spanish note wins over the English recap of the same id
# - An id not archived, an unsafe id and a language other than en or es are unknown with no read; with News off every id is unknown
# - A feed is rebuilt 15 minutes after its build, so a game the site gets later is picked up
# - news_game keeps the sides and score without their identities
#
# What is covered:
# - Feed kind: success publishes a valid feed, unknown ids answer unknown, off answers unknown
#
# Run with: cd api && .venv/bin/python -m pytest tests/jobs/test_news_article_feed.py
#
# SEE: api/app/jobs/news_article_feed.py

import asyncio
import datetime as dt
from collections.abc import Iterator
from pathlib import Path
from typing import cast

import pytest
import respx

from app.feeds.days import PastGame
from app.feeds.games import Score
from app.feeds.news import NewsLanguage
from app.feeds.news_article import NewsArticleFeed
from app.jobs.games import GamesJob
from app.jobs.news_article_feed import KIND, NewsArticleFeeds, news_game
from app.jobs.on_demand import FeedCache, IdStatus, UnknownFeedError
from app.jobs.past_game_detail_feed import PastGameDetailFeeds
from app.settings import Settings
from app.sources.scoreboard import ScoreboardGame
from app.storage.state import StateStore
from tests.jobs.test_news_feed import NOW, note
from tests.jobs.test_news_recap_feed import game
from tests.jobs.test_past_game_detail_feed import past_game

MINUTE = dt.timedelta(minutes=1)


class ArticleKit:
    """A feed cache and the article kind over one clock."""

    def __init__(self, path: Path, *, enabled: bool = True) -> None:
        self.clock = [NOW]
        self.store = StateStore(path)
        self.store.migrate()
        self.settings = Settings(  # type: ignore[call-arg]
            _env_file=None, data_dir=path, news_enabled=enabled
        )
        self.cache = FeedCache(path, self.store, clock=lambda: self.clock[0])
        self.loaded: dict[str, ScoreboardGame] = {}
        self.past: dict[str, PastGame] = {}
        self.feeds = NewsArticleFeeds(
            self.settings,
            self.store,
            self.cache,
            cast(GamesJob, self),
            cast(PastGameDetailFeeds, self),
        )

    def loaded_game(self, game_id: str) -> ScoreboardGame | None:
        return self.loaded.get(game_id)

    def past_game(self, game_id: str) -> PastGame | None:
        return self.past.get(game_id)

    async def serve(
        self, feed_id: str, at: dt.datetime | None = None
    ) -> NewsArticleFeed:
        if at is not None:
            self.clock[0] = at
        body = await self.cache.serve(KIND, feed_id)
        while self.cache.in_flight:
            await next(iter(self.cache.in_flight.values()))
            await asyncio.sleep(0)
        await asyncio.sleep(0)
        return NewsArticleFeed.model_validate_json(body)


@pytest.fixture(autouse=True)
def no_network() -> Iterator[None]:
    with respx.mock:
        yield


@pytest.fixture
def kit(tmp_path: Path) -> ArticleKit:
    return ArticleKit(tmp_path)


@pytest.mark.anyio
async def test_serves_an_archived_note_with_its_tags_and_the_game_the_site_holds(
    kit: ArticleKit,
) -> None:
    kit.store.add_news_notes(
        [
            note(
                "9001",
                4,
                teams=["BOS", "NYK"],
                players=[{"player_id": "111", "name": "Ana Lee"}],
                game_id="401",
            )
        ],
        NOW,
    )
    kit.loaded["401"] = game("401")

    feed = await kit.serve("en-9001")

    assert feed.note is not None
    assert feed.note.teams == ["BOS", "NYK"]
    assert [p.name for p in feed.note.players] == ["Ana Lee"]
    assert feed.game is not None
    assert (feed.game.id, feed.game.away.code, feed.game.home.code) == (
        "401",
        "NYK",
        "BOS",
    )
    assert feed.game.score == Score(away=40, home=43)


@pytest.mark.anyio
async def test_serves_no_game_when_the_site_does_not_hold_it_or_the_note_has_none(
    kit: ArticleKit,
) -> None:
    kit.store.add_news_notes([note("9001", 4, game_id="401"), note("9002", 3)], NOW)

    elsewhere = await kit.serve("en-9001")
    without = await kit.serve("en-9002")

    assert elsewhere.note is not None and elsewhere.game is None
    assert without.note is not None and without.game is None


@pytest.mark.anyio
async def test_takes_the_game_from_a_final_game_of_a_stored_day(
    kit: ArticleKit,
) -> None:
    kit.store.add_news_notes([note("9001", 4, game_id="1")], NOW)
    kit.past["1"] = past_game("1")

    feed = await kit.serve("en-9001")

    assert feed.game is not None and feed.game.id == "1"


@pytest.mark.anyio
async def test_the_spanish_path_serves_an_english_recap_and_not_an_english_news_note(
    kit: ArticleKit,
) -> None:
    kit.store.add_news_notes(
        [note("9003", 4, kind="recap", game_id="401"), note("9001", 5)], NOW
    )

    recap = await kit.serve("es-9003")

    assert recap.note is not None and recap.note.language is NewsLanguage.EN
    assert kit.feeds.check("es-9001") is IdStatus.UNKNOWN
    with pytest.raises(UnknownFeedError):
        await kit.cache.serve(KIND, "es-9001")


@pytest.mark.anyio
async def test_the_spanish_path_hides_an_english_recap_once_the_spanish_recap_is_archived(
    kit: ArticleKit,
) -> None:
    kit.store.add_news_notes([note("9003", 4, kind="recap", game_id="401")], NOW)
    assert kit.feeds.check("es-9003") is IdStatus.KNOWN

    kit.store.add_news_notes(
        [note("recap-401", 5, kind="recap", game_id="401", language="es")], NOW
    )

    assert kit.feeds.check("es-9003") is IdStatus.UNKNOWN
    with pytest.raises(UnknownFeedError):
        await kit.cache.serve(KIND, "es-9003")


@pytest.mark.anyio
async def test_a_spanish_note_wins_over_the_english_recap_of_the_same_id(
    kit: ArticleKit,
) -> None:
    kit.store.add_news_notes(
        [
            note("9003", 4, kind="recap"),
            note("9003", 4, kind="recap", language="es"),
        ],
        NOW,
    )

    feed = await kit.serve("es-9003")

    assert feed.note is not None and feed.note.language is NewsLanguage.ES


@pytest.mark.anyio
async def test_an_id_that_is_not_archived_is_unknown(kit: ArticleKit) -> None:
    kit.store.add_news_notes([note("9001", 4)], NOW)

    for feed_id in ("en-1234", "es-1234", "fr-9001", "9001", "en-", "en-a/b", "en-a b"):
        assert kit.feeds.check(feed_id) is IdStatus.UNKNOWN
    with pytest.raises(UnknownFeedError):
        await kit.cache.serve(KIND, "en-1234")
    assert kit.feeds.check("en-9001") is IdStatus.KNOWN


@pytest.mark.anyio
async def test_with_news_off_every_id_is_unknown(tmp_path: Path) -> None:
    kit = ArticleKit(tmp_path, enabled=False)
    kit.store.add_news_notes([note("9001", 4)], NOW)

    assert kit.feeds.check("en-9001") is IdStatus.UNKNOWN
    with pytest.raises(UnknownFeedError):
        await kit.cache.serve(KIND, "en-9001")


@pytest.mark.anyio
async def test_a_game_the_site_gets_later_is_picked_up_after_15_minutes(
    kit: ArticleKit,
) -> None:
    kit.store.add_news_notes([note("9001", 4, game_id="401")], NOW)
    first = await kit.serve("en-9001")
    kit.loaded["401"] = game("401")

    within = await kit.serve("en-9001", NOW + 14 * MINUTE)
    await kit.serve("en-9001", NOW + 15 * MINUTE)
    after = await kit.serve("en-9001", NOW + 16 * MINUTE)

    assert (first.game, within.game) == (None, None)
    assert after.game is not None


def test_news_game_keeps_the_sides_and_score_without_their_identities() -> None:
    result = news_game(game("401"))

    assert result.id == "401"
    assert (result.away.code, result.home.code) == ("NYK", "BOS")
    assert (result.away.logo, result.home.colors) == (None, None)
    assert result.score == Score(away=40, home=43)
