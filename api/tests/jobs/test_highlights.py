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
# - Loads the stored highlights on start, before any lookup
# - Keeps the attempt count across a new job over the same store
# - Logs every failed attempt with the game, its number and its reason, for a no-match, and a failed request as not counted
# - A failed request leaves the attempt count unchanged, records the failure and keeps the stored highlights
# - A matched video without a thumbnail, or a missing embed template, records the failure
# - Lists the uploads once per run with every due game and its US Eastern date
# - A failed thumbnail check for one game leaves its attempt and still matches the others
# - Retries the same attempt no sooner than ten minutes after a failed request
# - Measures the ten minutes from the failed request, not from the start of the run
# - A failed request does not move the attempt schedule
# - A lookup that answers with no match still uses up an attempt
# - Any other source error still uses up an attempt
# - A game first seen final after a restart gets its highlight, with the largest 16:9 thumbnail, from an older page on the first run, through the real adapter
# - Gives every game a search URL from the template, and none without it
# - A run with no due game makes no request and records nothing
# - An attempt keeps the game date of the row
# - Every listing of a run lists uploads fetched at or after the run's start
# - A run with three due games lists each page once, back to the oldest due game, through the real adapter
# - Every due game is matched against the one listing, including a game on a later page
# - A listing that fails on a later page uses up no attempt, even of a game matched earlier
# - A listing that is invalid on a later page keeps the match of a game found on an earlier page and uses up an attempt of the others
# - A failed listing uses up no attempt of any due game and retries each no sooner than ten minutes
# - A listing with another error uses up one attempt of each due game
# - A successful listing counts each due game as its own lookup did
#
# What is covered:
# - Job: a successful run gives the games job its data, a failed run keeps the last valid state
#
# The listing and the thumbnail check are fakes passed to the job, except in the restart test and the tests that name the real adapter, which use it over respx, and times are passed to run(). Every job gets
# a frozen or test-driven clock, so no test uses the real clock. Every test runs in an empty respx mock: a real request fails.
# The data has one source, so there is no fallback source to test.
#
# Run with: cd api && .venv/bin/python -m pytest tests/jobs/test_highlights.py
#
# SEE: api/app/jobs/highlights.py

import datetime as dt
import logging
from collections.abc import Callable, Iterator, Sequence
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx

from app.feeds.games import GameStatus, Team
from app.jobs.highlights import JOB, RETRY, HighlightsJob
from app.settings import Settings
from app.sources.http import SourceError, create_client
from app.sources.scoreboard import ScoreboardGame
from app.sources.video_channel import ChannelVideo
from app.storage.state import StateStore

# 21:00 US Eastern (EDT) on 2026-10-04.
FINAL_TIME = dt.datetime(2026, 10, 5, 1, 0, tzinfo=dt.UTC)
START = dt.datetime(2026, 10, 4, 23, 0, tzinfo=dt.UTC)
# The US Eastern date of START.
GAME_DATE = dt.date(2026, 10, 4)
HOUR = dt.timedelta(hours=1)
TITLE = "WARRIORS at CLIPPERS | FULL GAME HIGHLIGHTS | October 4, 2026"
FIXTURES = Path(__file__).parent / "fixtures" / "highlights"
MATCH = ChannelVideo(
    video_id="vid1",
    title=TITLE,
    channel="Channel",
    thumbnail_url="https://example.com/t/vid1.jpg",
)
REQUEST_FAILED = SourceError("video_channel", "request timed out", request_failed=True)
OTHER = ChannelVideo(
    video_id="vid2",
    title="Something else",
    channel="Channel",
    thumbnail_url="https://example.com/t/vid2.jpg",
)


def make_game(
    game_id: str = "g1",
    away: tuple[str, str] = ("GSW", "Warriors"),
    home: tuple[str, str] = ("LAC", "Clippers"),
    start: dt.datetime = START,
) -> ScoreboardGame:
    return ScoreboardGame(
        id=game_id,
        away=Team(code=away[0], name=away[1], city="City"),
        home=Team(code=home[0], name=home[1], city="City"),
        status=GameStatus.FINAL,
        start_time=start,
        venue="Arena",
        line_score={"away": [20], "home": [18]},  # type: ignore[arg-type]
        score={"away": 20, "home": 18},  # type: ignore[arg-type]
    )


JAZZ = ("UTA", "Jazz")
NUGGETS = ("DEN", "Nuggets")
NETS = ("BKN", "Nets")
HEAT = ("MIA", "Heat")


