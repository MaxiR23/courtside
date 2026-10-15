# api/tests/jobs/test_highlights_backfill.py
#
# Tests for the highlights backfill job.
#
# Tested:
# - Reads at most HIGHLIGHTS_BACKFILL_PAGES pages a day and saves the sweep at the next page
# - The next day reads from the stored page token and keeps the oldest upload time reached; it does not run again the same day, even after a restart
# - A finished sweep with an unmatched game reads nothing the next day
# - A game pending ahead of the running sweep is matched by it with no restart
# - A game that became pending after the sweep passed its date gets a new sweep from the newest upload
# - A game that became pending during a sweep, whose upload the sweep already read, gets a new sweep and is matched
# - A game that became pending during a sweep is never swept by that sweep
# - Two matching uploads for one game: the first in channel order is stored
# - A match is stored like a live one: in the state and served by the highlights job
# - Skips an All-Star game, a game with a highlight and a game with live attempts left
# - Reads the games job's final games, the stored day feeds and each injected game source, each game once
# - A failed page read stops the step, records the failure, keeps the earlier matches and the resume point
# - A failed thumbnail request stops the step and does not advance past that page
# - A matched upload without a valid highlight records the failure and sweeps the target
# - Stores the edition video per season and sweeps an edition that is not found
# - With no target makes no request and records nothing; with no embed template records the failure and makes no request
# - Runs through the real adapter over a stored sweep across two days
#
# What is covered:
# - Job: a successful run stores and serves, a failed run keeps what was stored
# - The data has one source, so there is no fallback source to test
#
# The page read and the thumbnail check are fakes passed to the job, except in
# the adapter test, which uses the real ones over respx. Times are passed to run().
# No test uses the real clock or a real request. Fixtures use example.com and
# invented titles.
#
# Run with: cd api && .venv/bin/python -m pytest tests/jobs/test_highlights_backfill.py
#
# SEE: api/app/jobs/highlights_backfill.py

import datetime as dt
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx

from app.feeds.days import DayFeed
from app.feeds.games import GameAllStar, GameStatus, GameTeam, Highlight
from app.jobs import day_feed
from app.jobs.all_star_edition_videos import AllStarEditionVideos
from app.jobs.day_feed import build_day_feed
from app.jobs.highlights import HighlightsJob
from app.jobs.highlights_backfill import JOB, GameTarget, HighlightsBackfill
from app.settings import Settings
from app.sources.http import SourceClient, SourceError, create_client
from app.sources.scoreboard import ScoreboardGame
from app.sources.video_channel import ChannelVideo, UploadsPage
from app.storage.feeds import publish_by_id
from app.storage.state import StateStore

FIXTURES = Path(__file__).parent / "fixtures" / "highlights_backfill"
NOW = dt.datetime(2026, 10, 20, 15, 0, tzinfo=dt.UTC)
DAY = dt.timedelta(days=1)
HOUR = dt.timedelta(hours=1)
# Oct 4 US Eastern.
GAME_START = dt.datetime(2026, 10, 4, 23, 0, tzinfo=dt.UTC)
PUBLISHED = dt.datetime(2026, 10, 5, 6, 0, tzinfo=dt.UTC)
REQUEST_FAILED = SourceError("video_channel", "request timed out", request_failed=True)


def title(away: str, home: str, date: str = "October 4, 2026") -> str:
    return f"{away.upper()} at {home.upper()} | FULL GAME HIGHLIGHTS | {date}"


def video(
    video_id: str,
    video_title: str = "Something else",
    published_at: dt.datetime = PUBLISHED,
) -> ChannelVideo:
    return ChannelVideo(
        video_id=video_id,
        title=video_title,
        channel="Channel",
        published_at=published_at,
        thumbnail_url=None,
        thumbnail_candidates=(f"https://example.com/t/{video_id}.jpg",),
    )


def filler(index: int) -> ChannelVideo:
    """An upload that matches nothing, published `index` days before NOW."""
    return video(f"f{index}", published_at=NOW - index * DAY)


