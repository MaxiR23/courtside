# api/tests/jobs/test_past_player_ids.py
#
# Tests for the index of player ids known from the stored past feeds.
#
# Tested:
# - An id from the roster of a stored past team feed is known
# - An id from the box score of a stored past game detail is known
# - A past game with a null box score adds no id
# - An id in neither is unknown, and nothing is known with no stored feed
# - Each stored file is read once: a second call reads no file again, and a file stored later is indexed on the next call
# - An invalid stored file is skipped and read again on the next call
#
# What is covered:
# - Pure index logic: happy path, edges and errors, with no source request
#
# Run with: cd api && .venv/bin/python -m pytest tests/jobs/test_past_player_ids.py
#
# SEE: api/app/jobs/past_player_ids.py

from pathlib import Path

import pytest

from app.feeds.game_detail import PastGameDetailFeed
from app.jobs import past_player_ids
from app.jobs.past_game_detail_feed import KIND as PAST_GAMES
from app.jobs.past_player_ids import PastPlayerIds
from app.jobs.season_team_feed import KIND as SEASON_TEAMS
from app.storage.feeds import publish_by_id, read_by_id
from tests.feeds.test_game_detail import past_detail
from tests.jobs.test_season_team_feed import build


def store_team(path: Path, feed_id: str = "2004-okc") -> None:
    feed = build()
    publish_by_id(path, SEASON_TEAMS, type(feed), feed_id, feed)


def box_ids(feed: PastGameDetailFeed) -> set[str]:
    assert feed.box_score is not None
    return {
        player.player_id
        for side in (feed.box_score.away, feed.box_score.home)
        for player in side.players
    }


def store_game(path: Path, game_id: str = "g1", *, box_score: bool = True) -> set[str]:
    payload = past_detail(id=game_id)
    if not box_score:
        payload["boxScore"] = None
    feed = PastGameDetailFeed.model_validate(payload)
    publish_by_id(path, PAST_GAMES, PastGameDetailFeed, game_id, feed)
    return box_ids(feed) if feed.box_score else set()


def test_an_id_from_the_roster_of_a_stored_past_team_feed_is_known(
    tmp_path: Path,
) -> None:
    store_team(tmp_path)
    index = PastPlayerIds(tmp_path)

    assert index.known("1") is True
    assert index.known("2") is True


def test_an_id_from_the_box_score_of_a_stored_past_game_is_known(
    tmp_path: Path,
) -> None:
    ids = store_game(tmp_path)
    index = PastPlayerIds(tmp_path)

    assert ids
    assert all(index.known(player_id) for player_id in ids)


def test_a_past_game_with_a_null_box_score_adds_no_id(tmp_path: Path) -> None:
    store_game(tmp_path, box_score=False)

    assert PastPlayerIds(tmp_path).known("p1") is False


def test_an_id_in_neither_is_unknown_and_nothing_is_known_with_no_stored_feed(
    tmp_path: Path,
) -> None:
    assert PastPlayerIds(tmp_path).known("1") is False
    store_team(tmp_path)
    store_game(tmp_path)

    assert PastPlayerIds(tmp_path).known("nobody") is False


def test_each_stored_file_is_read_once_and_a_file_stored_later_is_indexed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store_team(tmp_path)
    reads: list[tuple[str, str]] = []
    real = read_by_id

    def counted(data_dir: Path, kind: str, feed_id: str) -> bytes | None:
        reads.append((kind, feed_id))
        return real(data_dir, kind, feed_id)

    monkeypatch.setattr(past_player_ids, "read_by_id", counted)
    index = PastPlayerIds(tmp_path)

    assert index.known("nobody") is False
    assert index.known("other") is False
    assert reads == [(SEASON_TEAMS, "2004-okc")]
    ids = store_game(tmp_path)
    assert index.known(min(ids)) is True
    assert reads == [(SEASON_TEAMS, "2004-okc"), (PAST_GAMES, "g1")]


def test_an_invalid_stored_file_is_skipped_and_read_again(tmp_path: Path) -> None:
    folder = tmp_path / "feeds" / SEASON_TEAMS
    folder.mkdir(parents=True)
    (folder / "2004-okc.json").write_text("{}", encoding="utf-8")
    index = PastPlayerIds(tmp_path)

    assert index.known("1") is False

    store_team(tmp_path)

    assert index.known("1") is True
