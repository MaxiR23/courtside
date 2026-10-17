# api/tests/jobs/test_day_feed.py
#
# Tests for the day feed builder and its feed kind.
#
# Tested:
# - The builder sets null stars, empty highlights, the search link, the winner and unavailable stats on a final game, and nulls on scheduled and postponed games
# - The builder skips a game that is not a valid past game with a log line by event id, and keeps the others
# - The builder lists a day whose All-Star games are final with scores and no line score, with a null line score and unavailable stats (ADR 0051)
# - The day id also refuses a trailing newline
# - The builder sets the season 1999 and the label 1998-99
# - The builder gives an empty day for no event, and wraps an invalid feed in a build error
# - The day id: a real YYYY-MM-DD date only
# - The kind: 2024-13-01, 20240101, abc, 1993-09-30, tomorrow and a day of the stored games feed answer unknown with no source request
# - The kind: 1993-10-01 is known, a day before the games job's window is known, and with no games feed stored a day inside the window is unknown
# - The kind: a request builds and stores a valid feed and a second request reads storage
# - The kind: an all-final day and an empty day are fresh after a year, a day with a postponed or scheduled game is fresh before 6 hours and stale at 6 hours
# - The kind: a failed read with nothing stored answers unavailable, and a failed rebuild keeps the stored feed
# - The kind: the stored highlight of a final game is added when served and not stored, and an All-Star game gets none
# - The kind: the cleanup keeps every day
# - The kind: a final day stored without the current build version is served, then rebuilt with season names; one of the current version is served as stored (ADR 0053)
# - The kind: league sides are named by the day's season team object, a guest side keeps its name, and a failed season team read keeps the last valid feed (ADR 0053)
#
# What is covered:
# - Pure conversions: happy path, edges and errors; the built feed validates
# - Feed kind: success publishes a valid feed, failure keeps the last valid feed, expiry edges
#
# Run with: cd api && .venv/bin/python -m pytest tests/jobs/test_day_feed.py
#
# SEE: api/app/jobs/day_feed.py

import asyncio
import datetime as dt
import logging
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

from app.feeds.days import DayFeed
from app.feeds.games import (
    GameAllStar,
    GamesFeed,
    GameStatus,
    Highlight,
    LineScore,
    Score,
    StatsAvailability,
)
from app.feeds.opponent import Side
from app.jobs.day_feed import (
    FIRST_DAY,
    KIND,
    REBUILD_AFTER,
    DayBuildError,
    DayFeeds,
    build_day_feed,
    parse_day,
    stored_window_days,
)
from app.jobs.on_demand import (
    SEASON_BUILD_VERSION,
    FeedCache,
    FeedUnavailableError,
    IdStatus,
    UnknownFeedError,
)
from app.jobs.stars import StarsJob
from app.jobs.team_names import TeamNamesFeeds
from app.settings import Settings
from app.sources.http import SourceClient, SourceError, create_client
from app.sources.scoreboard import PastScoreboardDay, ScoreboardGame
from app.sources.season_team import SeasonTeam
from app.storage.feeds import publish_by_id, publish_feed, read_by_id
from app.storage.state import StateStore

NOW = dt.datetime(2026, 10, 8, 15, 0, tzinfo=dt.UTC)
TODAY = dt.date(2026, 10, 8)
PAST = dt.date(2026, 9, 1)
SEARCH = "https://example.com/search?q={query}"
YEAR = dt.timedelta(days=365)
SECOND = dt.timedelta(seconds=1)


def side(code: str) -> dict[str, Any]:
    return {"code": code, "name": "Name", "city": "City"}


def game(game_id: str, status: GameStatus, **changes: Any) -> ScoreboardGame:
    data: dict[str, Any] = {
        "id": game_id,
        "away": side("DEN"),
        "home": side("OKC"),
        "status": status,
        "start_time": dt.datetime(2026, 9, 1, 23, 0, tzinfo=dt.UTC),
        "venue": "Arena",
    }
    if status is GameStatus.FINAL:
        data["line_score"] = LineScore(away=[20, 20], home=[22, 21])
        data["score"] = Score(away=40, home=43)
    data.update(changes)
    return ScoreboardGame.model_validate(data)