def make_game(
    game_id: str = "g1",
    away: str = "Warriors",
    home: str = "Clippers",
    start: dt.datetime = GAME_START,
    **changes: Any,
) -> ScoreboardGame:
    data: dict[str, Any] = {
        "id": game_id,
        "away": GameTeam(code="AAA", name=away, city="City"),
        "home": GameTeam(code="BBB", name=home, city="City"),
        "status": GameStatus.FINAL,
        "start_time": start,
        "venue": "Arena",
        "line_score": {"away": [20], "home": [18]},
        "score": {"away": 20, "home": 18},
    }
    data.update(changes)
    return ScoreboardGame.model_validate(data)


class FakeChannel:
    """Serves the pages in order. The token of page i is None for 0 and p{i}
    after it. Records the tokens read."""

    def __init__(self, pages: list[list[ChannelVideo]]) -> None:
        self.pages = pages
        self.tokens: list[str | None] = []
        self.errors: dict[int, SourceError] = {}
        self.thumbnail_error: SourceError | None = None
        self.without_thumbnail: set[str] = set()

    async def read_page(
        self,
        client: SourceClient,
        settings: Settings,
        token: str | None,
        listed_since: dt.datetime,
    ) -> UploadsPage:
        self.tokens.append(token)
        index = 0 if token is None else int(token[1:])
        if index in self.errors:
            raise self.errors[index]
        more = index + 1 < len(self.pages)
        return UploadsPage(
            videos=self.pages[index], next_page_token=f"p{index + 1}" if more else None
        )

    async def check_thumbnail(
        self, client: SourceClient, found: ChannelVideo
    ) -> ChannelVideo:
        if self.thumbnail_error is not None:
            raise self.thumbnail_error
        if found.video_id in self.without_thumbnail:
            return found
        return found.model_copy(
            update={"thumbnail_url": f"https://example.com/t/{found.video_id}.jpg"}
        )


@pytest.fixture(autouse=True)
def no_network() -> Iterator[None]:
    with respx.mock:
        yield


@pytest.fixture
def store(tmp_path: Path) -> StateStore:
    state = StateStore(tmp_path)
    state.migrate()
    return state


def make_settings(tmp_path: Path, **values: Any) -> Settings:
    defaults = {"video_embed_url": "https://example.com/e/{video_id}"}
    return Settings(_env_file=None, data_dir=tmp_path, **{**defaults, **values})  # type: ignore[call-arg]


class Kit:
    def __init__(
        self,
        tmp_path: Path,
        store: StateStore,
        channel: FakeChannel | None,
        games: list[ScoreboardGame],
        **values: Any,
    ) -> None:
        self.games = games
        self.highlights = HighlightsJob(
            make_settings(tmp_path),
            store,
            create_client(store),
            final_games=lambda: self.games,
        )
        self.channel = channel
        self.settings = make_settings(tmp_path, **values)
        self.store = store
        self.client = create_client(store)

    def job(self, **options: Any) -> HighlightsBackfill:
        if self.channel is not None:
            options.setdefault("read_page", self.channel.read_page)
            options.setdefault("check_thumbnail", self.channel.check_thumbnail)
        return HighlightsBackfill(
            self.settings,
            self.store,
            self.client,
            self.highlights,
            final_games=lambda: self.games,
            **options,
        )


def kit(
    tmp_path: Path,
    store: StateStore,
    pages: list[list[ChannelVideo]] | None,
    games: list[ScoreboardGame] | None = None,
    **values: Any,
) -> Kit:
    channel = None if pages is None else FakeChannel(pages)
    return Kit(
        tmp_path, store, channel, [make_game()] if games is None else games, **values
    )


def job_state(store: StateStore) -> Any:
    return next((s for s in store.job_states() if s.name == JOB), None)