class FakeLookup:
    def __init__(self) -> None:
        self.default: ChannelVideo | None = None
        self.uploads: list[ChannelVideo] | None = None
        self.error: SourceError | None = None
        self.thumbnail_errors: dict[str, SourceError] = {}
        self.calls: list[list[tuple[str, dt.date]]] = []
        self.listed_since_calls: list[dt.datetime] = []

    async def list_uploads(
        self,
        client: httpx.AsyncClient,
        games: Sequence[tuple[ScoreboardGame, dt.date]],
        settings: Settings,
        listed_since: dt.datetime,
    ) -> list[ChannelVideo]:
        self.calls.append([(game.id, day) for game, day in games])
        self.listed_since_calls.append(listed_since)
        if self.error is not None:
            raise self.error
        if self.uploads is not None:
            return list(self.uploads)
        return [] if self.default is None else [self.default]

    async def check_thumbnail(
        self, client: httpx.AsyncClient, video: ChannelVideo
    ) -> ChannelVideo:
        if video.video_id in self.thumbnail_errors:
            raise self.thumbnail_errors[video.video_id]
        return video


@pytest.fixture(autouse=True)
def no_network() -> Iterator[None]:
    with respx.mock:
        yield


@pytest.fixture
def lookup() -> FakeLookup:
    return FakeLookup()


@pytest.fixture
def store(tmp_path: Path) -> StateStore:
    state = StateStore(tmp_path)
    state.migrate()
    return state


def make_settings(tmp_path: Path, **values: Any) -> Settings:
    defaults = {
        "video_embed_url": "https://example.com/e/{video_id}",
        "highlights_search_url": "https://example.com/s?q={query}",
    }
    return Settings(_env_file=None, data_dir=tmp_path, **{**defaults, **values})  # type: ignore[call-arg]


def make_job(
    tmp_path: Path,
    store: StateStore,
    lookup: FakeLookup,
    games: list[ScoreboardGame],
    clock: Callable[[], dt.datetime] = lambda: FINAL_TIME,
    **values: Any,
) -> HighlightsJob:
    return HighlightsJob(
        make_settings(tmp_path, **values),
        store,
        create_client(store),
        final_games=lambda: games,
        list_uploads=lookup.list_uploads,
        check_thumbnail=lookup.check_thumbnail,
        clock=clock,
    )


@pytest.mark.anyio
async def test_makes_no_attempt_before_one_hour_after_the_final_time(
    tmp_path: Path, store: StateStore, lookup: FakeLookup
) -> None:
    store.set_final_time("g1", GAME_DATE, FINAL_TIME)
    job = make_job(tmp_path, store, lookup, [make_game()])

    await job.run(FINAL_TIME + HOUR - dt.timedelta(seconds=1))

    assert len(lookup.calls) == 0
    assert store.highlight_attempts("g1") == 0
    assert store.job_states() == []


@pytest.mark.anyio
async def test_attempts_at_one_two_and_three_hours_one_attempt_per_slot(
    tmp_path: Path, store: StateStore, lookup: FakeLookup
) -> None:
    store.set_final_time("g1", GAME_DATE, FINAL_TIME)
    job = make_job(tmp_path, store, lookup, [make_game()])

    for hours, expected in [(1, 1), (2, 2), (3, 3)]:
        slot = FINAL_TIME + hours * HOUR
        await job.run(slot - dt.timedelta(minutes=1))
        assert len(lookup.calls) == expected - 1
        await job.run(slot)
        assert len(lookup.calls) == expected
        await job.run(slot + dt.timedelta(minutes=30))
        assert len(lookup.calls) == expected
        assert store.highlight_attempts("g1") == expected


@pytest.mark.anyio
async def test_never_attempts_after_the_third_failed_attempt(
    tmp_path: Path, store: StateStore, lookup: FakeLookup
) -> None:
    store.set_final_time("g1", GAME_DATE, FINAL_TIME)
    job = make_job(tmp_path, store, lookup, [make_game()])
    for hours in (1, 2, 3):
        await job.run(FINAL_TIME + hours * HOUR)

    await job.run(FINAL_TIME + 4 * HOUR)
    await job.run(FINAL_TIME + 24 * HOUR)

    assert len(lookup.calls) == 3
    assert store.highlight_attempts("g1") == 3
    assert job.highlights_of(make_game()) == []


