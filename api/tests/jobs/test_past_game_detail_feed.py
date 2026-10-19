# api/tests/jobs/test_past_game_detail_feed.py
#
# Tests for the past game detail builder and its feed kind.
#
# Tested:
# - The builder takes the id, status, time, score, winner, marks, sides and search link from the stored day game, and the venue, box score, team stats and win probability from the sections
# - The builder builds a past All-Star final without a line score (ADR 0051) and a game whose sections carry null percentages (ADR 0052)
# - The builder carries the leaders of the sections and always writes the key, null or not (ADR 0057)
# - The builder sets the season label from the sections' season end year
# - The builder leaves injuries, last games, standings, stars, the season series, highlights and both records null; the stored highlight is added when served (ADR 0048)
# - The builder leaves the box score, team stats and win probability null when the sections lack them
# - A side by a known id keeps its standard code and the event's name and city, and an unknown id is a guest
# - The builder fails for a game that is not final and for sections without a season, and wraps an invalid feed
# - The kind: a final game of a stored day is known; an id in no day, a postponed game of a stored day and an unsafe id are unknown with no source request
# - The kind: a day stored after the first lookup is indexed on the next lookup
# - The kind: a registered game with no stored day is known and builds its day first, one the day does not list as final fails the build, and an id neither stored nor registered stays unknown (ADR 0053)
# - The kind: a request builds and stores a valid feed and a second request makes no source request
# - The kind: after a restart the stored feed is served with no source request
# - The kind: the stored feed is fresh after a year
# - The kind: a stored detail without the leaders key is rebuilt before it is served (the request waits); one with a null leaders block of the current version is fresh; a failed rebuild keeps serving the stored one (ADR 0057)
# - The kind: a stored detail without the current build version is served, then rebuilt from a day made current first; one of the current version is served as stored (ADR 0053)
# - The kind: a failed build answers unavailable and is not retried for 10 minutes
# - The kind: a summary without a season fails the build and stores nothing
# - The kind: the stored highlight is added when served as a list of one, null without one and on an All-Star game, and is not stored
# - The kind: serving reads only the highlight of its game
# - The kind: a built game is registered with its day, stays known and builds its day first after its day feed is deleted and a restart, and a check touches the registered row (ADR 0063)
# - The kind: the build sends one read under a budget of one
# - The kind: the cleanup keeps every past game detail
# - The kind: the games job, its day change and its cleanup never refresh or delete a past game detail
# - The kind: an upper-case postseason note gives the title-case mark and a finals note gives a finals mark without a number
#
# What is covered:
# - Pure conversions: happy path, edges and errors; the built feed validates
# - Feed kind: success publishes a valid feed, failure keeps nothing, kept forever
#
# Run with: cd api && .venv/bin/python -m pytest tests/jobs/test_past_game_detail_feed.py
#
# SEE: api/app/jobs/past_game_detail_feed.py

import datetime as dt
import json
import sqlite3
from collections.abc import Iterable, Iterator
from contextlib import closing
from pathlib import Path
from typing import Any

import pytest
import respx

from app.feeds.days import DayFeed, PastGame
from app.feeds.game_detail import PastGameDetailFeed
from app.feeds.games import GameAllStar, GameStatus, Highlight, PostseasonStage
from app.jobs.day_feed import KIND as DAY_KIND
from app.jobs.day_feed import build_day_feed
from app.jobs.on_demand import (
    RETRY_AFTER,
    SEASON_BUILD_VERSION,
    FeedCache,
    FeedUnavailableError,
    IdStatus,
    UnknownFeedError,
    with_build_version,
)
from app.jobs.past_game_detail_feed import (
    KIND,
    READ_BUDGET,
    PastDetailBuildError,
    PastGameDetailFeeds,
    build_past_game_detail_feed,
)
from app.settings import Settings
from app.sources import scoreboard
from app.sources.game_detail import GameDetailSections
from app.sources.http import Freshness, SourceClient, SourceError
from app.storage.feeds import _by_id_dir, delete_by_id, publish_by_id, read_by_id
from app.storage.state import STATE_FILE
from tests.feeds.test_game_detail import (
    box_team,
    leaders,
    leaders_of_game,
    pair,
    stats,
)
from tests.jobs.test_day_feed import NOW, PAST, SECOND, YEAR, DayKit, game, search_url
from tests.jobs.test_game_detail_feed import AFTER_MIDNIGHT, Harness
from tests.jobs.test_game_detail_feed import game as live_game