@pytest.mark.anyio
async def test_reads_at_most_the_page_cap_a_day_and_saves_the_sweep_at_the_next_page(
    tmp_path: Path, store: StateStore
) -> None:
    k = kit(
        tmp_path, store, [[filler(i)] for i in range(5)], highlights_backfill_pages=2
    )
    assert k.channel is not None

    await k.job().run(NOW)

    assert k.channel.tokens == [None, "p1"]
    sweep = store.backfill_sweep()
    assert sweep is not None and sweep.page_token == "p2"
    assert sweep.oldest == filler(1).published_at
    assert job_state(store).last_success == NOW


@pytest.mark.anyio
async def test_the_next_day_reads_from_the_stored_token_and_does_not_run_twice_in_a_day(
    tmp_path: Path, store: StateStore
) -> None:
    k = kit(
        tmp_path, store, [[filler(i)] for i in range(6)], highlights_backfill_pages=2
    )
    assert k.channel is not None
    await k.job().run(NOW)

    await k.job().run(NOW + HOUR)
    assert k.channel.tokens == [None, "p1"]

    await k.job().run(NOW + 2 * HOUR)
    assert k.channel.tokens == [None, "p1"]

    await k.job().run(NOW + DAY)
    assert k.channel.tokens == [None, "p1", "p2", "p3"]
    sweep = store.backfill_sweep()
    assert sweep is not None and sweep.page_token == "p4"
    assert sweep.oldest == filler(3).published_at


@pytest.mark.anyio
async def test_a_finished_sweep_with_an_unmatched_game_reads_nothing_the_next_day(
    tmp_path: Path, store: StateStore
) -> None:
    k = kit(tmp_path, store, [[filler(i)] for i in range(3)])
    assert k.channel is not None

    await k.job().run(NOW)
    await k.job().run(NOW + DAY)

    assert k.channel.tokens == [None, "p1", "p2"]
    assert store.backfill_sweep() is None
    assert store.backfill_swept("game") == {"g1"}


@pytest.mark.anyio
async def test_a_game_ahead_of_the_running_sweep_is_matched_with_no_restart(
    tmp_path: Path, store: StateStore
) -> None:
    pages = [[filler(0)], [video("v1", title("Warriors", "Clippers"))]]
    k = kit(tmp_path, store, pages, highlights_backfill_pages=1)
    assert k.channel is not None

    await k.job().run(NOW)
    assert store.highlights() == {}
    await k.job().run(NOW + DAY)

    assert k.channel.tokens == [None, "p1"]
    assert store.highlights()["g1"].title == title("Warriors", "Clippers")


@pytest.mark.anyio
async def test_a_game_pending_after_the_sweep_passed_its_date_gets_a_new_sweep(
    tmp_path: Path, store: StateStore
) -> None:
    later = dt.datetime(2026, 10, 25, 23, 0, tzinfo=dt.UTC)
    pages = [
        [
            video(
                "v2",
                title("Jazz", "Nuggets", "October 25, 2026"),
                dt.datetime(2026, 10, 26, 6, 0, tzinfo=dt.UTC),
            ),
            filler(10),
        ],
        [filler(20)],
    ]
    k = kit(tmp_path, store, pages, highlights_backfill_pages=1)
    assert k.channel is not None
    await k.job().run(NOW)
    k.games = [make_game(), make_game("g2", "Jazz", "Nuggets", later)]
    k.settings = make_settings(tmp_path, highlights_backfill_pages=5)

    await k.job().run(NOW + 10 * DAY)

    assert k.channel.tokens == [None, "p1", None]
    assert "g2" in store.highlights() and "g1" not in store.highlights()
    assert store.backfill_swept("game") == {"g1"}


