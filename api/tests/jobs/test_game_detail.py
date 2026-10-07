# api/tests/jobs/test_game_detail.py
#
# Tests for the game detail job and its feed builder.
#
# Tested:
# - Builds a scheduled game with records, standings, injuries and last games
# - Builds a final game with its winner, box score and season series
# - Carries the win probability periods of the sections into the feed, or null
# - Takes each series arena from the team schedules and this game's venue
# - Passes the series leader, each game's winner and the current game into the feed
# - Lists no injuries for a team absent from the league injuries
# - Puts null highlights when the game has none
# - Rejects a game whose team has no standing, a series game with no arena and a live game without team stats
# - A successful run publishes a valid feed per game and records success
# - Does nothing while the days shown are not loaded
# - Cadences: live every 30 seconds, other statuses hourly, final at its final time and 2, 4 and 6 hours after a failure
# - Never builds a final game without a final time or after a success
# - Fetches standings and league injuries once per run and a team schedule once per run, and nothing when no game is due
# - A failed build keeps the last valid feed and records the reason, without blocking the other games
# - A failed standings fetch keeps every feed and uses up a final attempt
# - An invalid feed is not written and keeps the last valid one
# - Deletes the feeds of games that leave the days shown and feeds left from before a start
# - Republishes with no source call when highlights or stars change, and not when unchanged
#
# What is covered:
# - Pure logic: happy path, edge cases, error case
# - Job: successful publication, failed run keeps the last valid feed
#
# Adapters are fakes passed to the job and times are passed to run(), so no test
# uses the real clock. Every test runs in an empty respx mock: a real request fails.
#
# Run with: cd api && .venv/bin/python -m pytest tests/jobs/test_game_detail.py
#
# SEE: api/app/jobs/game_detail.py

import datetime as dt
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx
from pydantic import HttpUrl

from app.feeds.game_detail import GameDetailFeed, Injury, LastGame
from app.feeds.games import GameStatus, Highlight, LineScore, Score, Star, Stars, Team
from app.jobs.game_detail import (
    JOB,
    DetailBuildError,
    GameDetailJob,
    build_game_detail_feed,
)
from app.settings import Settings
from app.sources.game_detail import GameDetailSections
from app.sources.http import SourceError, create_client
from app.sources.league_injuries import LeagueInjuries
from app.sources.scoreboard import ScoreboardGame
from app.sources.standings import LeagueStandings
from app.sources.team_schedule import TeamSchedule
from app.storage.feeds import publish_game_detail, read_game_detail
from app.storage.state import StateStore

NOON = dt.datetime(2026, 10, 5, 16, 0, tzinfo=dt.UTC)
START = NOON - dt.timedelta(hours=3)
PHOTO = HttpUrl("https://example.com/p.png")
SEARCH_URL = "https://example.com/search?q=game"

RECORD = {"wins": 3, "losses": 2}
STANDING = {
    "conference": "east",
    "conference_rank": 2,
    "record": RECORD,
    "home_record": RECORD,
    "away_record": RECORD,
    "last_ten": RECORD,
}
STATS_ROW = {
    "field_goal_pct": 0.5,
    "three_point_pct": 0.4,
    "free_throw_pct": 0.8,
    "rebounds": 40,
    "assists": 20,
    "turnovers": 10,
    "steals": 5,
    "blocks": 4,
}
TEAM_STATS = {
    "away": STATS_ROW,
    "home": STATS_ROW,
    "leaders": {
        "field_goal_pct": None,
        "three_point_pct": None,
        "free_throw_pct": None,
        "rebounds": None,
        "assists": None,
        "turnovers": None,
        "steals": None,
        "blocks": None,
    },
}
VENUE = {"name": "Garden", "city": "New York"}


def star(code: str) -> Star:
    return Star(
        player_id=f"s{code}",
        first_name="A",
        last_name="B",
        team_code=code,
        photo_url=PHOTO,
        short_name="A. B",
    )


STARS = Stars(away=star("BOS"), home=star("NYK"))
HIGHLIGHT = Highlight(
    title="T",
    channel="C",
    thumbnail_url=HttpUrl("https://example.com/t.png"),
    embed_url=HttpUrl("https://example.com/e"),
)


def team(code: str) -> Team:
    return Team(code=code, name=code.title(), city=code.title())


