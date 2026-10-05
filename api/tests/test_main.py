# api/tests/test_main.py
#
# Tests for the app factory: startup and CORS.
#
# Tested:
# - Creates the data directory and state file on startup
# - Allows a configured origin
# - Does not allow an origin outside the configuration
# - Refuses a preflight from an origin outside the configuration
# - Allows no origin when none is configured
# - Starts the scheduler with the app and stops it on shutdown, with the games and stars jobs each failing on its unconfigured source and the highlights job recording nothing without due games
# - Does not start the scheduler when jobs are off
# - Wires the stars and highlights providers into the games job
# - Closes the HTTP client when the scheduler fails to stop
#
# What is covered:
# - Success response, refused cases, scheduler start and stop
#
# Run with: cd api && .venv/bin/python -m pytest tests/test_main.py
#
# SEE: api/app/main.py

from pathlib import Path
from typing import Any

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from app import main
from app.jobs.games import GamesJob
from app.jobs.highlights import HighlightsJob
from app.jobs.scheduler import Scheduler
from app.jobs.stars import StarsJob
from app.main import create_app
from app.settings import Settings
from app.sources.http import create_client
from app.storage.state import STATE_FILE, StateStore

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

    assert not app.state.scheduler.running
    states = StateStore(tmp_path).job_states()
    assert [state.name for state in states] == ["games", "stars"]
    games, stars = (state.last_failure_reason for state in states)
    assert games is not None and games.startswith("scoreboard:")
    assert stars is not None and stars.startswith("team_players:")


def test_does_not_start_the_scheduler_when_jobs_are_off(tmp_path: Path) -> None:
    settings = Settings(_env_file=None, data_dir=tmp_path)  # type: ignore[call-arg]
    app = create_app(settings, run_jobs=False)

    with TestClient(app):
        assert not app.state.scheduler.running

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
    assert kwargs["highlights"] == built["highlights"].highlights_of
    assert kwargs["highlights_search_url"] == built["highlights"].search_url_of


def test_closes_the_http_client_when_the_scheduler_fails_to_stop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = create_client()
    closed: list[bool] = []
    close = client.aclose

    async def recording_close() -> None:
        closed.append(True)
        await close()

    async def failing_stop(self: Scheduler) -> None:
        raise RuntimeError("stop failed")

    monkeypatch.setattr(client, "aclose", recording_close)
    monkeypatch.setattr(main, "create_client", lambda: client)
    monkeypatch.setattr(Scheduler, "stop", failing_stop)

    with pytest.raises(RuntimeError, match="stop failed"), make_client(tmp_path, []):
        pass

    assert closed == [True]
    assert isinstance(client, httpx.AsyncClient)
