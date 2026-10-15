# api/tests/jobs/test_cup_backfill_games.py
#
# Tests for the Cup games provider of the highlights backfill.
#
# Tested:
# - Lists the final games of the current Cup feed and of every stored season Cup feed
# - Skips a game that is not final
# - Skips a game with a side without a name
# - Gives nothing with no stored feed and skips an invalid stored file
#
# What is covered:
# - Stored-feed reads over a temporary data directory; valid feeds built from the feed model tests' payloads
#
# No test reads a source or the real clock.
#
# Run with: cd api && .venv/bin/python -m pytest tests/jobs/test_cup_backfill_games.py
#
# SEE: api/app/jobs/cup_backfill_games.py

import datetime as dt
import json
from pathlib import Path
from typing import Any

from app.jobs.cup_backfill_games import cup_backfill_games
from app.jobs.highlights_backfill import GameTarget
from tests.feeds.test_cup import game, valid_feed


def final(game_id: str, **changes: Any) -> dict[str, Any]:
    return game(
        id=game_id,
        status="final",
        score={"away": 90, "home": 100},
        winner="home",
        **changes,
    )


def stored(
    data_dir: Path, kind: str, feed_id: str, games: list[dict[str, Any]]
) -> None:
    feed = valid_feed()
    feed["games"]["days"] = [{"date": "2026-11-03", "games": games}]
    feed["games"]["counts"]["all"] = len(games)
    feed["games"]["counts"]["group"] = len(games)
    path = data_dir / "feeds" / kind / f"{feed_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(feed), encoding="utf-8")


def test_lists_the_final_games_of_the_current_and_every_season_cup_feed(
    tmp_path: Path,
) -> None:
    stored(tmp_path, "cup", "league", [final("g1")])
    stored(tmp_path, "season-cup", "2025-26", [final("g2")])
    stored(tmp_path, "season-cup", "2024-25", [final("g3")])

    found = cup_backfill_games(tmp_path)

    assert sorted(g.id for g in found) == ["g1", "g2", "g3"]
    assert (
        GameTarget("g1", "Hawks", "Hawks", dt.datetime(2026, 11, 4, tzinfo=dt.UTC))
        in found
    )


def test_skips_a_game_that_is_not_final(tmp_path: Path) -> None:
    stored(tmp_path, "cup", "league", [final("g1"), game(id="g2")])

    assert [g.id for g in cup_backfill_games(tmp_path)] == ["g1"]


def test_skips_a_game_with_a_side_without_a_name(tmp_path: Path) -> None:
    nameless = {"code": "BOS", "name": None, "city": "Boston", "guest": False}
    stored(tmp_path, "cup", "league", [final("g1", away=nameless), final("g2")])

    assert [g.id for g in cup_backfill_games(tmp_path)] == ["g2"]


def test_gives_nothing_with_no_stored_feed(tmp_path: Path) -> None:
    assert cup_backfill_games(tmp_path) == []


def test_skips_an_invalid_stored_file(tmp_path: Path) -> None:
    stored(tmp_path, "cup", "league", [final("g1")])
    bad = tmp_path / "feeds" / "season-cup" / "2025-26.json"
    bad.parent.mkdir(parents=True)
    bad.write_text("{not json", encoding="utf-8")

    assert [g.id for g in cup_backfill_games(tmp_path)] == ["g1"]