def game(
    game_id: str,
    status: GameStatus,
    score: Score | None = None,
) -> ScoreboardGame:
    data: dict[str, Any] = {
        "id": game_id,
        "away": team("BOS"),
        "home": team("NYK"),
        "status": status,
        "start_time": START,
        "venue": "Garden",
    }
    if status is GameStatus.LIVE:
        data.update(period=2, clock="5:00")
    if status in (GameStatus.LIVE, GameStatus.FINAL):
        data["line_score"] = LineScore(away=[20, 20], home=[18, 20])
        data["score"] = score or Score(away=40, home=38)
    return ScoreboardGame.model_validate(data)


def sections(
    status: GameStatus = GameStatus.SCHEDULED,
    series: dict[str, Any] | None = None,
) -> GameDetailSections:
    data: dict[str, Any] = {"venue": VENUE, "season_series": series}
    if status is GameStatus.LIVE:
        data["team_stats"] = TEAM_STATS
    return GameDetailSections.model_validate(data)


def standings(*codes: str) -> LeagueStandings:
    return LeagueStandings.model_validate(
        {"teams": {code: STANDING for code in codes or ("BOS", "NYK")}}
    )


def injuries(teams: dict[str, list[Injury]] | None = None) -> LeagueInjuries:
    return LeagueInjuries(teams=teams or {})


def schedule(arenas: dict[str, str] | None = None) -> TeamSchedule:
    last = LastGame(
        date=dt.date(2026, 10, 1),
        opponent="MIA",
        is_home=True,
        result="win",  # type: ignore[arg-type]
        team_score=100,
        opponent_score=90,
    )
    return TeamSchedule(last_games=[last], arenas=arenas or {})


def series(*game_ids: str) -> dict[str, Any]:
    return {
        "total_games": len(game_ids),
        "away_wins": 1,
        "home_wins": 0,
        "leader": "BOS",
        "games": [
            {
                "game_id": game_id,
                "date": dt.date(2026, 1, 1),
                "away": "BOS",
                "home": "NYK",
                "is_current": False,
                "score": {"away": 100, "home": 90},
                "winner": "BOS",
            }
            for game_id in game_ids
        ],
    }


def build(
    scoreboard_game: ScoreboardGame,
    detail: GameDetailSections | None = None,
    *,
    league_standings: LeagueStandings | None = None,
    league_injuries: LeagueInjuries | None = None,
    away_schedule: TeamSchedule | None = None,
    home_schedule: TeamSchedule | None = None,
    highlights: Any = None,
) -> GameDetailFeed:
    return build_game_detail_feed(
        scoreboard_game,
        detail or sections(scoreboard_game.status),
        league_standings or standings(),
        league_injuries or injuries(),
        away_schedule or schedule(),
        home_schedule or schedule(),
        stars=lambda _: STARS,
        highlights=highlights or (lambda _: []),
        highlights_search_url=lambda _: SEARCH_URL,
    )


# Group 1: the builder


def test_builds_a_scheduled_game_with_records_standings_injuries_and_last_games() -> (
    None
):
    out = Injury(display_name="A B", status="out")  # type: ignore[arg-type]

    feed = build(
        game("1", GameStatus.SCHEDULED), league_injuries=injuries({"BOS": [out]})
    )

    assert feed.away.record.wins == 3
    assert feed.home.code == "NYK"
    assert feed.standings is not None and feed.standings.away.conference_rank == 2
    assert feed.injuries is not None and feed.injuries.away == [out]
    assert feed.last_games is not None and len(feed.last_games.home) == 1
    assert feed.venue.name == "Garden"
    assert feed.stars == STARS
    assert str(feed.highlights_search_url) == SEARCH_URL
    assert feed.winner is None


def test_builds_a_final_game_with_its_winner_box_score_and_season_series() -> None:
    feed = build(
        game("1", GameStatus.FINAL),
        sections(GameStatus.FINAL, series("1")),
        away_schedule=schedule({"1": "Garden"}),
    )

    assert feed.winner == "BOS"
    assert feed.season_series is not None
    assert feed.season_series.games[0].arena == "Garden"
    assert feed.win_probability_periods is None