def search_url(_: ScoreboardGame) -> str | None:
    return "https://example.com/search?q=x"


def build(*games: ScoreboardGame, url: Any = search_url) -> DayFeed:
    return build_day_feed(NOW, PAST, 1999, games, url)


def test_a_final_game_has_null_stars_no_highlights_unavailable_stats_and_a_winner() -> (
    None
):
    feed = build(game("1", GameStatus.FINAL))

    built = feed.day.games[0]
    assert built.stars.away is None and built.stars.home is None
    assert built.highlights == []
    assert built.stats_availability is StatsAvailability.UNAVAILABLE
    assert built.leaders is None and built.team_stats is None
    assert built.winner is Side.HOME
    assert str(built.highlights_search_url) == "https://example.com/search?q=x"
    assert feed.day.date == PAST


def test_a_day_of_untimed_final_all_star_games_lists_them_without_a_line_score() -> (
    None
):
    mark = GameAllStar(round_label="All-Star Game", championship=False)
    untimed = game("1", GameStatus.FINAL, all_star=mark).model_copy(
        update={"line_score": None}
    )

    feed = build(
        untimed,
        game("2", GameStatus.FINAL, all_star=mark).model_copy(
            update={"line_score": None}
        ),
    )

    assert [g.id for g in feed.day.games] == ["1", "2"]
    for built in feed.day.games:
        assert built.line_score is None
        assert built.score is not None
        assert built.stats_availability is StatsAvailability.UNAVAILABLE


def test_scheduled_and_postponed_games_have_no_search_link_stats_or_winner() -> None:
    feed = build(game("1", GameStatus.SCHEDULED), game("2", GameStatus.POSTPONED))

    for built in feed.day.games:
        assert built.highlights_search_url is None
        assert built.stats_availability is None
        assert built.winner is None
        assert built.leaders is None and built.team_stats is None
        assert built.stars.away is None and built.stars.home is None


def test_a_game_that_is_not_a_valid_past_game_is_skipped_with_a_log_line(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.WARNING, logger="app.jobs.day_feed"):
        feed = build(
            game("1", GameStatus.FINAL),
            game("2", GameStatus.FINAL),
            game("3", GameStatus.SCHEDULED),
            url=lambda g: None if g.id == "2" else search_url(g),
        )

    assert [g.id for g in feed.day.games] == ["1", "3"]
    assert len(caplog.records) == 1
    assert caplog.records[0].getMessage().startswith("days: game 2 skipped: ")


def test_the_builder_sets_the_season_and_its_label() -> None:
    feed = build()

    assert feed.season == 1999
    assert feed.season_label == "1998-99"


def test_no_event_gives_an_empty_day() -> None:
    feed = build()

    assert feed.day.games == []
    assert feed.day.date == PAST


def test_an_invalid_feed_is_wrapped_in_a_build_error() -> None:
    naive = NOW.replace(tzinfo=None)

    with pytest.raises(DayBuildError) as raised:
        build_day_feed(naive, PAST, 1999, [], search_url)

    assert raised.value.reason.startswith("invalid feed: ")


@pytest.mark.parametrize(
    ("feed_id", "expected"),
    [
        ("2024-02-29", dt.date(2024, 2, 29)),
        ("2024-13-01", None),
        ("2023-02-29", None),
        ("20240101", None),
        ("2024-1-1", None),
        ("abc", None),
        ("", None),
    ],
)
def test_the_day_id_is_a_real_iso_date_only(
    feed_id: str, expected: dt.date | None
) -> None:
    assert parse_day(feed_id) == expected


