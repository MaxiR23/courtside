# api/tests/test_main.py
#
# Tests for the app factory: startup and CORS.
#
# Tested:
# - Wires the games job's final games into the stars job
# - Creates the data directory and state file on startup
# - Stops startup with the migration error when a state migration fails, leaving the state database empty
# - Allows a configured origin
# - Does not allow an origin outside the configuration
# - Refuses a preflight from an origin outside the configuration
# - Allows no origin when none is configured
# - Starts the scheduler with the app and stops it on shutdown, with the games and stars jobs each failing on its unconfigured source and the highlights job recording nothing without due games
# - Starts and stops the stars scheduler with the games scheduler
# - A stars run that never ends does not stop the games job
# - Does not start the schedulers when jobs are off
# - Wires the stars and highlights providers and the stars readiness check into the games job
# - Wires the games job, the feed cache, stars and highlights into the game detail feeds
# - Wires presence and the after-run hook into the games job
# - Wires the team and player feed kinds into the feed cache, the player feeds into app.state, and the cleanup into the stars job's after-run hook
# - Closes the HTTP client when the scheduler fails to stop
#
# What is covered:
# - Success response, refused cases, scheduler start and stop, error case (failed migration)
#
# Run with: cd api && .venv/bin/python -m pytest tests/test_main.py
#
# SEE: api/app/main.py

import asyncio
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from app import main
from app.jobs.game_detail_feed import GameDetailFeeds
from app.jobs.games import GamesJob
from app.jobs.highlights import HighlightsJob
from app.jobs.player_feed import PlayerFeeds
from app.jobs.presence import Presence
from app.jobs.scheduler import Scheduler
from app.jobs.stars import StarsJob
from app.main import create_app
from app.settings import Settings
from app.sources.http import create_client
from app.storage import state
from app.storage.state import MIGRATIONS, STATE_FILE, StateMigrationError, StateStore

ALLOWED = "https://allowed.example"
OTHER = "https://other.example"


def make_client(path: Path, origins: list[str]) -> TestClient:
    settings = Settings(  # type: ignore[call-arg]
        _env_file=None, data_dir=path, cors_origins=origins
    )
    return TestClient(create_app(settings, run_jobs=False))


def test_creates_the_data_directory_and_state_file_on_startup(
    tmp_path: Path,
) -> None:
    data_dir = tmp_path / "nested" / "data"

    with make_client(data_dir, []):
        pass

    assert (data_dir / STATE_FILE).is_file()


def test_stops_startup_when_a_state_migration_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        state, "MIGRATIONS", (*MIGRATIONS, ("INSERT INTO missing_table VALUES (1)",))
    )

    with (
        pytest.raises(
            StateMigrationError, match=f"state migration {len(MIGRATIONS) + 1} failed"
        ),
        make_client(tmp_path, []),
    ):
        pass

    with closing(sqlite3.connect(tmp_path / STATE_FILE)) as connection:
        assert connection.execute("PRAGMA user_version").fetchone() == (0,)
        assert connection.execute("SELECT name FROM sqlite_master").fetchall() == []


def test_allows_a_configured_origin(tmp_path: Path) -> None:
    with make_client(tmp_path, [ALLOWED]) as client:
        response = client.get("/health", headers={"Origin": ALLOWED})

    assert response.headers["access-control-allow-origin"] == ALLOWED


def test_does_not_allow_an_origin_outside_the_configuration(tmp_path: Path) -> None:
    with make_client(tmp_path, [ALLOWED]) as client:
        response = client.get("/health", headers={"Origin": OTHER})

    assert "access-control-allow-origin" not in response.headers


def test_refuses_a_preflight_from_an_origin_outside_the_configuration(
    tmp_path: Path,
) -> None:
    with make_client(tmp_path, [ALLOWED]) as client:
        response = client.options(
            "/health",
            headers={"Origin": OTHER, "Access-Control-Request-Method": "GET"},
        )

    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


