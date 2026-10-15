# api/tests/jobs/test_playoffs_backfill_games.py
#
# Tests for the playoffs games provider of the highlights backfill.
#
# Tested:
# - Lists the final series games of the current playoffs feed and of every stored season playoffs feed
# - Lists a final play-in game
# - Skips a game that is not final and a game with a side without a name
# - Lists no game twice
# - Gives nothing with no stored feed and skips an invalid stored file
#
# What is covered:
# - Stored-feed reads over a temporary data directory; valid feeds built from the feed model tests' payloads
#
# No test reads a source or the real clock.
#
# Run with: cd api && .venv/bin/python -m pytest tests/jobs/test_playoffs_backfill_games.py
#
# SEE: api/app/jobs/playoffs_backfill_games.py

import json
from pathlib import Path
from typing import Any

from app.jobs.playoffs_backfill_games import playoffs_backfill_games
from tests.feeds.test_playoffs import final_game, game, picture_feed


def series_games(feed: dict[str, Any], games: list[dict[str, Any]]) -> dict[str, Any]:
    feed["bracket"][0]["games"] = [
        {**g, "number": number} for number, g in enumerate(games, start=1)
    ]
    return feed


def stored(data_dir: Path, kind: str, feed_id: str, feed: dict[str, Any]) -> None:
    path = data_dir / "feeds" / kind / f"{feed_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(feed), encoding="utf-8")


def test_lists_the_final_series_games_of_the_current_and_every_season_feed(
    tmp_path: Path,
) -> None:
    stored(
        tmp_path,
        "playoffs",
        "league",
        series_games(picture_feed(), [final_game(id="g1")]),
    )
    stored(
        tmp_path,
        "season-playoffs",
        "2025-26",
        series_games(picture_feed(), [final_game(id="g2")]),
    )

    found = playoffs_backfill_games(tmp_path)

    assert sorted(g.id for g in found) == ["g1", "g2"]
    assert (found[0].away, found[0].home) == ("Celtics", "Hawks")


def test_lists_a_final_play_in_game(tmp_path: Path) -> None:
    feed = picture_feed()
    feed["playIn"][0]["games"][0]["game"] = final_game(id="p1")
    feed["playIn"][0]["games"][0]["outcome"] = {"seed": 7, "loserOut": False}
    stored(tmp_path, "playoffs", "league", feed)

    assert [g.id for g in playoffs_backfill_games(tmp_path)] == ["p1"]


def test_skips_a_game_that_is_not_final_and_a_game_with_a_side_without_a_name(
    tmp_path: Path,
) -> None:
    nameless = {"code": "BOS", "name": None, "city": "Boston", "guest": False}
    games = [game(id="g1"), final_game(id="g2", away=nameless), final_game(id="g3")]
    stored(tmp_path, "playoffs", "league", series_games(picture_feed(), games))

    assert [g.id for g in playoffs_backfill_games(tmp_path)] == ["g3"]


def test_lists_no_game_twice(tmp_path: Path) -> None:
    feed = series_games(picture_feed(), [final_game(id="g1")])
    stored(tmp_path, "playoffs", "league", feed)
    stored(tmp_path, "season-playoffs", "2025-26", feed)

    assert [g.id for g in playoffs_backfill_games(tmp_path)] == ["g1"]


def test_gives_nothing_with_no_stored_feed(tmp_path: Path) -> None:
    assert playoffs_backfill_games(tmp_path) == []


def test_skips_an_invalid_stored_file(tmp_path: Path) -> None:
    stored(
        tmp_path,
        "playoffs",
        "league",
        series_games(picture_feed(), [final_game(id="g1")]),
    )
    bad = tmp_path / "feeds" / "season-playoffs" / "2025-26.json"
    bad.parent.mkdir(parents=True)
    bad.write_text('{"season": 1}', encoding="utf-8")

    assert [g.id for g in playoffs_backfill_games(tmp_path)] == ["g1"]