NOON = dt.datetime(2026, 10, 5, 16, 0, tzinfo=dt.UTC)
SCOREBOARD_TEMPLATE = "https://example.com/scoreboard/{date}"
FIXTURES = Path(__file__).parent.parent / "sources" / "fixtures" / "scoreboard"
MINUTE = dt.timedelta(minutes=1)


@pytest.fixture(autouse=True)
def no_network() -> Iterator[None]:
    with respx.mock:
        yield


def sections(**changes: Any) -> GameDetailSections:
    data: dict[str, Any] = {
        "venue": {"name": "Arena", "city": "City"},
        "season": 2005,
    }
    data.update(changes)
    return GameDetailSections.model_validate(data)


def full_sections() -> GameDetailSections:
    return sections(
        team_stats={**pair(stats(), stats()), "leaders": leaders()},
        box_score=pair(box_team(), box_team()),
        win_probability=[
            {"elapsed_seconds": 0, "home_win_probability": 0.5},
            {"elapsed_seconds": 2880, "home_win_probability": 0.9},
        ],
        win_probability_leader={"side": "home", "win_probability": 0.9},
        win_probability_periods={
            "periods": [{"number": 1, "start_elapsed_seconds": 0}],
            "end_elapsed_seconds": 2880,
        },
    )


def past_game(
    game_id: str = "1", status: GameStatus = GameStatus.FINAL, **changes: Any
) -> PastGame:
    feed = build_day_feed(
        NOW, PAST, 2026, [game(game_id, status, **changes)], search_url
    )
    return feed.day.games[0]


def test_builds_a_final_past_game_with_the_day_games_score_marks_sides_and_search_url_and_the_sections_blocks() -> (
    None
):
    day_game = past_game(
        broadcast="Network",
        postseason={
            "stage": "playoffs",
            "round": 1,
            "conference": "east",
            "number": 2,
            "summary": "Pilots lead 1-0",
            "play_in": None,
            "stakes": None,
        },
    )

    feed = build_past_game_detail_feed(day_game, full_sections())

    assert PastGameDetailFeed.model_validate_json(feed.model_dump_json()) == feed
    assert (feed.id, feed.status, feed.start_time) == (
        "1",
        GameStatus.FINAL,
        day_game.start_time,
    )
    assert feed.broadcast == "Network"
    assert feed.score == day_game.score and feed.line_score == day_game.line_score
    assert feed.winner is day_game.winner
    assert feed.postseason == day_game.postseason
    assert feed.postseason is not None
    assert feed.postseason.stage is PostseasonStage.PLAYOFFS
    assert str(feed.highlights_search_url) == "https://example.com/search?q=x"
    assert feed.venue is not None
    assert (feed.venue.name, feed.venue.city) == ("Arena", "City")
    assert feed.box_score is not None and feed.team_stats is not None
    assert feed.win_probability is not None and len(feed.win_probability) == 2
    assert feed.win_probability_leader is not None
    assert feed.win_probability_periods is not None


def test_builds_the_leaders_of_the_sections_and_always_writes_the_key() -> None:
    with_leaders = build_past_game_detail_feed(
        past_game(), sections(leaders=leaders_of_game())
    )
    without = build_past_game_detail_feed(past_game(), sections())

    assert with_leaders.leaders is not None
    assert with_leaders.leaders.away.player_id == "p1"
    assert without.leaders is None
    assert "leaders" in without.model_fields_set
    assert '"leaders":null' in without.model_dump_json(by_alias=True)


