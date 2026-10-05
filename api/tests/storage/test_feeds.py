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

from app.feeds.games import GamesFeed
from app.storage.feeds import publish_feed, read_feed

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