def test_builds_a_final_game_with_its_win_probability_periods() -> None:
    found = GameDetailSections.model_validate(
        {
            "venue": VENUE,
            "win_probability": [{"elapsed_seconds": 5, "home_win_probability": 0.5}],
            "win_probability_periods": {
                "periods": [
                    {"number": 1, "start_elapsed_seconds": 0},
                    {"number": 2, "start_elapsed_seconds": 10},
                ],
                "end_elapsed_seconds": 20,
            },
        }
    )

    feed = build(game("1", GameStatus.FINAL), found, away_schedule=schedule())

    assert feed.win_probability_periods is not None
    assert feed.win_probability_periods.end_elapsed_seconds == 20
    assert [p.start_elapsed_seconds for p in feed.win_probability_periods.periods] == [
        0,
        10,
    ]


def test_takes_each_series_arena_from_the_team_schedules_and_this_games_venue() -> None:
    feed = build(
        game("9", GameStatus.SCHEDULED),
        sections(series=series("1", "2", "9")),
        away_schedule=schedule({"1": "Away Arena"}),
        home_schedule=schedule({"2": "Home Arena"}),
    )

    assert feed.season_series is not None
    assert [g.arena for g in feed.season_series.games] == [
        "Away Arena",
        "Home Arena",
        "Garden",
    ]


def test_passes_the_series_leader_winners_and_current_game_into_the_feed() -> None:
    found = series("1", "9")
    found["games"][1].update(is_current=True, score=None, winner=None)

    feed = build(
        game("9", GameStatus.SCHEDULED),
        sections(series=found),
        away_schedule=schedule({"1": "Away Arena"}),
    )

    assert feed.season_series is not None
    assert feed.season_series.leader == found["leader"]
    completed, current = feed.season_series.games
    assert (completed.is_current, completed.winner) == (False, "BOS")
    assert current.is_current is True
    assert current.score is None
    assert current.winner is None
    assert current.arena == "Garden"


def test_lists_no_injuries_for_a_team_absent_from_the_league_injuries() -> None:
    feed = build(game("1", GameStatus.SCHEDULED))

    assert feed.injuries is not None
    assert feed.injuries.away == [] and feed.injuries.home == []


def test_puts_null_highlights_when_the_game_has_none() -> None:
    none = build(game("1", GameStatus.SCHEDULED))
    some = build(game("1", GameStatus.SCHEDULED), highlights=lambda _: [HIGHLIGHT])

    assert none.highlights is None
    assert some.highlights == [HIGHLIGHT]


def test_rejects_a_game_whose_team_has_no_standing() -> None:
    with pytest.raises(DetailBuildError, match="team NYK has no standing"):
        build(game("1", GameStatus.SCHEDULED), league_standings=standings("BOS"))


def test_rejects_a_series_game_with_no_arena() -> None:
    with pytest.raises(DetailBuildError, match="series game 1 has no arena"):
        build(game("9", GameStatus.SCHEDULED), sections(series=series("1")))


def test_rejects_a_live_game_without_team_stats() -> None:
    detail = GameDetailSections.model_validate({"venue": VENUE})

    with pytest.raises(DetailBuildError, match="invalid feed: 1 errors, first at"):
        build(game("1", GameStatus.LIVE), detail)


# Group 2: the job


class FakeSources:
    def __init__(self) -> None:
        self.statuses: dict[str, GameStatus] = {}
        self.section_errors: dict[str, SourceError] = {}
        self.schedule_errors: dict[str, SourceError] = {}
        self.standings_error: SourceError | None = None
        self.section_calls: list[str] = []
        self.standings_calls = 0
        self.injuries_calls = 0
        self.schedule_calls: list[str] = []

    async def fetch_sections(
        self, client: httpx.AsyncClient, game_id: str, settings: Settings
    ) -> GameDetailSections:
        self.section_calls.append(game_id)
        if game_id in self.section_errors:
            raise self.section_errors[game_id]
        return sections(self.statuses.get(game_id, GameStatus.SCHEDULED))

    async def fetch_standings(
        self, client: httpx.AsyncClient, settings: Settings
    ) -> LeagueStandings:
        self.standings_calls += 1
        if self.standings_error is not None:
            raise self.standings_error
        return standings()

    async def fetch_injuries(
        self, client: httpx.AsyncClient, settings: Settings
    ) -> LeagueInjuries:
        self.injuries_calls += 1
        return injuries()

    async def fetch_team_schedule(
        self, client: httpx.AsyncClient, code: str, settings: Settings
    ) -> TeamSchedule:
        self.schedule_calls.append(code)
        if code in self.schedule_errors:
            raise self.schedule_errors[code]
        return schedule()


