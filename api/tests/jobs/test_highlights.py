# api/tests/jobs/test_highlights.py
#
# Tests for the highlights job.
#
# Tested:
# - Makes no attempt, and no request, before one hour after the final time
# - Attempts at 1, 2 and 3 hours after the final time, one attempt per slot, counting 1, 2, 3
# - Never attempts after the third failed attempt
# - For a game first seen final, attempts right away, 1 and 2 hours later, and never after the third
# - Makes no attempt for a final game without a stored final time
# - On a match stores the highlight, serves it, makes no further attempt and records success
# - Serves no highlights for an unmatched final game
# - Loads the stored highlights on start, before any fetch
# - Keeps the attempt count across a new job over the same store
# - Logs every failed attempt with the game, its number and its reason, for a no-match and a source error
# - A failed feed fetch spends the attempt, records the failure and keeps the stored highlights
# - A missing thumbnail or embed template records the failure
# - Fetches the channel feed once per run for several due games
# - Gives every game a search URL from the template, and none without it
# - A run with no due game makes no request and records nothing
#
# What is covered:
# - Job: a successful run gives the games job its data, a failed run keeps the last valid state
#
# The fetch is a fake passed to the job and times are passed to run(), so no test
# uses the real clock. Every test runs in an empty respx mock: a real request fails.
# The data has one source, so there is no fallback source to test.
#
# Run with: cd api && .venv/bin/python -m pytest tests/jobs/test_highlights.py
#
# SEE: api/app/jobs/highlights.py

import datetime as dt
import logging
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx

from app.feeds.games import GameStatus, Team
from app.jobs.highlights import JOB, HighlightsJob
from app.settings import Settings
from app.sources.http import SourceError, create_client
from app.sources.scoreboard import ScoreboardGame
from app.sources.video_channel import ChannelVideo
from app.storage.state import StateStore

# 21:00 US Eastern (EDT) on 2026-10-04.
FINAL_TIME = dt.datetime(2026, 10, 5, 1, 0, tzinfo=dt.UTC)
START = dt.datetime(2026, 10, 4, 23, 0, tzinfo=dt.UTC)
HOUR = dt.timedelta(hours=1)
TITLE = "WARRIORS at CLIPPERS | FULL GAME HIGHLIGHTS | October 4, 2026"
MATCH = ChannelVideo(video_id="vid1", title=TITLE, channel="Channel")
OTHER = ChannelVideo(video_id="vid2", title="Something else", channel="Channel")


def make_game(game_id: str = "g1") -> ScoreboardGame:
    return ScoreboardGame(
        id=game_id,
        away=Team(code="GSW", name="Warriors", city="Golden State"),
        home=Team(code="LAC", name="Clippers", city="Los Angeles"),
        status=GameStatus.FINAL,
        start_time=START,
        venue="Arena",
        line_score={"away": [20], "home": [18]},  # type: ignore[arg-type]
        score={"away": 20, "home": 18},  # type: ignore[arg-type]
    )


class FakeVideos:
    def __init__(self) -> None:
        self.videos: list[ChannelVideo] = []
        self.error: SourceError | None = None
        self.calls = 0

    async def fetch_videos(
        self, client: httpx.AsyncClient, settings: Settings
    ) -> list[ChannelVideo]:
        self.calls += 1
        if self.error is not None:
            raise self.error
        return list(self.videos)


@pytest.fixture(autouse=True)
def no_network() -> Iterator[None]:
    with respx.mock:
        yield


@pytest.fixture
def videos() -> FakeVideos:
    return FakeVideos()


@pytest.fixture
def store(tmp_path: Path) -> StateStore:
    state = StateStore(tmp_path)
    state.create_tables()
    return state


def make_settings(tmp_path: Path, **values: Any) -> Settings:
    defaults = {
        "video_thumbnail_url": "https://example.com/t/{video_id}.jpg",
        "video_embed_url": "https://example.com/e/{video_id}",
        "highlights_search_url": "https://example.com/s?q={query}",
    }
    return Settings(_env_file=None, data_dir=tmp_path, **{**defaults, **values})  # type: ignore[call-arg]


def make_job(
    tmp_path: Path,
    store: StateStore,
    videos: FakeVideos,
    games: list[ScoreboardGame],
    **values: Any,
) -> HighlightsJob:
    return HighlightsJob(
        make_settings(tmp_path, **values),
        store,
        create_client(),
        final_games=lambda: games,
        fetch_videos=videos.fetch_videos,
    )


@pytest.mark.anyio
async def test_makes_no_attempt_before_one_hour_after_the_final_time(
    tmp_path: Path, store: StateStore, videos: FakeVideos
) -> None:
    store.set_final_time("g1", FINAL_TIME)
    job = make_job(tmp_path, store, videos, [make_game()])

    await job.run(FINAL_TIME + HOUR - dt.timedelta(seconds=1))

    assert videos.calls == 0
    assert store.highlight_attempts("g1") == 0
    assert store.job_states() == []