@pytest.mark.anyio
async def test_a_game_that_joins_a_resumed_sweep_late_still_gets_its_earlier_upload(
    tmp_path: Path, store: StateStore
) -> None:
    pages = [
        [
            video(
                "v2",
                title("Jazz", "Nuggets", "October 9, 2026"),
                dt.datetime(2026, 10, 10, 5, 0, tzinfo=dt.UTC),
            ),
            video("f-a", published_at=dt.datetime(2026, 10, 10, 3, 0, tzinfo=dt.UTC)),
        ],
        [video("f-b", published_at=dt.datetime(2026, 10, 8, 3, 0, tzinfo=dt.UTC))],
        [video("f-c", published_at=dt.datetime(2026, 10, 1, 3, 0, tzinfo=dt.UTC))],
    ]
    k = kit(tmp_path, store, pages, highlights_backfill_pages=1)
    assert k.channel is not None
    await k.job().run(NOW)
    k.games = [
        make_game(),
        make_game(
            "g2", "Jazz", "Nuggets", dt.datetime(2026, 10, 10, 0, 30, tzinfo=dt.UTC)
        ),
    ]
    k.settings = make_settings(tmp_path, highlights_backfill_pages=5)

    await k.job().run(NOW + DAY)

    assert k.channel.tokens == [None, "p1", "p2", None]
    assert store.highlights()["g2"].title == title("Jazz", "Nuggets", "October 9, 2026")
    assert store.backfill_swept("game") == {"g1"}
    assert store.backfill_sweep() is None


@pytest.mark.anyio
async def test_a_game_that_joins_during_a_sweep_is_never_swept_by_that_sweep(
    tmp_path: Path, store: StateStore
) -> None:
    pages = [
        [
            video(
                "v2",
                title("Jazz", "Nuggets", "October 9, 2026"),
                dt.datetime(2026, 10, 10, 5, 0, tzinfo=dt.UTC),
            ),
            video("f-a", published_at=dt.datetime(2026, 10, 10, 3, 0, tzinfo=dt.UTC)),
        ],
        [video("f-b", published_at=dt.datetime(2026, 10, 8, 3, 0, tzinfo=dt.UTC))],
        [video("f-c", published_at=dt.datetime(2026, 10, 1, 3, 0, tzinfo=dt.UTC))],
    ]
    k = kit(tmp_path, store, pages, highlights_backfill_pages=1)
    assert k.channel is not None
    await k.job().run(NOW)
    k.games = [
        make_game(),
        make_game(
            "g2", "Jazz", "Nuggets", dt.datetime(2026, 10, 10, 0, 30, tzinfo=dt.UTC)
        ),
    ]

    await k.job().run(NOW + DAY)

    assert k.channel.tokens == [None, "p1"]
    assert store.backfill_swept("game") == set()
    assert "g2" not in store.highlights()
    await k.job().run(NOW + 2 * DAY)
    assert k.channel.tokens == [None, "p1", "p2"]
    assert store.backfill_swept("game") == {"g1"}
    await k.job().run(NOW + 3 * DAY)
    assert k.channel.tokens == [None, "p1", "p2", None]
    assert "g2" in store.highlights()


@pytest.mark.anyio
async def test_the_first_of_two_matching_uploads_in_channel_order_is_stored(
    tmp_path: Path, store: StateStore
) -> None:
    page = [
        video("first", title("Warriors", "Clippers")),
        video("second", title("Warriors", "Clippers")),
    ]
    k = kit(tmp_path, store, [page])

    await k.job().run(NOW)

    assert str(store.highlights()["g1"].embed_url) == "https://example.com/e/first"


@pytest.mark.anyio
async def test_a_match_is_stored_like_a_live_one_and_served_by_the_highlights_job(
    tmp_path: Path, store: StateStore
) -> None:
    k = kit(tmp_path, store, [[video("v1", title("Warriors", "Clippers"))]])

    await k.job().run(NOW)

    [served] = k.highlights.highlights_of(k.games[0])
    assert store.highlights() == {"g1": served}
    assert str(served.thumbnail_url) == "https://example.com/t/v1.jpg"
    assert str(served.embed_url) == "https://example.com/e/v1"


def old_highlight() -> Highlight:
    return Highlight.model_validate(
        {
            "title": "Old",
            "channel": "Channel",
            "thumbnail_url": "https://example.com/t/old.jpg",
            "embed_url": "https://example.com/e/old",
        }
    )


