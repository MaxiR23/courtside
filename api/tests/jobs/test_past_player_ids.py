# api/tests/jobs/test_past_player_ids.py
#
# Tests for the index of player ids known from the stored past feeds.
#
# Tested:
# - An id from the roster of a stored past team feed is known
# - An id from the box score of a stored past game detail is known
# - A stored past team feed with a null roster adds no id
# - An id named by a stored past playoffs leader or award, or a stored past Finals MVP or average, is known in season only
# - A past game with a null box score adds no id
# - An id in neither is unknown, and nothing is known with no stored feed
# - Each stored file, the playoffs and Finals ones included, is read once: a second call reads no file again, and a file stored later is indexed on the next call
# - An invalid stored file is skipped and read again on the next call, and stores no id
# - An indexed id is stored with its scope and the clock time
# - A known player stays known after his stored feeds are deleted and a restart
# - An in-season id stays in season only after a restart
# - The stored ids are read once per scope per process
# - save_stored keeps the ids of every stored file, for the daily cleanup
#
# What is covered:
# - Pure index logic: happy path, edges and errors, with no source request
#
# Run with: cd api && .venv/bin/python -m pytest tests/jobs/test_past_player_ids.py
#
# SEE: api/app/jobs/past_player_ids.py

import datetime as dt
import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

from app.feeds.game_detail import PastGameDetailFeed
from app.feeds.playoffs import PlayoffsFeed
from app.feeds.playoffs_finals import PlayoffsFinalsFeed
from app.feeds.team import RosterPlayer
from app.jobs import past_player_ids
from app.jobs.past_game_detail_feed import KIND as PAST_GAMES
from app.jobs.past_player_ids import PastPlayerIds
from app.jobs.season_playoffs_feed import KIND as SEASON_PLAYOFFS
from app.jobs.season_playoffs_feed import stored_player_ids as playoffs_ids
from app.jobs.season_playoffs_finals_feed import KIND as SEASON_FINALS
from app.jobs.season_playoffs_finals_feed import stored_player_ids as finals_ids
from app.jobs.season_team_feed import KIND as SEASON_TEAMS
from app.storage.feeds import delete_by_id, publish_by_id, read_by_id
from app.storage.state import STATE_FILE, PastPlayerScope, StateStore
from tests.feeds.test_game_detail import past_detail
from tests.feeds.test_playoffs import complete_feed
from tests.feeds.test_playoffs_finals import valid as finals_data
from tests.jobs.test_season_team_feed import build

FIXED = dt.datetime(2026, 10, 19, 12, 0, tzinfo=dt.UTC)


def state(path: Path) -> StateStore:
    store = StateStore(path)
    store.migrate()
    return store


def index_of(path: Path) -> PastPlayerIds:
    return PastPlayerIds(path, state(path), clock=lambda: FIXED)


def store_team(path: Path, feed_id: str = "2004-okc", *, roster: bool = True) -> None:
    """A past team feed; the roster is the one a feed stored before ADR 0059 has."""
    feed = build()
    if roster:
        feed = feed.model_copy(
            update={
                "roster": [
                    RosterPlayer(id="1", name="Player 1", status="active"),
                    RosterPlayer(id="2", name="Player 2", status="active"),
                ]
            }
        )
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
    index = index_of(tmp_path)

    assert index.known("1") is True
    assert index.known("2") is True


def test_an_id_from_the_box_score_of_a_stored_past_game_is_known(
    tmp_path: Path,
) -> None:
    ids = store_game(tmp_path)
    index = named_index(tmp_path)

    assert ids
    assert all(index.known(player_id) for player_id in ids)


def test_a_past_game_with_a_null_box_score_adds_no_id(tmp_path: Path) -> None:
    store_game(tmp_path, box_score=False)

    assert index_of(tmp_path).known("p1") is False


def test_an_id_in_neither_is_unknown_and_nothing_is_known_with_no_stored_feed(
    tmp_path: Path,
) -> None:
    assert index_of(tmp_path).known("1") is False
    store_team(tmp_path)
    store_game(tmp_path)

    assert index_of(tmp_path).known("nobody") is False


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
    index = named_index(tmp_path)

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
    index = index_of(tmp_path)

    assert index.known("1") is False
    assert state(tmp_path).past_player_ids("known") == set()

    store_team(tmp_path)

    assert index.known("1") is True


def test_a_past_team_feed_with_a_null_roster_adds_no_id(tmp_path: Path) -> None:
    store_team(tmp_path, roster=False)

    assert index_of(tmp_path).known("1") is False


def named_index(path: Path) -> PastPlayerIds:
    return PastPlayerIds(
        path,
        state(path),
        clock=lambda: FIXED,
        named=(
            (SEASON_PLAYOFFS, playoffs_ids),
            (SEASON_FINALS, finals_ids),
        ),
    )


def test_no_playoffs_id_is_known_in_season_without_the_readers(
    tmp_path: Path,
) -> None:
    store_playoffs(tmp_path)

    assert index_of(tmp_path).known_in_season("leader") is False


def store_playoffs(path: Path, season: str = "2025") -> None:
    data = complete_feed()
    data["leaders"][0]["leaders"][0]["playerId"] = "leader"
    data["awards"][0]["winners"][0]["playerId"] = "winner"
    feed = PlayoffsFeed.model_validate(data)
    publish_by_id(path, SEASON_PLAYOFFS, PlayoffsFeed, season, feed)