@pytest.mark.anyio
async def test_attempts_at_one_two_and_three_hours_one_attempt_per_slot(
    tmp_path: Path, store: StateStore, videos: FakeVideos
) -> None:
    store.set_final_time("g1", FINAL_TIME)
    job = make_job(tmp_path, store, videos, [make_game()])

    for hours, expected in [(1, 1), (2, 2), (3, 3)]:
        slot = FINAL_TIME + hours * HOUR
        await job.run(slot - dt.timedelta(minutes=1))
        assert videos.calls == expected - 1
        await job.run(slot)
        assert videos.calls == expected
        await job.run(slot + dt.timedelta(minutes=30))
        assert videos.calls == expected
        assert store.highlight_attempts("g1") == expected


@pytest.mark.anyio
async def test_never_attempts_after_the_third_failed_attempt(
    tmp_path: Path, store: StateStore, videos: FakeVideos
) -> None:
    store.set_final_time("g1", FINAL_TIME)
    job = make_job(tmp_path, store, videos, [make_game()])
    for hours in (1, 2, 3):
        await job.run(FINAL_TIME + hours * HOUR)

    await job.run(FINAL_TIME + 4 * HOUR)
    await job.run(FINAL_TIME + 24 * HOUR)

    assert videos.calls == 3
    assert store.highlight_attempts("g1") == 3
    assert job.highlights_of(make_game()) == []


@pytest.mark.anyio
async def test_attempts_right_away_then_one_and_two_hours_later_for_a_game_first_seen_final(
    tmp_path: Path, store: StateStore, videos: FakeVideos
) -> None:
    store.set_final_time("g1", FINAL_TIME, first_seen=True)
    job = make_job(tmp_path, store, videos, [make_game()])

    for hours, expected in [(0, 1), (1, 2), (2, 3)]:
        slot = FINAL_TIME + hours * HOUR
        if hours:
            await job.run(slot - dt.timedelta(minutes=1))
            assert videos.calls == expected - 1
        await job.run(slot)
        assert videos.calls == expected
        await job.run(slot + dt.timedelta(minutes=30))
        assert videos.calls == expected
        assert store.highlight_attempts("g1") == expected


@pytest.mark.anyio
async def test_never_attempts_after_the_third_failed_attempt_for_a_game_first_seen_final(
    tmp_path: Path, store: StateStore, videos: FakeVideos
) -> None:
    store.set_final_time("g1", FINAL_TIME, first_seen=True)
    job = make_job(tmp_path, store, videos, [make_game()])
    for hours in (0, 1, 2):
        await job.run(FINAL_TIME + hours * HOUR)

    await job.run(FINAL_TIME + 3 * HOUR)
    await job.run(FINAL_TIME + 24 * HOUR)

    assert videos.calls == 3


@pytest.mark.anyio
async def test_makes_no_attempt_for_a_final_game_without_a_stored_final_time(
    tmp_path: Path, store: StateStore, videos: FakeVideos
) -> None:
    job = make_job(tmp_path, store, videos, [make_game()])

    await job.run(FINAL_TIME + 5 * HOUR)

    assert videos.calls == 0
    assert store.highlight_attempts("g1") == 0


@pytest.mark.anyio
async def test_on_a_match_stores_the_highlight_serves_it_and_stops_attempting(
    tmp_path: Path, store: StateStore, videos: FakeVideos
) -> None:
    store.set_final_time("g1", FINAL_TIME)
    videos.videos = [OTHER, MATCH]
    job = make_job(tmp_path, store, videos, [make_game()])
    now = FINAL_TIME + HOUR

    await job.run(now)
    await job.run(FINAL_TIME + 2 * HOUR)

    [highlight] = job.highlights_of(make_game())
    assert highlight.title == TITLE
    assert highlight.channel == "Channel"
    assert str(highlight.thumbnail_url) == "https://example.com/t/vid1.jpg"
    assert str(highlight.embed_url) == "https://example.com/e/vid1"
    assert store.highlights() == {"g1": highlight}
    assert videos.calls == 1
    assert store.job_states()[0].name == JOB
    assert store.job_states()[0].last_success == now


@pytest.mark.anyio
async def test_serves_no_highlights_for_an_unmatched_final_game(
    tmp_path: Path, store: StateStore, videos: FakeVideos
) -> None:
    store.set_final_time("g1", FINAL_TIME)
    videos.videos = [OTHER]
    job = make_job(tmp_path, store, videos, [make_game()])

    await job.run(FINAL_TIME + HOUR)

    assert job.highlights_of(make_game()) == []
    assert store.highlights() == {}


@pytest.mark.anyio
async def test_loads_the_stored_highlights_on_start_before_any_fetch(
    tmp_path: Path, store: StateStore, videos: FakeVideos
) -> None:
    store.set_final_time("g1", FINAL_TIME)
    videos.videos = [MATCH]
    await make_job(tmp_path, store, videos, [make_game()]).run(FINAL_TIME + HOUR)
    videos.calls = 0

    restarted = make_job(tmp_path, store, videos, [make_game()])

    assert [h.title for h in restarted.highlights_of(make_game())] == [TITLE]
    await restarted.run(FINAL_TIME + 2 * HOUR)
    assert videos.calls == 0


