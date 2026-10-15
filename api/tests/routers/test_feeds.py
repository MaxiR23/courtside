# api/tests/routers/test_feeds.py
#
# Tests for the feed endpoint.
#
# Tested:
# - Serves the published games feed with Cache-Control and ETag
# - Changes the ETag when the feed changes
# - Responds 304 with no body when the ETag matches, listed, weak or `*`
# - Serves the feed when the ETag does not match
# - Responds 503 with a JSON error before the first publication, even with an ETag
# - Keeps serving the last valid feed after an invalid publish
# - Serves a game detail feed through the on-demand cache with Cache-Control and ETag
# - Responds 304 when the game detail ETag matches
# - Responds 404 with a JSON error for a game outside the days shown and for an id that is not a game id
# - Responds 503 for a game detail before the days shown are loaded
# - Every feed request records presence, also one answered 503
# - A live game detail request waits at most one budget in total: a games refresh that uses the budget leaves the stored body served though the rebuild ends within a second budget
# - A games feed request with live data older than 30 seconds serves the refreshed feed
# - Serves an on-demand feed with the same Cache-Control and a SHA-256 ETag as the games feed
# - Responds 304 with no body for a matching, listed, weak or `*` If-None-Match on an on-demand feed
# - Responds 404 with a JSON error for an unknown on-demand id
# - Responds 503 with a JSON error for a not-ready on-demand id, even with If-None-Match `*`
# - Serves a team feed with Cache-Control and ETag, answers 304 for a matching ETag, 404 for an unknown or uppercase code and 503 when the build fails
# - Serves a player feed with Cache-Control and ETag, answers 304 for a matching ETag, 404 for an id in no roster once the rosters are fetched and 503 before, also through the app with no jobs
# - A team and a player request record presence
# - Serves the standings feed with Cache-Control and ETag, answers 304 for a matching ETag, 503 when the read fails with nothing stored and keeps serving the stored feed when a rebuild fails
# - Serves the search feed with Cache-Control and ETag, with 30 teams and every roster player, and answers 304 for a matching ETag
# - Responds 503 with a JSON error for the search feed before the rosters are fetched or when the standings read fails with nothing stored, and keeps serving the stored feed when a rebuild fails
#
# - Serves the Cup feed with Cache-Control and ETag and answers 304 for a matching ETag
# - Responds 503 with a JSON error for the Cup feed when a group read fails with nothing stored and before the season is known
# - Serves a Cup matchup feed for each of the 7 slot ids with Cache-Control and ETag and answers 304 for a matching ETag
# - Responds 404 with a JSON error for an id outside the 7 slots with no source request
# - Responds 503 for a Cup matchup before the season is known and when a roster read fails with nothing stored
# - Serves the playoffs feed with Cache-Control and ETag and answers 304 for a matching ETag
# - Responds 503 with a JSON error for the playoffs feed when a season type read fails with nothing stored and before the season or the rosters are known, and keeps serving the stored feed when a rebuild fails
# - Serves the playoffs finals feed with Cache-Control and ETag and answers 304 for a matching ETag
# - Responds 404 with a JSON error when the Finals has no game, with no finals read, and 503 when the playoffs feed cannot be built with nothing stored
# - Keeps serving the stored playoffs finals feed when a rebuild fails
# - Serves the All-Star feed with Cache-Control and ETag and answers 304 for a matching ETag
# - Responds 503 with a JSON error for the All-Star feed when the scoreboard day read fails with nothing stored and before the season, the rosters or the discovery are known, and keeps serving the stored feed when a rebuild fails
#
# - Serves the calendar feed with Cache-Control and ETag and answers 304 for a matching ETag
# - Serves current as the current season's calendar with the same body and ETag as its end-year path, answers 304 for that ETag and 503 while the season is not known, and responds 404 for Current and currentx
# - Responds 404 for a calendar of 1993, the season after the current one and a season that is not a number or has a trailing newline with no source request, and 503 while the season is not known or when the read fails with nothing stored
# - Serves the day feed with Cache-Control and ETag, with its season and label and an empty games list for a day with no event, and answers 304 for a matching ETag
# - Responds 404 for a day that is not a date, before 1993-10-01, tomorrow and a day of the stored games feed with no source request, and 503 when the read fails with nothing stored
# - Serves the game detail of a final game of a stored day through the game detail route with Cache-Control, ETag and a season label, and answers 304 for a matching ETag
# - Responds 404 for a game id in no stored day and for a postponed game of a stored day, with no source request, and 503 for a past game whose build fails with nothing stored
# - A game the games job has loaded takes the games path with a null season label even when a stored day lists it
# - Serves the standings, team and player feed of a past season with Cache-Control and ETag, answers 304 for a matching ETag, 404 for 1993, the current season, a future season and a non-integer with no source request, 503 while the season is not known, and 404 for a franchise with no team that season
# - Serves the Cup and a Cup matchup of a past season with Cache-Control and ETag and answers 304 for a matching ETag
# - Responds 404 with a JSON error and no source request on both season Cup paths for 2023, a season after the current one, a non-integer, a trailing newline and a leading zero, and for an unknown slot on a past and the current season
# - The current season serves the current Cup and Cup matchup feeds with the same body and ETag and stores nothing under the season kinds
# - Responds 503 on both season Cup paths while the current season is not known and when a past build fails with nothing stored
# - The current player path serves a player on no roster who is known from a stored past feed
#
# What is covered:
# - Success response, documented failures (503, 404), edge case of an invalid publish
#
# Run with: cd api && .venv/bin/python -m pytest tests/routers/test_feeds.py
#
# SEE: api/app/routers/feeds.py

import asyncio
import datetime as dt
import hashlib
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
import respx
from fastapi import FastAPI, Request, Response
from fastapi.testclient import TestClient

from app.feeds.all_star import AllStarFeed
from app.feeds.calendar import CalendarFeed
from app.feeds.cup import CupFeed, SlotId
from app.feeds.cup_matchup import CupMatchupFeed
from app.feeds.days import DayFeed
from app.feeds.game_detail import GameDetailFeed, PastGameDetailFeed
from app.feeds.games import GamesFeed, GameStatus, Star, Stars
from app.feeds.player import PastPlayerFeed, PlayerFeed
from app.feeds.playoffs import PlayoffsFeed
from app.feeds.playoffs_finals import PlayoffsFinalsFeed
from app.feeds.search import SearchFeed
from app.feeds.standings import StandingsFeed
from app.feeds.team import PastTeamFeed, TeamFeed
from app.jobs.day_feed import KIND as DAY_KIND
from app.jobs.day_feed import build_day_feed
from app.jobs.game_detail_feed import GameDetailFeeds
from app.jobs.games import GamesJob
from app.jobs.on_demand import MISSING_WAIT_SECONDS, FeedCache, FeedKind, IdStatus
from app.jobs.past_game_detail_feed import KIND as PAST_KIND
from app.jobs.past_game_detail_feed import PastGameDetailFeeds
from app.jobs.presence import Presence
from app.jobs.team_feed import FEED_LIFETIME
from app.main import create_app
from app.routers import feeds as feeds_router
from app.routers.feeds import CACHE_CONTROL, serve_on_demand
from app.settings import Settings
from app.sources.game_detail import GameDetail, GameDetailSections
from app.sources.http import SourceClient, create_client
from app.sources.league_injuries import LeagueInjuries
from app.sources.player_draft import PlayerAthlete
from app.sources.scoreboard import ScoreboardGame
from app.sources.standings import LeagueStandings
from app.sources.team_schedule import TeamSchedule
from app.storage.feeds import publish_by_id, publish_feed
from app.storage.state import StateStore
from tests.jobs.test_all_star_feed import DAY as ALL_STAR_DAY
from tests.jobs.test_all_star_feed import AllStarKit
from tests.jobs.test_calendar_feed import CalendarKit
from tests.jobs.test_cup_feed import CupKit
from tests.jobs.test_cup_matchup_feed import MatchupKit
from tests.jobs.test_day_feed import NOW as DAY_NOW
from tests.jobs.test_day_feed import PAST, DayKit, search_url
from tests.jobs.test_day_feed import game as day_game
from tests.jobs.test_past_game_detail_feed import PastKit
from tests.jobs.test_player_feed import PlayerKit, player
from tests.jobs.test_playoffs_feed import PlayoffsKit
from tests.jobs.test_playoffs_finals_feed import FinalsKit, postseason
from tests.jobs.test_search_feed import SearchKit
from tests.jobs.test_season_cup_matchup_feed import SeasonMatchupKit
from tests.jobs.test_season_player_feed import SeasonPlayerKit
from tests.jobs.test_season_standings_feed import StandingsKit as SeasonStandingsKit
from tests.jobs.test_season_team_feed import SeasonTeamKit
from tests.jobs.test_standings_feed import StandingsKit