def test_builds_a_past_all_star_final_without_a_line_score() -> None:
    mark = GameAllStar(round_label="All-Star Game", championship=False)
    day_game = past_game(all_star=mark, line_score=None)

    feed = build_past_game_detail_feed(day_game, full_sections())

    assert feed.line_score is None
    assert feed.score == day_game.score
    assert feed.all_star == mark
    assert PastGameDetailFeed.model_validate_json(feed.model_dump_json()) == feed


def test_builds_a_game_whose_sections_have_null_percentages() -> None:
    missing = {**stats(), "fieldGoalPct": None, "freeThrowPct": None}
    box = box_team()
    box["totals"]["fieldGoalPct"] = None
    box["players"][0]["plusMinus"] = None
    found = sections(
        team_stats={
            **pair(missing, stats()),
            "leaders": {**leaders(), "fieldGoalPct": None},
        },
        box_score=pair(box, box_team()),
    )

    feed = build_past_game_detail_feed(past_game(), found)

    assert feed.team_stats is not None and feed.box_score is not None
    assert feed.team_stats.away.field_goal_pct is None
    assert feed.team_stats.away.free_throw_pct is None
    assert feed.box_score.away.totals.field_goal_pct is None
    assert feed.box_score.away.players[0].plus_minus is None
    assert PastGameDetailFeed.model_validate_json(feed.model_dump_json()) == feed


def test_sets_the_season_label_from_the_sections_season() -> None:
    feed = build_past_game_detail_feed(past_game(), sections(season=2005))

    assert feed.season_label == "2004-05"


def test_injuries_last_games_standings_stars_series_highlights_and_records_are_null() -> (
    None
):
    feed = build_past_game_detail_feed(past_game(), full_sections())

    assert feed.injuries is None and feed.last_games is None
    assert feed.standings is None and feed.stars is None
    assert feed.season_series is None and feed.highlights is None
    assert feed.away.record is None and feed.home.record is None


def test_box_score_team_stats_and_win_probability_are_null_when_the_sections_lack_them() -> (
    None
):
    feed = build_past_game_detail_feed(past_game(), sections())

    assert feed.box_score is None and feed.team_stats is None
    assert feed.win_probability is None
    assert feed.win_probability_leader is None
    assert feed.win_probability_periods is None


def test_a_side_by_known_id_keeps_its_standard_code_and_the_events_name_and_city_and_an_unknown_id_is_a_guest() -> (
    None
):
    guest = {"code": "HBR", "name": "Mariners", "city": "Bay Town", "guest": True}
    day_game = past_game(
        away=guest,
        home={"code": "OKC", "name": "Pilots", "city": "Harbor City"},
    )

    feed = build_past_game_detail_feed(day_game, sections())

    assert (feed.home.code, feed.home.name, feed.home.city) == (
        "OKC",
        "Pilots",
        "Harbor City",
    )
    assert feed.home.guest is False
    assert (feed.away.code, feed.away.name, feed.away.guest) == (
        "HBR",
        "Mariners",
        True,
    )


def test_fails_the_build_without_a_season_or_for_a_game_that_is_not_final() -> None:
    with pytest.raises(PastDetailBuildError, match="game 1 has no season"):
        build_past_game_detail_feed(past_game(), sections(season=None))
    with pytest.raises(PastDetailBuildError, match="game 2 is not final"):
        build_past_game_detail_feed(past_game("2", GameStatus.POSTPONED), sections())


def test_wraps_an_invalid_feed_in_a_build_error() -> None:
    bad = sections(
        win_probability_leader={"side": "away", "win_probability": 0.9},
        win_probability=[{"elapsed_seconds": 0, "home_win_probability": 0.9}],
    )

    with pytest.raises(PastDetailBuildError, match="invalid feed: 1 errors, first at"):
        build_past_game_detail_feed(past_game(), bad)