@pytest.mark.anyio
async def test_skips_an_all_star_game_a_game_with_a_highlight_and_a_game_with_live_attempts_left(
    tmp_path: Path, store: StateStore
) -> None:
    all_star = make_game(
        "g1", all_star=GameAllStar(round_label="Final", championship=True)
    )
    stored = make_game("g2", "Jazz", "Nuggets")
    live = make_game("g3", "Nets", "Heat")
    k = kit(
        tmp_path,
        store,
        [[video("v", title("Warriors", "Clippers"))]],
        [all_star, stored, live],
    )
    assert k.channel is not None
    k.highlights.add_highlight("g2", old_highlight())
    store.set_final_time("g3", dt.date(2026, 10, 4), GAME_START + 3 * HOUR)

    await k.job().run(NOW)

    assert k.channel.tokens == []
    assert job_state(store) is None


@pytest.mark.anyio
async def test_reads_the_games_job_the_stored_day_feeds_and_each_game_source_once_each(
    tmp_path: Path, store: StateStore
) -> None:
    stored_game = make_game("g2", "Jazz", "Nuggets")
    feed = build_day_feed(
        NOW,
        dt.date(2026, 10, 4),
        2026,
        [make_game(), stored_game],
        lambda _: "https://example.com/s?q=x",
    )
    assert isinstance(feed, DayFeed)
    publish_by_id(tmp_path, day_feed.KIND, DayFeed, "2026-10-04", feed)
    sourced = GameTarget("g3", "Nets", "Heat", GAME_START)
    duplicate = GameTarget("g1", "Warriors", "Clippers", GAME_START)
    page = [
        video("v1", title("Warriors", "Clippers")),
        video("v2", title("Jazz", "Nuggets")),
        video("v3", title("Nets", "Heat")),
    ]
    k = kit(tmp_path, store, [page])
    assert k.channel is not None

    await k.job(game_sources=[lambda: [sourced, duplicate]]).run(NOW)

    assert set(store.highlights()) == {"g1", "g2", "g3"}
    assert k.channel.tokens == [None]


@pytest.mark.anyio
async def test_a_failed_page_read_stops_the_step_keeps_the_matches_and_the_resume_point(
    tmp_path: Path, store: StateStore
) -> None:
    older = make_game("g2", "Jazz", "Nuggets", dt.datetime(2026, 10, 3, tzinfo=dt.UTC))
    pages = [[video("v1", title("Warriors", "Clippers"))], [filler(1)]]
    k = kit(tmp_path, store, pages, [make_game(), older])
    assert k.channel is not None
    k.channel.errors[1] = REQUEST_FAILED

    await k.job().run(NOW)

    assert set(store.highlights()) == {"g1"}
    state = job_state(store)
    assert state.last_failure == NOW and state.last_failure_reason is not None
    sweep = store.backfill_sweep()
    assert sweep is not None and sweep.page_token == "p1"

    del k.channel.errors[1]
    await k.job().run(NOW + DAY)

    assert k.channel.tokens == [None, "p1", "p1"]


@pytest.mark.anyio
async def test_a_failed_thumbnail_request_stops_the_step_and_does_not_advance_past_the_page(
    tmp_path: Path, store: StateStore
) -> None:
    k = kit(
        tmp_path,
        store,
        [[video("v1", title("Warriors", "Clippers"))], [filler(1)]],
    )
    assert k.channel is not None
    k.channel.thumbnail_error = REQUEST_FAILED

    await k.job().run(NOW)

    assert store.highlights() == {}
    assert store.backfill_sweep() is None
    assert job_state(store).last_failure == NOW

    k.channel.thumbnail_error = None
    await k.job().run(NOW + DAY)

    assert k.channel.tokens[:2] == [None, None]
    assert "g1" in store.highlights()


