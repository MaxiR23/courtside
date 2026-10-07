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
# - Serves a published game detail feed with Cache-Control and ETag
# - Responds 304 when the game detail ETag matches
# - Responds 404 with a JSON error for an unknown game and for an id that is not a game id
#
# What is covered:
# - Success response, documented failures (503, 404), edge case of an invalid publish
#
# Run with: cd api && .venv/bin/python -m pytest tests/routers/test_feeds.py
#
# SEE: api/app/routers/feeds.py

import datetime as dt
from pathlib import Path

from fastapi.testclient import TestClient

from app.feeds.game_detail import GameDetailFeed
from app.feeds.games import GamesFeed, GameStatus
from app.main import create_app
from app.routers.feeds import CACHE_CONTROL
from app.settings import Settings
from app.storage.feeds import publish_feed, publish_game_detail


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


def detail_feed(game_id: str = "401") -> GameDetailFeed:
    record = {"wins": 1, "losses": 1}
    return GameDetailFeed.model_validate(
        {
            "id": game_id,
            "status": "scheduled",
            "start_time": dt.datetime(2026, 1, 10, 12, 0, tzinfo=dt.UTC),
            "venue": {"name": "Garden", "city": "New York"},
            "away": {
                "code": "BOS",
                "name": "Celtics",
                "city": "Boston",
                "record": record,
            },
            "home": {
                "code": "NYK",
                "name": "Knicks",
                "city": "New York",
                "record": record,
            },
        }
    )


def invalid_detail_feed() -> GameDetailFeed:
    return detail_feed().model_copy(update={"status": GameStatus.FINAL})


def test_serves_a_published_game_detail_feed_with_cache_control_and_etag(
    tmp_path: Path,
) -> None:
    with make_client(tmp_path) as client:
        publish_game_detail(tmp_path, detail_feed("401"))

        response = client.get("/feeds/games/401.json")

    assert response.status_code == 200
    assert response.content == detail_feed("401").model_dump_json().encode("utf-8")
    assert response.headers["content-type"] == "application/json"
    assert response.headers["cache-control"] == CACHE_CONTROL
    etag = response.headers["etag"]
    assert etag.startswith('"') and etag.endswith('"')


def test_responds_304_when_the_game_detail_etag_matches(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        publish_game_detail(tmp_path, detail_feed("401"))
        first = client.get("/feeds/games/401.json")

        response = client.get(
            "/feeds/games/401.json", headers={"If-None-Match": first.headers["etag"]}
        )

    assert response.status_code == 304
    assert response.content == b""
    assert response.headers["cache-control"] == CACHE_CONTROL


def test_responds_404_with_a_json_error_for_an_unknown_game(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        response = client.get("/feeds/games/999.json")

    assert response.status_code == 404
    assert isinstance(response.json()["detail"], str)


def test_responds_404_for_an_id_that_is_not_a_game_id(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        response = client.get("/feeds/games/a.b.json")

    assert response.status_code == 404
