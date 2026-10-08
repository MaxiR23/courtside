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
# - Publishes a feed by id under its directory, validated and readable back
# - Never writes an invalid feed by id and keeps the last valid one
# - Refuses a feed id or a directory that is not a safe id
# - Reads nothing for an unknown or unsafe id
# - Lists the published ids of a directory without temporary files, and none for a missing directory
# - Deletes a feed by id and ignores one that is missing
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
    delete_by_id,
    publish_by_id,
    publish_feed,
    published_ids,
    read_by_id,
    read_feed,
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


def test_publishes_a_feed_by_id_under_its_directory_validated_and_readable_back(
    tmp_path: Path,
) -> None:
    feed = detail_feed("7")

    assert publish_by_id(tmp_path, "players", GameDetailFeed, "7", feed) is True

    assert (tmp_path / "feeds" / "players" / "7.json").is_file()
    assert read_by_id(tmp_path, "players", "7") == feed.model_dump_json().encode(
        "utf-8"
    )


def test_never_writes_an_invalid_feed_by_id_and_keeps_the_last_valid_one(
    tmp_path: Path,
) -> None:
    assert (
        publish_by_id(tmp_path, "players", GameDetailFeed, "7", invalid_detail_feed())
        is False
    )
    assert read_by_id(tmp_path, "players", "7") is None
    publish_by_id(tmp_path, "players", GameDetailFeed, "7", detail_feed("7"))
    before = read_by_id(tmp_path, "players", "7")

    assert (
        publish_by_id(tmp_path, "players", GameDetailFeed, "7", invalid_detail_feed())
        is False
    )
    assert read_by_id(tmp_path, "players", "7") == before


def test_refuses_a_feed_id_or_a_directory_that_is_not_a_safe_id(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.ERROR):
        assert (
            publish_by_id(tmp_path, "players", GameDetailFeed, "../x", detail_feed())
            is False
        )
        assert (
            publish_by_id(tmp_path, "../x", GameDetailFeed, "7", detail_feed()) is False
        )

    assert "invalid id" in caplog.text
    assert not (tmp_path / "feeds").exists()


def test_reads_nothing_for_an_unknown_or_unsafe_id(tmp_path: Path) -> None:
    publish_by_id(tmp_path, "players", GameDetailFeed, "7", detail_feed("7"))

    assert read_by_id(tmp_path, "players", "8") is None
    assert read_by_id(tmp_path, "players", "..") is None
    assert read_by_id(tmp_path, "players", "a.b") is None
    assert read_by_id(tmp_path, "..", "7") is None


def test_lists_the_published_ids_of_a_directory_without_temporary_files(
    tmp_path: Path,
) -> None:
    assert published_ids(tmp_path, "players") == set()
    publish_by_id(tmp_path, "players", GameDetailFeed, "1", detail_feed("1"))
    publish_by_id(tmp_path, "players", GameDetailFeed, "2", detail_feed("2"))
    (tmp_path / "feeds" / "players" / ".3.abc.tmp").write_bytes(b"x")

    assert published_ids(tmp_path, "players") == {"1", "2"}
    assert published_ids(tmp_path, "..") == set()


def test_deletes_a_feed_by_id_and_ignores_one_that_is_missing(tmp_path: Path) -> None:
    publish_by_id(tmp_path, "players", GameDetailFeed, "1", detail_feed("1"))

    delete_by_id(tmp_path, "players", "1")
    delete_by_id(tmp_path, "players", "1")
    delete_by_id(tmp_path, "players", "../x")

    assert read_by_id(tmp_path, "players", "1") is None
