# api/tests/jobs/test_game_detail_feed.py
#
# Tests for the game detail feed kind and its feed builder.
#
# Tested:
# - Builds a scheduled game with records, standings, injuries and last games
# - Builds a final game with its winner, box score and season series
# - Carries the win probability periods of the sections into the feed, or null
# - Carries the win probability leader of the sections into the feed and fails the build when it does not match the latest point
# - Takes each series arena from the team schedules and this game's venue
# - Passes the series leader, each game's winner and the current game into the feed
# - Lists no injuries for a team absent from the league injuries
# - Sets each injury's playerId from the recorded league injuries, null when the source has no athlete id
# - Puts null highlights when the game has none
# - Rejects a game whose team has no standing, a series game with no arena and a live game without team stats
# - The pre-game expiry is 12 hours with tip-off more than 48 hours away, 6 hours from 48 to 12 hours, 3 hours under 12 hours and once tip-off has passed
# - A pre-game detail is fresh until its expiry and stale at it, in each bucket
# - The final slot is the latest attempt time passed, and none before the final time
# - No source call happens without a detail request for a pre-game game
# - A pre-game detail is built on request and served from storage until it expires
# - A live game viewed by two clients causes one detail source request per interval
# - A stale live detail waits for the rebuild, so the score is never older than 30 seconds
# - A final game's detail is built once with the ADR 0010 attempts and never again
# - A final game is never built after the fourth failed attempt
# - A game turning final shares one summary request with the games job
# - A requested final game never starts a build
# - Stars, highlights and the search URL are added when served and not stored
# - A game id outside the days shown answers unknown with no source request
# - A request before the days shown load answers unavailable
# - The cleanup deletes the stored detail of a game that left the days shown with no source request, and runs only when the games shown change
# - A failed build keeps the stored feed and is listed as failed
# - After a day change whose new-day fetch fails, loaded games keep being served with their additions and no stored feed is deleted, an id not loaded answers unavailable, and once the day loads an id outside the days shown answers unknown
# - A guest game builds with the box score and team stats of both sides, a record, standing, injuries and last games only for the league side, no season series and a null win probability; the guest side's schedule is never fetched and the served stars have none for the guest
#
# What is covered:
# - Pure logic: happy path, edge cases, error case
# - Kind: wired to a real games job and feed cache, with counted source requests
#
# Adapters are fakes passed to the games job and the kind, the clock is shared
# by the client and the cache, so no test uses the real clock. Every test runs in
# an empty respx mock: a real request fails.
#
# Run with: cd api && .venv/bin/python -m pytest tests/jobs/test_game_detail_feed.py
#
# SEE: api/app/jobs/game_detail_feed.py

import asyncio
import datetime as dt
import json
from collections.abc import Iterator
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import httpx
import pytest
import respx
from pydantic import HttpUrl

from app.feeds.game_detail import GameDetailFeed, Injury, LastGame
from app.feeds.games import (
    GameStatus,
    GameTeam,
    Highlight,
    Leader,
    Leaders,
    LineScore,
    Score,
    Star,
    Stars,
    TeamStats,
)
from app.jobs.game_detail_feed import (
    KIND,
    DetailBuildError,
    GameDetailFeeds,
    build_game_detail_feed,
    final_slot,
    pre_game_expiry,
)
from app.jobs.games import STATS_ATTEMPT_DELAYS, GamesJob
from app.jobs.on_demand import FeedCache, FeedUnavailableError, UnknownFeedError
from app.settings import Settings
from app.sources.game_detail import GameDetail, GameDetailSections
from app.sources.http import (
    Freshness,
    SourceClient,
    SourceError,
    create_client,
    get_json,
)
from app.sources.league_injuries import (
    InjuryReport,
    LeagueInjuries,
    fetch_league_injuries,
)
from app.sources.scoreboard import ScoreboardGame
from app.sources.standings import LeagueStandings
from app.sources.team_schedule import TeamSchedule
from app.storage.feeds import publish_by_id, read_by_id
from app.storage.state import StateStore