@pytest.fixture(autouse=True)
def no_network() -> Iterator[None]:
    with respx.mock:
        yield


@pytest.fixture
def sources() -> FakeSources:
    return FakeSources()


@pytest.fixture
def store(tmp_path: Path) -> StateStore:
    state = StateStore(tmp_path)
    state.migrate()
    return state


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(_env_file=None, data_dir=tmp_path)  # type: ignore[call-arg]


class Shown:
    """The games provider: a list the test changes, or None before the window loads."""

    def __init__(self, games: list[ScoreboardGame] | None) -> None:
        self.games = games

    def __call__(self) -> list[ScoreboardGame] | None:
        return self.games


def make_job(
    settings: Settings,
    store: StateStore,
    sources: FakeSources,
    shown: Shown,
    **extra: Any,
) -> GameDetailJob:
    for live in shown.games or []:
        sources.statuses[live.id] = live.status
    return GameDetailJob(
        settings,
        store,
        create_client(),
        games=shown,
        fetch_sections=sources.fetch_sections,
        fetch_standings=sources.fetch_standings,
        fetch_injuries=sources.fetch_injuries,
        fetch_team_schedule=sources.fetch_team_schedule,
        stars=extra.pop("stars", lambda _: STARS),
        highlights_search_url=extra.pop("highlights_search_url", lambda _: SEARCH_URL),
        **extra,
    )


def reason(store: StateStore) -> str | None:
    return store.job_states()[0].last_failure_reason


def read(settings: Settings, game_id: str) -> GameDetailFeed:
    body = read_game_detail(settings.data_dir, game_id)
    assert body is not None
    return GameDetailFeed.model_validate_json(body)


@pytest.mark.anyio
async def test_a_successful_run_publishes_a_valid_feed_per_game_and_records_success(
    settings: Settings, store: StateStore, sources: FakeSources
) -> None:
    shown = Shown([game("1", GameStatus.SCHEDULED), game("2", GameStatus.LIVE)])
    job = make_job(settings, store, sources, shown)

    await job.run(NOON)

    assert read(settings, "1").status is GameStatus.SCHEDULED
    assert read(settings, "2").status is GameStatus.LIVE
    state = store.job_states()[0]
    assert state.name == JOB and state.last_success == NOON


@pytest.mark.anyio
async def test_does_nothing_while_the_days_shown_are_not_loaded(
    settings: Settings, store: StateStore, sources: FakeSources
) -> None:
    publish_game_detail(settings.data_dir, build(game("7", GameStatus.SCHEDULED)))
    job = make_job(settings, store, sources, Shown(None))

    await job.run(NOON)

    assert sources.standings_calls == 0 and sources.section_calls == []
    assert read_game_detail(settings.data_dir, "7") is not None
    assert store.job_states() == []


@pytest.mark.anyio
async def test_rebuilds_a_live_game_every_thirty_seconds(
    settings: Settings, store: StateStore, sources: FakeSources
) -> None:
    job = make_job(settings, store, sources, Shown([game("1", GameStatus.LIVE)]))

    await job.run(NOON)
    await job.run(NOON + dt.timedelta(seconds=29))
    assert sources.section_calls == ["1"]
    await job.run(NOON + dt.timedelta(seconds=30))

    assert sources.section_calls == ["1", "1"]


@pytest.mark.anyio
@pytest.mark.parametrize(
    "status",
    [
        GameStatus.SCHEDULED,
        GameStatus.DELAYED,
        GameStatus.POSTPONED,
        GameStatus.CANCELED,
    ],
)
async def test_rebuilds_scheduled_delayed_postponed_and_canceled_games_every_hour(
    settings: Settings, store: StateStore, sources: FakeSources, status: GameStatus
) -> None:
    job = make_job(settings, store, sources, Shown([game("1", status)]))

    await job.run(NOON)
    await job.run(NOON + dt.timedelta(minutes=59))
    assert sources.section_calls == ["1"]
    await job.run(NOON + dt.timedelta(minutes=60))

    assert sources.section_calls == ["1", "1"]


