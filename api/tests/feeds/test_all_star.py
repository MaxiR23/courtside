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
# - A previous edition: accepted after and before, rejected with a game not final, without games, without a date, without the recap or with another date
# - Counts that differ from the lists, final and live above the games, a default game missing, outside the list or with no games, and two next games are rejected
# - A next game that is live or final, a leading side that is not the higher score of a live game or set on a final game are rejected; a tie has none
# - Top points on every tied top scorer are accepted; on a player below the top, missing on the top scorer or on a team with no points they are rejected
# - A team record that differs from its results and a result that does not match its scores are rejected
# - An edition, a previous edition and a recap accept an edition highlight or null; a feed without the key reads it as null; an invalid edition highlight is rejected
# - A format: a target score with untimed, periods and minutes, both shapes or neither rejected, untimed without a target score rejected, the retired formatLine key rejected
# - A feed with a build version is accepted, one with zero is rejected, and a stored feed without the field reads with a null version
#
# - Accepts null Top 5 values, null MVP values and totals that are null when any line is null, and rejects a total that is not null then (ADR 0055)
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

from app.feeds.all_star import (
    AllStarFeed,
    AllStarFormat,
    AllStarGame,
    AllStarMvp,
    AllStarTeamBox,
    AllStarTeamResult,
    TeamStatKind,
)

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
        "leading": "away" if status == "live" else None,
        "attendance": None,
        "broadcasts": [],
        "round_label": "Championship",
        "championship": True,
        "is_next": False,
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
        "results": [],
        "placement": {"kind": kind, "round_label": label},
        "roster": [],
    }


def recount(edition: dict[str, Any]) -> None:
    """Set the counts and the default game from the teams and games."""
    games = edition["games"]
    edition["counts"] = {
        "games": len(games),
        "teams": len(edition["teams"]),
        "final": sum(g["status"] == "final" for g in games),
        "live": sum(g["status"] == "live" for g in games),
    }
    edition["default_game_id"] = games[0]["id"] if games else None


def format_parts(**changes: Any) -> dict[str, Any]:
    parts: dict[str, Any] = {
        "target_points": None,
        "untimed": False,
        "periods": 1,
        "minutes": 12.0,
    }
    parts.update(changes)
    return parts


def feed(
    state: str = "after", games: list[dict[str, Any]] | None = None, **changes: Any
) -> dict[str, Any]:
    edition: dict[str, Any] = {
        "date": dt.date(2027, 2, 14),
        "venue": {"name": "Example Arena", "city": "Exampleton"},
        "format": format_parts(),
        "teams": [team("STR", "champion"), team("WAV", "runner_up")],
        "games": [game()] if games is None else games,
    }
    if state == "before":
        edition.update(teams=[], games=[] if games is None else games)
    recount(edition)
    data: dict[str, Any] = {
        "year": 2027,
        "state": state,
        "edition": edition,
        "mvp": None,
        "previous": None,
        "previous_edition": None,
    }
    data.update(changes)
    return data


def previous_edition(**changes: Any) -> dict[str, Any]:
    edition: dict[str, Any] = {
        "date": dt.date(2026, 2, 15),
        "venue": {"name": "Example Arena", "city": "Exampleton"},
        "format": format_parts(),
        "teams": [team("STR", "champion"), team("WAV", "runner_up")],
        "games": [game()],
        "mvp": mvp(),
    }
    edition.update(changes)
    recount(edition)
    return edition


def recap(**changes: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "year": 2026,
        "date": dt.date(2026, 2, 15),
        "venue": None,
        "championship": {
            "game_id": "g1",
            "away": STRIPES,
            "home": WAVES,
            "score": {"away": 30, "home": 20},
            "winner": "away",
            "overtime": False,
        },
        "mvp": None,
    }
    data.update(changes)
    return data


def box_player(points: int, top_points: bool, player_id: str = "p1") -> dict[str, Any]:
    return {
        "player_id": player_id,
        "display_name": "Ada Example",
        "starter": True,
        "minutes": "10",
        "plus_minus": 1,
        "photo_url": None,
        **line(),
        "points": points,
        "jersey": None,
        "position": None,
        "league_team": None,
        "top_points": top_points,
    }


def box(*points: tuple[int, bool]) -> dict[str, Any]:
    totals = {**line(), "field_goal_pct": 0.5, "three_point_pct": 0.5}
    totals["free_throw_pct"] = 0.0
    return {
        "players": [box_player(p, top, f"p{n}") for n, (p, top) in enumerate(points)],
        "totals": totals,
    }