@pytest.mark.anyio
async def test_attempts_right_away_then_one_and_two_hours_later_for_a_game_first_seen_final(
    tmp_path: Path, store: StateStore, lookup: FakeLookup
) -> None:
    store.set_final_time("g1", GAME_DATE, FINAL_TIME, first_seen=True)
    job = make_job(tmp_path, store, lookup, [make_game()])

    for hours, expected in [(0, 1), (1, 2), (2, 3)]:
        slot = FINAL_TIME + hours * HOUR
        if hours:
            await job.run(slot - dt.timedelta(minutes=1))
            assert len(lookup.calls) == expected - 1
        await job.run(slot)
        assert len(lookup.calls) == expected
        await job.run(slot + dt.timedelta(minutes=30))
        assert len(lookup.calls) == expected
        assert store.highlight_attempts("g1") == expected


@pytest.mark.anyio
async def test_never_attempts_after_the_third_failed_attempt_for_a_game_first_seen_final(
    tmp_path: Path, store: StateStore, lookup: FakeLookup
) -> None:
    store.set_final_time("g1", GAME_DATE, FINAL_TIME, first_seen=True)
    job = make_job(tmp_path, store, lookup, [make_game()])
    for hours in (0, 1, 2):
        await job.run(FINAL_TIME + hours * HOUR)

    await job.run(FINAL_TIME + 3 * HOUR)
    await job.run(FINAL_TIME + 24 * HOUR)

    assert len(lookup.calls) == 3


@pytest.mark.anyio
async def test_makes_no_attempt_for_a_final_game_without_a_stored_final_time(
    tmp_path: Path, store: StateStore, lookup: FakeLookup
) -> None:
    job = make_job(tmp_path, store, lookup, [make_game()])

    await job.run(FINAL_TIME + 5 * HOUR)

    assert len(lookup.calls) == 0
    assert store.highlight_attempts("g1") == 0


@pytest.mark.anyio
async def test_on_a_match_stores_the_highlight_serves_it_and_stops_attempting(
    tmp_path: Path, store: StateStore, lookup: FakeLookup
) -> None:
    store.set_final_time("g1", GAME_DATE, FINAL_TIME)
    lookup.default = MATCH
    job = make_job(tmp_path, store, lookup, [make_game()])
    now = FINAL_TIME + HOUR

    await job.run(now)
    await job.run(FINAL_TIME + 2 * HOUR)

    [highlight] = job.highlights_of(make_game())
    assert highlight.title == TITLE
    assert highlight.channel == "Channel"
    assert str(highlight.thumbnail_url) == "https://example.com/t/vid1.jpg"
    assert str(highlight.embed_url) == "https://example.com/e/vid1"
    assert store.highlights() == {"g1": highlight}
    assert len(lookup.calls) == 1
    assert store.job_states()[0].name == JOB
    assert store.job_states()[0].last_success == now


@pytest.mark.anyio
async def test_serves_no_highlights_for_an_unmatched_final_game(
    tmp_path: Path, store: StateStore, lookup: FakeLookup
) -> None:
    store.set_final_time("g1", GAME_DATE, FINAL_TIME)
    lookup.default = None
    job = make_job(tmp_path, store, lookup, [make_game()])

    await job.run(FINAL_TIME + HOUR)

    assert job.highlights_of(make_game()) == []
    assert store.highlights() == {}


@pytest.mark.anyio
async def test_loads_the_stored_highlights_on_start_before_any_fetch(
    tmp_path: Path, store: StateStore, lookup: FakeLookup
) -> None:
    store.set_final_time("g1", GAME_DATE, FINAL_TIME)
    lookup.default = MATCH
    await make_job(tmp_path, store, lookup, [make_game()]).run(FINAL_TIME + HOUR)
    lookup.calls.clear()

    restarted = make_job(tmp_path, store, lookup, [make_game()])

    assert [h.title for h in restarted.highlights_of(make_game())] == [TITLE]
    await restarted.run(FINAL_TIME + 2 * HOUR)
    assert len(lookup.calls) == 0


@pytest.mark.anyio
async def test_keeps_the_attempt_count_across_a_new_job_over_the_same_store(
    tmp_path: Path, store: StateStore, lookup: FakeLookup
) -> None:
    store.set_final_time("g1", GAME_DATE, FINAL_TIME)
    await make_job(tmp_path, store, lookup, [make_game()]).run(FINAL_TIME + HOUR)

    restarted = make_job(tmp_path, store, lookup, [make_game()])
    await restarted.run(FINAL_TIME + HOUR)
    await restarted.run(FINAL_TIME + 2 * HOUR)

    assert len(lookup.calls) == 2
    assert store.highlight_attempts("g1") == 2