class PastKit(DayKit):
    """The day kit plus the past game detail kind over the same cache, with a
    fake game detail adapter that counts its calls."""

    def __init__(self, path: Path) -> None:
        super().__init__(path)
        self.section_calls: list[str] = []
        self.sections_failing = False
        self.season: int | None = 2005
        self.leaders: Any = None
        self.past_kind = PastGameDetailFeeds(
            self.settings,
            self.store,
            self.client,
            self.cache,
            fetch_sections=self.fetch_sections,
        )

    async def fetch_sections(
        self, client: SourceClient, game_id: str, settings: Settings, fresh: Freshness
    ) -> GameDetailSections:
        self.section_calls.append(game_id)
        if self.sections_failing:
            raise SourceError("test", "game detail is down")
        return sections(season=self.season, leaders=self.leaders)

    async def store_day(self, *games: Any) -> None:
        self.days[PAST] = list(games)
        await self.serve(PAST)

    async def serve_past(self, game_id: str, at: dt.datetime | None = None) -> bytes:
        if at is not None:
            self.clock[0] = at
        body = await self.cache.serve(KIND, game_id)
        await self.settle()
        return body


@pytest.fixture
def kit(tmp_path: Path) -> PastKit:
    return PastKit(tmp_path)


@pytest.mark.anyio
async def test_a_final_game_of_a_stored_day_is_known_and_any_other_id_is_unknown_with_no_source_request(
    kit: PastKit,
) -> None:
    await kit.store_day(game("1", GameStatus.FINAL), game("2", GameStatus.POSTPONED))

    assert kit.past_kind.check("1") is IdStatus.KNOWN
    for unknown in ("2", "nowhere", "a.b", "1\n"):
        assert kit.past_kind.check(unknown) is IdStatus.UNKNOWN
        with pytest.raises(UnknownFeedError):
            await kit.cache.serve(KIND, unknown)
    assert kit.section_calls == []


@pytest.mark.anyio
async def test_the_build_sends_one_read_under_its_budget(kit: PastKit) -> None:
    await kit.store_day(game("1", GameStatus.FINAL))

    await kit.serve_past("1")

    assert READ_BUDGET == 1
    assert kit.section_calls == ["1"]


@pytest.mark.anyio
async def test_a_day_stored_after_the_first_lookup_is_indexed_on_the_next_lookup(
    kit: PastKit,
) -> None:
    assert kit.past_kind.check("1") is IdStatus.UNKNOWN

    await kit.store_day(game("1", GameStatus.FINAL))

    assert kit.past_kind.check("1") is IdStatus.KNOWN


@pytest.mark.anyio
async def test_a_registered_game_with_no_stored_day_is_known_and_builds_its_day_first(
    kit: PastKit,
) -> None:
    kit.days[PAST] = [game("1", GameStatus.FINAL)]
    kit.store.set_past_game_dates({"1": PAST}, at=NOW)

    assert kit.past_kind.check("1") is IdStatus.KNOWN
    assert read_by_id(kit.path, DAY_KIND, PAST.isoformat()) is None
    body = await kit.serve_past("1")

    assert PastGameDetailFeed.model_validate_json(body).id == "1"
    assert read_by_id(kit.path, DAY_KIND, PAST.isoformat()) is not None
    assert kit.calls == [PAST]
    assert kit.section_calls == ["1"]


@pytest.mark.anyio
async def test_a_registered_game_the_day_does_not_list_as_final_fails_the_build(
    kit: PastKit,
) -> None:
    kit.days[PAST] = [game("1", GameStatus.POSTPONED)]
    kit.store.set_past_game_dates({"1": PAST}, at=NOW)

    with pytest.raises(FeedUnavailableError):
        await kit.serve_past("1")

    assert kit.section_calls == []
    assert read_by_id(kit.path, KIND, "1") is None


@pytest.mark.anyio
async def test_an_id_neither_stored_nor_registered_stays_unknown(kit: PastKit) -> None:
    kit.store.set_past_game_dates({"1": PAST}, at=NOW)

    assert kit.past_kind.check("2") is IdStatus.UNKNOWN
    with pytest.raises(UnknownFeedError):
        await kit.cache.serve(KIND, "2")
    assert kit.calls == [] and kit.section_calls == []