class DayKit:
    """A feed cache and the day kind over one client and one clock, with a
    fake scoreboard adapter that counts its calls."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.clock = [NOW]
        self.store = StateStore(path)
        self.store.migrate()
        self.settings = Settings(  # type: ignore[call-arg]
            _env_file=None, data_dir=path, highlights_search_url=SEARCH
        )
        self.client = create_client(self.store, clock=lambda: self.clock[0])
        self.calls: list[dt.date] = []
        self.failing = False
        self.days: dict[dt.date, list[ScoreboardGame]] = {}
        self.cache = FeedCache(path, self.store, clock=lambda: self.clock[0])
        # The (name, city) of the season team object by code; the default is the
        # name and city of the sides the tests draw, so a side is renamed only when
        # a test says so.
        self.season_names: dict[str, tuple[str, str]] = {}
        self.season_team_calls: list[tuple[str, int]] = []
        self.season_team_failing = False
        self.names = TeamNamesFeeds(
            self.settings,
            self.store,
            self.client,
            self.cache,
            cast(StarsJob, SimpleNamespace(current_season=lambda: 2027)),
            fetch_season_team=self.fetch_season_team,
        )
        self.days_kind = DayFeeds(
            self.settings,
            self.store,
            self.client,
            self.cache,
            self.names,
            fetch_past_day=self.fetch_past_day,
        )

    async def fetch_season_team(
        self, client: SourceClient, code: str, season: int, settings: Settings
    ) -> SeasonTeam | None:
        self.season_team_calls.append((code, season))
        if self.season_team_failing:
            raise SourceError("test", "season team is down")
        name, city = self.season_names.get(code, ("Name", "City"))
        return SeasonTeam(
            team_id="1",
            abbreviation=code,
            display_name=f"{city} {name}",
            name=name,
            location=city,
        )

    async def fetch_past_day(
        self, client: SourceClient, day: dt.date, settings: Settings
    ) -> PastScoreboardDay:
        self.calls.append(day)
        if self.failing:
            raise SourceError("test", "scoreboard is down")
        return PastScoreboardDay(season=1999, games=list(self.days.get(day, [])))

    async def settle(self) -> None:
        while self.cache.in_flight:
            await next(iter(self.cache.in_flight.values()))
            await asyncio.sleep(0)
        await asyncio.sleep(0)

    async def serve(self, day: dt.date, at: dt.datetime | None = None) -> bytes:
        if at is not None:
            self.clock[0] = at
        body = await self.cache.serve(KIND, day.isoformat())
        await self.settle()
        return body

    def store_games_feed(self, *days: dt.date) -> None:
        feed = GamesFeed.model_validate(
            {"generated_at": NOW, "days": [{"date": d, "games": []} for d in days]}
        )
        publish_feed(self.path, "games", feed)


@pytest.fixture
def kit(tmp_path: Path) -> DayKit:
    return DayKit(tmp_path)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "feed_id",
    ["2024-13-01", "20240101", "abc", "1993-09-30", "2026-10-09", "2026-10-01\n"],
)
async def test_an_invalid_early_or_future_day_is_unknown_with_no_source_request(
    kit: DayKit, feed_id: str
) -> None:
    assert kit.days_kind.check(feed_id) is IdStatus.UNKNOWN
    with pytest.raises(UnknownFeedError):
        await kit.cache.serve(KIND, feed_id)

    assert kit.calls == []


@pytest.mark.anyio
async def test_the_first_day_is_known_and_a_day_of_the_stored_games_feed_is_unknown(
    kit: DayKit,
) -> None:
    kit.store_games_feed(dt.date(2026, 9, 20), dt.date(2026, 9, 21))

    assert FIRST_DAY == dt.date(1993, 10, 1)
    assert kit.days_kind.check("1993-10-01") is IdStatus.KNOWN
    assert kit.days_kind.check("2026-09-20") is IdStatus.UNKNOWN
    assert kit.days_kind.check("2026-09-21") is IdStatus.UNKNOWN
    assert kit.days_kind.check("2026-09-19") is IdStatus.KNOWN
    assert stored_window_days(kit.path) == [dt.date(2026, 9, 20), dt.date(2026, 9, 21)]
    assert kit.calls == []


@pytest.mark.anyio
async def test_with_no_games_feed_stored_the_days_the_games_job_shows_are_unknown(
    kit: DayKit,
) -> None:
    assert stored_window_days(kit.path) is None
    assert kit.days_kind.check("2026-10-05") is IdStatus.UNKNOWN
    assert kit.days_kind.check("2026-10-08") is IdStatus.UNKNOWN
    assert kit.days_kind.check("2026-10-04") is IdStatus.KNOWN


@pytest.mark.anyio
async def test_an_invalid_stored_games_feed_counts_as_none_stored(kit: DayKit) -> None:
    (kit.path / "feeds").mkdir(exist_ok=True)
    (kit.path / "feeds" / "games.json").write_text("{", encoding="utf-8")

    assert stored_window_days(kit.path) is None


@pytest.mark.anyio
async def test_a_request_builds_and_stores_a_valid_feed_and_a_second_reads_storage(
    kit: DayKit,
) -> None:
    kit.days[PAST] = [game("1", GameStatus.FINAL)]

    first = await kit.serve(PAST)
    second = await kit.serve(PAST)

    assert first == second
    assert kit.calls == [PAST]
    stored = read_by_id(kit.path, KIND, PAST.isoformat())
    assert stored is not None
    feed = DayFeed.model_validate_json(stored)
    assert [g.id for g in feed.day.games] == ["1"]
    assert feed.generated_at == NOW


@pytest.mark.anyio
async def test_an_all_final_day_is_fresh_after_a_year(kit: DayKit) -> None:
    kit.days[PAST] = [game("1", GameStatus.FINAL)]

    await kit.serve(PAST)
    await kit.serve(PAST, NOW + YEAR)

    assert kit.calls == [PAST]


@pytest.mark.anyio
async def test_an_empty_day_is_fresh_after_a_year(kit: DayKit) -> None:
    await kit.serve(PAST)
    body = await kit.serve(PAST, NOW + YEAR)

    assert DayFeed.model_validate_json(body).day.games == []
    assert kit.calls == [PAST]


@pytest.mark.anyio
@pytest.mark.parametrize("status", [GameStatus.POSTPONED, GameStatus.SCHEDULED])
async def test_a_day_with_an_unfinished_game_is_fresh_before_6_hours_and_stale_at_6_hours(
    kit: DayKit, status: GameStatus
) -> None:
    kit.days[PAST] = [game("1", GameStatus.FINAL), game("2", status)]

    await kit.serve(PAST)
    await kit.serve(PAST, NOW + REBUILD_AFTER - SECOND)
    assert kit.calls == [PAST]
    await kit.serve(PAST, NOW + REBUILD_AFTER)

    assert kit.calls == [PAST, PAST]


@pytest.mark.anyio
async def test_a_failed_read_with_nothing_stored_answers_unavailable(
    kit: DayKit,
) -> None:
    kit.failing = True

    with pytest.raises(FeedUnavailableError):
        await kit.serve(PAST)

    assert read_by_id(kit.path, KIND, PAST.isoformat()) is None


@pytest.mark.anyio
async def test_a_failed_rebuild_keeps_and_serves_the_stored_feed(kit: DayKit) -> None:
    kit.days[PAST] = [game("1", GameStatus.POSTPONED)]
    first = await kit.serve(PAST)
    kit.failing = True

    body = await kit.serve(PAST, NOW + REBUILD_AFTER)

    assert body == first
    assert len(kit.calls) == 2


@pytest.mark.anyio
async def test_the_cleanup_keeps_every_day(kit: DayKit) -> None:
    assert kit.days_kind.keep("2026-09-01") is True
    assert kit.days_kind.keep("1993-10-01") is True


@pytest.mark.anyio
async def test_league_sides_are_named_by_the_days_season_team_object(
    kit: DayKit,
) -> None:
    kit.season_names = {"DEN": ("Harbor Gulls", "Seattle")}
    kit.days[PAST] = [game("1", GameStatus.FINAL)]

    feed = DayFeed.model_validate_json(await kit.serve(PAST))

    built = feed.day.games[0]
    assert (built.away.code, built.away.name, built.away.city) == (
        "DEN",
        "Harbor Gulls",
        "Seattle",
    )
    assert (built.home.code, built.home.name, built.home.city) == (
        "OKC",
        "Name",
        "City",
    )
    assert sorted(kit.season_team_calls) == [("DEN", 1999), ("OKC", 1999)]


@pytest.mark.anyio
async def test_a_final_day_stored_without_the_build_version_is_served_then_rebuilt_with_season_names(
    kit: DayKit,
) -> None:
    kit.days[PAST] = [game("1", GameStatus.FINAL)]
    await kit.serve(PAST)
    stale = DayFeed.model_validate_json(
        read_by_id(kit.path, KIND, PAST.isoformat()) or b""
    ).model_copy(update={"build_version": None})
    assert publish_by_id(kit.path, KIND, DayFeed, PAST.isoformat(), stale)
    kit.season_names = {"DEN": ("Harbor Gulls", "Seattle")}

    served = DayFeed.model_validate_json(await kit.serve(PAST, NOW + YEAR))

    assert served.build_version is None
    rebuilt = DayFeed.model_validate_json(
        read_by_id(kit.path, KIND, PAST.isoformat()) or b""
    )
    assert rebuilt.build_version == SEASON_BUILD_VERSION
    assert rebuilt.day.games[0].away.name == "Harbor Gulls"
    assert kit.calls == [PAST, PAST]


@pytest.mark.anyio
async def test_a_final_day_of_the_current_build_version_is_served_as_stored(
    kit: DayKit,
) -> None:
    kit.days[PAST] = [game("1", GameStatus.FINAL)]
    first = await kit.serve(PAST)

    again = await kit.serve(PAST, NOW + YEAR)

    assert again == first
    assert DayFeed.model_validate_json(first).build_version == SEASON_BUILD_VERSION
    assert kit.calls == [PAST]


@pytest.mark.anyio
async def test_a_guest_side_keeps_its_name(kit: DayKit) -> None:
    guest = {"code": "HCM", "name": "Guests", "city": None, "guest": True}
    kit.days[PAST] = [game("1", GameStatus.FINAL, away=guest)]

    feed = DayFeed.model_validate_json(await kit.serve(PAST))

    built = feed.day.games[0]
    assert (built.away.name, built.away.guest) == ("Guests", True)
    assert [code for code, _ in kit.season_team_calls] == ["OKC"]


@pytest.mark.anyio
async def test_a_failed_season_team_read_keeps_the_last_valid_feed(
    kit: DayKit,
) -> None:
    kit.days[PAST] = [game("1", GameStatus.POSTPONED)]
    first = await kit.serve(PAST)
    kit.season_names = {"DEN": ("Harbor Gulls", "Seattle")}
    kit.season_team_failing = True

    body = await kit.serve(PAST, NOW + REBUILD_AFTER)

    assert body == first


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
async def test_the_stored_highlight_of_a_final_game_is_added_when_served_and_not_stored(
    kit: DayKit,
) -> None:
    kit.days[PAST] = [game("1", GameStatus.FINAL), game("2", GameStatus.FINAL)]
    kit.store.set_highlight("1", clip())

    served = DayFeed.model_validate_json(await kit.serve(PAST))

    assert [g.highlights for g in served.day.games] == [[clip()], []]
    stored = read_by_id(kit.path, KIND, PAST.isoformat())
    assert stored is not None
    assert all(
        g.highlights == [] for g in DayFeed.model_validate_json(stored).day.games
    )


@pytest.mark.anyio
async def test_an_all_star_game_gets_no_highlight_when_served(kit: DayKit) -> None:
    mark = GameAllStar(round_label="Final", championship=True)
    kit.days[PAST] = [game("1", GameStatus.FINAL, all_star=mark)]
    kit.store.set_highlight("1", clip())

    served = DayFeed.model_validate_json(await kit.serve(PAST))

    assert served.day.games[0].highlights == []