@pytest.mark.anyio
async def test_a_matched_upload_without_a_valid_highlight_records_the_failure_and_sweeps_the_target(
    tmp_path: Path, store: StateStore, caplog: pytest.LogCaptureFixture
) -> None:
    k = kit(tmp_path, store, [[video("v1", title("Warriors", "Clippers"))]])
    assert k.channel is not None
    k.channel.without_thumbnail.add("v1")

    with caplog.at_level("WARNING"):
        await k.job().run(NOW)

    assert store.highlights() == {}
    assert store.backfill_swept("game") == {"g1"}
    assert "video v1 has no thumbnail" in job_state(store).last_failure_reason
    assert "highlights backfill: game g1" in caplog.text

    await k.job().run(NOW + DAY)
    assert k.channel.tokens == [None]


@pytest.mark.anyio
async def test_stores_the_edition_video_per_season_and_sweeps_an_edition_not_found(
    tmp_path: Path, store: StateStore
) -> None:
    store.set_all_star_edition(2026, dt.date(2026, 2, 15), ["a1"])
    store.set_all_star_edition(2025, dt.date(2025, 2, 16), ["a0"])
    pages = [
        [
            filler(1),
            video(
                "ev",
                "2026 NBA All-Star Game | Full Highlights",
                dt.datetime(2026, 2, 16, 9, 0, tzinfo=dt.UTC),
            ),
        ],
        [video("old", published_at=dt.datetime(2026, 1, 5, tzinfo=dt.UTC))],
    ]
    k = kit(tmp_path, store, pages, [])

    await k.job(editions=AllStarEditionVideos(store)).run(NOW)

    found = store.all_star_edition_highlight(2026)
    assert found is not None and str(found.embed_url) == "https://example.com/e/ev"
    assert store.all_star_edition_highlight(2025) is None
    assert store.backfill_swept("edition") == {"2025"}
    assert store.highlights() == {}


@pytest.mark.anyio
async def test_with_no_target_makes_no_request_and_records_nothing(
    tmp_path: Path, store: StateStore
) -> None:
    k = kit(tmp_path, store, [[filler(0)]], [])
    assert k.channel is not None

    await k.job().run(NOW)

    assert k.channel.tokens == []
    assert store.job_states() == []


@pytest.mark.anyio
async def test_without_the_embed_template_records_the_failure_and_makes_no_request(
    tmp_path: Path, store: StateStore
) -> None:
    k = kit(tmp_path, store, [[filler(0)]], video_embed_url=None)
    assert k.channel is not None

    await k.job().run(NOW)

    assert k.channel.tokens == []
    assert job_state(store).last_failure_reason == (
        "video_channel: video embed URL is not configured"
    )


def adapter_pages() -> Callable[[httpx.Request], httpx.Response]:
    def handler(request: httpx.Request) -> httpx.Response:
        token = request.url.params.get("pageToken")
        name = "page-2" if token == "page-2" else "page-1"
        number = name[-1]
        return httpx.Response(
            200, text=(FIXTURES / f"uploads-page-{number}.json").read_text("utf-8")
        )

    return handler


@pytest.mark.anyio
async def test_runs_through_the_real_adapter_and_stores_the_sweep_between_two_days(
    tmp_path: Path, store: StateStore
) -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return adapter_pages()(request)

    respx.get("https://example.com/uploads").mock(side_effect=handler)
    respx.head(url__startswith="https://example.com/thumbs/").mock(
        return_value=httpx.Response(200)
    )
    k = kit(
        tmp_path,
        store,
        None,
        highlights_backfill_pages=1,
        highlights_source_url="https://example.com/uploads",
        highlights_source_key="test-key-value",
    )
    k.client = create_client(store, clock=lambda: NOW + 2 * DAY)

    await k.job().run(NOW)
    sweep = store.backfill_sweep()
    assert sweep is not None and sweep.page_token == "page-2"
    assert store.highlights() == {}

    await k.job().run(NOW + DAY)

    assert [r.url.params.get("pageToken") for r in seen] == [None, "page-2"]
    found = store.highlights()["g1"]
    assert str(found.thumbnail_url) == "https://example.com/thumbs/vid-game/maxres.jpg"
    assert str(found.embed_url) == "https://example.com/e/vid-game"
    assert "test-key-value" not in str(found)