@pytest.mark.anyio
async def test_builds_a_final_game_at_its_final_time_and_never_again_after_a_success(
    settings: Settings, store: StateStore, sources: FakeSources
) -> None:
    store.set_final_time("1", dt.date(2026, 10, 5), NOON)
    job = make_job(settings, store, sources, Shown([game("1", GameStatus.FINAL)]))

    await job.run(NOON - dt.timedelta(seconds=1))
    assert sources.section_calls == []
    await job.run(NOON)
    await job.run(NOON + dt.timedelta(hours=7))

    assert sources.section_calls == ["1"]
    assert read(settings, "1").winner == "BOS"


@pytest.mark.anyio
async def test_retries_a_failed_final_game_only_2_4_and_6_hours_after_its_final_time(
    settings: Settings, store: StateStore, sources: FakeSources
) -> None:
    store.set_final_time("1", dt.date(2026, 10, 5), NOON)
    sources.section_errors["1"] = SourceError("game_detail", "down")
    job = make_job(settings, store, sources, Shown([game("1", GameStatus.FINAL)]))

    for hours in (0, 2, 4, 6):
        await job.run(NOON + dt.timedelta(hours=hours) - dt.timedelta(minutes=1))
        calls = len(sources.section_calls)
        await job.run(NOON + dt.timedelta(hours=hours))
        assert len(sources.section_calls) == calls + 1
    await job.run(NOON + dt.timedelta(hours=30))

    assert len(sources.section_calls) == 4


@pytest.mark.anyio
async def test_does_not_build_a_final_game_without_a_stored_final_time(
    settings: Settings, store: StateStore, sources: FakeSources
) -> None:
    job = make_job(settings, store, sources, Shown([game("1", GameStatus.FINAL)]))

    await job.run(NOON)

    assert sources.section_calls == [] and sources.standings_calls == 0


@pytest.mark.anyio
async def test_fetches_standings_and_league_injuries_once_per_run_for_every_due_game(
    settings: Settings, store: StateStore, sources: FakeSources
) -> None:
    shown = Shown([game(i, GameStatus.SCHEDULED) for i in ("1", "2", "3")])
    job = make_job(settings, store, sources, shown)

    await job.run(NOON)

    assert sources.standings_calls == 1 and sources.injuries_calls == 1
    assert sources.section_calls == ["1", "2", "3"]


@pytest.mark.anyio
async def test_fetches_no_league_data_when_no_game_is_due(
    settings: Settings, store: StateStore, sources: FakeSources
) -> None:
    job = make_job(settings, store, sources, Shown([game("1", GameStatus.SCHEDULED)]))
    await job.run(NOON)

    await job.run(NOON + dt.timedelta(minutes=1))

    assert sources.standings_calls == 1 and sources.injuries_calls == 1


@pytest.mark.anyio
async def test_fetches_each_team_schedule_once_per_run(
    settings: Settings, store: StateStore, sources: FakeSources
) -> None:
    shown = Shown([game("1", GameStatus.SCHEDULED), game("2", GameStatus.LIVE)])
    job = make_job(settings, store, sources, shown)

    await job.run(NOON)

    assert sorted(sources.schedule_calls) == ["BOS", "NYK"]


@pytest.mark.anyio
async def test_a_failed_build_keeps_the_last_valid_feed_and_records_the_reason(
    settings: Settings, store: StateStore, sources: FakeSources
) -> None:
    job = make_job(settings, store, sources, Shown([game("1", GameStatus.LIVE)]))
    await job.run(NOON)
    before = read_game_detail(settings.data_dir, "1")
    sources.section_errors["1"] = SourceError("game_detail", "down")

    await job.run(NOON + dt.timedelta(seconds=30))

    assert read_game_detail(settings.data_dir, "1") == before
    failure = reason(store)
    assert failure is not None and failure.startswith("game 1:")


@pytest.mark.anyio
async def test_a_failed_game_never_blocks_the_other_games_of_the_run(
    settings: Settings, store: StateStore, sources: FakeSources
) -> None:
    sources.section_errors["1"] = SourceError("game_detail", "down")
    shown = Shown([game("1", GameStatus.SCHEDULED), game("2", GameStatus.SCHEDULED)])
    job = make_job(settings, store, sources, shown)

    await job.run(NOON)

    assert read_game_detail(settings.data_dir, "1") is None
    assert read(settings, "2").id == "2"
    state = store.job_states()[0]
    assert state.last_success == NOON and state.last_failure_reason is not None