def test_allows_no_origin_when_none_is_configured(tmp_path: Path) -> None:
    with make_client(tmp_path, []) as client:
        response = client.get("/health", headers={"Origin": ALLOWED})

    assert "access-control-allow-origin" not in response.headers


def test_starts_the_scheduler_with_the_app_and_stops_it_on_shutdown(
    tmp_path: Path,
) -> None:
    settings = Settings(_env_file=None, data_dir=tmp_path)  # type: ignore[call-arg]
    app = create_app(settings)

    with respx.mock, TestClient(app):
        assert app.state.scheduler.running
        assert app.state.stars_scheduler.running

    assert not app.state.scheduler.running
    assert not app.state.stars_scheduler.running
    states = StateStore(tmp_path).job_states()
    assert [state.name for state in states] == ["games", "stars"]
    games, stars = (state.last_failure_reason for state in states)
    assert games is not None and games.startswith("scoreboard:")
    assert stars is not None and stars.startswith("team_players:")


def test_a_stars_run_that_never_ends_does_not_stop_the_games_job(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class NeverEndingStars(StarsJob):
        async def run(self, now: Any) -> None:
            await asyncio.Event().wait()

    monkeypatch.setattr(main, "StarsJob", NeverEndingStars)
    settings = Settings(_env_file=None, data_dir=tmp_path)  # type: ignore[call-arg]
    app = create_app(settings)

    with respx.mock, TestClient(app):
        pass

    states = StateStore(tmp_path).job_states()
    assert [state.name for state in states] == ["games"]
    reason = states[0].last_failure_reason
    assert reason is not None and reason.startswith("scoreboard:")


def test_does_not_start_the_scheduler_when_jobs_are_off(tmp_path: Path) -> None:
    settings = Settings(_env_file=None, data_dir=tmp_path)  # type: ignore[call-arg]
    app = create_app(settings, run_jobs=False)

    with TestClient(app):
        assert not app.state.scheduler.running
        assert not app.state.stars_scheduler.running

    assert StateStore(tmp_path).job_states() == []


def test_wires_the_stars_and_highlights_providers_into_the_games_job(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    built: dict[str, Any] = {}

    class RecordingStars(StarsJob):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, **kwargs)
            built["stars"] = self

    class RecordingHighlights(HighlightsJob):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, **kwargs)
            built["highlights"] = self

    class RecordingGames(GamesJob):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, **kwargs)
            built["games_kwargs"] = kwargs

    monkeypatch.setattr(main, "StarsJob", RecordingStars)
    monkeypatch.setattr(main, "HighlightsJob", RecordingHighlights)
    monkeypatch.setattr(main, "GamesJob", RecordingGames)

    with make_client(tmp_path, []):
        pass

    kwargs = built["games_kwargs"]
    assert kwargs["stars"] == built["stars"].stars_of
    assert kwargs["stars_ready"] == built["stars"].has_every_star
    assert kwargs["highlights"] == built["highlights"].highlights_of
    assert kwargs["highlights_search_url"] == built["highlights"].search_url_of


def test_wires_the_games_jobs_final_games_into_the_stars_job(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    built: dict[str, Any] = {}
    sentinel: list[Any] = []

    class RecordingStars(StarsJob):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, **kwargs)
            built["stars_kwargs"] = kwargs

    class RecordingGames(GamesJob):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, **kwargs)
            built["games"] = self

    monkeypatch.setattr(main, "StarsJob", RecordingStars)
    monkeypatch.setattr(main, "GamesJob", RecordingGames)

    with make_client(tmp_path, []):
        monkeypatch.setattr(built["games"], "final_games", lambda: sentinel)
        assert built["stars_kwargs"]["final_games"]() is sentinel


