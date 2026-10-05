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
#
# What is covered:
# - Success response, refused cases
#
# Run with: cd api && .venv/bin/python -m pytest tests/test_main.py
#
# SEE: api/app/main.py

from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app
from app.settings import Settings
from app.storage.state import STATE_FILE

ALLOWED = "https://allowed.example"
OTHER = "https://other.example"


def make_client(path: Path, origins: list[str]) -> TestClient:
    settings = Settings(  # type: ignore[call-arg]
        _env_file=None, data_dir=path, cors_origins=origins
    )
    return TestClient(create_app(settings))


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
