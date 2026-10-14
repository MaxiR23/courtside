# api/tests/feeds/test_all_star.py
#
# Tests for the All-Star feed models.
#
# Tested:
# - A valid feed is accepted in each state: before with a date and no games, live and after
# - A before feed with games or teams, a before feed with an MVP, an after feed with a game not final and a live feed with every game final are rejected
# - A winner on a live game, a winner that does not match the score and a missing winner on a final game are rejected
# - toBeDetermined that does not match a null side is rejected; a live game with a null side is rejected
# - A Top 5 out of order or longer than 5 is rejected
# - A better side that is not the higher value is rejected; a tie has none
# - An eliminated placement without a round label, or any other placement with one, is rejected
# - Two champions are rejected
# - MVP totals that differ from the lines are rejected
#
# What is covered:
# - Feed models: a valid feed is accepted and an invalid one is rejected
#
# Run with: cd api && .venv/bin/python -m pytest tests/feeds/test_all_star.py
#
# SEE: api/app/feeds/all_star.py

import datetime as dt
from typing import Any

import pytest
from pydantic import ValidationError

from app.feeds.all_star import AllStarFeed, AllStarGame, AllStarMvp, TeamStatKind

START = dt.datetime(2027, 2, 14, 0, 0, tzinfo=dt.UTC)
STRIPES = {"code": "STR", "name": "Team Stripes", "city": None, "guest": True}
WAVES = {"code": "WAV", "name": "Team Waves", "city": None, "guest": True}


def line() -> dict[str, int]:
    return {
        "points": 10,
        "field_goals_made": 4,
        "field_goals_attempted": 8,
        "three_points_made": 2,
        "three_points_attempted": 4,
        "free_throws_made": 0,
        "free_throws_attempted": 0,
        "offensive_rebounds": 1,
        "defensive_rebounds": 2,
        "rebounds": 3,
        "assists": 2,
        "turnovers": 1,
        "steals": 1,
        "blocks": 0,
        "fouls": 1,
    }


def top5(points: int, rebounds: int = 0, assists: int = 0) -> dict[str, Any]:
    return {
        "player_id": f"p{points}",
        "name": "Ada Example",
        "photo_url": None,
        "side": "away",
        "league_team": None,
        "points": points,
        "rebounds": rebounds,
        "assists": assists,
    }


def stats(**changes: Any) -> list[dict[str, Any]]:
    rows = [
        {"stat": kind.value, "away": 1.0, "home": 2.0, "better": "home"}
        for kind in TeamStatKind
    ]
    rows[0].update(changes)
    return rows


def game(status: str = "final", **changes: Any) -> dict[str, Any]:
    played = status in ("live", "final")
    data: dict[str, Any] = {
        "id": "g1",
        "start_time": START,
        "status": status,
        "status_text": None,
        "clock": None,
        "period": None,
        "score": {"away": 30, "home": 20} if played else None,
        "overtime": False,
        "winner": "away" if status == "final" else None,
        "attendance": None,
        "broadcasts": [],
        "round_label": "Championship",
        "championship": True,
        "away": STRIPES,
        "home": WAVES,
        "to_be_determined": False,
        "box_score": None,
        "team_stats": None,
        "leaders": None,
        "top5": [],
        "highlights": None,
    }
    data.update(changes)
    return data


def team(
    code: str = "STR", kind: str = "so_far", label: str | None = None
) -> dict[str, Any]:
    return {
        "team": {"code": code, "name": "Team", "city": None, "guest": True},
        "wins": 0,
        "losses": 0,
        "placement": {"kind": kind, "round_label": label},
        "roster": [],
    }


def feed(
    state: str = "after", games: list[dict[str, Any]] | None = None, **changes: Any
) -> dict[str, Any]:
    edition: dict[str, Any] = {
        "date": dt.date(2027, 2, 14),
        "venue": {"name": "Example Arena", "city": "Exampleton"},
        "format_line": "1 period · 12 min",
        "teams": [team("STR", "champion"), team("WAV", "runner_up")],
        "games": [game()] if games is None else games,
    }
    if state == "before":
        edition.update(teams=[], games=[] if games is None else games)
    data: dict[str, Any] = {
        "year": 2027,
        "state": state,
        "edition": edition,
        "mvp": None,
        "previous": None,
    }
    data.update(changes)
    return data


def mvp(**changes: Any) -> dict[str, Any]:
    entry = {
        "game_id": "g1",
        "round_label": "Championship",
        "result": "win",
        "team_score": 30,
        "opponent_score": 20,
        "opponent": WAVES,
        "points": 20,
        "rebounds": 5,
        "assists": 4,
    }
    data: dict[str, Any] = {
        "player_id": "p1",
        "name": "Ada Example",
        "photo_url": None,
        "jersey": "7",
        "league_team": None,
        "lines": [entry, {**entry, "game_id": "g2", "points": 10}],
        "totals": {"games": 2, "points": 30, "rebounds": 10, "assists": 8},
    }
    data.update(changes)
    return data


def test_accepts_an_after_feed() -> None:
    parsed = AllStarFeed.model_validate(feed("after"))

    assert parsed.edition.games[0].winner == "away"
    assert parsed.model_dump(mode="json", by_alias=True)["edition"]["formatLine"]


def test_accepts_a_before_feed_with_a_date_and_no_games() -> None:
    parsed = AllStarFeed.model_validate(feed("before"))

    assert parsed.edition.games == [] and parsed.edition.teams == []


def test_accepts_a_live_feed_with_one_final_and_one_scheduled_game() -> None:
    games = [game(), game("scheduled", id="g2", championship=False)]

    parsed = AllStarFeed.model_validate(feed("live", games))

    assert parsed.state == "live"