@pytest.mark.anyio
async def test_a_request_builds_and_stores_a_valid_feed_and_a_second_makes_no_source_request(
    kit: PastKit,
) -> None:
    await kit.store_day(game("1", GameStatus.FINAL))

    first = await kit.serve_past("1")
    second = await kit.serve_past("1")

    assert first == second
    assert kit.section_calls == ["1"]
    stored = read_by_id(kit.path, KIND, "1")
    assert stored is not None
    feed = PastGameDetailFeed.model_validate_json(stored)
    assert feed.season_label == "2004-05" and feed.id == "1"
    state = kit.store.feed_build(KIND, "1")
    assert state is not None and state.last_build == NOW


@pytest.mark.anyio
async def test_a_stored_detail_without_the_build_version_is_served_then_rebuilt_from_a_current_day(
    kit: PastKit,
) -> None:
    await kit.store_day(game("1", GameStatus.FINAL))
    await kit.serve_past("1")
    stored_day = DayFeed.model_validate_json(
        read_by_id(kit.path, DAY_KIND, PAST.isoformat()) or b""
    )
    stale_day = stored_day.model_copy(update={"build_version": None})
    assert publish_by_id(kit.path, DAY_KIND, DayFeed, PAST.isoformat(), stale_day)
    stale = PastGameDetailFeed.model_validate_json(
        read_by_id(kit.path, KIND, "1") or b""
    ).model_copy(update={"build_version": None})
    assert publish_by_id(kit.path, KIND, PastGameDetailFeed, "1", stale)

    served = PastGameDetailFeed.model_validate_json(
        await kit.serve_past("1", NOW + YEAR)
    )

    assert served.build_version is None
    day = DayFeed.model_validate_json(
        read_by_id(kit.path, DAY_KIND, PAST.isoformat()) or b""
    )
    rebuilt = PastGameDetailFeed.model_validate_json(
        read_by_id(kit.path, KIND, "1") or b""
    )
    assert day.build_version == SEASON_BUILD_VERSION
    assert rebuilt.build_version == SEASON_BUILD_VERSION
    assert kit.section_calls == ["1", "1"]
    assert kit.calls == [PAST, PAST]


@pytest.mark.anyio
async def test_a_stored_detail_of_the_current_build_version_is_served_as_stored(
    kit: PastKit,
) -> None:
    await kit.store_day(game("1", GameStatus.FINAL))
    first = await kit.serve_past("1")

    again = await kit.serve_past("1", NOW + YEAR)

    assert again == first
    assert PastGameDetailFeed.model_validate_json(first).build_version == (
        SEASON_BUILD_VERSION
    )
    assert kit.section_calls == ["1"]


@pytest.mark.anyio
async def test_after_a_restart_the_stored_feed_is_served_with_no_source_request(
    kit: PastKit, tmp_path: Path
) -> None:
    await kit.store_day(game("1", GameStatus.FINAL))
    first = await kit.serve_past("1")

    restarted = PastKit(tmp_path)
    again = await restarted.serve_past("1", NOW + YEAR)

    assert again == first
    assert restarted.section_calls == []


@pytest.mark.anyio
async def test_the_stored_feed_is_fresh_after_a_year(kit: PastKit) -> None:
    await kit.store_day(game("1", GameStatus.FINAL))
    await kit.serve_past("1")

    await kit.serve_past("1", NOW + YEAR)

    assert kit.section_calls == ["1"]


@pytest.mark.anyio
async def test_a_failed_build_answers_unavailable_and_is_not_retried_for_10_minutes(
    kit: PastKit,
) -> None:
    await kit.store_day(game("1", GameStatus.FINAL))
    kit.sections_failing = True

    with pytest.raises(FeedUnavailableError):
        await kit.serve_past("1")
    assert read_by_id(kit.path, KIND, "1") is None
    assert kit.section_calls == ["1"]
    with pytest.raises(FeedUnavailableError):
        await kit.serve_past("1", NOW + RETRY_AFTER - MINUTE)
    assert kit.section_calls == ["1"]
    kit.sections_failing = False
    body = await kit.serve_past("1", NOW + RETRY_AFTER)

    assert kit.section_calls == ["1", "1"]
    assert PastGameDetailFeed.model_validate_json(body).id == "1"