def result(**changes: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "game_id": "g1",
        "round_label": "Championship",
        "result": "win",
        "team_score": 30,
        "opponent_score": 20,
        "opponent": WAVES,
        "overtime": False,
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
    assert parsed.model_dump(mode="json", by_alias=True)["edition"]["format"] == {
        "targetPoints": None,
        "untimed": False,
        "periods": 1,
        "minutes": 12.0,
    }


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
    recount(data["edition"])

    with pytest.raises(ValidationError, match="round label"):
        AllStarFeed.model_validate(data)


def test_accepts_an_eliminated_placement_with_a_round_label() -> None:
    data = feed()
    data["edition"]["teams"].append(team("PKS", "eliminated", "Round Robin"))
    recount(data["edition"])

    assert len(AllStarFeed.model_validate(data).edition.teams) == 3


def test_rejects_two_champions() -> None:
    data = feed()
    data["edition"]["teams"] = [team("STR", "champion"), team("WAV", "champion")]
    recount(data["edition"])

    with pytest.raises(ValidationError, match="champion"):
        AllStarFeed.model_validate(data)


def test_accepts_an_mvp_whose_totals_are_the_sums_of_the_lines() -> None:
    assert AllStarMvp.model_validate(mvp()).totals.games == 2


def test_accepts_null_top5_values_ordered_with_a_missing_value_as_zero() -> None:
    row = {**top5(10), "rebounds": None, "assists": None}
    rows = [top5(10, 1, 1), row]

    assert len(AllStarGame.model_validate(game(top5=rows)).top5) == 2


def test_accepts_an_mvp_with_a_null_line_value_and_a_null_total() -> None:
    data = mvp()
    data["lines"][1]["rebounds"] = None
    data["totals"]["rebounds"] = None

    parsed = AllStarMvp.model_validate(data)

    assert parsed.totals.rebounds is None and parsed.totals.points == 30


def test_rejects_an_mvp_total_that_is_not_null_when_a_line_is_null() -> None:
    data = mvp()
    data["lines"][1]["rebounds"] = None

    with pytest.raises(ValidationError, match="totals"):
        AllStarMvp.model_validate(data)


def test_rejects_mvp_totals_that_differ_from_the_lines() -> None:
    totals = {"games": 2, "points": 31, "rebounds": 10, "assists": 8}

    with pytest.raises(ValidationError, match="totals"):
        AllStarMvp.model_validate(mvp(totals=totals))


def test_rejects_an_mvp_without_lines() -> None:
    totals = {"games": 1, "points": 0, "rebounds": 0, "assists": 0}

    with pytest.raises(ValidationError):
        AllStarMvp.model_validate(mvp(lines=[], totals=totals))


def with_previous(edition: dict[str, Any], state: str = "after") -> dict[str, Any]:
    return feed(state, previous=recap(), previous_edition=edition)


def test_accepts_a_feed_with_a_previous_edition() -> None:
    parsed = AllStarFeed.model_validate(with_previous(previous_edition()))

    assert parsed.previous_edition is not None
    assert parsed.previous_edition.mvp is not None
    assert parsed.previous_edition.counts.final == 1
    assert parsed.previous_edition.default_game_id == "g1"


def test_accepts_a_before_feed_with_a_previous_edition() -> None:
    parsed = AllStarFeed.model_validate(with_previous(previous_edition(), "before"))

    assert parsed.state == "before" and parsed.previous_edition is not None


def test_accepts_a_previous_edition_without_an_mvp() -> None:
    parsed = AllStarFeed.model_validate(with_previous(previous_edition(mvp=None)))

    assert parsed.previous_edition is not None
    assert parsed.previous_edition.mvp is None


def test_rejects_a_previous_edition_with_a_game_not_final() -> None:
    games = [game(), game("scheduled", id="g2", championship=False)]

    with pytest.raises(ValidationError, match="every game of a previous edition"):
        AllStarFeed.model_validate(with_previous(previous_edition(games=games)))


def test_rejects_a_previous_edition_without_games() -> None:
    with pytest.raises(ValidationError, match="date and games"):
        AllStarFeed.model_validate(with_previous(previous_edition(games=[])))


def test_rejects_a_previous_edition_without_a_date() -> None:
    with pytest.raises(ValidationError, match="date and games"):
        AllStarFeed.model_validate(with_previous(previous_edition(date=None)))


def test_rejects_a_previous_edition_without_the_recap() -> None:
    data = feed("after", previous_edition=previous_edition())

    with pytest.raises(ValidationError, match="the recap"):
        AllStarFeed.model_validate(data)


def test_rejects_a_previous_edition_whose_date_differs_from_the_recap() -> None:
    data = feed(
        "after",
        previous=recap(date=dt.date(2026, 2, 14)),
        previous_edition=previous_edition(),
    )

    with pytest.raises(ValidationError, match="the recap"):
        AllStarFeed.model_validate(data)


def test_a_previous_edition_carries_its_counts_and_default_game() -> None:
    games = [game(), game(id="g2", championship=False)]

    parsed = AllStarFeed.model_validate(
        with_previous(previous_edition(games=games))
    ).previous_edition

    assert parsed is not None
    assert parsed.counts.games == 2 and parsed.default_game_id == "g1"


@pytest.mark.parametrize("key", ["games", "teams", "final", "live"])
def test_rejects_counts_that_differ_from_the_lists(key: str) -> None:
    data = feed()
    data["edition"]["counts"][key] += 1

    with pytest.raises(ValidationError):
        AllStarFeed.model_validate(data)


def test_rejects_final_and_live_counts_above_the_games() -> None:
    data = feed()
    data["edition"]["counts"] = {"games": 1, "teams": 2, "final": 1, "live": 1}

    with pytest.raises(ValidationError, match="within the games"):
        AllStarFeed.model_validate(data)


def test_accepts_a_before_feed_with_zero_counts_and_no_default_game() -> None:
    parsed = AllStarFeed.model_validate(feed("before"))

    assert parsed.edition.counts.games == 0
    assert parsed.edition.default_game_id is None


def test_rejects_a_default_game_that_is_not_in_the_games() -> None:
    data = feed()
    data["edition"]["default_game_id"] = "g9"

    with pytest.raises(ValidationError, match="default game"):
        AllStarFeed.model_validate(data)


def test_rejects_a_default_game_with_no_games() -> None:
    data = feed("before")
    data["edition"]["default_game_id"] = "g1"

    with pytest.raises(ValidationError, match="default game"):
        AllStarFeed.model_validate(data)


def test_rejects_no_default_game_with_games() -> None:
    data = feed()
    data["edition"]["default_game_id"] = None

    with pytest.raises(ValidationError, match="default game"):
        AllStarFeed.model_validate(data)


def test_rejects_two_next_games() -> None:
    games = [
        game(),
        game("scheduled", id="g2", championship=False, is_next=True),
        game("scheduled", id="g3", championship=False, is_next=True),
    ]

    with pytest.raises(ValidationError, match="next game"):
        AllStarFeed.model_validate(feed("live", games))


def test_accepts_one_next_game_that_is_scheduled() -> None:
    games = [game(), game("scheduled", id="g2", championship=False, is_next=True)]

    parsed = AllStarFeed.model_validate(feed("live", games))

    assert [g.is_next for g in parsed.edition.games] == [False, True]


@pytest.mark.parametrize("status", ["live", "final"])
def test_rejects_a_next_game_that_is_live_or_final(status: str) -> None:
    changes: dict[str, Any] = {"is_next": True}
    if status == "final":
        changes["leading"] = None

    with pytest.raises(ValidationError, match="next game"):
        AllStarGame.model_validate(game(status, **changes))


def test_accepts_a_leading_side_of_a_live_game_and_none_on_a_tie() -> None:
    assert AllStarGame.model_validate(game("live")).leading == "away"
    tie = game("live", score={"away": 20, "home": 20}, leading=None)

    assert AllStarGame.model_validate(tie).leading is None


def test_rejects_a_leading_side_on_a_final_game() -> None:
    with pytest.raises(ValidationError, match="leading"):
        AllStarGame.model_validate(game(leading="away"))


def test_rejects_a_leading_side_that_is_not_the_higher_score() -> None:
    with pytest.raises(ValidationError, match="leading"):
        AllStarGame.model_validate(game("live", leading="home"))
    with pytest.raises(ValidationError, match="leading"):
        AllStarGame.model_validate(game("live", leading=None))


def test_accepts_top_points_on_every_tied_top_scorer() -> None:
    parsed = AllStarTeamBox.model_validate(box((20, True), (20, True), (5, False)))

    assert [p.top_points for p in parsed.players] == [True, True, False]


def test_rejects_top_points_on_a_player_below_the_top() -> None:
    with pytest.raises(ValidationError, match="topPoints"):
        AllStarTeamBox.model_validate(box((20, True), (5, True)))


def test_rejects_top_points_missing_on_the_top_scorer() -> None:
    with pytest.raises(ValidationError, match="topPoints"):
        AllStarTeamBox.model_validate(box((20, False), (5, False)))


def test_accepts_no_top_points_in_a_team_box_with_no_points() -> None:
    parsed = AllStarTeamBox.model_validate(box((0, False), (0, False)))

    assert not any(p.top_points for p in parsed.players)
    assert AllStarTeamBox.model_validate(box()).players == []


def test_rejects_top_points_on_a_team_with_no_points() -> None:
    with pytest.raises(ValidationError, match="topPoints"):
        AllStarTeamBox.model_validate(box((0, True)))


def test_rejects_a_team_record_that_differs_from_its_results() -> None:
    data = feed()
    data["edition"]["teams"][0]["results"] = [result()]

    with pytest.raises(ValidationError, match="wins and losses"):
        AllStarFeed.model_validate(data)


def test_accepts_a_team_record_that_matches_its_results() -> None:
    data = feed()
    stripes = data["edition"]["teams"][0]
    stripes["results"] = [result(), result(game_id="g2", result="loss", team_score=1)]
    stripes["wins"], stripes["losses"] = 1, 1
    stripes["results"][1]["opponent_score"] = 5

    parsed = AllStarFeed.model_validate(data)

    assert len(parsed.edition.teams[0].results) == 2


@pytest.mark.parametrize(
    "changes",
    [
        {"result": "loss"},
        {"result": "win", "team_score": 10, "opponent_score": 20},
        {"team_score": 20, "opponent_score": 20},
    ],
)
def test_rejects_a_result_that_does_not_match_its_scores(
    changes: dict[str, Any],
) -> None:
    with pytest.raises(ValidationError):
        AllStarTeamResult.model_validate(result(**changes))


EDITION_HIGHLIGHT = {
    "title": "Example All-Star Game Highlights",
    "channel": "Example Channel",
    "thumbnail_url": "https://example.com/t.jpg",
    "embed_url": "https://example.com/e/v1",
}


def test_accepts_an_edition_highlight_on_the_edition_the_previous_edition_and_the_recap() -> (
    None
):
    data = with_previous(previous_edition(edition_highlight=EDITION_HIGHLIGHT), "after")
    data["edition"]["edition_highlight"] = EDITION_HIGHLIGHT
    data["previous"]["edition_highlight"] = EDITION_HIGHLIGHT

    parsed = AllStarFeed.model_validate(data)

    assert parsed.edition.edition_highlight is not None
    assert parsed.previous is not None and parsed.previous.edition_highlight is not None
    assert parsed.previous_edition is not None
    assert parsed.previous_edition.edition_highlight is not None
    assert parsed.edition.edition_highlight.title == EDITION_HIGHLIGHT["title"]


def test_reads_a_stored_feed_without_an_edition_highlight_as_null() -> None:
    data = with_previous(previous_edition())

    parsed = AllStarFeed.model_validate(data)

    assert parsed.edition.edition_highlight is None
    assert parsed.previous is not None and parsed.previous.edition_highlight is None
    assert parsed.previous_edition is not None
    assert parsed.previous_edition.edition_highlight is None


def test_rejects_an_invalid_edition_highlight() -> None:
    data = feed()
    data["edition"]["edition_highlight"] = {
        **EDITION_HIGHLIGHT,
        "thumbnail_url": "not a url",
    }

    with pytest.raises(ValidationError):
        AllStarFeed.model_validate(data)


def test_accepts_a_build_version_and_rejects_zero_and_reads_none_as_null() -> None:
    stored = feed("after")
    assert AllStarFeed.model_validate(stored).build_version is None

    assert AllStarFeed.model_validate({**stored, "buildVersion": 1}).build_version == 1
    with pytest.raises(ValidationError):
        AllStarFeed.model_validate({**stored, "buildVersion": 0})


def test_accepts_a_target_score_format_with_untimed() -> None:
    data = feed()
    data["edition"]["format"] = format_parts(
        target_points=40, untimed=True, periods=None, minutes=None
    )

    parsed = AllStarFeed.model_validate(data)

    assert parsed.edition.format is not None
    assert parsed.edition.format.target_points == 40
    assert parsed.edition.format.untimed is True


def test_accepts_a_periods_and_minutes_format() -> None:
    parsed = AllStarFeed.model_validate(feed())

    assert parsed.edition.format is not None
    assert (parsed.edition.format.periods, parsed.edition.format.minutes) == (1, 12.0)


def test_rejects_a_format_with_both_shapes_or_neither() -> None:
    with pytest.raises(ValidationError):
        AllStarFormat.model_validate(format_parts(target_points=40))
    with pytest.raises(ValidationError):
        AllStarFormat.model_validate(format_parts(periods=None, minutes=None))
    with pytest.raises(ValidationError):
        AllStarFormat.model_validate(format_parts(periods=1, minutes=None))


def test_rejects_untimed_without_a_target_score() -> None:
    with pytest.raises(ValidationError):
        AllStarFormat.model_validate(format_parts(untimed=True))


def test_rejects_the_retired_format_line_key() -> None:
    data = feed()
    data["edition"]["format_line"] = "1 period · 12 min"

    with pytest.raises(ValidationError):
        AllStarFeed.model_validate(data)