@pytest.mark.anyio
async def test_keeps_the_attempt_count_across_a_new_job_over_the_same_store(
    tmp_path: Path, store: StateStore, videos: FakeVideos
) -> None:
    store.set_final_time("g1", FINAL_TIME)
    await make_job(tmp_path, store, videos, [make_game()]).run(FINAL_TIME + HOUR)

    restarted = make_job(tmp_path, store, videos, [make_game()])
    await restarted.run(FINAL_TIME + HOUR)
    await restarted.run(FINAL_TIME + 2 * HOUR)

    assert videos.calls == 2
    assert store.highlight_attempts("g1") == 2


@pytest.mark.anyio
async def test_logs_every_failed_attempt_with_the_game_its_number_and_its_reason(
    tmp_path: Path,
    store: StateStore,
    videos: FakeVideos,
    caplog: pytest.LogCaptureFixture,
) -> None:
    store.set_final_time("g1", FINAL_TIME)
    videos.videos = [OTHER]
    job = make_job(tmp_path, store, videos, [make_game()])

    with caplog.at_level(logging.WARNING):
        await job.run(FINAL_TIME + HOUR)
        videos.error = SourceError("video_channel", "request failed")
        await job.run(FINAL_TIME + 2 * HOUR)

    messages = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert messages == [
        "highlights for game g1: attempt 1 of 3 failed: no video matched",
        "highlights for game g1: attempt 2 of 3 failed: video_channel: request failed",
    ]


@pytest.mark.anyio
async def test_a_failed_fetch_spends_the_attempt_and_keeps_the_stored_highlights(
    tmp_path: Path, store: StateStore, videos: FakeVideos
) -> None:
    store.set_final_time("g1", FINAL_TIME)
    store.set_final_time("g2", FINAL_TIME)
    videos.videos = [MATCH]
    job = make_job(tmp_path, store, videos, [make_game("g1")])
    await job.run(FINAL_TIME + HOUR)
    job = make_job(tmp_path, store, videos, [make_game("g1"), make_game("g2")])
    videos.error = SourceError("video_channel", "request timed out")
    now = FINAL_TIME + HOUR

    await job.run(now)

    assert store.highlight_attempts("g2") == 1
    state = store.job_states()[0]
    assert state.last_failure == now
    assert state.last_failure_reason == "video_channel: request timed out"
    assert [h.title for h in job.highlights_of(make_game("g1"))] == [TITLE]


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("missing", "reason"),
    [
        ("video_thumbnail_url", "video_channel: video thumbnail URL is not configured"),
        ("video_embed_url", "video_channel: video embed URL is not configured"),
    ],
)
async def test_a_missing_template_records_the_failure(
    tmp_path: Path, store: StateStore, videos: FakeVideos, missing: str, reason: str
) -> None:
    store.set_final_time("g1", FINAL_TIME)
    videos.videos = [MATCH]
    templates: dict[str, Any] = {
        "video_thumbnail_url": "https://example.com/t/{video_id}",
        "video_embed_url": "https://example.com/e/{video_id}",
        missing: None,
    }
    settings = Settings(_env_file=None, data_dir=tmp_path, **templates)  # type: ignore[call-arg]
    job = HighlightsJob(
        settings,
        store,
        create_client(),
        final_games=lambda: [make_game()],
        fetch_videos=videos.fetch_videos,
    )

    await job.run(FINAL_TIME + HOUR)

    assert store.job_states()[0].last_failure_reason == reason
    assert job.highlights_of(make_game()) == []


@pytest.mark.anyio
async def test_fetches_the_channel_feed_once_per_run_for_several_due_games(
    tmp_path: Path, store: StateStore, videos: FakeVideos
) -> None:
    for game_id in ("g1", "g2", "g3"):
        store.set_final_time(game_id, FINAL_TIME)
    games = [make_game("g1"), make_game("g2"), make_game("g3")]
    job = make_job(tmp_path, store, videos, games)

    await job.run(FINAL_TIME + HOUR)

    assert videos.calls == 1
    assert [store.highlight_attempts(g.id) for g in games] == [1, 1, 1]


def test_gives_every_game_a_search_url_from_the_template(
    tmp_path: Path, store: StateStore, videos: FakeVideos
) -> None:
    job = make_job(tmp_path, store, videos, [])

    url = job.search_url_of(make_game())

    assert (
        url
        == "https://example.com/s?q=Warriors+Clippers+full+game+highlights+October+4%2C+2026"
    )


def test_gives_no_search_url_without_the_template(
    tmp_path: Path, store: StateStore, videos: FakeVideos
) -> None:
    settings = Settings(_env_file=None, data_dir=tmp_path)  # type: ignore[call-arg]
    job = HighlightsJob(
        settings,
        store,
        create_client(),
        final_games=list,
        fetch_videos=videos.fetch_videos,
    )

    assert job.search_url_of(make_game()) is None