@pytest.mark.anyio
async def test_logs_every_failed_attempt_with_the_game_its_number_and_its_reason(
    tmp_path: Path,
    store: StateStore,
    lookup: FakeLookup,
    caplog: pytest.LogCaptureFixture,
) -> None:
    store.set_final_time("g1", GAME_DATE, FINAL_TIME)
    lookup.default = None
    job = make_job(tmp_path, store, lookup, [make_game()])

    with caplog.at_level(logging.WARNING):
        await job.run(FINAL_TIME + HOUR)
        lookup.error = SourceError(
            "video_channel", "request failed", request_failed=True
        )
        await job.run(FINAL_TIME + 2 * HOUR)

    messages = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert messages == [
        "highlights for game g1: attempt 1 of 3 failed: no video matched",
        "highlights for game g1: attempt 2 of 3 not counted, retrying in 10 minutes: video_channel: request failed",
    ]


@pytest.mark.anyio
async def test_a_failed_request_leaves_the_attempt_count_unchanged_records_the_failure_and_keeps_the_stored_highlights(
    tmp_path: Path, store: StateStore, lookup: FakeLookup
) -> None:
    store.set_final_time("g1", GAME_DATE, FINAL_TIME)
    store.set_final_time("g2", GAME_DATE, FINAL_TIME)
    lookup.default = MATCH
    job = make_job(tmp_path, store, lookup, [make_game("g1")])
    await job.run(FINAL_TIME + HOUR)
    job = make_job(tmp_path, store, lookup, [make_game("g1"), make_game("g2")])
    lookup.error = REQUEST_FAILED
    now = FINAL_TIME + HOUR

    await job.run(now)

    assert store.highlight_attempts("g2") == 0
    state = store.job_states()[0]
    assert state.last_failure == now
    assert state.last_failure_reason == "video_channel: request timed out"
    assert [h.title for h in job.highlights_of(make_game("g1"))] == [TITLE]


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("video", "embed_url", "reason"),
    [
        (
            MATCH.model_copy(update={"thumbnail_url": None}),
            "https://example.com/e/{video_id}",
            "video_channel: video vid1 has no thumbnail",
        ),
        (MATCH, None, "video_channel: video embed URL is not configured"),
    ],
)
async def test_a_video_without_a_thumbnail_or_a_missing_template_records_the_failure(
    tmp_path: Path,
    store: StateStore,
    lookup: FakeLookup,
    video: ChannelVideo,
    embed_url: str | None,
    reason: str,
) -> None:
    store.set_final_time("g1", GAME_DATE, FINAL_TIME)
    lookup.default = video
    settings = Settings(_env_file=None, data_dir=tmp_path, video_embed_url=embed_url)  # type: ignore[call-arg]
    job = HighlightsJob(
        settings,
        store,
        create_client(store, clock=lambda: FINAL_TIME),
        final_games=lambda: [make_game()],
        list_uploads=lookup.list_uploads,
        check_thumbnail=lookup.check_thumbnail,
        clock=lambda: FINAL_TIME,
    )

    await job.run(FINAL_TIME + HOUR)

    assert store.job_states()[0].last_failure_reason == reason
    assert job.highlights_of(make_game()) == []


@pytest.mark.anyio
async def test_lists_once_per_run_with_every_due_game_and_its_eastern_date(
    tmp_path: Path, store: StateStore, lookup: FakeLookup
) -> None:
    for game_id in ("g1", "g2", "g3"):
        store.set_final_time(game_id, GAME_DATE, FINAL_TIME)
    games = [make_game("g1"), make_game("g2"), make_game("g3")]
    job = make_job(tmp_path, store, lookup, games)

    await job.run(FINAL_TIME + HOUR)

    assert lookup.calls == [[("g1", GAME_DATE), ("g2", GAME_DATE), ("g3", GAME_DATE)]]
    assert [store.highlight_attempts(g.id) for g in games] == [1, 1, 1]