def test_accepts_a_scheduled_team_less_championship() -> None:
    data = game("scheduled", away=None, home=None, to_be_determined=True)

    assert AllStarGame.model_validate(data).to_be_determined


def test_rejects_a_before_feed_with_games() -> None:
    data = feed("before", [game("scheduled")])

    with pytest.raises(ValidationError, match="before feed"):
        AllStarFeed.model_validate(data)


def test_rejects_a_before_feed_with_an_mvp() -> None:
    with pytest.raises(ValidationError, match="before feed"):
        AllStarFeed.model_validate(feed("before", mvp=mvp()))


def test_rejects_an_after_feed_with_a_game_not_final() -> None:
    data = feed("after", [game(), game("scheduled", id="g2")])

    with pytest.raises(ValidationError, match="after feed"):
        AllStarFeed.model_validate(data)


def test_rejects_a_live_feed_with_every_game_final() -> None:
    with pytest.raises(ValidationError, match="live feed"):
        AllStarFeed.model_validate(feed("live"))


def test_rejects_a_winner_on_a_live_game() -> None:
    with pytest.raises(ValidationError, match="winner"):
        AllStarGame.model_validate(game("live", winner="away"))


def test_rejects_a_winner_that_does_not_match_the_score() -> None:
    with pytest.raises(ValidationError, match="winner"):
        AllStarGame.model_validate(game(winner="home"))


def test_rejects_a_final_game_without_a_winner() -> None:
    with pytest.raises(ValidationError, match="winner"):
        AllStarGame.model_validate(game(winner=None))


def test_rejects_to_be_determined_that_does_not_match_a_null_side() -> None:
    with pytest.raises(ValidationError, match="toBeDetermined"):
        AllStarGame.model_validate(game("scheduled", away=None, to_be_determined=False))
    with pytest.raises(ValidationError, match="toBeDetermined"):
        AllStarGame.model_validate(game("scheduled", to_be_determined=True))


def test_rejects_a_live_game_with_a_null_side() -> None:
    data = game("live", away=None, to_be_determined=True)

    with pytest.raises(ValidationError, match="both sides"):
        AllStarGame.model_validate(data)


def test_rejects_overtime_on_a_scheduled_game() -> None:
    with pytest.raises(ValidationError, match="overtime"):
        AllStarGame.model_validate(game("scheduled", overtime=True))


def test_accepts_a_top5_sorted_by_points_then_rebounds_plus_assists() -> None:
    rows = [top5(20, 5, 5), top5(20, 4, 5), top5(10)]

    assert len(AllStarGame.model_validate(game(top5=rows)).top5) == 3


def test_rejects_a_top5_out_of_order() -> None:
    rows = [top5(20, 4, 5), top5(20, 5, 5)]

    with pytest.raises(ValidationError, match="top5"):
        AllStarGame.model_validate(game(top5=rows))


def test_rejects_a_top5_longer_than_5() -> None:
    rows = [top5(30 - n) for n in range(6)]

    with pytest.raises(ValidationError):
        AllStarGame.model_validate(game(top5=rows))


def test_accepts_team_stats_with_a_tie_and_no_better_side() -> None:
    rows = stats(away=2.0, home=2.0, better=None)

    assert AllStarGame.model_validate(game(team_stats=rows)).team_stats is not None


def test_rejects_a_better_side_that_is_not_the_higher_value() -> None:
    with pytest.raises(ValidationError, match="better"):
        AllStarGame.model_validate(game(team_stats=stats(better="away")))
    with pytest.raises(ValidationError, match="better"):
        AllStarGame.model_validate(
            game(team_stats=stats(away=2.0, home=2.0, better="away"))
        )


def test_rejects_team_stats_out_of_order() -> None:
    rows = list(reversed(stats()))

    with pytest.raises(ValidationError, match="6 stats"):
        AllStarGame.model_validate(game(team_stats=rows))


@pytest.mark.parametrize(
    ("kind", "label"),
    [("eliminated", None), ("champion", "Semifinals"), ("so_far", "Semifinals")],
)
def test_rejects_a_placement_with_a_round_label_that_does_not_fit(
    kind: str, label: str | None
) -> None:
    data = feed()
    data["edition"]["teams"] = [team("STR", kind, label)]

    with pytest.raises(ValidationError, match="round label"):
        AllStarFeed.model_validate(data)


def test_accepts_an_eliminated_placement_with_a_round_label() -> None:
    data = feed()
    data["edition"]["teams"].append(team("PKS", "eliminated", "Round Robin"))

    assert len(AllStarFeed.model_validate(data).edition.teams) == 3


def test_rejects_two_champions() -> None:
    data = feed()
    data["edition"]["teams"] = [team("STR", "champion"), team("WAV", "champion")]

    with pytest.raises(ValidationError, match="champion"):
        AllStarFeed.model_validate(data)


def test_accepts_an_mvp_whose_totals_are_the_sums_of_the_lines() -> None:
    assert AllStarMvp.model_validate(mvp()).totals.games == 2


def test_rejects_mvp_totals_that_differ_from_the_lines() -> None:
    totals = {"games": 2, "points": 31, "rebounds": 10, "assists": 8}

    with pytest.raises(ValidationError, match="totals"):
        AllStarMvp.model_validate(mvp(totals=totals))


def test_rejects_an_mvp_without_lines() -> None:
    totals = {"games": 1, "points": 0, "rebounds": 0, "assists": 0}

    with pytest.raises(ValidationError):
        AllStarMvp.model_validate(mvp(lines=[], totals=totals))
