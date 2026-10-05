# api/tests/routers/test_feeds.py
#
# Tests for the feed endpoint.
#
# Tested:
# - Serves the published games feed with Cache-Control and ETag
# - Changes the ETag when the feed changes
# - Responds 503 with a JSON error before the first publication
# - Keeps serving the last valid feed after an invalid publish
#
# What is covered:
# - Success response, documented failure (503), edge case of an invalid publish
#
# Run with: cd api && .venv/bin/python -m pytest tests/routers/test_feeds.py
#
# SEE: api/app/routers/feeds.py

import datetime as dt
from pathlib import Path

from fastapi.testclient import TestClient

from app.feeds.games import GamesFeed
from app.main import create_app
from app.routers.feeds import CACHE_CONTROL
from app.settings import Settings
from app.storage.feeds import publish_feed


def make_client(path: Path) -> TestClient:
    settings = Settings(_env_file=None, data_dir=path)  # type: ignore[call-arg]
    return TestClient(create_app(settings))


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