@pytest.mark.anyio
async def test_a_failed_thumbnail_check_for_one_game_leaves_its_attempt_and_still_matches_the_others(
    tmp_path: Path,
    store: StateStore,
    lookup: FakeLookup,
    caplog: pytest.LogCaptureFixture,
) -> None:
    store.set_final_time("g1", GAME_DATE, FINAL_TIME)
    store.set_final_time("g2", GAME_DATE, FINAL_TIME)
    first = MATCH.model_copy(update={"video_id": "vid-g1"})
    second = MATCH.model_copy(
        update={
            "video_id": "vid-g2",
            "title": "JAZZ at NUGGETS | FULL GAME HIGHLIGHTS | October 4, 2026",
        }
    )
    lookup.uploads = [first, second]
    lookup.thumbnail_errors["vid-g1"] = SourceError(
        "video_channel", "request failed", request_failed=True
    )
    games = [make_game("g1"), make_game("g2", JAZZ, NUGGETS)]
    job = make_job(tmp_path, store, lookup, games)
    now = FINAL_TIME + HOUR

    with caplog.at_level(logging.WARNING):
        await job.run(now)

    messages = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert messages == [
        "highlights for game g1: attempt 1 of 3 not counted, retrying in 10 minutes: video_channel: request failed"
    ]
    assert [h.title for h in job.highlights_of(games[1])] == [second.title]
    assert job.highlights_of(games[0]) == []
    assert store.highlight_attempts("g1") == 0
    assert store.highlight_attempts("g2") == 1
    state = store.job_states()[0]
    assert state.last_failure == now
    assert state.last_failure_reason == "video_channel: request failed"