@pytest.mark.anyio
async def test_a_summary_without_a_season_fails_the_build(kit: PastKit) -> None:
    await kit.store_day(game("1", GameStatus.FINAL))
    kit.season = None

    with pytest.raises(FeedUnavailableError):
        await kit.serve_past("1")

    assert read_by_id(kit.path, KIND, "1") is None


@pytest.mark.anyio
async def test_the_cleanup_keeps_every_past_game_detail(kit: PastKit) -> None:
    await kit.store_day(game("1", GameStatus.FINAL))
    body = await kit.serve_past("1")

    kit.cache.cleanup()

    assert kit.past_kind.keep("1") is True
    assert read_by_id(kit.path, KIND, "1") == body
    assert kit.store.feed_build(KIND, "1") is not None
    assert read_by_id(kit.path, DAY_KIND, PAST.isoformat()) is not None


@pytest.mark.anyio
async def test_the_games_job_never_refreshes_or_deletes_a_past_game_detail(
    tmp_path: Path,
) -> None:
    harness = Harness(tmp_path)
    calls: list[str] = []

    async def fetch_sections(
        client: SourceClient, game_id: str, settings: Settings, fresh: Freshness
    ) -> GameDetailSections:
        calls.append(game_id)
        return sections()

    PastGameDetailFeeds(
        harness.settings,
        harness.store,
        harness.client,
        harness.cache,
        fetch_sections=fetch_sections,
    )
    day = with_build_version(
        build_day_feed(NOW, PAST, 2026, [game("p1", GameStatus.FINAL)], search_url)
    )
    publish_by_id(tmp_path, DAY_KIND, DayFeed, PAST.isoformat(), day)
    harness.games = [
        live_game("1", GameStatus.SCHEDULED, start=NOON + 5 * dt.timedelta(hours=1))
    ]
    await harness.run(NOON)
    body = await harness.cache.serve(KIND, "p1")
    await harness.settle()
    built = harness.store.feed_build(KIND, "p1")
    assert built is not None and calls == ["p1"]

    await harness.run(AFTER_MIDNIGHT)
    await harness.run(AFTER_MIDNIGHT + 30 * SECOND)

    assert read_by_id(tmp_path, KIND, "p1") == body
    assert harness.store.feed_build(KIND, "p1") == built
    assert calls == ["p1"]


@pytest.mark.anyio
async def test_an_upper_case_postseason_note_gives_the_title_case_mark_and_a_finals_note_gives_a_finals_mark_without_a_number(
    kit: PastKit,
) -> None:
    day = dt.date(1999, 2, 4)
    scoreboard_settings = Settings(  # type: ignore[call-arg]
        _env_file=None, scoreboard_url=SCOREBOARD_TEMPLATE
    )
    payload = json.loads((FIXTURES / "past-day.json").read_text(encoding="utf-8"))
    respx.get("https://example.com/scoreboard/19990204").respond(json=payload)
    past = await scoreboard.fetch_past_day(kit.client, day, scoreboard_settings)
    stored = with_build_version(
        build_day_feed(NOW, day, past.season, past.games, search_url)
    )
    publish_by_id(kit.path, DAY_KIND, DayFeed, day.isoformat(), stored)
    by_id = {g.id: g for g in stored.day.games}

    marked = PastGameDetailFeed.model_validate_json(await kit.serve_past("7005"))
    finals = PastGameDetailFeed.model_validate_json(await kit.serve_past("7006"))

    assert marked.postseason is not None
    assert marked.postseason == by_id["7005"].postseason
    assert marked.postseason.stage is PostseasonStage.PLAYOFFS
    assert (marked.postseason.round, marked.postseason.number) == (1, 1)
    assert finals.postseason is not None
    assert finals.postseason == by_id["7006"].postseason
    assert finals.postseason.stage is PostseasonStage.FINALS
    assert (finals.postseason.round, finals.postseason.number) == (4, None)
    assert kit.section_calls == ["7005", "7006"]