def make_client(path: Path) -> TestClient:
    settings = Settings(_env_file=None, data_dir=path)  # type: ignore[call-arg]
    return TestClient(create_app(settings, run_jobs=False))


def feed(day: int) -> GamesFeed:
    return GamesFeed(
        generated_at=dt.datetime(2026, 1, day, 12, 0, tzinfo=dt.UTC), days=[]
    )


def test_serves_the_published_games_feed_with_cache_control_and_etag(
    tmp_path: Path,
) -> None:
    with make_client(tmp_path) as client:
        publish_feed(tmp_path, "games", feed(10))

        response = client.get("/feeds/games.json")

    assert response.status_code == 200
    assert response.content == feed(10).model_dump_json().encode("utf-8")
    assert response.headers["content-type"] == "application/json"
    assert response.headers["cache-control"] == CACHE_CONTROL
    etag = response.headers["etag"]
    assert etag.startswith('"') and etag.endswith('"')


def test_changes_the_etag_when_the_feed_changes(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        publish_feed(tmp_path, "games", feed(10))
        first = client.get("/feeds/games.json").headers["etag"]
        same = client.get("/feeds/games.json").headers["etag"]
        publish_feed(tmp_path, "games", feed(11))
        second = client.get("/feeds/games.json").headers["etag"]

    assert first == same
    assert first != second


def test_responds_503_with_a_json_error_before_the_first_publication(
    tmp_path: Path,
) -> None:
    with make_client(tmp_path) as client:
        response = client.get("/feeds/games.json")

    assert response.status_code == 503
    assert isinstance(response.json()["detail"], str)


def test_keeps_serving_the_last_valid_feed_after_an_invalid_publish(
    tmp_path: Path,
) -> None:
    invalid = GamesFeed.model_construct(
        generated_at=dt.datetime(2026, 1, 12, 12, 0, tzinfo=dt.UTC).replace(
            tzinfo=None
        ),
        days=[],
    )
    with make_client(tmp_path) as client:
        publish_feed(tmp_path, "games", feed(10))
        publish_feed(tmp_path, "games", invalid)

        response = client.get("/feeds/games.json")

    assert response.status_code == 200
    assert response.content == feed(10).model_dump_json().encode("utf-8")


def test_responds_304_when_the_etag_matches(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        publish_feed(tmp_path, "games", feed(10))
        first = client.get("/feeds/games.json")

        response = client.get(
            "/feeds/games.json", headers={"If-None-Match": first.headers["etag"]}
        )

    assert response.status_code == 304
    assert response.content == b""
    assert response.headers["etag"] == first.headers["etag"]
    assert response.headers["cache-control"] == CACHE_CONTROL


def test_responds_304_when_a_listed_or_weak_etag_matches(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        publish_feed(tmp_path, "games", feed(10))
        etag = client.get("/feeds/games.json").headers["etag"]

        listed = client.get(
            "/feeds/games.json", headers={"If-None-Match": f'"other", {etag}'}
        )
        weak = client.get("/feeds/games.json", headers={"If-None-Match": f"W/{etag}"})
        star = client.get("/feeds/games.json", headers={"If-None-Match": "*"})

    assert listed.status_code == weak.status_code == star.status_code == 304


def test_serves_the_feed_when_the_etag_does_not_match(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        publish_feed(tmp_path, "games", feed(10))

        response = client.get("/feeds/games.json", headers={"If-None-Match": '"stale"'})

    assert response.status_code == 200
    assert response.content == feed(10).model_dump_json().encode("utf-8")


def test_responds_503_before_the_first_publication_even_with_an_etag(
    tmp_path: Path,
) -> None:
    with make_client(tmp_path) as client:
        response = client.get("/feeds/games.json", headers={"If-None-Match": "*"})

    assert response.status_code == 503


NOW = dt.datetime(2026, 10, 5, 16, 0, tzinfo=dt.UTC)
RECORD = {"wins": 1, "losses": 1}
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
        name: None
        for name in (
            "field_goal_pct",
            "three_point_pct",
            "free_throw_pct",
            "rebounds",
            "assists",
            "turnovers",
            "steals",
            "blocks",
        )
    },
}


def star(code: str) -> Star:
    return Star.model_validate(
        {
            "player_id": f"s{code}",
            "first_name": "A",
            "last_name": "B",
            "team_code": code,
            "photo_url": "https://example.com/p.png",
            "short_name": "A. B",
        }
    )


STARS = Stars(away=star("BOS"), home=star("NYK"))


def scoreboard_game(game_id: str, status: GameStatus) -> ScoreboardGame:
    data: dict[str, object] = {
        "id": game_id,
        "away": {"code": "BOS", "name": "Celtics", "city": "Boston"},
        "home": {"code": "NYK", "name": "Knicks", "city": "New York"},
        "status": status,
        "start_time": NOW + dt.timedelta(hours=5),
        "venue": "Garden",
    }
    if status is GameStatus.LIVE:
        data.update(
            period=2,
            clock="5:00",
            start_time=NOW - dt.timedelta(hours=1),
            line_score={"away": [20, 20], "home": [18, 20]},
            score={"away": 40, "home": 38},
        )
    return ScoreboardGame.model_validate(data)


class Detail:
    """An app with the feeds router, a games job and the game detail kind, over fakes."""

    def __init__(
        self, path: Path, status: GameStatus, *, wait: float = MISSING_WAIT_SECONDS
    ) -> None:
        self.clock = [NOW]
        self.games_gate: asyncio.Event | None = None
        self.sections_delay = 0.0
        self.venue = "Garden"
        settings = Settings(_env_file=None, data_dir=path)  # type: ignore[call-arg]
        store = StateStore(path)
        store.migrate()
        self.presence = Presence(clock=lambda: self.clock[0])
        self.game = scoreboard_game("401", status)

        async def fetch_games(
            client: SourceClient, day: dt.date, settings: Settings
        ) -> list[ScoreboardGame]:
            if self.games_gate is not None:
                await self.games_gate.wait()
            return [self.game] if day == NOW.date() else []

        async def game_detail(
            client: SourceClient, game_id: str, settings: Settings, fresh: object
        ) -> GameDetail:
            leader = {
                "player_id": "l1",
                "display_name": "A B",
                "team_code": "BOS",
                "photo_url": "https://example.com/p.png",
                "points": 20,
                "rebounds": 5,
                "assists": 5,
            }
            stats = {
                "field_goal_pct": 0.5,
                "three_point_pct": 0.4,
                "rebounds": 40,
                "assists": 20,
                "turnovers": 10,
            }
            return GameDetail.model_validate(
                {
                    "leaders": {"away": leader, "home": {**leader, "team_code": "NYK"}},
                    "team_stats": {"away": stats, "home": stats},
                }
            )

        async def sections(
            client: SourceClient, game_id: str, settings: Settings, fresh: object
        ) -> GameDetailSections:
            await asyncio.sleep(self.sections_delay)
            data: dict[str, object] = {
                "venue": {"name": self.venue, "city": "New York"}
            }
            if self.game.status is GameStatus.LIVE:
                data["team_stats"] = TEAM_STATS
            return GameDetailSections.model_validate(data)

        async def standings(
            client: SourceClient, settings: Settings
        ) -> LeagueStandings:
            return LeagueStandings.model_validate(
                {"teams": {"BOS": STANDING, "NYK": STANDING}}
            )

        async def injuries(client: SourceClient, settings: Settings) -> LeagueInjuries:
            return LeagueInjuries(teams={})

        async def schedule(
            client: SourceClient, code: str, settings: Settings
        ) -> TeamSchedule:
            return TeamSchedule(last_games=[], arenas={})

        client = create_client(store, clock=lambda: self.clock[0])
        cache = FeedCache(path, store, clock=lambda: self.clock[0], wait=wait)
        self.job = GamesJob(
            settings,
            store,
            client,
            fetch_games=fetch_games,
            fetch_game_detail=game_detail,
            present=lambda now: True,
            stars=lambda game: STARS,
        )
        GameDetailFeeds(
            settings,
            store,
            client,
            cache,
            self.job,
            fetch_sections=sections,
            fetch_standings=standings,
            fetch_injuries=injuries,
            fetch_team_schedule=schedule,
        )
        self.app = FastAPI()
        self.app.include_router(feeds_router.router)
        self.app.state.settings = settings
        self.app.state.presence = self.presence
        self.app.state.games_job = self.job
        self.app.state.feed_cache = cache


def test_serves_a_game_detail_feed_through_the_cache_with_cache_control_and_etag(
    tmp_path: Path,
) -> None:
    detail = Detail(tmp_path, GameStatus.SCHEDULED)
    with TestClient(detail.app) as client:
        client.portal.call(detail.job.run, NOW)  # type: ignore[union-attr]

        response = client.get("/feeds/games/401.json")

    assert response.status_code == 200
    assert GameDetailFeed.model_validate_json(response.content).id == "401"
    assert response.headers["content-type"] == "application/json"
    assert response.headers["cache-control"] == CACHE_CONTROL
    etag = response.headers["etag"]
    assert etag.startswith('"') and etag.endswith('"')


def test_responds_304_when_the_game_detail_etag_matches(tmp_path: Path) -> None:
    detail = Detail(tmp_path, GameStatus.SCHEDULED)
    with TestClient(detail.app) as client:
        client.portal.call(detail.job.run, NOW)  # type: ignore[union-attr]
        first = client.get("/feeds/games/401.json")

        response = client.get(
            "/feeds/games/401.json", headers={"If-None-Match": first.headers["etag"]}
        )

    assert response.status_code == 304
    assert response.content == b""
    assert response.headers["cache-control"] == CACHE_CONTROL


def test_responds_404_with_a_json_error_for_a_game_outside_the_days_shown(
    tmp_path: Path,
) -> None:
    detail = Detail(tmp_path, GameStatus.SCHEDULED)
    with TestClient(detail.app) as client:
        client.portal.call(detail.job.run, NOW)  # type: ignore[union-attr]

        response = client.get("/feeds/games/999.json")

    assert response.status_code == 404
    assert isinstance(response.json()["detail"], str)


def test_responds_404_for_an_id_that_is_not_a_game_id(tmp_path: Path) -> None:
    detail = Detail(tmp_path, GameStatus.SCHEDULED)
    with TestClient(detail.app) as client:
        client.portal.call(detail.job.run, NOW)  # type: ignore[union-attr]

        response = client.get("/feeds/games/a.b.json")

    assert response.status_code == 404


def test_responds_503_for_a_game_detail_before_the_days_shown_are_loaded(
    tmp_path: Path,
) -> None:
    with make_client(tmp_path) as client:
        response = client.get("/feeds/games/401.json")

    assert response.status_code == 503
    assert isinstance(response.json()["detail"], str)


def test_every_feed_request_records_presence(tmp_path: Path) -> None:
    first_path = tmp_path / "first"
    first_path.mkdir()
    detail = Detail(first_path, GameStatus.SCHEDULED)
    with TestClient(detail.app) as client:
        assert not detail.presence.present(NOW)
        assert client.get("/feeds/games.json").status_code == 503
        assert detail.presence.present(NOW)

    second_path = tmp_path / "second"
    second_path.mkdir()
    second = Detail(second_path, GameStatus.SCHEDULED)
    with TestClient(second.app) as client:
        client.portal.call(second.job.run, NOW)  # type: ignore[union-attr]
        assert not second.presence.present(NOW)
        client.get("/feeds/games/401.json")
        assert second.presence.present(NOW)


def test_a_games_feed_request_with_live_data_older_than_30_seconds_serves_the_refreshed_feed(
    tmp_path: Path,
) -> None:
    detail = Detail(tmp_path, GameStatus.LIVE)
    later = NOW + dt.timedelta(seconds=31)
    with TestClient(detail.app) as client:
        client.portal.call(detail.job.run, NOW)  # type: ignore[union-attr]
        first = GamesFeed.model_validate_json(client.get("/feeds/games.json").content)
        detail.clock[0] = later

        second = GamesFeed.model_validate_json(client.get("/feeds/games.json").content)

    assert first.generated_at == NOW
    assert second.generated_at == later


def test_a_live_game_detail_request_waits_at_most_one_budget_in_total(
    tmp_path: Path,
) -> None:
    budget = 0.2
    detail = Detail(tmp_path, GameStatus.LIVE, wait=budget)
    with TestClient(detail.app) as client:
        client.portal.call(detail.job.run, NOW)  # type: ignore[union-attr]
        assert client.get("/feeds/games/401.json").status_code == 200
        detail.clock[0] = NOW + dt.timedelta(seconds=31)
        client.portal.call(detail.job.run, detail.clock[0])  # type: ignore[union-attr]
        detail.clock[0] = NOW + dt.timedelta(seconds=62)
        detail.games_gate = asyncio.Event()
        detail.venue = "New Arena"
        detail.sections_delay = budget / 2

        response = client.get("/feeds/games/401.json")

        client.portal.call(detail.games_gate.set)  # type: ignore[union-attr]

    assert response.status_code == 200
    assert GameDetailFeed.model_validate_json(response.content).venue.name == "Garden"


BUILT = dt.datetime(2026, 1, 10, 12, 0, tzinfo=dt.UTC)


async def never_built(feed_id: str) -> GamesFeed:
    raise AssertionError("no build expected")


def on_demand_status(feed_id: str) -> IdStatus:
    if feed_id == "ready":
        return IdStatus.KNOWN
    if feed_id == "soon":
        return IdStatus.NOT_READY
    return IdStatus.UNKNOWN


def make_on_demand_client(path: Path) -> TestClient:
    store = StateStore(path)
    store.migrate()
    store.record_build("fakes", "ready", BUILT)
    publish_by_id(path, "fakes", GamesFeed, "ready", feed(10))
    cache = FeedCache(path, store, clock=lambda: BUILT)
    cache.register(
        FeedKind(
            "fakes",
            GamesFeed,
            check=on_demand_status,
            build=never_built,
            is_fresh=lambda feed, built_at, now: True,
            keep=lambda feed_id: True,
        )
    )
    app = FastAPI()

    @app.get("/test/{feed_id}.json")
    async def read(feed_id: str, request: Request) -> Response:
        return await serve_on_demand(cache, "fakes", feed_id, request)

    return TestClient(app)


def test_serves_an_on_demand_feed_with_cache_control_and_a_sha256_etag(
    tmp_path: Path,
) -> None:
    client = make_on_demand_client(tmp_path)

    response = client.get("/test/ready.json")

    assert response.status_code == 200
    assert response.content == feed(10).model_dump_json().encode("utf-8")
    assert response.headers["cache-control"] == CACHE_CONTROL
    assert (
        response.headers["etag"] == f'"{hashlib.sha256(response.content).hexdigest()}"'
    )


def test_responds_304_with_no_body_for_a_matching_on_demand_etag(
    tmp_path: Path,
) -> None:
    client = make_on_demand_client(tmp_path)
    etag = client.get("/test/ready.json").headers["etag"]

    for header in (etag, f'"x", {etag}', f"W/{etag}", "*"):
        response = client.get("/test/ready.json", headers={"If-None-Match": header})

        assert response.status_code == 304
        assert response.content == b""
        assert response.headers["etag"] == etag
        assert response.headers["cache-control"] == CACHE_CONTROL


def test_responds_404_with_a_json_error_for_an_unknown_on_demand_id(
    tmp_path: Path,
) -> None:
    response = make_on_demand_client(tmp_path).get("/test/nobody.json")

    assert response.status_code == 404
    assert isinstance(response.json()["detail"], str)


def test_responds_503_with_a_json_error_for_a_not_ready_on_demand_id_even_with_an_etag(
    tmp_path: Path,
) -> None:
    response = make_on_demand_client(tmp_path).get(
        "/test/soon.json", headers={"If-None-Match": "*"}
    )

    assert response.status_code == 503
    assert isinstance(response.json()["detail"], str)


class Profiles:
    """An app with the feeds router and the team and player kinds over the player kit's fakes."""

    def __init__(self, path: Path) -> None:
        self.kit = PlayerKit(path)
        self.presence = Presence(clock=lambda: self.kit.clock[0])
        self.app = FastAPI()
        self.app.include_router(feeds_router.router)
        self.app.state.settings = self.kit.settings
        self.app.state.presence = self.presence
        self.app.state.games_job = self.kit.games
        self.app.state.feed_cache = self.kit.cache
        self.app.state.player_feeds = self.kit.players


@pytest.fixture
def profiles(tmp_path: Path) -> Iterator[Profiles]:
    with respx.mock:
        yield Profiles(tmp_path)


def test_serves_a_team_feed_with_cache_control_and_an_etag(profiles: Profiles) -> None:
    with TestClient(profiles.app) as client:
        response = client.get("/feeds/teams/okc.json")

    assert response.status_code == 200
    assert TeamFeed.model_validate_json(response.content).code == "OKC"
    assert response.headers["content-type"] == "application/json"
    assert response.headers["cache-control"] == CACHE_CONTROL
    etag = response.headers["etag"]
    assert etag.startswith('"') and etag.endswith('"')


def test_responds_304_when_the_team_etag_matches(profiles: Profiles) -> None:
    with TestClient(profiles.app) as client:
        first = client.get("/feeds/teams/okc.json")

        response = client.get(
            "/feeds/teams/okc.json", headers={"If-None-Match": first.headers["etag"]}
        )

    assert response.status_code == 304
    assert response.content == b""


def test_responds_404_with_a_json_error_for_an_unknown_or_uppercase_team_code(
    profiles: Profiles,
) -> None:
    with TestClient(profiles.app) as client:
        for code in ("xyz", "OKC"):
            response = client.get(f"/feeds/teams/{code}.json")

            assert response.status_code == 404
            assert isinstance(response.json()["detail"], str)

    assert profiles.kit.requests == []


def test_responds_503_with_a_json_error_when_the_team_build_fails(
    profiles: Profiles,
) -> None:
    profiles.kit.failing.add("info/OKC")
    with TestClient(profiles.app) as client:
        response = client.get("/feeds/teams/okc.json")

    assert response.status_code == 503
    assert isinstance(response.json()["detail"], str)


def test_serves_a_player_feed_with_cache_control_and_an_etag(
    profiles: Profiles,
) -> None:
    with TestClient(profiles.app) as client:
        client.portal.call(profiles.kit.run_stars)  # type: ignore[union-attr]

        response = client.get("/feeds/players/1.json")

    assert response.status_code == 200
    assert PlayerFeed.model_validate_json(response.content).id == "1"
    assert response.headers["content-type"] == "application/json"
    assert response.headers["cache-control"] == CACHE_CONTROL
    etag = response.headers["etag"]
    assert etag.startswith('"') and etag.endswith('"')


def test_responds_304_when_the_player_etag_matches(profiles: Profiles) -> None:
    with TestClient(profiles.app) as client:
        client.portal.call(profiles.kit.run_stars)  # type: ignore[union-attr]
        first = client.get("/feeds/players/1.json")

        response = client.get(
            "/feeds/players/1.json", headers={"If-None-Match": first.headers["etag"]}
        )

    assert response.status_code == 304
    assert response.content == b""


def test_responds_404_for_a_player_in_no_roster_and_503_before_the_rosters_are_fetched(
    profiles: Profiles,
) -> None:
    with TestClient(profiles.app) as client:
        before = client.get("/feeds/players/nobody.json")
        client.portal.call(profiles.kit.run_stars)  # type: ignore[union-attr]
        after = client.get("/feeds/players/nobody.json")

    assert before.status_code == 503
    assert isinstance(before.json()["detail"], str)
    assert after.status_code == 404
    assert isinstance(after.json()["detail"], str)
    assert profiles.kit.requests == []


def test_responds_503_for_a_player_through_the_app_with_no_jobs(
    tmp_path: Path,
) -> None:
    with make_client(tmp_path) as client:
        response = client.get("/feeds/players/1.json")

    assert response.status_code == 503
    assert isinstance(response.json()["detail"], str)


def test_a_team_and_a_player_request_record_presence(profiles: Profiles) -> None:
    now = profiles.kit.clock[0]
    with TestClient(profiles.app) as client:
        assert not profiles.presence.present(now)
        client.get("/feeds/teams/xyz.json")
        assert profiles.presence.present(now)

    second = profiles.kit.clock[0] + dt.timedelta(hours=1)
    with TestClient(profiles.app) as client:
        assert not profiles.presence.present(second)
        profiles.kit.clock[0] = second
        client.get("/feeds/players/nobody.json")
        assert profiles.presence.present(second)


class Standings:
    """An app with the feeds router and the standings kind over the standings kit's fakes."""

    def __init__(self, path: Path) -> None:
        self.kit = StandingsKit(path)
        self.app = FastAPI()
        self.app.include_router(feeds_router.router)
        self.app.state.settings = self.kit.settings
        self.app.state.presence = Presence(clock=lambda: self.kit.clock[0])
        self.app.state.games_job = self.kit.games
        self.app.state.feed_cache = self.kit.cache


@pytest.fixture
def standings(tmp_path: Path) -> Iterator[Standings]:
    with respx.mock:
        yield Standings(tmp_path)


def test_serves_the_standings_feed_with_cache_control_and_an_etag(
    standings: Standings,
) -> None:
    with TestClient(standings.app) as client:
        response = client.get("/feeds/standings.json")

    assert response.status_code == 200
    feed = StandingsFeed.model_validate_json(response.content)
    assert len(feed.conferences) == 2 and len(feed.divisions) >= 1
    assert response.headers["content-type"] == "application/json"
    assert response.headers["cache-control"] == CACHE_CONTROL
    etag = response.headers["etag"]
    assert etag.startswith('"') and etag.endswith('"')


def test_responds_304_when_the_standings_etag_matches(standings: Standings) -> None:
    with TestClient(standings.app) as client:
        first = client.get("/feeds/standings.json")

        response = client.get(
            "/feeds/standings.json", headers={"If-None-Match": first.headers["etag"]}
        )

    assert response.status_code == 304
    assert response.content == b""


def test_responds_503_with_a_json_error_when_the_standings_read_fails_with_no_stored_feed(
    standings: Standings,
) -> None:
    standings.kit.failing.add("standings")
    with TestClient(standings.app) as client:
        response = client.get("/feeds/standings.json")

    assert response.status_code == 503
    assert isinstance(response.json()["detail"], str)


def test_keeps_serving_the_stored_standings_when_a_rebuild_fails(
    standings: Standings,
) -> None:
    with TestClient(standings.app) as client:
        first = client.get("/feeds/standings.json")
        standings.kit.clock[0] += FEED_LIFETIME
        standings.kit.failing.add("standings")

        response = client.get("/feeds/standings.json")

    assert response.status_code == 200
    assert response.content == first.content


class Search:
    """An app with the feeds router and the search kind over the search kit's fakes."""

    def __init__(self, path: Path) -> None:
        self.kit = SearchKit(path)
        self.app = FastAPI()
        self.app.include_router(feeds_router.router)
        self.app.state.settings = self.kit.settings
        self.app.state.presence = Presence(clock=lambda: self.kit.clock[0])
        self.app.state.games_job = self.kit.games
        self.app.state.feed_cache = self.kit.cache

    def fetch_rosters(self) -> None:
        now = self.kit.clock[0]
        asyncio.run(self.kit.run_stars(now - dt.timedelta(hours=1)))
        self.kit.clock[0] = now


@pytest.fixture
def search(tmp_path: Path) -> Iterator[Search]:
    with respx.mock:
        yield Search(tmp_path)


def test_serves_the_search_feed_with_cache_control_and_an_etag(
    search: Search,
) -> None:
    search.fetch_rosters()
    with TestClient(search.app) as client:
        response = client.get("/feeds/search.json")

    assert response.status_code == 200
    feed = SearchFeed.model_validate_json(response.content)
    assert len(feed.teams) == 30 and len(feed.players) == 60
    assert response.headers["content-type"] == "application/json"
    assert response.headers["cache-control"] == CACHE_CONTROL
    etag = response.headers["etag"]
    assert etag.startswith('"') and etag.endswith('"')


def test_responds_304_when_the_search_etag_matches(search: Search) -> None:
    search.fetch_rosters()
    with TestClient(search.app) as client:
        first = client.get("/feeds/search.json")

        response = client.get(
            "/feeds/search.json", headers={"If-None-Match": first.headers["etag"]}
        )

    assert response.status_code == 304
    assert response.content == b""


def test_responds_503_with_a_json_error_before_the_rosters_are_fetched(
    search: Search,
) -> None:
    with TestClient(search.app) as client:
        response = client.get("/feeds/search.json")

    assert response.status_code == 503
    assert isinstance(response.json()["detail"], str)
    assert search.kit.requests == []


def test_responds_503_when_the_search_standings_read_fails_with_no_stored_feed(
    search: Search,
) -> None:
    search.fetch_rosters()
    search.kit.failing.add("standings")
    with TestClient(search.app) as client:
        response = client.get("/feeds/search.json")

    assert response.status_code == 503
    assert isinstance(response.json()["detail"], str)


def test_keeps_serving_the_stored_search_feed_when_a_rebuild_fails(
    search: Search,
) -> None:
    search.fetch_rosters()
    with TestClient(search.app) as client:
        first = client.get("/feeds/search.json")
        search.kit.clock[0] += FEED_LIFETIME
        search.kit.failing.add("standings")

        response = client.get("/feeds/search.json")

    assert response.status_code == 200
    assert response.content == first.content


class Cup:
    """An app with the feeds router and the Cup kind over the Cup kit's fakes."""

    def __init__(self, path: Path) -> None:
        self.kit = CupKit(path)
        self.app = FastAPI()
        self.app.include_router(feeds_router.router)
        self.app.state.settings = self.kit.settings
        self.app.state.presence = Presence(clock=lambda: self.kit.clock[0])
        self.app.state.games_job = self.kit.games
        self.app.state.feed_cache = self.kit.cache


@pytest.fixture
def cup(tmp_path: Path) -> Iterator[Cup]:
    with respx.mock:
        yield Cup(tmp_path)


def test_serves_the_cup_feed_with_cache_control_and_an_etag(cup: Cup) -> None:
    with TestClient(cup.app) as client:
        response = client.get("/feeds/cup.json")

    assert response.status_code == 200
    feed = CupFeed.model_validate_json(response.content)
    assert feed.drawn and len(feed.groups) == 6
    assert response.headers["content-type"] == "application/json"
    assert response.headers["cache-control"] == CACHE_CONTROL
    etag = response.headers["etag"]
    assert etag.startswith('"') and etag.endswith('"')


def test_responds_304_when_the_cup_etag_matches(cup: Cup) -> None:
    with TestClient(cup.app) as client:
        first = client.get("/feeds/cup.json")

        response = client.get(
            "/feeds/cup.json", headers={"If-None-Match": first.headers["etag"]}
        )

    assert response.status_code == 304
    assert response.content == b""


def test_responds_503_when_a_cup_group_read_fails_with_no_stored_feed(cup: Cup) -> None:
    cup.kit.failing.add("table/eastA")
    with TestClient(cup.app) as client:
        response = client.get("/feeds/cup.json")

    assert response.status_code == 503
    assert isinstance(response.json()["detail"], str)


def test_responds_503_before_the_season_is_known(cup: Cup) -> None:
    cup.kit.stars.season = None
    with TestClient(cup.app) as client:
        response = client.get("/feeds/cup.json")

    assert response.status_code == 503
    assert cup.kit.calls == []


class Playoffs:
    """An app with the feeds router and the playoffs kind over the playoffs kit's fakes."""

    def __init__(self, path: Path) -> None:
        self.kit = PlayoffsKit(path)
        self.app = FastAPI()
        self.app.include_router(feeds_router.router)
        self.app.state.settings = self.kit.settings
        self.app.state.presence = Presence(clock=lambda: self.kit.clock[0])
        self.app.state.games_job = self.kit.games
        self.app.state.feed_cache = self.kit.cache


@pytest.fixture
def playoffs(tmp_path: Path) -> Iterator[Playoffs]:
    with respx.mock:
        yield Playoffs(tmp_path)


def test_serves_the_playoffs_feed_with_cache_control_and_an_etag(
    playoffs: Playoffs,
) -> None:
    with TestClient(playoffs.app) as client:
        response = client.get("/feeds/playoffs.json")

    assert response.status_code == 200
    feed = PlayoffsFeed.model_validate_json(response.content)
    assert len(feed.bracket) == 15
    assert response.headers["content-type"] == "application/json"
    assert response.headers["cache-control"] == CACHE_CONTROL
    etag = response.headers["etag"]
    assert etag.startswith('"') and etag.endswith('"')


def test_responds_304_when_the_playoffs_etag_matches(playoffs: Playoffs) -> None:
    with TestClient(playoffs.app) as client:
        first = client.get("/feeds/playoffs.json")

        response = client.get(
            "/feeds/playoffs.json", headers={"If-None-Match": first.headers["etag"]}
        )

    assert response.status_code == 304
    assert response.content == b""


def test_responds_503_when_a_season_type_read_fails_with_nothing_stored(
    playoffs: Playoffs,
) -> None:
    playoffs.kit.failing.add("type/5")
    with TestClient(playoffs.app) as client:
        response = client.get("/feeds/playoffs.json")

    assert response.status_code == 503
    assert isinstance(response.json()["detail"], str)


def test_responds_503_before_the_season_or_the_rosters_are_known(
    playoffs: Playoffs,
) -> None:
    with TestClient(playoffs.app) as client:
        playoffs.kit.stars.season = None
        assert client.get("/feeds/playoffs.json").status_code == 503
        playoffs.kit.stars.season = 2027
        playoffs.kit.stars.ready = False
        assert client.get("/feeds/playoffs.json").status_code == 503

    assert playoffs.kit.calls == []


def test_keeps_serving_the_stored_playoffs_feed_when_a_rebuild_fails(
    playoffs: Playoffs,
) -> None:
    with TestClient(playoffs.app) as client:
        first = client.get("/feeds/playoffs.json")
        playoffs.kit.failing.add("standings")
        playoffs.kit.clock[0] = playoffs.kit.clock[0] + FEED_LIFETIME

        response = client.get("/feeds/playoffs.json")

    assert response.status_code == 200
    assert response.content == first.content


class Finals:
    """An app with the feeds router and the playoffs finals kind over the finals kit's fakes."""

    def __init__(self, path: Path) -> None:
        self.kit = FinalsKit(path)
        self.app = FastAPI()
        self.app.include_router(feeds_router.router)
        self.app.state.settings = self.kit.settings
        self.app.state.presence = Presence(clock=lambda: self.kit.clock[0])
        self.app.state.games_job = self.kit.games
        self.app.state.feed_cache = self.kit.cache


@pytest.fixture
def finals(tmp_path: Path) -> Iterator[Finals]:
    with respx.mock:
        yield Finals(tmp_path)


def test_serves_the_playoffs_finals_feed_with_cache_control_and_an_etag(
    finals: Finals,
) -> None:
    with TestClient(finals.app) as client:
        response = client.get("/feeds/playoffs/finals.json")

    assert response.status_code == 200
    feed = PlayoffsFinalsFeed.model_validate_json(response.content)
    assert len(feed.games) == 4
    assert response.headers["content-type"] == "application/json"
    assert response.headers["cache-control"] == CACHE_CONTROL
    etag = response.headers["etag"]
    assert etag.startswith('"') and etag.endswith('"')


def test_responds_304_when_the_playoffs_finals_etag_matches(finals: Finals) -> None:
    with TestClient(finals.app) as client:
        first = client.get("/feeds/playoffs/finals.json")

        response = client.get(
            "/feeds/playoffs/finals.json",
            headers={"If-None-Match": first.headers["etag"]},
        )

    assert response.status_code == 304
    assert response.content == b""


def test_responds_404_when_the_finals_has_no_game_and_reads_no_finals_source(
    finals: Finals,
) -> None:
    finals.kit.load([g for g in postseason() if not g.game.id.startswith("finals")])
    with TestClient(finals.app) as client:
        response = client.get("/feeds/playoffs/finals.json")

    assert response.status_code == 404
    assert response.json() == {"detail": "feed not found"}
    prefixes = ("detail/", "sections/", "plays/", "player/", "finals-record/", "stats/")
    assert not [n for n in finals.kit.calls if n.startswith(prefixes)]


def test_responds_503_when_the_playoffs_feed_cannot_be_built_with_nothing_stored(
    finals: Finals,
) -> None:
    finals.kit.failing.add("type/5")
    with TestClient(finals.app) as client:
        response = client.get("/feeds/playoffs/finals.json")

    assert response.status_code == 503
    assert isinstance(response.json()["detail"], str)
    assert not [n for n in finals.kit.calls if n.startswith("detail/")]


def test_keeps_serving_the_stored_playoffs_finals_feed_when_a_rebuild_fails(
    finals: Finals,
) -> None:
    finals.kit.load(postseason("TBT", scheduled=2))
    with TestClient(finals.app) as client:
        first = client.get("/feeds/playoffs/finals.json")
        finals.kit.failing.add("standings")
        finals.kit.clock[0] = finals.kit.clock[0] + FEED_LIFETIME

        response = client.get("/feeds/playoffs/finals.json")

    assert response.status_code == 200
    assert response.content == first.content


class Matchup:
    """An app with the feeds router and the Cup matchup kind over the matchup kit's fakes."""

    def __init__(self, path: Path) -> None:
        self.kit = MatchupKit(path)
        self.app = FastAPI()
        self.app.include_router(feeds_router.router)
        self.app.state.settings = self.kit.settings
        self.app.state.presence = Presence(clock=lambda: self.kit.clock[0])
        self.app.state.games_job = self.kit.games
        self.app.state.feed_cache = self.kit.cache


@pytest.fixture
def matchup(tmp_path: Path) -> Iterator[Matchup]:
    with respx.mock:
        yield Matchup(tmp_path)


@pytest.mark.parametrize("slot_id", [slot.value for slot in SlotId])
def test_serves_a_matchup_feed_for_each_slot_with_cache_control_and_an_etag(
    matchup: Matchup, slot_id: str
) -> None:
    with TestClient(matchup.app) as client:
        response = client.get(f"/feeds/cup/matchups/{slot_id}.json")

    assert response.status_code == 200
    assert CupMatchupFeed.model_validate_json(response.content).id.value == slot_id
    assert response.headers["content-type"] == "application/json"
    assert response.headers["cache-control"] == CACHE_CONTROL
    etag = response.headers["etag"]
    assert etag.startswith('"') and etag.endswith('"')


def test_responds_304_when_the_matchup_etag_matches(matchup: Matchup) -> None:
    url = "/feeds/cup/matchups/east-qf-1.json"
    with TestClient(matchup.app) as client:
        first = client.get(url)

        response = client.get(url, headers={"If-None-Match": first.headers["etag"]})

    assert response.status_code == 304
    assert response.content == b""


@pytest.mark.parametrize(
    "slot_id", ["east-qf-3", "league", "EAST-QF-1", "east-qf-1%0A"]
)
def test_responds_404_for_an_unknown_slot_id_with_no_source_request(
    matchup: Matchup, slot_id: str
) -> None:
    with TestClient(matchup.app) as client:
        response = client.get(f"/feeds/cup/matchups/{slot_id}.json")

    assert response.status_code == 404
    assert isinstance(response.json()["detail"], str)
    assert matchup.kit.calls == []


def test_responds_503_for_a_matchup_before_the_season_is_known(
    matchup: Matchup,
) -> None:
    matchup.kit.stars.season = None
    with TestClient(matchup.app) as client:
        response = client.get("/feeds/cup/matchups/east-qf-1.json")

    assert response.status_code == 503
    assert matchup.kit.calls == []


def test_responds_503_when_a_matchup_roster_read_fails_with_nothing_stored(
    matchup: Matchup,
) -> None:
    matchup.kit.failing.add("roster/ATL")
    with TestClient(matchup.app) as client:
        response = client.get("/feeds/cup/matchups/east-qf-1.json")

    assert response.status_code == 503
    assert isinstance(response.json()["detail"], str)


class AllStar:
    """An app with the feeds router and the All-Star kind over the All-Star kit's fakes."""

    def __init__(self, path: Path) -> None:
        self.kit = AllStarKit(path)
        asyncio.run(self.kit.discover())
        self.app = FastAPI()
        self.app.include_router(feeds_router.router)
        self.app.state.settings = self.kit.settings
        self.app.state.presence = Presence(clock=lambda: self.kit.clock[0])
        self.app.state.games_job = self.kit.games
        self.app.state.feed_cache = self.kit.cache


@pytest.fixture
def all_star(tmp_path: Path) -> Iterator[AllStar]:
    with respx.mock:
        yield AllStar(tmp_path)


def test_serves_the_all_star_feed_with_cache_control_and_an_etag(
    all_star: AllStar,
) -> None:
    with TestClient(all_star.app) as client:
        response = client.get("/feeds/all-star.json")

    assert response.status_code == 200
    feed = AllStarFeed.model_validate_json(response.content)
    assert feed.edition.date == ALL_STAR_DAY
    assert len(feed.edition.games) == 4
    assert response.headers["content-type"] == "application/json"
    assert response.headers["cache-control"] == CACHE_CONTROL
    etag = response.headers["etag"]
    assert etag.startswith('"') and etag.endswith('"')


def test_responds_304_when_the_all_star_etag_matches(all_star: AllStar) -> None:
    with TestClient(all_star.app) as client:
        first = client.get("/feeds/all-star.json")

        response = client.get(
            "/feeds/all-star.json", headers={"If-None-Match": first.headers["etag"]}
        )

    assert response.status_code == 304
    assert response.content == b""


def test_responds_503_when_the_all_star_day_read_fails_with_nothing_stored(
    all_star: AllStar,
) -> None:
    all_star.kit.failing.add(f"day/{ALL_STAR_DAY.isoformat()}")
    with TestClient(all_star.app) as client:
        response = client.get("/feeds/all-star.json")

    assert response.status_code == 503
    assert isinstance(response.json()["detail"], str)


def test_responds_503_before_the_season_the_rosters_or_the_discovery_are_known(
    all_star: AllStar,
) -> None:
    with TestClient(all_star.app) as client:
        all_star.kit.stars.season = None
        assert client.get("/feeds/all-star.json").status_code == 503
        all_star.kit.stars.season = 2027
        all_star.kit.stars.ready = False
        assert client.get("/feeds/all-star.json").status_code == 503
        all_star.kit.stars.ready = True
        all_star.kit.discovery._ready_season = None
        assert client.get("/feeds/all-star.json").status_code == 503

    assert all_star.kit.calls == []


def test_keeps_serving_the_stored_all_star_feed_when_a_rebuild_fails(
    all_star: AllStar,
) -> None:
    all_star.kit.days[ALL_STAR_DAY] = all_star.kit.days[ALL_STAR_DAY][:1]
    with TestClient(all_star.app) as client:
        first = client.get("/feeds/all-star.json")
        all_star.kit.failing.add(f"day/{ALL_STAR_DAY.isoformat()}")
        all_star.kit.clock[0] = all_star.kit.clock[0] + dt.timedelta(minutes=1)

        response = client.get("/feeds/all-star.json")

    assert response.status_code == 200
    assert response.content == first.content


class Calendar:
    """An app with the feeds router and the calendar kind over the calendar kit's fakes."""

    def __init__(self, path: Path) -> None:
        self.kit = CalendarKit(path)
        self.app = FastAPI()
        self.app.include_router(feeds_router.router)
        self.app.state.settings = self.kit.settings
        self.app.state.presence = Presence(clock=lambda: self.kit.clock[0])
        self.app.state.feed_cache = self.kit.cache
        self.app.state.calendar_feeds = self.kit.calendars


@pytest.fixture
def calendar(tmp_path: Path) -> Calendar:
    return Calendar(tmp_path)


def test_serves_the_calendar_feed_with_cache_control_and_an_etag(
    calendar: Calendar,
) -> None:
    with TestClient(calendar.app) as client:
        response = client.get("/feeds/seasons/2027/calendar.json")

    assert response.status_code == 200
    feed = CalendarFeed.model_validate_json(response.content)
    assert feed.season == 2027
    assert feed.season_label == "2026-27"
    assert response.headers["content-type"] == "application/json"
    assert response.headers["cache-control"] == CACHE_CONTROL
    etag = response.headers["etag"]
    assert etag.startswith('"') and etag.endswith('"')


def test_responds_304_when_the_calendar_etag_matches(calendar: Calendar) -> None:
    with TestClient(calendar.app) as client:
        first = client.get("/feeds/seasons/2027/calendar.json")

        response = client.get(
            "/feeds/seasons/2027/calendar.json",
            headers={"If-None-Match": first.headers["etag"]},
        )

    assert response.status_code == 304
    assert response.content == b""


@pytest.mark.parametrize(
    "season", ["1993", "2028", "abc", "2027%0A", "Current", "currentx"]
)
def test_responds_404_for_a_calendar_season_that_does_not_exist(
    calendar: Calendar, season: str
) -> None:
    with TestClient(calendar.app) as client:
        response = client.get(f"/feeds/seasons/{season}/calendar.json")

    assert response.status_code == 404
    assert isinstance(response.json()["detail"], str)
    assert calendar.kit.calls == []


def test_serves_the_current_calendar_as_the_current_seasons_calendar(
    calendar: Calendar,
) -> None:
    with TestClient(calendar.app) as client:
        current = client.get("/feeds/seasons/current/calendar.json")
        year = client.get("/feeds/seasons/2027/calendar.json")

    assert current.status_code == 200
    assert current.content == year.content
    assert current.headers["etag"] == year.headers["etag"]
    assert current.headers["cache-control"] == CACHE_CONTROL
    feed = CalendarFeed.model_validate_json(current.content)
    assert feed.season == 2027
    assert feed.seasons[0].season == 2027
    assert calendar.kit.calls == [2027]


def test_responds_304_when_the_current_calendar_etag_is_the_season_etag(
    calendar: Calendar,
) -> None:
    with TestClient(calendar.app) as client:
        year = client.get("/feeds/seasons/2027/calendar.json")

        response = client.get(
            "/feeds/seasons/current/calendar.json",
            headers={"If-None-Match": year.headers["etag"]},
        )

    assert response.status_code == 304


def test_responds_503_for_the_current_calendar_while_the_season_is_not_known(
    calendar: Calendar,
) -> None:
    calendar.kit.stars.season = None
    with TestClient(calendar.app) as client:
        response = client.get("/feeds/seasons/current/calendar.json")

    assert response.status_code == 503
    assert response.json()["detail"] == "feed is not available yet"
    assert calendar.kit.calls == []


def test_responds_503_for_a_calendar_while_the_season_is_not_known(
    calendar: Calendar,
) -> None:
    calendar.kit.stars.season = None
    with TestClient(calendar.app) as client:
        response = client.get("/feeds/seasons/2027/calendar.json")

    assert response.status_code == 503
    assert calendar.kit.calls == []


def test_responds_503_for_a_calendar_when_the_read_fails_with_nothing_stored(
    calendar: Calendar,
) -> None:
    calendar.kit.failing = True
    with TestClient(calendar.app) as client:
        response = client.get("/feeds/seasons/2027/calendar.json")

    assert response.status_code == 503
    assert isinstance(response.json()["detail"], str)


class Day:
    """An app with the feeds router and the day kind over the day kit's fakes."""

    def __init__(self, path: Path) -> None:
        self.kit = DayKit(path)
        self.app = FastAPI()
        self.app.include_router(feeds_router.router)
        self.app.state.settings = self.kit.settings
        self.app.state.presence = Presence(clock=lambda: self.kit.clock[0])
        self.app.state.feed_cache = self.kit.cache


@pytest.fixture
def day(tmp_path: Path) -> Day:
    return Day(tmp_path)


def test_serves_the_day_feed_with_an_empty_games_list_for_a_day_with_no_event(
    day: Day,
) -> None:
    with TestClient(day.app) as client:
        response = client.get("/feeds/days/2026-09-01.json")

    assert response.status_code == 200
    feed = DayFeed.model_validate_json(response.content)
    assert feed.day.date == dt.date(2026, 9, 1)
    assert feed.day.games == []
    assert feed.season == 1999
    assert feed.season_label == "1998-99"
    assert response.headers["content-type"] == "application/json"
    assert response.headers["cache-control"] == CACHE_CONTROL
    etag = response.headers["etag"]
    assert etag.startswith('"') and etag.endswith('"')


def test_responds_304_when_the_day_etag_matches(day: Day) -> None:
    with TestClient(day.app) as client:
        first = client.get("/feeds/days/2026-09-01.json")

        response = client.get(
            "/feeds/days/2026-09-01.json",
            headers={"If-None-Match": first.headers["etag"]},
        )

    assert response.status_code == 304
    assert response.content == b""


@pytest.mark.parametrize(
    "feed_id", ["not-a-date", "1993-09-30", "2026-10-09", "2026-10-06"]
)
def test_responds_404_for_a_day_that_is_not_served(day: Day, feed_id: str) -> None:
    day.kit.store_games_feed(dt.date(2026, 10, 6))
    with TestClient(day.app) as client:
        response = client.get(f"/feeds/days/{feed_id}.json")

    assert response.status_code == 404
    assert isinstance(response.json()["detail"], str)
    assert day.kit.calls == []


def test_responds_503_for_a_day_when_the_read_fails_with_nothing_stored(
    day: Day,
) -> None:
    day.kit.failing = True
    with TestClient(day.app) as client:
        response = client.get("/feeds/days/2026-09-01.json")

    assert response.status_code == 503
    assert isinstance(response.json()["detail"], str)


class PastDetail:
    """An app with the feeds router, the day, game detail and past game detail
    kinds and a games job with no game, so it has loaded none."""

    def __init__(self, path: Path) -> None:
        self.kit = PastKit(path)

        async def no_games(
            client: SourceClient, day: dt.date, settings: Settings
        ) -> list[ScoreboardGame]:
            return []

        self.job = GamesJob(
            self.kit.settings,
            self.kit.store,
            self.kit.client,
            fetch_games=no_games,
            present=lambda now: True,
        )
        GameDetailFeeds(
            self.kit.settings,
            self.kit.store,
            self.kit.client,
            self.kit.cache,
            self.job,
        )
        self.app = FastAPI()
        self.app.include_router(feeds_router.router)
        self.app.state.settings = self.kit.settings
        self.app.state.presence = Presence(clock=lambda: self.kit.clock[0])
        self.app.state.games_job = self.job
        self.app.state.feed_cache = self.kit.cache

    def store_day(self, client: TestClient, *games: ScoreboardGame) -> None:
        client.portal.call(self.job.run, DAY_NOW)  # type: ignore[union-attr]
        client.portal.call(self.kit.store_day, *games)  # type: ignore[union-attr]


@pytest.fixture
def past(tmp_path: Path) -> PastDetail:
    return PastDetail(tmp_path)


def test_serves_a_past_game_detail_with_status_final_and_a_season_label_with_cache_control_and_etag(
    past: PastDetail,
) -> None:
    with TestClient(past.app) as client:
        past.store_day(client, day_game("1", GameStatus.FINAL))

        response = client.get("/feeds/games/1.json")

    assert response.status_code == 200
    feed = PastGameDetailFeed.model_validate_json(response.content)
    assert feed.id == "1" and feed.status is GameStatus.FINAL
    assert feed.season_label == "2004-05"
    assert response.headers["content-type"] == "application/json"
    assert response.headers["cache-control"] == CACHE_CONTROL
    etag = response.headers["etag"]
    assert etag.startswith('"') and etag.endswith('"')
    assert past.kit.section_calls == ["1"]


def test_responds_304_when_the_past_game_detail_etag_matches(past: PastDetail) -> None:
    with TestClient(past.app) as client:
        past.store_day(client, day_game("1", GameStatus.FINAL))
        first = client.get("/feeds/games/1.json")

        response = client.get(
            "/feeds/games/1.json", headers={"If-None-Match": first.headers["etag"]}
        )

    assert response.status_code == 304
    assert response.content == b""
    assert past.kit.section_calls == ["1"]


def test_responds_404_for_an_id_in_no_stored_day_and_outside_the_days_shown_with_no_source_request(
    past: PastDetail,
) -> None:
    with TestClient(past.app) as client:
        past.store_day(client, day_game("1", GameStatus.FINAL))

        response = client.get("/feeds/games/999.json")

    assert response.status_code == 404
    assert isinstance(response.json()["detail"], str)
    assert past.kit.section_calls == []


def test_responds_404_for_a_postponed_game_of_a_stored_day_with_no_source_request(
    past: PastDetail,
) -> None:
    with TestClient(past.app) as client:
        past.store_day(
            client,
            day_game("1", GameStatus.FINAL),
            day_game("2", GameStatus.POSTPONED),
        )

        response = client.get("/feeds/games/2.json")

    assert response.status_code == 404
    assert past.kit.section_calls == []


def test_responds_503_for_a_past_game_whose_build_fails_with_nothing_stored(
    past: PastDetail,
) -> None:
    with TestClient(past.app) as client:
        past.store_day(client, day_game("1", GameStatus.FINAL))
        past.kit.sections_failing = True

        response = client.get("/feeds/games/1.json")

    assert response.status_code == 503
    assert isinstance(response.json()["detail"], str)


def test_a_game_the_games_job_has_loaded_takes_the_games_path_with_a_null_season_label(
    tmp_path: Path,
) -> None:
    detail = Detail(tmp_path, GameStatus.SCHEDULED)
    settings = detail.app.state.settings
    store = StateStore(tmp_path)
    store.migrate()
    calls: list[str] = []

    async def sections(
        client: SourceClient, game_id: str, settings: Settings, fresh: object
    ) -> GameDetailSections:
        calls.append(game_id)
        return GameDetailSections.model_validate(
            {"venue": {"name": "Old"}, "season": 2005}
        )

    PastGameDetailFeeds(
        settings,
        store,
        create_client(store),
        detail.app.state.feed_cache,
        fetch_sections=sections,
    )
    stored = build_day_feed(
        DAY_NOW, PAST, 2026, [day_game("401", GameStatus.FINAL)], search_url
    )
    publish_by_id(tmp_path, DAY_KIND, DayFeed, PAST.isoformat(), stored)
    with TestClient(detail.app) as client:
        client.portal.call(detail.job.run, NOW)  # type: ignore[union-attr]
        assert detail.app.state.feed_cache.status(PAST_KIND, "401") is IdStatus.KNOWN

        response = client.get("/feeds/games/401.json")

    assert response.status_code == 200
    feed = GameDetailFeed.model_validate_json(response.content)
    assert feed.status is GameStatus.SCHEDULED and feed.venue.name == "Garden"
    assert feed.season_label is None
    assert calls == []


class SeasonApp:
    """An app with the feeds router over one season kit's cache."""

    def __init__(self, kit: Any) -> None:
        self.kit = kit
        self.app = FastAPI()
        self.app.include_router(feeds_router.router)
        self.app.state.settings = kit.settings
        self.app.state.presence = Presence(clock=lambda: kit.clock[0])
        self.app.state.feed_cache = kit.cache


@pytest.fixture
def season_standings(tmp_path: Path) -> SeasonApp:
    return SeasonApp(SeasonStandingsKit(tmp_path))


@pytest.fixture
def season_team(tmp_path: Path) -> SeasonApp:
    return SeasonApp(SeasonTeamKit(tmp_path))


@pytest.fixture
def season_player(tmp_path: Path) -> SeasonApp:
    return SeasonApp(SeasonPlayerKit(tmp_path))


SEASON_PATHS = {
    "standings": "/feeds/seasons/{season}/standings.json",
    "team": "/feeds/seasons/{season}/teams/okc.json",
    "player": "/feeds/seasons/{season}/players/77.json",
}
SEASON_FEEDS: dict[str, Any] = {
    "standings": StandingsFeed,
    "team": PastTeamFeed,
    "player": PastPlayerFeed,
}


def season_app(request: pytest.FixtureRequest, kind: str) -> SeasonApp:
    app: SeasonApp = request.getfixturevalue(f"season_{kind}")
    return app


@pytest.mark.parametrize("kind", SEASON_PATHS)
def test_serves_a_past_season_feed_with_cache_control_and_an_etag_and_answers_304(
    request: pytest.FixtureRequest, kind: str
) -> None:
    app = season_app(request, kind)
    path = SEASON_PATHS[kind].format(season="2004")
    with TestClient(app.app) as client:
        response = client.get(path)
        again = client.get(path, headers={"If-None-Match": response.headers["etag"]})

    assert response.status_code == 200
    SEASON_FEEDS[kind].model_validate_json(response.content)
    assert response.headers["content-type"] == "application/json"
    assert response.headers["cache-control"] == CACHE_CONTROL
    etag = response.headers["etag"]
    assert etag.startswith('"') and etag.endswith('"')
    assert again.status_code == 304
    assert again.content == b""


@pytest.mark.parametrize("kind", SEASON_PATHS)
@pytest.mark.parametrize("season", ["1993", "2027", "2028", "abc", "2004%0A", "02004"])
def test_responds_404_for_a_season_before_1994_the_current_or_a_future_one_or_not_a_number(
    request: pytest.FixtureRequest, kind: str, season: str
) -> None:
    app = season_app(request, kind)
    with TestClient(app.app) as client:
        response = client.get(SEASON_PATHS[kind].format(season=season))

    assert response.status_code == 404
    assert isinstance(response.json()["detail"], str)
    assert app.kit.calls == []


@pytest.mark.parametrize("kind", SEASON_PATHS)
def test_responds_503_for_a_season_feed_while_the_current_season_is_not_known(
    request: pytest.FixtureRequest, kind: str
) -> None:
    app = season_app(request, kind)
    app.kit.stars.season = None
    with TestClient(app.app) as client:
        response = client.get(SEASON_PATHS[kind].format(season="2004"))

    assert response.status_code == 503
    assert response.json()["detail"] == "feed is not available yet"
    assert app.kit.calls == []


@pytest.mark.parametrize("kind", SEASON_PATHS)
def test_responds_503_for_a_season_feed_whose_build_fails_with_nothing_stored(
    request: pytest.FixtureRequest, kind: str
) -> None:
    app = season_app(request, kind)
    app.kit.failing = True
    with TestClient(app.app) as client:
        response = client.get(SEASON_PATHS[kind].format(season="2004"))

    assert response.status_code == 503


def test_responds_404_for_a_season_team_path_of_a_franchise_with_no_team_that_season(
    season_team: SeasonApp,
) -> None:
    season_team.kit.missing = True
    with TestClient(season_team.app) as client:
        first = client.get("/feeds/seasons/2004/teams/okc.json")
        reads = len(season_team.kit.calls)
        second = client.get("/feeds/seasons/2004/teams/okc.json")

    assert first.status_code == 404
    assert second.status_code == 404
    assert len(season_team.kit.calls) == reads


def test_responds_404_for_an_upper_case_or_unknown_team_code_on_the_season_team_path(
    season_team: SeasonApp,
) -> None:
    with TestClient(season_team.app) as client:
        upper = client.get("/feeds/seasons/2004/teams/OKC.json")
        unknown = client.get("/feeds/seasons/2004/teams/xyz.json")

    assert upper.status_code == 404 and unknown.status_code == 404
    assert season_team.kit.calls == []


def test_the_current_player_path_serves_a_retired_player_known_from_a_past_feed(
    profiles: Profiles,
) -> None:
    kit = profiles.kit
    kit.past_known.add("retired1")
    kit.athletes["retired1"] = PlayerAthlete(
        active=False, entry=player("retired1", jersey=None)
    )
    with TestClient(profiles.app) as client:
        client.portal.call(kit.run_stars)  # type: ignore[union-attr]
        response = client.get("/feeds/players/retired1.json")
        unknown = client.get("/feeds/players/nobody.json")

    assert response.status_code == 200
    feed = PlayerFeed.model_validate_json(response.content)
    assert (feed.active, feed.team) == (False, None)
    assert unknown.status_code == 404


class SeasonCup:
    """An app with the feeds router and the Cup, Cup matchup and season Cup kinds
    over the season matchup kit's fakes."""

    def __init__(self, path: Path) -> None:
        self.kit = SeasonMatchupKit(path)
        self.app = FastAPI()
        self.app.include_router(feeds_router.router)
        self.app.state.settings = self.kit.settings
        self.app.state.presence = Presence(clock=lambda: self.kit.clock[0])
        self.app.state.games_job = self.kit.games
        self.app.state.feed_cache = self.kit.cache
        self.app.state.season_cup_feeds = self.kit.season_cups
        self.app.state.season_cup_matchup_feeds = self.kit.season_matchups


@pytest.fixture
def season_cup(tmp_path: Path) -> Iterator[SeasonCup]:
    with respx.mock:
        yield SeasonCup(tmp_path)


SEASON_CUP_PATHS = [
    "/feeds/seasons/{season}/cup.json",
    "/feeds/seasons/{season}/cup/matchups/east-qf-1.json",
]


@pytest.mark.parametrize("path", SEASON_CUP_PATHS)
def test_serves_the_cup_feeds_of_a_past_season_with_cache_control_and_an_etag(
    season_cup: SeasonCup, path: str
) -> None:
    url = path.format(season="2025")
    with TestClient(season_cup.app) as client:
        response = client.get(url)
        again = client.get(url, headers={"If-None-Match": response.headers["etag"]})

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    assert response.headers["cache-control"] == CACHE_CONTROL
    assert again.status_code == 304 and again.content == b""
    body = response.content
    if path.endswith("cup.json"):
        assert CupFeed.model_validate_json(body).season == "2024-25"
    else:
        assert CupMatchupFeed.model_validate_json(body).season == "2024-25"


@pytest.mark.parametrize("path", SEASON_CUP_PATHS)
@pytest.mark.parametrize("season", ["2023", "2028", "abc", "2025%0A", "02025"])
def test_responds_404_for_a_season_outside_the_cup_seasons_with_no_source_request(
    season_cup: SeasonCup, path: str, season: str
) -> None:
    with TestClient(season_cup.app) as client:
        response = client.get(path.format(season=season))

    assert response.status_code == 404
    assert isinstance(response.json()["detail"], str)
    assert season_cup.kit.calls == []


@pytest.mark.parametrize("season", ["2025", "2027"])
@pytest.mark.parametrize(
    "slot_id", ["east-qf-3", "league", "EAST-QF-1", "east-qf-1%0A"]
)
def test_responds_404_for_an_unknown_slot_on_the_season_matchup_path(
    season_cup: SeasonCup, season: str, slot_id: str
) -> None:
    with TestClient(season_cup.app) as client:
        response = client.get(f"/feeds/seasons/{season}/cup/matchups/{slot_id}.json")

    assert response.status_code == 404
    assert season_cup.kit.calls == []


def test_the_current_season_serves_the_current_cup_feeds_and_stores_no_season_feed(
    season_cup: SeasonCup,
) -> None:
    kit = season_cup.kit
    with TestClient(season_cup.app) as client:
        season = client.get("/feeds/seasons/2027/cup.json")
        current = client.get("/feeds/cup.json")
        season_matchup = client.get("/feeds/seasons/2027/cup/matchups/east-qf-1.json")
        current_matchup = client.get("/feeds/cup/matchups/east-qf-1.json")

    assert season.status_code == 200 and season_matchup.status_code == 200
    assert season.content == current.content
    assert season.headers["etag"] == current.headers["etag"]
    assert season_matchup.content == current_matchup.content
    assert season_matchup.headers["etag"] == current_matchup.headers["etag"]
    assert not (kit.path / "feeds" / "season-cup").exists()
    assert not (kit.path / "feeds" / "season-cup-matchups").exists()


@pytest.mark.parametrize("path", SEASON_CUP_PATHS)
@pytest.mark.parametrize("season", ["2025", "2027"])
def test_responds_503_on_the_season_cup_paths_while_the_season_is_not_known(
    season_cup: SeasonCup, path: str, season: str
) -> None:
    season_cup.kit.stars.season = None
    with TestClient(season_cup.app) as client:
        response = client.get(path.format(season=season))

    assert response.status_code == 503
    assert season_cup.kit.calls == []


@pytest.mark.parametrize("path", SEASON_CUP_PATHS)
def test_responds_503_when_a_past_cup_build_fails_with_nothing_stored(
    season_cup: SeasonCup, path: str
) -> None:
    season_cup.kit.failing.add("teams/eastA/2025")
    with TestClient(season_cup.app) as client:
        response = client.get(path.format(season="2025"))

    assert response.status_code == 503
    assert isinstance(response.json()["detail"], str)