def test_wires_the_games_job_cache_stars_and_highlights_into_the_game_detail_feeds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    built: dict[str, Any] = {}

    class RecordingStars(StarsJob):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, **kwargs)
            built["stars"] = self

    class RecordingHighlights(HighlightsJob):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, **kwargs)
            built["highlights"] = self

    class RecordingGames(GamesJob):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, **kwargs)
            built["games"] = self

    class RecordingDetail(GameDetailFeeds):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, **kwargs)
            built["detail_args"] = args
            built["detail_kwargs"] = kwargs

    monkeypatch.setattr(main, "StarsJob", RecordingStars)
    monkeypatch.setattr(main, "HighlightsJob", RecordingHighlights)
    monkeypatch.setattr(main, "GamesJob", RecordingGames)
    monkeypatch.setattr(main, "GameDetailFeeds", RecordingDetail)

    app = create_app(
        Settings(_env_file=None, data_dir=tmp_path),  # type: ignore[call-arg]
        run_jobs=False,
    )
    with TestClient(app):
        assert app.state.games_job is built["games"]
        assert isinstance(app.state.presence, Presence)
        assert "games" in app.state.feed_cache._kinds
        args = built["detail_args"]
        assert args[3] is app.state.feed_cache
        assert args[4] is built["games"]

    kwargs = built["detail_kwargs"]
    assert kwargs["stars"] == built["stars"].stars_of
    assert kwargs["highlights"] == built["highlights"].highlights_of
    assert kwargs["highlights_search_url"] == built["highlights"].search_url_of


def test_wires_presence_and_the_after_run_hook_into_the_games_job(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    built: dict[str, Any] = {}

    class RecordingDetail(GameDetailFeeds):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, **kwargs)
            built["detail"] = self
            self.hook_calls = 0

        def after_games_run(self) -> None:
            self.hook_calls += 1

    class RecordingGames(GamesJob):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, **kwargs)
            built["games_kwargs"] = kwargs

    monkeypatch.setattr(main, "GameDetailFeeds", RecordingDetail)
    monkeypatch.setattr(main, "GamesJob", RecordingGames)
    app = create_app(
        Settings(_env_file=None, data_dir=tmp_path),  # type: ignore[call-arg]
        run_jobs=False,
    )

    with TestClient(app):
        kwargs = built["games_kwargs"]
        assert kwargs["present"] == app.state.presence.present
        kwargs["after_run"]()

    assert built["detail"].hook_calls == 1


def test_wires_the_team_and_player_feed_kinds_and_the_cleanup_into_the_stars_job(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    built: dict[str, Any] = {}

    class RecordingStars(StarsJob):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, **kwargs)
            built["stars"] = self
            built["stars_kwargs"] = kwargs

    class RecordingPlayers(PlayerFeeds):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, **kwargs)
            built["players"] = self
            built["players_args"] = args
            self.cleanups = 0

        def after_stars_run(self) -> None:
            self.cleanups += 1

    monkeypatch.setattr(main, "StarsJob", RecordingStars)
    monkeypatch.setattr(main, "PlayerFeeds", RecordingPlayers)
    app = create_app(
        Settings(_env_file=None, data_dir=tmp_path),  # type: ignore[call-arg]
        run_jobs=False,
    )

    with TestClient(app):
        assert {"teams", "players", "games"} <= set(app.state.feed_cache._kinds)
        assert app.state.player_feeds is built["players"]
        args = built["players_args"]
        assert args[3] is app.state.feed_cache
        assert args[4] is app.state.games_job
        assert args[5] is built["stars"]
        built["stars_kwargs"]["after_run"]()

    assert built["players"].cleanups == 1


def test_closes_the_http_client_when_the_scheduler_fails_to_stop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = create_client(StateStore(tmp_path))
    closed: list[bool] = []
    close = client.aclose

    async def recording_close() -> None:
        closed.append(True)
        await close()

    async def failing_stop(self: Scheduler) -> None:
        raise RuntimeError("stop failed")

    monkeypatch.setattr(client, "aclose", recording_close)
    monkeypatch.setattr(main, "create_client", lambda store: client)
    monkeypatch.setattr(Scheduler, "stop", failing_stop)

    with pytest.raises(RuntimeError, match="stop failed"), make_client(tmp_path, []):
        pass

    assert closed == [True]
    assert isinstance(client, httpx.AsyncClient)
