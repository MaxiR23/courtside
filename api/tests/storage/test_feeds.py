# api/tests/storage/test_feeds.py
#
# Tests for the feed writer and reader.
#
# Tested:
# - Publishes a valid feed
# - Never writes an invalid feed
# - Keeps the last valid feed when an invalid one is published
# - Logs the reason of a rejected feed
# - Leaves no temporary file behind
# - Keeps the last valid feed when the write fails
# - Reads nothing before the first publication
# - Publishes a game detail feed under games by its id
# - Never writes an invalid game detail feed and keeps the last valid one
# - Refuses a game detail feed whose id is not a game id
# - Reads no game detail for an unknown or unsafe id
# - Lists the published game details without temporary files
# - Deletes a game detail and ignores one that is missing
#
# What is covered:
# - Happy path, error cases (invalid feed, write failure), edge cases (no temporary file, nothing published)
#
# Run with: cd api && .venv/bin/python -m pytest tests/storage/test_feeds.py
#
# SEE: api/app/storage/feeds.py

import datetime as dt
import logging
import os
from pathlib import Path

import pytest

from app.feeds.game_detail import GameDetailFeed
from app.feeds.games import GamesFeed, GameStatus
from app.storage.feeds import (
    delete_game_detail,
    publish_feed,
    publish_game_detail,
    published_game_details,
    read_feed,
    read_game_detail,
)

GENERATED_AT = dt.datetime(2026, 1, 10, 12, 0, tzinfo=dt.UTC)


def valid_feed() -> GamesFeed:
    return GamesFeed(generated_at=GENERATED_AT, days=[])


def invalid_feed() -> GamesFeed:
    return GamesFeed.model_construct(
        generated_at=dt.datetime(2026, 1, 10, 12, 0, tzinfo=dt.UTC).replace(
            tzinfo=None
        ),
        days=[],
    )


def test_publishes_a_valid_feed(tmp_path: Path) -> None:
    feed = valid_feed()

    assert publish_feed(tmp_path, "games", feed) is True
    assert read_feed(tmp_path, "games") == feed.model_dump_json().encode("utf-8")


def test_never_writes_an_invalid_feed(tmp_path: Path) -> None:
    assert publish_feed(tmp_path, "games", invalid_feed()) is False
    assert not (tmp_path / "feeds" / "games.json").exists()


def test_keeps_the_last_valid_feed_when_an_invalid_one_is_published(
    tmp_path: Path,
) -> None:
    publish_feed(tmp_path, "games", valid_feed())
    before = read_feed(tmp_path, "games")

    assert publish_feed(tmp_path, "games", invalid_feed()) is False
    assert read_feed(tmp_path, "games") == before


def test_logs_the_reason_of_a_rejected_feed(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.ERROR):
        publish_feed(tmp_path, "games", invalid_feed())

    assert "games" in caplog.text
    assert "invalid feed" in caplog.text


def test_leaves_no_temporary_file_behind(tmp_path: Path) -> None:
    publish_feed(tmp_path, "games", valid_feed())
    publish_feed(tmp_path, "games", invalid_feed())

    assert [p.name for p in (tmp_path / "feeds").iterdir()] == ["games.json"]


def test_keeps_the_last_valid_feed_when_the_write_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    publish_feed(tmp_path, "games", valid_feed())
    before = read_feed(tmp_path, "games")

    def fail(*_: object) -> None:
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(os, "replace", fail)
    other = GamesFeed(
        generated_at=dt.datetime(2026, 1, 11, 12, 0, tzinfo=dt.UTC), days=[]
    )
    with caplog.at_level(logging.ERROR):
        assert publish_feed(tmp_path, "games", other) is False

    assert read_feed(tmp_path, "games") == before
    assert "No space left on device" in caplog.text
    assert [p.name for p in (tmp_path / "feeds").iterdir()] == ["games.json"]


def test_reads_nothing_before_the_first_publication(tmp_path: Path) -> None:
    assert read_feed(tmp_path, "games") is None


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


def test_publishes_a_game_detail_feed_under_games_by_its_id(tmp_path: Path) -> None:
    feed = detail_feed("401")

    assert publish_game_detail(tmp_path, feed) is True
    assert (tmp_path / "feeds" / "games" / "401.json").is_file()
    assert read_game_detail(tmp_path, "401") == feed.model_dump_json().encode("utf-8")


def test_never_writes_an_invalid_game_detail_feed_and_keeps_the_last_valid_one(
    tmp_path: Path,
) -> None:
    assert publish_game_detail(tmp_path, invalid_detail_feed()) is False
    assert read_game_detail(tmp_path, "401") is None
    publish_game_detail(tmp_path, detail_feed())
    before = read_game_detail(tmp_path, "401")

    assert publish_game_detail(tmp_path, invalid_detail_feed()) is False
    assert read_game_detail(tmp_path, "401") == before


def test_refuses_a_game_detail_feed_whose_id_is_not_a_game_id(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.ERROR):
        assert publish_game_detail(tmp_path, detail_feed("../x")) is False

    assert "invalid game id" in caplog.text
    assert not (tmp_path / "feeds").exists()


def test_reads_no_game_detail_for_an_unknown_or_unsafe_id(tmp_path: Path) -> None:
    publish_game_detail(tmp_path, detail_feed())

    assert read_game_detail(tmp_path, "404") is None
    assert read_game_detail(tmp_path, "..") is None
    assert read_game_detail(tmp_path, "a.b") is None


def test_lists_the_published_game_details_without_temporary_files(
    tmp_path: Path,
) -> None:
    assert published_game_details(tmp_path) == set()
    publish_game_detail(tmp_path, detail_feed("1"))
    publish_game_detail(tmp_path, detail_feed("2"))
    (tmp_path / "feeds" / "games" / ".3.abc.tmp").write_bytes(b"x")

    assert published_game_details(tmp_path) == {"1", "2"}


def test_deletes_a_game_detail_and_ignores_one_that_is_missing(
    tmp_path: Path,
) -> None:
    publish_game_detail(tmp_path, detail_feed("1"))

    delete_game_detail(tmp_path, "1")
    delete_game_detail(tmp_path, "1")
    delete_game_detail(tmp_path, "../x")

    assert read_game_detail(tmp_path, "1") is None