def clip() -> Highlight:
    return Highlight.model_validate(
        {
            "title": "Example highlights",
            "channel": "Example Channel",
            "thumbnail_url": "https://example.com/t.jpg",
            "embed_url": "https://example.com/e/v1",
        }
    )


@pytest.mark.anyio
async def test_the_stored_highlight_is_added_when_served_as_a_list_of_one_and_not_stored(
    kit: PastKit,
) -> None:
    await kit.store_day(game("1", GameStatus.FINAL), game("2", GameStatus.FINAL))
    kit.store.set_highlight("1", clip())

    with_clip = PastGameDetailFeed.model_validate_json(await kit.serve_past("1"))
    without = PastGameDetailFeed.model_validate_json(await kit.serve_past("2"))

    assert with_clip.highlights == [clip()]
    assert without.highlights is None
    stored = read_by_id(kit.path, KIND, "1")
    assert stored is not None
    assert PastGameDetailFeed.model_validate_json(stored).highlights is None


@pytest.mark.anyio
async def test_an_all_star_game_gets_no_highlight_when_served(kit: PastKit) -> None:
    mark = GameAllStar(round_label="Final", championship=True)
    await kit.store_day(game("1", GameStatus.FINAL, all_star=mark))
    kit.store.set_highlight("1", clip())

    served = PastGameDetailFeed.model_validate_json(await kit.serve_past("1"))

    assert served.all_star is not None
    assert served.highlights is None


def without_leaders_key(kit: PastKit) -> bytes:
    """Rewrites the stored detail as it was before the field: no leaders key."""
    body = json.loads(read_by_id(kit.path, KIND, "1") or b"")
    del body["leaders"]
    raw = json.dumps(body).encode()
    (_by_id_dir(kit.path, KIND) / "1.json").write_bytes(raw)
    return raw


@pytest.mark.anyio
async def test_a_stored_detail_without_the_leaders_key_is_rebuilt_before_it_is_served(
    kit: PastKit,
) -> None:
    await kit.store_day(game("1", GameStatus.FINAL))
    await kit.serve_past("1")
    old = without_leaders_key(kit)
    assert "leaders" not in PastGameDetailFeed.model_validate_json(old).model_fields_set
    kit.leaders = leaders_of_game()

    served = PastGameDetailFeed.model_validate_json(
        await kit.serve_past("1", NOW + YEAR)
    )

    assert served.leaders is not None
    assert served.leaders.away.player_id == "p1"
    rebuilt = PastGameDetailFeed.model_validate_json(
        read_by_id(kit.path, KIND, "1") or b""
    )
    assert "leaders" in rebuilt.model_fields_set
    assert kit.section_calls == ["1", "1"]


@pytest.mark.anyio
async def test_a_stored_detail_of_an_old_build_version_with_the_leaders_key_is_not_waited_for(
    kit: PastKit,
) -> None:
    await kit.store_day(game("1", GameStatus.FINAL))
    await kit.serve_past("1")
    stale = PastGameDetailFeed.model_validate_json(
        read_by_id(kit.path, KIND, "1") or b""
    ).model_copy(update={"build_version": None})
    assert publish_by_id(kit.path, KIND, PastGameDetailFeed, "1", stale)

    assert not kit.past_kind.wait_when_stale("1")
    assert not kit.past_kind.wait_when_stale("2")
    without_leaders_key(kit)
    assert kit.past_kind.wait_when_stale("1")


@pytest.mark.anyio
async def test_a_stored_detail_with_a_null_leaders_block_of_the_current_version_is_fresh(
    kit: PastKit,
) -> None:
    await kit.store_day(game("1", GameStatus.FINAL))
    first = await kit.serve_past("1")
    assert PastGameDetailFeed.model_validate_json(first).leaders is None

    again = await kit.serve_past("1", NOW + YEAR)

    assert again == first
    assert kit.section_calls == ["1"]


