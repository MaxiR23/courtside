# api/tests/routers/test_health.py
#
# Tests for the health endpoint.
#
# Tested:
# - Reports ok with no jobs before any run
# - Reports each job's last success and last failure
# - Reports job state recorded before an app restart
# - Reports the fallback reason after a failure recorded with an empty reason
# - Reports a feed's build failure with its last build in camelCase
# - Leaves out a feed that has built and never failed
#
# What is covered:
# - Success response (the endpoint documents no failures), job state in camelCase, restart
#
# Run with: cd api && .venv/bin/python -m pytest tests/routers/test_health.py
#
# SEE: api/app/routers/health.py

import datetime as dt
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app
from app.settings import Settings
from app.storage.state import NO_REASON, StateStore

SUCCESS = dt.datetime(2026, 1, 10, 12, 0, tzinfo=dt.UTC)
FAILURE = dt.datetime(2026, 1, 10, 13, 0, tzinfo=dt.UTC)


def make_client(path: Path) -> TestClient:
    settings = Settings(_env_file=None, data_dir=path)  # type: ignore[call-arg]
    return TestClient(create_app(settings, run_jobs=False))


def test_reports_ok_with_no_jobs_before_any_run(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "jobs": [], "feeds": []}


def test_reports_each_jobs_last_success_and_last_failure(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        store = StateStore(tmp_path)
        store.record_success("games", SUCCESS)
        store.record_failure("games", FAILURE, "source down")

        response = client.get("/health")

    assert response.json()["jobs"] == [
        {
            "name": "games",
            "lastSuccess": "2026-01-10T12:00:00Z",
            "lastFailure": "2026-01-10T13:00:00Z",
            "lastFailureReason": "source down",
        }
    ]


def test_reports_job_state_recorded_before_an_app_restart(tmp_path: Path) -> None:
    with make_client(tmp_path):
        StateStore(tmp_path).record_failure("games", FAILURE, "source down")

    with make_client(tmp_path) as client:
        response = client.get("/health")

    assert response.json()["jobs"][0]["lastFailureReason"] == "source down"


def test_reports_the_fallback_reason_for_a_failure_with_an_empty_reason(
    tmp_path: Path,
) -> None:
    with make_client(tmp_path) as client:
        StateStore(tmp_path).record_failure("games", FAILURE, str(TimeoutError()))

        response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["jobs"][0]["lastFailureReason"] == NO_REASON


def test_reports_a_feeds_build_failure_with_its_last_build(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        store = StateStore(tmp_path)
        store.record_build("players", "p1", SUCCESS)
        store.record_build_failure("players", "p1", FAILURE, "source down")

        response = client.get("/health")

    assert response.json()["feeds"] == [
        {
            "kind": "players",
            "feedId": "p1",
            "lastBuild": "2026-01-10T12:00:00Z",
            "lastFailure": "2026-01-10T13:00:00Z",
            "lastFailureReason": "source down",
        }
    ]


def test_leaves_out_a_feed_that_has_built_and_never_failed(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        StateStore(tmp_path).record_build("players", "p1", SUCCESS)

        response = client.get("/health")

    assert response.json()["feeds"] == []