def store_finals(path: Path, season: str = "2025") -> set[str]:
    feed = PlayoffsFinalsFeed.model_validate(finals_data())
    publish_by_id(path, SEASON_FINALS, PlayoffsFinalsFeed, season, feed)
    assert feed.finals_mvp is not None and feed.averages is not None
    return {feed.finals_mvp.player_id} | {
        player.player_id for side in feed.averages for player in side.players
    }


def test_an_id_named_by_a_stored_past_playoffs_leader_or_award_is_known_in_season_only(
    tmp_path: Path,
) -> None:
    store_playoffs(tmp_path)
    index = named_index(tmp_path)

    assert index.known("leader") is False
    assert index.known_in_season("leader") is True
    assert index.known_in_season("winner") is True
    assert index.known_in_season("nobody") is False


def test_an_id_named_by_a_stored_past_finals_mvp_is_known_in_season_only(
    tmp_path: Path,
) -> None:
    ids = store_finals(tmp_path)
    index = named_index(tmp_path)

    assert ids
    assert not any(index.known(player_id) for player_id in ids)
    assert all(index.known_in_season(player_id) for player_id in ids)


def test_known_in_season_also_knows_a_roster_or_box_score_id(tmp_path: Path) -> None:
    store_team(tmp_path)

    assert named_index(tmp_path).known_in_season("1") is True


def test_each_competition_file_is_read_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store_playoffs(tmp_path)
    store_finals(tmp_path)
    reads: list[tuple[str, str]] = []
    real = read_by_id

    def counted(data_dir: Path, kind: str, feed_id: str) -> bytes | None:
        reads.append((kind, feed_id))
        return real(data_dir, kind, feed_id)

    monkeypatch.setattr(past_player_ids, "read_by_id", counted)
    index = named_index(tmp_path)

    assert index.known_in_season("nobody") is False
    assert index.known_in_season("other") is False
    assert sorted(reads) == sorted([(SEASON_FINALS, "2025"), (SEASON_PLAYOFFS, "2025")])


def test_an_indexed_id_is_stored_with_its_scope_and_the_clock_time(
    tmp_path: Path,
) -> None:
    store_team(tmp_path)
    store_playoffs(tmp_path)
    index = named_index(tmp_path)

    assert index.known("nobody") is False
    assert index.known_in_season("nobody") is False

    store = state(tmp_path)
    assert store.past_player_ids("known") == {"1", "2"}
    assert {"leader", "winner"} <= store.past_player_ids("in_season")
    with closing(sqlite3.connect(tmp_path / STATE_FILE)) as connection:
        learned = connection.execute(
            "SELECT DISTINCT learned_at FROM past_player_ids"
        ).fetchall()
    assert learned == [(FIXED.isoformat(),)]


def test_a_known_player_stays_known_after_his_stored_feeds_are_deleted_and_a_restart(
    tmp_path: Path,
) -> None:
    store_team(tmp_path)
    ids = store_game(tmp_path)
    assert index_of(tmp_path).known("nobody") is False

    delete_by_id(tmp_path, SEASON_TEAMS, "2004-okc")
    delete_by_id(tmp_path, PAST_GAMES, "g1")
    restarted = index_of(tmp_path)

    assert restarted.known("1") is True
    assert all(restarted.known(player_id) for player_id in ids)
    assert restarted.known("nobody") is False


def test_an_in_season_id_stays_in_season_only_after_a_restart(tmp_path: Path) -> None:
    store_playoffs(tmp_path)
    assert named_index(tmp_path).known_in_season("leader") is True

    delete_by_id(tmp_path, SEASON_PLAYOFFS, "2025")
    restarted = named_index(tmp_path)

    assert restarted.known("leader") is False
    assert restarted.known_in_season("leader") is True


def test_the_stored_ids_are_read_once_per_process(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = state(tmp_path)
    scopes: list[str] = []
    real = store.past_player_ids

    def counted(scope: PastPlayerScope) -> set[str]:
        scopes.append(scope)
        return real(scope)

    monkeypatch.setattr(store, "past_player_ids", counted)
    index = PastPlayerIds(tmp_path, store, clock=lambda: FIXED)

    assert index.known("a") is False
    assert index.known("b") is False
    assert index.known_in_season("a") is False
    assert index.known_in_season("b") is False
    assert sorted(scopes) == ["in_season", "known"]


def test_save_stored_keeps_the_ids_of_every_stored_file_before_they_are_deleted(
    tmp_path: Path,
) -> None:
    store_team(tmp_path)
    store_playoffs(tmp_path)
    ids = store_finals(tmp_path)
    index = named_index(tmp_path)

    index.save_stored()
    delete_by_id(tmp_path, SEASON_TEAMS, "2004-okc")
    delete_by_id(tmp_path, SEASON_PLAYOFFS, "2025")
    delete_by_id(tmp_path, SEASON_FINALS, "2025")
    restarted = named_index(tmp_path)

    assert restarted.known("1") is True
    assert restarted.known("leader") is False
    assert restarted.known_in_season("leader") is True
    assert restarted.known_in_season("winner") is True
    assert all(restarted.known_in_season(player_id) for player_id in ids)