@pytest.mark.anyio
async def test_a_game_first_seen_final_after_a_restart_gets_its_highlight_from_an_older_page_on_the_first_run(
    tmp_path: Path, store: StateStore
) -> None:
    store.set_final_time("g1", GAME_DATE, FINAL_TIME, first_seen=True)
    requests: list[httpx.Request] = []

    def serve(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        name = "page-2" if request.url.params.get("pageToken") == "page-2" else "page-1"
        return httpx.Response(
            200, text=(FIXTURES / f"uploads-{name}.json").read_text(encoding="utf-8")
        )

    respx.get("https://example.com/uploads").mock(side_effect=serve)
    respx.head(url__startswith="https://example.com/thumbs/").respond(200)
    settings = make_settings(
        tmp_path,
        highlights_source_url="https://example.com/uploads",
        highlights_source_key="test-key-value",
    )
    job = HighlightsJob(
        settings,
        store,
        create_client(store, clock=lambda: FINAL_TIME),
        final_games=lambda: [make_game()],
        clock=lambda: FINAL_TIME,
    )

    await job.run(FINAL_TIME)

    [highlight] = job.highlights_of(make_game())
    assert highlight.title == TITLE
    assert (
        str(highlight.thumbnail_url) == "https://example.com/thumbs/vid-full/maxres.jpg"
    )
    assert [
        h.title
        for h in HighlightsJob(
            settings,
            store,
            create_client(store, clock=lambda: FINAL_TIME),
            final_games=lambda: [make_game()],
            clock=lambda: FINAL_TIME,
        ).highlights_of(make_game())
    ] == [TITLE]
    assert len(requests) == 2
    assert store.job_states()[0].last_success == FINAL_TIME


def test_gives_every_game_a_search_url_from_the_template(
    tmp_path: Path, store: StateStore, lookup: FakeLookup
) -> None:
    job = make_job(tmp_path, store, lookup, [])

    url = job.search_url_of(make_game())

    assert (
        url
        == "https://example.com/s?q=Warriors+Clippers+full+game+highlights+October+4%2C+2026"
    )


def test_gives_no_search_url_without_the_template(
    tmp_path: Path, store: StateStore, lookup: FakeLookup
) -> None:
    settings = Settings(_env_file=None, data_dir=tmp_path)  # type: ignore[call-arg]
    job = HighlightsJob(
        settings,
        store,
        create_client(store),
        final_games=list,
        list_uploads=lookup.list_uploads,
        check_thumbnail=lookup.check_thumbnail,
    )

    assert job.search_url_of(make_game()) is None


@pytest.mark.anyio
async def test_an_attempt_keeps_the_game_date_of_the_row(
    tmp_path: Path, store: StateStore, lookup: FakeLookup
) -> None:
    store.set_final_time("g1", GAME_DATE, FINAL_TIME)
    job = make_job(tmp_path, store, lookup, [make_game()])

    await job.run(FINAL_TIME + HOUR)

    assert store.game_date("g1") == GAME_DATE
    assert store.highlight_attempts("g1") == 1


@pytest.mark.anyio
async def test_retries_the_same_attempt_no_sooner_than_ten_minutes_after_a_failed_request(
    tmp_path: Path, store: StateStore, lookup: FakeLookup
) -> None:
    store.set_final_time("g1", GAME_DATE, FINAL_TIME)
    now = FINAL_TIME + HOUR
    job = make_job(tmp_path, store, lookup, [make_game()], clock=lambda: now)
    lookup.error = REQUEST_FAILED
    await job.run(now)
    lookup.error = None
    lookup.default = None

    await job.run(now + RETRY - dt.timedelta(seconds=1))
    assert len(lookup.calls) == 1
    await job.run(now + RETRY)

    assert RETRY == dt.timedelta(minutes=10)
    assert len(lookup.calls) == 2
    assert store.highlight_attempts("g1") == 1


@pytest.mark.anyio
async def test_measures_the_ten_minutes_from_the_failed_request_not_from_the_start_of_the_run(
    tmp_path: Path, store: StateStore, lookup: FakeLookup
) -> None:
    store.set_final_time("g1", GAME_DATE, FINAL_TIME)
    start = FINAL_TIME + HOUR
    slow = dt.timedelta(seconds=30)
    clock = [start]
    job = make_job(tmp_path, store, lookup, [make_game()], clock=lambda: clock[0])

    async def slow_failure(
        client: httpx.AsyncClient,
        games: Sequence[tuple[ScoreboardGame, dt.date]],
        settings: Settings,
        listed_since: dt.datetime,
    ) -> list[ChannelVideo]:
        lookup.calls.append([(game.id, day) for game, day in games])
        clock[0] = clock[0] + slow
        raise REQUEST_FAILED

    job._list_uploads = slow_failure
    await job.run(start)
    job._list_uploads = lookup.list_uploads

    await job.run(start + RETRY)
    assert len(lookup.calls) == 1
    await job.run(start + RETRY + slow)
    assert len(lookup.calls) == 2


@pytest.mark.anyio
async def test_a_failed_request_does_not_move_the_attempt_schedule(
    tmp_path: Path, store: StateStore, lookup: FakeLookup
) -> None:
    store.set_final_time("g1", GAME_DATE, FINAL_TIME)
    first = FINAL_TIME + HOUR
    job = make_job(tmp_path, store, lookup, [make_game()], clock=lambda: first)
    lookup.error = REQUEST_FAILED
    await job.run(first)
    lookup.error = None

    await job.run(first + RETRY)
    assert store.highlight_attempts("g1") == 1
    await job.run(FINAL_TIME + 2 * HOUR - dt.timedelta(minutes=1))
    assert store.highlight_attempts("g1") == 1
    await job.run(FINAL_TIME + 2 * HOUR)
    assert store.highlight_attempts("g1") == 2
    await job.run(FINAL_TIME + 3 * HOUR)
    await job.run(FINAL_TIME + 4 * HOUR)
    await job.run(FINAL_TIME + 24 * HOUR)

    assert store.highlight_attempts("g1") == 3
    assert len(lookup.calls) == 4


@pytest.mark.anyio
async def test_a_lookup_that_answers_with_no_match_still_uses_up_an_attempt(
    tmp_path: Path, store: StateStore, lookup: FakeLookup
) -> None:
    store.set_final_time("g1", GAME_DATE, FINAL_TIME)
    lookup.default = None
    job = make_job(tmp_path, store, lookup, [make_game()])
    now = FINAL_TIME + HOUR

    await job.run(now)
    await job.run(now + dt.timedelta(minutes=30))

    assert store.highlight_attempts("g1") == 1
    assert len(lookup.calls) == 1


@pytest.mark.anyio
@pytest.mark.parametrize("case", ["invalid payload", "no thumbnail"])
async def test_any_other_source_error_still_uses_up_an_attempt(
    tmp_path: Path, store: StateStore, lookup: FakeLookup, case: str
) -> None:
    store.set_final_time("g1", GAME_DATE, FINAL_TIME)
    if case == "invalid payload":
        lookup.error = SourceError("video_channel", "invalid payload: items")
    else:
        lookup.default = MATCH.model_copy(update={"thumbnail_url": None})
    job = make_job(tmp_path, store, lookup, [make_game()])

    await job.run(FINAL_TIME + HOUR)

    assert store.highlight_attempts("g1") == 1
    assert store.job_states()[0].last_failure is not None


@pytest.mark.anyio
async def test_every_listing_of_a_run_lists_uploads_fetched_at_or_after_the_runs_start(
    tmp_path: Path, store: StateStore, lookup: FakeLookup
) -> None:
    store.set_final_time("g1", GAME_DATE, FINAL_TIME)
    store.set_final_time("g2", GAME_DATE, FINAL_TIME)
    job = make_job(tmp_path, store, lookup, [make_game("g1"), make_game("g2")])
    now = FINAL_TIME + HOUR

    await job.run(now)
    later = now + HOUR
    await job.run(later)

    assert lookup.listed_since_calls == [now, later]


def serve_real(
    tmp_path: Path,
    store: StateStore,
    games: list[ScoreboardGame],
    later_page: httpx.Response | None = None,
) -> tuple[HighlightsJob, list[httpx.Request]]:
    """A job over the real adapter and respx. Page 2 answers `later_page` when given."""
    requests: list[httpx.Request] = []

    def serve(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        token = request.url.params.get("pageToken")
        if token == "page-2" and later_page is not None:
            return later_page
        names = {None: "page-1", "page-2": "page-2", "page-3": "page-3"}
        return httpx.Response(
            200,
            text=(FIXTURES / f"uploads-{names[token]}.json").read_text(
                encoding="utf-8"
            ),
        )

    respx.get("https://example.com/uploads").mock(side_effect=serve)
    respx.head(url__startswith="https://example.com/thumbs/").respond(200)
    settings = make_settings(
        tmp_path,
        highlights_source_url="https://example.com/uploads",
        highlights_source_key="test-key-value",
    )
    job = HighlightsJob(
        settings,
        store,
        create_client(store, clock=lambda: FINAL_TIME),
        final_games=lambda: games,
        clock=lambda: FINAL_TIME,
    )
    return job, requests


NETS_START = dt.datetime(2026, 10, 4, 19, 0, tzinfo=dt.UTC)


def three_games() -> list[ScoreboardGame]:
    return [
        make_game("g1", JAZZ, NUGGETS),
        make_game("g2"),
        make_game("g3", NETS, HEAT, NETS_START),
    ]


@pytest.mark.anyio
async def test_a_run_with_three_due_games_lists_each_page_once_back_to_the_oldest_due_game(
    tmp_path: Path, store: StateStore
) -> None:
    games = three_games()
    for game in games:
        store.set_final_time(game.id, GAME_DATE, FINAL_TIME)
    job, requests = serve_real(tmp_path, store, games)

    await job.run(FINAL_TIME + HOUR)

    assert [r.url.params.get("pageToken") for r in requests] == [
        None,
        "page-2",
        "page-3",
    ]


@pytest.mark.anyio
async def test_every_due_game_is_matched_against_the_one_listing_including_a_later_page(
    tmp_path: Path, store: StateStore
) -> None:
    games = three_games()
    for game in games:
        store.set_final_time(game.id, GAME_DATE, FINAL_TIME)
    job, _ = serve_real(tmp_path, store, games)
    now = FINAL_TIME + HOUR

    await job.run(now)

    assert [h.channel for g in games for h in job.highlights_of(g)] == [
        "Example Channel",
        "Example Channel",
    ]
    assert job.highlights_of(games[2]) == []
    assert [job.highlights_of(g) != [] for g in games] == [True, True, False]
    assert [store.highlight_attempts(g.id) for g in games] == [1, 1, 1]
    assert store.job_states()[0].last_success == now


@pytest.mark.anyio
async def test_a_listing_that_fails_on_a_later_page_uses_up_no_attempt_even_of_a_game_matched_earlier(
    tmp_path: Path, store: StateStore
) -> None:
    games = [make_game("g1", JAZZ, NUGGETS), make_game("g2")]
    for game in games:
        store.set_final_time(game.id, GAME_DATE, FINAL_TIME)
    job, _ = serve_real(tmp_path, store, games, httpx.Response(503))
    now = FINAL_TIME + HOUR

    await job.run(now)

    assert store.highlights() == {}
    assert [store.highlight_attempts(g.id) for g in games] == [0, 0]
    state = store.job_states()[0]
    assert state.last_failure == now
    assert state.last_failure_reason == "video_channel: responded with status 503"


@pytest.mark.anyio
async def test_a_listing_invalid_on_a_later_page_keeps_the_match_of_an_earlier_page_and_uses_up_an_attempt_of_the_others(
    tmp_path: Path,
    store: StateStore,
    caplog: pytest.LogCaptureFixture,
) -> None:
    games = [make_game("g1", JAZZ, NUGGETS), make_game("g2")]
    for game in games:
        store.set_final_time(game.id, GAME_DATE, FINAL_TIME)
    job, _ = serve_real(tmp_path, store, games, httpx.Response(200, text="not json"))
    now = FINAL_TIME + HOUR

    with caplog.at_level(logging.WARNING):
        await job.run(now)

    assert [h.title for h in job.highlights_of(games[0])] == [
        "JAZZ at NUGGETS | FULL GAME HIGHLIGHTS | October 4, 2026"
    ]
    assert job.highlights_of(games[1]) == []
    assert [store.highlight_attempts(g.id) for g in games] == [1, 1]
    messages = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert len(messages) == 1
    assert messages[0].startswith("highlights for game g2: attempt 1 of 3 failed: ")
    state = store.job_states()[0]
    assert state.last_failure == now
    assert state.last_failure_reason is not None


@pytest.mark.anyio
async def test_a_failed_listing_uses_up_no_attempt_of_any_due_game_and_retries_each_no_sooner_than_ten_minutes(
    tmp_path: Path,
    store: StateStore,
    lookup: FakeLookup,
    caplog: pytest.LogCaptureFixture,
) -> None:
    games = [make_game("g1"), make_game("g2"), make_game("g3")]
    for game in games:
        store.set_final_time(game.id, GAME_DATE, FINAL_TIME)
    now = FINAL_TIME + HOUR
    job = make_job(tmp_path, store, lookup, games, clock=lambda: now)
    lookup.error = REQUEST_FAILED

    with caplog.at_level(logging.WARNING):
        await job.run(now)

    messages = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert len(messages) == 3
    assert all("not counted, retrying in 10 minutes" in m for m in messages)
    assert [store.highlight_attempts(g.id) for g in games] == [0, 0, 0]
    assert store.job_states()[0].last_failure == now
    lookup.error = None

    await job.run(now + RETRY - dt.timedelta(seconds=1))
    assert len(lookup.calls) == 1
    await job.run(now + RETRY)

    assert lookup.calls[1] == [(g.id, GAME_DATE) for g in games]
    assert len(lookup.calls) == 2


@pytest.mark.anyio
async def test_a_listing_with_another_error_uses_up_one_attempt_of_each_due_game(
    tmp_path: Path, store: StateStore, lookup: FakeLookup
) -> None:
    games = [make_game("g1"), make_game("g2"), make_game("g3")]
    for game in games:
        store.set_final_time(game.id, GAME_DATE, FINAL_TIME)
    lookup.error = SourceError("video_channel", "invalid payload: items")
    job = make_job(tmp_path, store, lookup, games)

    await job.run(FINAL_TIME + HOUR)

    assert [store.highlight_attempts(g.id) for g in games] == [1, 1, 1]
    state = store.job_states()[0]
    assert state.last_failure_reason == "video_channel: invalid payload: items"


@pytest.mark.anyio
async def test_a_successful_listing_counts_each_due_game_as_its_own_lookup_did(
    tmp_path: Path,
    store: StateStore,
    lookup: FakeLookup,
    caplog: pytest.LogCaptureFixture,
) -> None:
    games = [
        make_game("g1"),
        make_game("g2", JAZZ, NUGGETS),
        make_game("g3", NETS, HEAT),
        make_game("g4", ("SAS", "Spurs"), ("PHX", "Suns")),
    ]
    for game in games:
        store.set_final_time(game.id, GAME_DATE, FINAL_TIME)

    def upload(video_id: str, name: str, thumbnail: bool) -> ChannelVideo:
        return ChannelVideo(
            video_id=video_id,
            title=f"{name} | FULL GAME HIGHLIGHTS | October 4, 2026",
            channel="Channel",
            thumbnail_url="https://example.com/t/x.jpg" if thumbnail else None,
        )

    lookup.uploads = [
        upload("v1", "WARRIORS at CLIPPERS", True),
        upload("v3", "NETS at HEAT", False),
        upload("v4", "SPURS at SUNS", True),
    ]
    lookup.thumbnail_errors["v4"] = REQUEST_FAILED
    now = FINAL_TIME + HOUR
    job = make_job(tmp_path, store, lookup, games, clock=lambda: now)

    with caplog.at_level(logging.WARNING):
        await job.run(now)

    messages = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert messages == [
        "highlights for game g2: attempt 1 of 3 failed: no video matched",
        "highlights for game g3: attempt 1 of 3 failed: video v3 has no thumbnail",
        "highlights for game g4: attempt 1 of 3 not counted, retrying in 10 minutes: video_channel: request timed out",
    ]
    assert len(lookup.calls) == 1
    assert [store.highlight_attempts(g.id) for g in games] == [1, 1, 1, 0]
    assert [job.highlights_of(g) != [] for g in games] == [True, False, False, False]
    lookup.thumbnail_errors.clear()

    await job.run(now + RETRY - dt.timedelta(seconds=1))
    assert len(lookup.calls) == 1
    await job.run(now + RETRY)

    assert lookup.calls[1] == [("g4", GAME_DATE)]
    assert store.highlight_attempts("g4") == 1