NOON = dt.datetime(2026, 10, 5, 16, 0, tzinfo=dt.UTC)
START = NOON - dt.timedelta(hours=3)
SOURCE_FIXTURES = Path(__file__).parent.parent / "sources" / "fixtures"
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
TEAM_STATS: dict[str, Any] = {
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


def team(code: str) -> GameTeam:
    return GameTeam(code=code, name=code.title(), city=code.title())


def game(
    game_id: str,
    status: GameStatus,
    score: Score | None = None,
    start: dt.datetime = START,
) -> ScoreboardGame:
    data: dict[str, Any] = {
        "id": game_id,
        "away": team("BOS"),
        "home": team("NYK"),
        "status": status,
        "start_time": start,
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
    return LeagueInjuries(
        teams={
            code: [InjuryReport(injury=injury) for injury in reports]
            for code, reports in (teams or {}).items()
        }
    )


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


GUEST = GameTeam(code="HCM", name="Mariners", city="Harbor City", guest=True)
GUEST_STARS = Stars(away=None, home=star("NYK"))
BOX_LINE = {
    "points": 20,
    "field_goals_made": 8,
    "field_goals_attempted": 15,
    "three_points_made": 2,
    "three_points_attempted": 6,
    "free_throws_made": 2,
    "free_throws_attempted": 3,
    "offensive_rebounds": 1,
    "defensive_rebounds": 5,
    "rebounds": 6,
    "assists": 4,
    "turnovers": 2,
    "steals": 1,
    "blocks": 0,
    "fouls": 3,
}


def box_team(photo: str | None) -> dict[str, Any]:
    player = {
        **BOX_LINE,
        "player_id": "p1",
        "display_name": "A B",
        "starter": True,
        "minutes": "30:00",
        "plus_minus": 2,
        "photo_url": photo,
    }
    totals = {
        **BOX_LINE,
        "field_goal_pct": 0.5,
        "three_point_pct": 0.3,
        "free_throw_pct": 0.7,
    }
    return {"players": [player], "totals": totals}


def guest_game(
    game_id: str, status: GameStatus, score: Score | None = None
) -> ScoreboardGame:
    """A game whose away side is the invented Harbor City Mariners."""
    return game(game_id, status, score).model_copy(update={"away": GUEST})


def guest_sections(
    status: GameStatus = GameStatus.FINAL, **more: Any
) -> GameDetailSections:
    data: dict[str, Any] = {"venue": VENUE, **more}
    if status is GameStatus.FINAL:
        data["team_stats"] = {
            **TEAM_STATS,
            "leaders": {**TEAM_STATS["leaders"], "rebounds": "HCM"},
        }
        data["box_score"] = {
            "away": box_team(None),
            "home": box_team("https://example.com/p.png"),
        }
    return GameDetailSections.model_validate(data)


def build_guest(
    scoreboard_game: ScoreboardGame,
    detail: GameDetailSections,
    *,
    league_injuries: LeagueInjuries | None = None,
) -> GameDetailFeed:
    return build_game_detail_feed(
        scoreboard_game,
        detail,
        standings("NYK"),
        league_injuries or injuries(),
        None,
        schedule(),
        stars=lambda _: GUEST_STARS,
        highlights=lambda _: [],
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

    assert feed.away.record is not None and feed.away.record.wins == 3
    assert feed.home.code == "NYK"
    assert feed.standings is not None
    assert feed.standings.away is not None
    assert feed.standings.away.conference_rank == 2
    assert feed.injuries is not None and feed.injuries.away == [out]
    assert feed.last_games is not None
    assert feed.last_games.home is not None and len(feed.last_games.home) == 1
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


def leader_sections(team_code: str) -> GameDetailSections:
    return GameDetailSections.model_validate(
        {
            "venue": VENUE,
            "win_probability": [{"elapsed_seconds": 5, "home_win_probability": 0.3}],
            "win_probability_leader": {"team_code": team_code, "win_probability": 0.7},
            "win_probability_periods": {
                "periods": [{"number": 1, "start_elapsed_seconds": 0}],
                "end_elapsed_seconds": 20,
            },
        }
    )


def test_builds_a_game_with_its_win_probability_leader() -> None:
    feed = build(
        game("1", GameStatus.FINAL),
        leader_sections("BOS"),
        away_schedule=schedule(),
    )

    assert feed.win_probability_leader is not None
    assert feed.win_probability_leader.team_code == "BOS"
    assert feed.win_probability_leader.win_probability == 0.7


def test_fails_the_build_when_the_win_probability_leader_does_not_match() -> None:
    with pytest.raises(DetailBuildError):
        build(
            game("1", GameStatus.FINAL),
            leader_sections("NYK"),
            away_schedule=schedule(),
        )


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


async def recorded_injuries(clear_links: bool = False) -> LeagueInjuries:
    payload = json.loads(
        (SOURCE_FIXTURES / "league_injuries" / "injuries-detail.json").read_text(
            encoding="utf-8"
        )
    )
    if clear_links:
        entry = next(e for e in payload["injuries"] if e["id"] == "25")
        for report in entry["injuries"]:
            report["athlete"]["links"] = []
    respx.get("https://example.com/injuries").respond(json=payload)
    settings = Settings(
        _env_file=None, league_injuries_url="https://example.com/injuries"
    )  # type: ignore[call-arg]
    with TemporaryDirectory() as directory:
        store = StateStore(Path(directory))
        store.migrate()
        async with create_client(store) as client:
            return await fetch_league_injuries(client, settings)


@pytest.mark.anyio
async def test_sets_the_injury_player_id_from_the_recorded_league_injuries() -> None:
    league = await recorded_injuries()

    feed = build(
        game("1", GameStatus.SCHEDULED),
        league_injuries=LeagueInjuries(teams={"BOS": league.teams["OKC"]}),
    )

    assert feed.injuries is not None
    assert feed.injuries.away is not None
    assert feed.injuries.away[0].player_id == "5061603"
    assert feed.injuries.away[0].display_name == "Thomas Sorber"
    dumped = feed.model_dump(mode="json")
    assert dumped["injuries"]["away"][0]["playerId"] == "5061603"


@pytest.mark.anyio
async def test_puts_a_null_injury_player_id_when_the_source_has_none() -> None:
    league = await recorded_injuries(clear_links=True)

    feed = build(
        game("1", GameStatus.SCHEDULED),
        league_injuries=LeagueInjuries(teams={"BOS": league.teams["OKC"]}),
    )

    assert feed.injuries is not None
    assert feed.injuries.away
    assert all(i.player_id is None for i in feed.injuries.away)
    dumped = feed.model_dump(mode="json")
    assert all(i["playerId"] is None for i in dumped["injuries"]["away"])


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


# Group 2: the pure helpers

HOUR = dt.timedelta(hours=1)
SECOND = dt.timedelta(seconds=1)


def test_pre_game_expiry_is_12_hours_with_tip_off_more_than_48_hours_away() -> None:
    assert pre_game_expiry(NOON + 48 * HOUR + SECOND, NOON) == 12 * HOUR


def test_pre_game_expiry_is_6_hours_at_48_hours_and_at_12_hours_and_between() -> None:
    for away in (48 * HOUR, 30 * HOUR, 12 * HOUR):
        assert pre_game_expiry(NOON + away, NOON) == 6 * HOUR


def test_pre_game_expiry_is_3_hours_under_12_hours_and_once_tip_off_has_passed() -> (
    None
):
    for away in (12 * HOUR - SECOND, dt.timedelta(0), -2 * HOUR):
        assert pre_game_expiry(NOON + away, NOON) == 3 * HOUR


def test_final_slot_is_the_latest_attempt_time_passed() -> None:
    final = NOON

    assert final_slot(final, final - SECOND) is None
    assert final_slot(final, final) == final
    assert final_slot(final, final + 2 * HOUR - SECOND) == final
    assert final_slot(final, final + 2 * HOUR) == final + 2 * HOUR
    assert final_slot(final, final + 6 * HOUR) == final + 6 * HOUR
    assert final_slot(final, final + 30 * HOUR) == final + 6 * HOUR
    assert STATS_ATTEMPT_DELAYS[-1] == 6 * HOUR


# Group 3: the kind wired to a real games job and feed cache

BASE = "https://example.com/detail/"
TODAY = dt.date(2026, 10, 5)
AFTER_MIDNIGHT = dt.datetime(2026, 10, 6, 4, 10, tzinfo=dt.UTC)


@pytest.fixture(autouse=True)
def no_network() -> Iterator[None]:
    with respx.mock:
        yield


def games_detail() -> GameDetail:
    leader = {
        code: Leader(
            player_id=f"l{code}",
            display_name="A B",
            team_code=code,
            photo_url=PHOTO,
            points=20,
            rebounds=5,
            assists=5,
        )
        for code in ("BOS", "NYK")
    }
    stats = TeamStats(
        field_goal_pct=0.5, three_point_pct=0.4, rebounds=40, assists=20, turnovers=10
    )
    return GameDetail.model_validate(
        {
            "leaders": Leaders(away=leader["BOS"], home=leader["NYK"]),
            "team_stats": {"away": stats, "home": stats},
        }
    )


class Harness:
    """A games job, a feed cache and the detail kind over one client and one clock.

    Both the games job and the kind read each game's summary through the source
    cache from one counted respx route, so route calls are real source requests.
    """

    def __init__(self, path: Path, *, hook: bool = True) -> None:
        self.clock = [NOON]
        self.store = StateStore(path)
        self.store.migrate()
        self.settings = Settings(_env_file=None, data_dir=path)  # type: ignore[call-arg]
        self.client = create_client(self.store, clock=lambda: self.clock[0])
        self.games: list[ScoreboardGame] = []
        self.other_days: dict[dt.date, list[ScoreboardGame]] = {}
        self.failing_days: set[dt.date] = set()
        self.states: dict[str, str] = {}
        self.requests: list[str] = []
        self.sections_fresh: list[Freshness] = []
        self.fail_standings = False
        self.standings_calls = 0
        self.schedule_calls: list[str] = []
        self.stars: Stars | None = STARS
        self.highlights: list[Highlight] = []
        self.search_url: str | None = SEARCH_URL
        respx.get(url__startswith=BASE).mock(side_effect=self.answer)
        self.cache = FeedCache(path, self.store, clock=lambda: self.clock[0])
        self.job = GamesJob(
            self.settings,
            self.store,
            self.client,
            fetch_games=self.fetch_games,
            fetch_game_detail=self.fetch_game_detail,
            stars=lambda _: self.stars,
            highlights=lambda _: self.highlights,
            highlights_search_url=lambda _: self.search_url,
            after_run=lambda: self.feeds.after_games_run() if hook else None,
        )
        self.feeds = GameDetailFeeds(
            self.settings,
            self.store,
            self.client,
            self.cache,
            self.job,
            fetch_sections=self.fetch_sections,
            fetch_standings=self.fetch_standings,
            fetch_injuries=self.fetch_injuries,
            fetch_team_schedule=self.fetch_team_schedule,
            stars=lambda _: self.stars,
            highlights=lambda _: self.highlights,
            highlights_search_url=lambda _: self.search_url,
        )

    def answer(self, request: httpx.Request) -> httpx.Response:
        game_id = request.url.path.rsplit("/", 1)[-1]
        self.requests.append(game_id)
        return httpx.Response(200, json={"state": self.states.get(game_id, "x")})

    def calls(self, game_id: str) -> int:
        return self.requests.count(game_id)

    async def read_state(self, game_id: str, fresh: Freshness) -> str:
        body = await get_json(self.client, BASE + game_id, source="test", fresh=fresh)
        return str(body["state"])  # type: ignore[index]

    async def fetch_games(
        self, client: SourceClient, day: dt.date, settings: Settings
    ) -> list[ScoreboardGame]:
        if day in self.failing_days:
            raise SourceError("scoreboard", "down")
        return list(self.games if day == TODAY else self.other_days.get(day, []))

    async def fetch_game_detail(
        self, client: SourceClient, game_id: str, settings: Settings, fresh: Freshness
    ) -> GameDetail:
        await self.read_state(game_id, fresh)
        return games_detail()

    async def fetch_sections(
        self, client: SourceClient, game_id: str, settings: Settings, fresh: Freshness
    ) -> GameDetailSections:
        self.sections_fresh.append(fresh)
        state = await self.read_state(game_id, fresh)
        every = [*self.games, *(g for day in self.other_days.values() for g in day)]
        status = next(g.status for g in every if g.id == game_id)
        data: dict[str, Any] = {"venue": {"name": state, "city": "New York"}}
        if status is GameStatus.LIVE:
            data["team_stats"] = TEAM_STATS
        return GameDetailSections.model_validate(data)

    async def fetch_standings(
        self, client: SourceClient, settings: Settings
    ) -> LeagueStandings:
        self.standings_calls += 1
        if self.fail_standings:
            raise SourceError("standings", "down")
        return standings()

    async def fetch_injuries(
        self, client: SourceClient, settings: Settings
    ) -> LeagueInjuries:
        return injuries()

    async def fetch_team_schedule(
        self, client: SourceClient, code: str, settings: Settings
    ) -> TeamSchedule:
        self.schedule_calls.append(code)
        return schedule()

    async def settle(self) -> None:
        while self.cache.in_flight:
            await next(iter(self.cache.in_flight.values()))
            await asyncio.sleep(0)
        await asyncio.sleep(0)

    async def run(self, at: dt.datetime) -> None:
        self.clock[0] = at
        await self.job.run(at)
        await self.settle()

    async def serve(self, game_id: str, at: dt.datetime | None = None) -> bytes:
        if at is not None:
            self.clock[0] = at
        body = await self.cache.serve(KIND, game_id)
        await self.settle()
        return body

    def venue(self, body: bytes) -> str:
        return GameDetailFeed.model_validate_json(body).venue.name

    def stored(self, game_id: str) -> GameDetailFeed | None:
        body = read_by_id(self.settings.data_dir, KIND, game_id)
        return None if body is None else GameDetailFeed.model_validate_json(body)

    def last_build(self, game_id: str) -> dt.datetime | None:
        state = self.store.feed_build(KIND, game_id)
        return None if state is None else state.last_build


def make_dir(path: Path) -> Path:
    path.mkdir()
    return path


@pytest.fixture
def harness(tmp_path: Path) -> Harness:
    return Harness(tmp_path)


@pytest.mark.anyio
async def test_no_game_detail_source_call_happens_without_a_detail_request_for_a_pre_game_game(
    harness: Harness, tmp_path: Path
) -> None:
    harness.games = [game("1", GameStatus.SCHEDULED, start=NOON + 5 * HOUR)]

    await harness.run(NOON)
    await harness.run(NOON + 30 * SECOND)
    await harness.run(NOON + HOUR)

    assert harness.calls("1") == 0
    assert not (tmp_path / "feeds" / "games").exists()
    assert harness.store.feed_build_ids(KIND) == set()
    await harness.serve("1")
    assert harness.calls("1") == 1


@pytest.mark.anyio
async def test_a_pre_game_detail_is_built_on_request_and_served_from_storage_until_it_expires(
    harness: Harness,
) -> None:
    harness.games = [game("1", GameStatus.SCHEDULED, start=NOON + 5 * HOUR)]
    await harness.run(NOON)
    first = await harness.serve("1")
    harness.states["1"] = "later"

    fresh = await harness.serve("1", NOON + 3 * HOUR - SECOND)
    assert fresh == first
    assert harness.calls("1") == 1
    stale = await harness.serve("1", NOON + 3 * HOUR)

    assert stale == first
    assert harness.calls("1") == 2
    assert harness.last_build("1") == NOON + 3 * HOUR
    assert harness.venue(await harness.serve("1")) == "later"
    assert harness.calls("1") == 2


@pytest.mark.parametrize(
    ("away_hours", "expiry_hours"), [(60, 12), (48, 6), (30, 6), (12, 6), (5, 3)]
)
@pytest.mark.anyio
async def test_a_pre_game_detail_is_fresh_until_its_expiry_and_stale_at_it(
    harness: Harness, away_hours: int, expiry_hours: int
) -> None:
    harness.games = [game("1", GameStatus.SCHEDULED, start=NOON + away_hours * HOUR)]
    await harness.run(NOON)
    await harness.serve("1")
    feed = harness.stored("1")
    assert feed is not None
    expiry = expiry_hours * HOUR

    assert harness.feeds.is_fresh(feed, NOON, NOON + expiry - SECOND)
    assert not harness.feeds.is_fresh(feed, NOON, NOON + expiry)


@pytest.mark.anyio
async def test_a_live_game_viewed_by_two_clients_causes_one_detail_source_request_per_interval(
    harness: Harness,
) -> None:
    harness.games = [game("1", GameStatus.LIVE)]
    await harness.run(NOON)

    first = await asyncio.gather(harness.serve("1"), harness.serve("1"))
    assert harness.calls("1") == 1

    await harness.run(NOON + 30 * SECOND)
    second = await asyncio.gather(harness.serve("1"), harness.serve("1"))

    assert harness.calls("1") == 2
    assert first[0] == first[1]
    assert second[0] == second[1]


@pytest.mark.anyio
async def test_a_stale_live_detail_waits_for_the_rebuild_so_the_score_is_never_older_than_30_seconds(
    harness: Harness,
) -> None:
    harness.games = [game("1", GameStatus.LIVE)]
    harness.states["1"] = "score-a"
    await harness.run(NOON)
    assert harness.venue(await harness.serve("1")) == "score-a"
    harness.states["1"] = "score-b"
    await harness.run(NOON + 30 * SECOND)

    body = await harness.serve("1")

    assert harness.venue(body) == "score-b"
    assert harness.last_build("1") == NOON + 30 * SECOND


async def turn_final(harness: Harness) -> dt.datetime:
    """Runs a live game, then the run that sees it final; returns its final time."""
    harness.games = [game("1", GameStatus.LIVE)]
    await harness.run(NOON)
    harness.games = [game("1", GameStatus.FINAL)]
    harness.states["1"] = "final"
    await harness.run(NOON + 30 * SECOND)
    final_time = harness.store.final_time("1")
    assert final_time == NOON + 30 * SECOND
    return final_time


@pytest.mark.anyio
async def test_a_final_game_detail_is_built_once_with_the_adr_0010_attempts_and_never_again(
    harness: Harness,
) -> None:
    harness.fail_standings = True
    harness.games = [game("1", GameStatus.LIVE)]
    await harness.run(NOON)
    harness.games = [game("1", GameStatus.FINAL)]
    harness.states["1"] = "final"
    await harness.run(NOON + 30 * SECOND)
    final_time = NOON + 30 * SECOND

    assert harness.standings_calls == 1
    assert harness.stored("1") is None
    state = harness.store.feed_build(KIND, "1")
    assert state is not None
    assert state.last_failure == final_time
    await harness.run(final_time + 2 * HOUR - SECOND)
    assert harness.standings_calls == 1

    harness.fail_standings = False
    requests = harness.calls("1")
    await harness.run(final_time + 2 * HOUR)
    assert harness.standings_calls == 2
    assert harness.calls("1") == requests + 1
    assert harness.sections_fresh[-1] == final_time + 2 * HOUR
    stored = harness.stored("1")
    assert stored is not None
    assert stored.status is GameStatus.FINAL
    built = harness.last_build("1")
    assert built == final_time + 2 * HOUR

    for later in (4 * HOUR, 6 * HOUR, 30 * HOUR):
        await harness.run(final_time + later)
        await harness.serve("1")
    assert harness.standings_calls == 2
    assert harness.last_build("1") == built


@pytest.mark.anyio
async def test_a_final_game_is_never_built_after_the_fourth_failed_attempt(
    harness: Harness,
) -> None:
    harness.fail_standings = True
    final_time = await turn_final(harness)
    for delay in STATS_ATTEMPT_DELAYS[1:]:
        await harness.run(final_time + delay)
    assert harness.standings_calls == 4

    await harness.run(final_time + 7 * HOUR)
    with pytest.raises(FeedUnavailableError):
        await harness.serve("1")

    assert harness.standings_calls == 4
    assert harness.stored("1") is None


@pytest.mark.anyio
async def test_a_final_game_turning_final_reads_the_same_summary_request_as_the_games_job(
    harness: Harness,
) -> None:
    harness.games = [game("1", GameStatus.LIVE)]
    await harness.run(NOON)
    before = harness.calls("1")
    harness.games = [game("1", GameStatus.FINAL)]
    harness.states["1"] = "final"

    await harness.run(NOON + 30 * SECOND)

    assert harness.calls("1") == before + 1
    stored = harness.stored("1")
    assert stored is not None
    assert harness.venue(read_by_id(harness.settings.data_dir, KIND, "1") or b"") == (
        "final"
    )


@pytest.mark.anyio
async def test_a_requested_final_game_never_starts_a_build(tmp_path: Path) -> None:
    harness = Harness(make_dir(tmp_path / "a"), hook=False)
    harness.games = [game("1", GameStatus.LIVE)]
    await harness.run(NOON)
    live = await harness.serve("1")
    harness.games = [game("1", GameStatus.FINAL)]
    await harness.run(NOON + 30 * SECOND)
    calls = harness.standings_calls

    served = await harness.serve("1", NOON + HOUR)

    assert GameDetailFeed.model_validate_json(served).status is GameStatus.LIVE
    assert served == live
    assert harness.standings_calls == calls

    empty = Harness(make_dir(tmp_path / "b"), hook=False)
    empty.games = [game("1", GameStatus.FINAL)]
    await empty.run(NOON)
    with pytest.raises(FeedUnavailableError):
        await empty.serve("1")
    assert empty.standings_calls == 0
    assert empty.stored("1") is None


@pytest.mark.anyio
async def test_stars_highlights_and_search_url_are_added_when_served_and_not_stored(
    harness: Harness,
) -> None:
    harness.highlights = [HIGHLIGHT]
    harness.games = [
        game("final", GameStatus.FINAL),
        game("live", GameStatus.LIVE),
        game("pre", GameStatus.SCHEDULED, start=NOON + 5 * HOUR),
    ]
    await harness.run(NOON)
    for game_id in ("final", "live", "pre"):
        await harness.serve(game_id)
    builds = harness.standings_calls

    for game_id in ("final", "live", "pre"):
        served = GameDetailFeed.model_validate_json(await harness.serve(game_id))
        assert served.stars == STARS
        assert served.highlights == [HIGHLIGHT]
        assert str(served.highlights_search_url) == SEARCH_URL
        stored = harness.stored(game_id)
        assert stored is not None
        assert stored.stars is None
        assert stored.highlights is None
        assert stored.highlights_search_url is None

    harness.stars = None
    harness.search_url = "https://example.com/other"
    for game_id in ("final", "live", "pre"):
        served = GameDetailFeed.model_validate_json(await harness.serve(game_id))
        assert served.stars is None
        assert str(served.highlights_search_url) == "https://example.com/other"
    assert harness.standings_calls == builds


@pytest.mark.anyio
async def test_a_game_id_outside_the_days_shown_answers_unknown_with_no_source_request(
    harness: Harness, tmp_path: Path
) -> None:
    harness.games = [game("1", GameStatus.SCHEDULED, start=NOON + 5 * HOUR)]
    await harness.run(NOON)

    with pytest.raises(UnknownFeedError):
        await harness.serve("elsewhere")

    assert harness.requests == []
    assert harness.store.feed_build(KIND, "elsewhere") is None
    assert not (tmp_path / "feeds" / "games" / "elsewhere.json").exists()


@pytest.mark.anyio
async def test_a_detail_request_before_the_days_shown_load_answers_unavailable(
    harness: Harness,
) -> None:
    with pytest.raises(FeedUnavailableError):
        await harness.serve("1")

    assert harness.requests == []


@pytest.mark.anyio
async def test_the_cleanup_deletes_the_stored_detail_of_a_game_that_left_the_days_shown_with_no_source_request(
    harness: Harness, tmp_path: Path
) -> None:
    gone_start = dt.datetime(2026, 10, 2, 16, 0, tzinfo=dt.UTC)
    harness.games = [
        game("shown", GameStatus.SCHEDULED, start=NOON + 5 * HOUR),
    ]
    harness.other_days[dt.date(2026, 10, 2)] = [
        game("gone", GameStatus.SCHEDULED, start=gone_start)
    ]
    await harness.run(NOON)
    await harness.serve("shown")
    await harness.serve("gone")
    publish_by_id(
        tmp_path,
        KIND,
        GameDetailFeed,
        "ghost",
        harness.stored("shown"),  # type: ignore[arg-type]
    )
    harness.store.record_build(KIND, "ghost", NOON)
    requests = len(harness.requests)

    await harness.run(AFTER_MIDNIGHT)

    assert harness.stored("shown") is not None
    assert harness.stored("gone") is None
    assert harness.stored("ghost") is None
    assert harness.store.feed_build_ids(KIND) == {"shown"}
    assert len(harness.requests) == requests


@pytest.mark.anyio
async def test_the_cleanup_runs_only_when_the_shown_games_change(
    harness: Harness,
) -> None:
    calls: list[int] = []
    original = harness.cache.cleanup

    def counting() -> None:
        calls.append(1)
        original()

    harness.cache.cleanup = counting  # type: ignore[method-assign]
    harness.games = [game("1", GameStatus.LIVE)]

    await harness.run(NOON)
    await harness.run(NOON + 30 * SECOND)
    assert calls == [1]
    harness.games = [game("1", GameStatus.LIVE), game("2", GameStatus.LIVE)]
    await harness.run(NOON + 60 * SECOND)
    await harness.run(NOON + 90 * SECOND)

    assert calls == [1, 1]


@pytest.mark.anyio
async def test_a_failed_build_keeps_the_stored_feed_and_is_listed_as_failed(
    harness: Harness,
) -> None:
    harness.games = [game("1", GameStatus.SCHEDULED, start=NOON + 5 * HOUR)]
    await harness.run(NOON)
    first = await harness.serve("1")
    harness.fail_standings = True

    body = await harness.serve("1", NOON + 3 * HOUR)

    assert body == first
    assert harness.standings_calls == 2
    assert [(f.kind, f.feed_id) for f in harness.store.failed_feed_builds()] == [
        (KIND, "1")
    ]
    assert json.loads(first)["id"] == "1"


@pytest.mark.anyio
async def test_after_a_day_change_whose_new_day_fetch_fails_loaded_games_keep_being_served(
    harness: Harness,
) -> None:
    harness.highlights = [HIGHLIGHT]
    harness.games = [
        game("1", GameStatus.LIVE),
        game("p", GameStatus.SCHEDULED, start=NOON + 20 * HOUR),
    ]
    await harness.run(NOON)
    await harness.serve("p")
    harness.games = [
        game("1", GameStatus.FINAL),
        game("p", GameStatus.SCHEDULED, start=NOON + 20 * HOUR),
    ]
    harness.states["1"] = "final"
    await harness.run(NOON + 30 * SECOND)
    stored_final = harness.stored("1")
    assert stored_final is not None
    assert stored_final.status is GameStatus.FINAL
    harness.failing_days = {dt.date(2026, 10, 9)}

    await harness.run(AFTER_MIDNIGHT)

    assert harness.job.shown_games() is None
    final = GameDetailFeed.model_validate_json(await harness.serve("1"))
    assert final.status is GameStatus.FINAL
    assert final.stars == STARS
    assert final.highlights == [HIGHLIGHT]
    assert str(final.highlights_search_url) == SEARCH_URL
    pre = GameDetailFeed.model_validate_json(await harness.serve("p"))
    assert pre.stars == STARS
    with pytest.raises(FeedUnavailableError):
        await harness.serve("never")
    assert harness.stored("1") is not None
    assert harness.stored("p") is not None
    assert harness.store.feed_build_ids(KIND) == {"1", "p"}

    harness.failing_days = set()
    await harness.run(AFTER_MIDNIGHT + 30 * SECOND)

    assert harness.job.shown_games() is not None
    with pytest.raises(UnknownFeedError):
        await harness.serve("never")
    assert (await harness.serve("1")) is not None


# Group: guest games


def test_builds_a_guest_game_with_the_box_score_team_stats_and_quarters_of_both_sides() -> (
    None
):
    feed = build_guest(guest_game("1", GameStatus.FINAL), guest_sections())

    assert feed.away.guest and feed.winner == "HCM"
    assert feed.box_score is not None
    assert feed.box_score.away.players[0].photo_url is None
    assert feed.box_score.home.players[0].photo_url == PHOTO
    assert feed.team_stats is not None
    assert feed.team_stats.leaders.rebounds == "HCM"
    assert feed.line_score is not None
    assert feed.line_score.away == [20, 20] and feed.line_score.home == [18, 20]


def test_a_guest_game_has_standings_injuries_last_games_and_record_only_for_the_league_side() -> (
    None
):
    out = Injury(display_name="A B", status="out")  # type: ignore[arg-type]

    feed = build_guest(
        guest_game("1", GameStatus.SCHEDULED),
        guest_sections(GameStatus.SCHEDULED),
        league_injuries=injuries({"NYK": [out]}),
    )

    assert feed.away.record is None
    assert feed.home.record is not None and feed.home.record.wins == 3
    assert feed.standings is not None
    assert feed.standings.away is None and feed.standings.home is not None
    assert feed.injuries is not None
    assert feed.injuries.away is None and feed.injuries.home == [out]
    assert feed.last_games is not None
    assert feed.last_games.away is None and feed.last_games.home is not None


def test_a_guest_game_has_no_season_series() -> None:
    meetings = series("1")

    feed = build_guest(
        guest_game("1", GameStatus.FINAL),
        guest_sections(GameStatus.FINAL, season_series=meetings),
    )

    assert feed.season_series is None


def test_a_guest_game_with_an_empty_win_probability_builds_with_null_win_probability() -> (
    None
):
    feed = build_guest(
        guest_game("1", GameStatus.FINAL),
        guest_sections(win_probability=None),
    )

    assert feed.win_probability is None
    assert feed.win_probability_leader is None
    assert feed.win_probability_periods is None


@pytest.mark.anyio
async def test_never_fetches_the_schedule_of_the_guest_side(harness: Harness) -> None:
    harness.stars = GUEST_STARS
    harness.games = [
        guest_game("g", GameStatus.SCHEDULED).model_copy(
            update={"start_time": NOON + 5 * HOUR}
        )
    ]
    await harness.run(NOON)

    feed = GameDetailFeed.model_validate_json(await harness.serve("g"))

    assert harness.schedule_calls == ["NYK"]
    assert feed.away.guest and feed.last_games is not None
    assert feed.last_games.away is None


@pytest.mark.anyio
async def test_stars_served_with_a_guest_game_have_none_for_the_guest_side(
    harness: Harness,
) -> None:
    harness.stars = GUEST_STARS
    harness.games = [
        guest_game("g", GameStatus.SCHEDULED).model_copy(
            update={"start_time": NOON + 5 * HOUR}
        )
    ]
    await harness.run(NOON)
    await harness.serve("g")

    served = GameDetailFeed.model_validate_json(await harness.serve("g"))

    assert served.stars == GUEST_STARS
    stored = harness.stored("g")
    assert stored is not None and stored.stars is None
