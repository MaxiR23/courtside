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
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.testclient import TestClient

from app.feeds.game_detail import GameDetailFeed
from app.feeds.games import GamesFeed, GameStatus, Star, Stars
from app.jobs.game_detail_feed import GameDetailFeeds
from app.jobs.games import GamesJob
from app.jobs.on_demand import MISSING_WAIT_SECONDS, FeedCache, FeedKind, IdStatus
from app.jobs.presence import Presence
from app.main import create_app
from app.routers import feeds as feeds_router
from app.routers.feeds import CACHE_CONTROL, serve_on_demand
from app.settings import Settings
from app.sources.game_detail import GameDetail, GameDetailSections
from app.sources.http import SourceClient, create_client
from app.sources.league_injuries import LeagueInjuries
from app.sources.scoreboard import ScoreboardGame
from app.sources.standings import LeagueStandings
from app.sources.team_schedule import TeamSchedule
from app.storage.feeds import publish_by_id, publish_feed
from app.storage.state import StateStore


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