@pytest.mark.anyio
async def test_a_failed_rebuild_of_a_detail_without_the_leaders_key_keeps_serving_it(
    kit: PastKit,
) -> None:
    await kit.store_day(game("1", GameStatus.FINAL))
    await kit.serve_past("1")
    old = without_leaders_key(kit)
    kit.sections_failing = True

    first = await kit.serve_past("1", NOW + YEAR)
    second = await kit.serve_past("1", NOW + YEAR + RETRY_AFTER * 2)

    for body in (first, second):
        assert PastGameDetailFeed.model_validate_json(body).id == "1"
    assert read_by_id(kit.path, KIND, "1") == old


@pytest.mark.anyio
async def test_serve_with_reads_only_the_highlight_of_its_game(
    kit: PastKit, monkeypatch: pytest.MonkeyPatch
) -> None:
    await kit.store_day(game("1", GameStatus.FINAL))
    kit.store.set_highlight("1", clip())
    kit.store.set_highlight("other", clip())
    seen: list[list[str]] = []
    real = kit.store.highlights_for

    def spy(game_ids: Iterable[str]) -> dict[str, Highlight]:
        ids = list(game_ids)
        seen.append(ids)
        return real(ids)

    def boom() -> dict[str, Highlight]:
        raise AssertionError("every highlight was loaded")

    monkeypatch.setattr(kit.store, "highlights_for", spy)
    monkeypatch.setattr(kit.store, "highlights", boom)

    served = PastGameDetailFeed.model_validate_json(await kit.serve_past("1"))

    assert seen == [["1"]]
    assert served.highlights == [clip()]


def touched_at(kit: PastKit, game_id: str) -> str | None:
    with closing(sqlite3.connect(kit.path / STATE_FILE)) as connection:
        row = connection.execute(
            "SELECT touched_at FROM past_games WHERE game_id = ?", (game_id,)
        ).fetchone()
    return None if row is None else str(row[0])


@pytest.mark.anyio
async def test_a_built_past_game_is_registered_with_its_day(kit: PastKit) -> None:
    await kit.store_day(game("1", GameStatus.FINAL))
    assert kit.store.past_game_date("1", at=NOW) is None

    await kit.serve_past("1")

    assert kit.store.past_game_date("1", at=NOW) == PAST


@pytest.mark.anyio
async def test_a_past_game_stays_known_and_its_deleted_day_is_built_first_after_a_restart(
    kit: PastKit,
) -> None:
    await kit.store_day(game("1", GameStatus.FINAL))
    await kit.serve_past("1")
    delete_by_id(kit.path, DAY_KIND, PAST.isoformat())
    kit.store.delete_feed_build(DAY_KIND, PAST.isoformat())
    delete_by_id(kit.path, KIND, "1")
    kit.store.delete_feed_build(KIND, "1")
    kit.section_calls.clear()
    kit.calls.clear()

    restarted = PastGameDetailFeeds(
        kit.settings,
        kit.store,
        kit.client,
        FeedCache(kit.path, kit.store, clock=lambda: kit.clock[0]),
        fetch_sections=kit.fetch_sections,
    )

    assert restarted.check("1") is IdStatus.KNOWN
    assert restarted.depends_on("1") == (DAY_KIND, PAST.isoformat())
    body = await kit.serve_past("1")
    assert PastGameDetailFeed.model_validate_json(body).id == "1"
    assert kit.calls == [PAST]


@pytest.mark.anyio
async def test_a_check_touches_the_registered_row(kit: PastKit) -> None:
    kit.store.set_past_game_dates({"1": PAST}, at=NOW)
    kit.clock[0] = NOW + 5 * YEAR

    assert kit.past_kind.check("1") is IdStatus.KNOWN

    assert touched_at(kit, "1") == (NOW + 5 * YEAR).isoformat()