@pytest.mark.anyio
async def test_a_failed_standings_fetch_keeps_every_feed_and_uses_up_a_final_attempt(
    settings: Settings, store: StateStore, sources: FakeSources
) -> None:
    store.set_final_time("2", dt.date(2026, 10, 5), NOON)
    shown = Shown([game("1", GameStatus.SCHEDULED), game("2", GameStatus.FINAL)])
    job = make_job(settings, store, sources, shown)
    sources.standings_error = SourceError("standings", "down")

    await job.run(NOON)
    assert read_game_detail(settings.data_dir, "1") is None
    sources.standings_error = None
    await job.run(NOON + dt.timedelta(hours=1))
    assert sources.section_calls == ["1"]
    await job.run(NOON + dt.timedelta(hours=2))

    assert sources.section_calls == ["1", "1", "2"]
    assert read(settings, "2").winner == "BOS"


@pytest.mark.anyio
async def test_an_invalid_feed_is_not_written_and_keeps_the_last_valid_one(
    settings: Settings, store: StateStore, sources: FakeSources
) -> None:
    live = game("1", GameStatus.LIVE)
    job = make_job(settings, store, sources, Shown([live]))
    await job.run(NOON)
    before = read_game_detail(settings.data_dir, "1")
    sources.statuses["1"] = GameStatus.SCHEDULED  # sections without team stats

    await job.run(NOON + dt.timedelta(seconds=30))

    assert read_game_detail(settings.data_dir, "1") == before
    failure = reason(store)
    assert failure is not None and "invalid feed" in failure


@pytest.mark.anyio
async def test_deletes_the_feeds_of_games_that_leave_the_days_shown(
    settings: Settings, store: StateStore, sources: FakeSources
) -> None:
    shown = Shown([game("1", GameStatus.SCHEDULED), game("2", GameStatus.SCHEDULED)])
    job = make_job(settings, store, sources, shown)
    await job.run(NOON)

    shown.games = [game("2", GameStatus.SCHEDULED)]
    await job.run(NOON + dt.timedelta(minutes=1))

    assert read_game_detail(settings.data_dir, "1") is None
    assert read_game_detail(settings.data_dir, "2") is not None


@pytest.mark.anyio
async def test_deletes_feeds_left_on_disk_from_before_a_start(
    settings: Settings, store: StateStore, sources: FakeSources
) -> None:
    publish_game_detail(settings.data_dir, build(game("old", GameStatus.SCHEDULED)))
    job = make_job(settings, store, sources, Shown([]))

    await job.run(NOON)

    assert read_game_detail(settings.data_dir, "old") is None


@pytest.mark.anyio
async def test_republishes_with_no_source_call_when_highlights_or_stars_change(
    settings: Settings, store: StateStore, sources: FakeSources
) -> None:
    current: dict[str, Any] = {"highlights": [], "stars": None}
    job = make_job(
        settings,
        store,
        sources,
        Shown([game("1", GameStatus.SCHEDULED)]),
        highlights=lambda _: current["highlights"],
        stars=lambda _: current["stars"],
    )
    await job.run(NOON)
    assert read(settings, "1").highlights is None
    calls = (sources.standings_calls, list(sources.section_calls))

    current["highlights"] = [HIGHLIGHT]
    await job.run(NOON + dt.timedelta(minutes=1))
    assert read(settings, "1").highlights == [HIGHLIGHT]
    current["stars"] = STARS
    await job.run(NOON + dt.timedelta(minutes=2))

    assert read(settings, "1").stars == STARS
    assert (sources.standings_calls, sources.section_calls) == calls


@pytest.mark.anyio
async def test_does_not_republish_when_highlights_and_stars_are_unchanged(
    settings: Settings, store: StateStore, sources: FakeSources
) -> None:
    job = make_job(settings, store, sources, Shown([game("1", GameStatus.SCHEDULED)]))
    await job.run(NOON)
    path = settings.data_dir / "feeds" / "games" / "1.json"
    before = path.stat().st_mtime_ns

    await job.run(NOON + dt.timedelta(minutes=1))

    assert path.stat().st_mtime_ns == before
    assert store.job_states()[0].last_success == NOON
