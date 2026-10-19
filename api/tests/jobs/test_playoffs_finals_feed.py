# api/tests/jobs/test_playoffs_finals_feed.py
#
# Tests for the playoffs finals feed builder and its feed kind.
#
# Tested:
# - Games: only the final Finals games in number order with the stored series game; games not played are absent; an overtime game keeps overtime; a scheduled game is not listed
# - Leaders come from the detail; a failed detail leaves the leaders, the curve and the deficit null and keeps the score
# - Curve team: the champion when complete, the leader at 3-1, the top side at 2-2; an away curve team gets one minus the home value to 3 decimals; no win probability gives a null curve
# - Largest deficit: its value and the second of the first play at it; null when never trailed, with no scored plays and with no read
# - Finals MVP: the season row averages, the best game by points with the earliest game on a tie, null with no finals_mvp award or no awards, null values with no season row or a failed read
# - Road: seed, regular season record, postseason record, the series with opponent, seed, wins, losses and result, the in-progress Finals with no result, a null record on a failed read
# - Head to head: 8 bars in order with percentages as fractions, the higher value better and technical fouls lower better, equal values with no better, null values with a failed read, the records of the road
# - Averages: one row per roster player in jersey order, a player with no stats last with null values
# - Errors: an invalid feed, a non-numeric jersey, no Finals game and a Finals side with no team fail with a build error
# - The kind: check answers unknown for another id, a Finals with no game and another season; not ready with no playoffs feed; nothing is read
# - The kind: no feed is built, stored or fetched without a request; a request builds the playoffs feed first and stores the finals feed; a second reads storage
# - The kind: each roster player is read once, the MVP on a roster is not read twice, a player who changed team is left out
# - The kind: the reads get the game's final time as freshness when known, else 1 hour
# - The kind: a failed build keeps and serves the stored feed and is not retried for 10 minutes
# - The kind: expiry (a postseason final game plus 1 hour, the playoffs feed rebuilt, 7 days, kept when complete while the season is current)
# - The kind: serving reads only the highlights of the Finals games
# - The kind: highlights and detailAvailable are added when served and not stored; the cleanup keeps league
#
# What is covered:
# - Pure conversions: happy path, edges and errors; the built feed validates
# - Feed kind: success publishes a valid feed, failure keeps the last valid feed, expiry edges
#
# Fake adapters and a fake clock are passed to the builder and the kind, so no
# test uses a real source or the real clock.
#
# Run with: cd api && .venv/bin/python -m pytest tests/jobs/test_playoffs_finals_feed.py
#
# SEE: api/app/jobs/playoffs_finals_feed.py

import datetime as dt
from collections.abc import Iterable
from pathlib import Path
from typing import Any, cast

import pytest
from pydantic import HttpUrl

from app.feeds.game_detail import GameResult
from app.feeds.games import GameStatus, Highlight, Leader, Leaders
from app.feeds.playoffs import AwardCode, PlayoffsFeed, SeriesId, SeriesStatus
from app.feeds.playoffs_finals import (
    HeadToHeadStat,
    PlayoffsFinalsFeed,
    RosterAverages,
)
from app.jobs import playoffs_feed
from app.jobs.games import GamesJob
from app.jobs.on_demand import (
    RETRY_AFTER,
    FeedUnavailableError,
    IdStatus,
    UnknownFeedError,
)
from app.jobs.playoffs_finals_feed import (
    FEED_ID,
    KIND,
    FinalsBuildError,
    FinalsSources,
    PlayoffsFinalsFeeds,
    build_finals_feed,
)
from app.jobs.stars import StarsJob
from app.jobs.team_feed import FEED_LIFETIME
from app.settings import Settings
from app.sources.finals_plays import PlayScore
from app.sources.game_detail import GameDetail, GameDetailSections
from app.sources.http import Freshness, SourceClient
from app.sources.player_stats import PlayerStats, StatLine
from app.sources.postseason_scoreboard import PostseasonGame
from app.sources.season_awards import SeasonAwards
from app.sources.team_players import RosterEntry
from app.sources.team_postseason import TeamPostseasonRecord, TeamPostseasonStats
from app.storage.feeds import read_by_id
from tests.jobs.test_playoffs_feed import (
    ALL,
    EAST,
    HOUR,
    NOW,
    SECOND,
    PlayoffsKit,
    award,
    both,
    finals,
    play_ins,
    player,
    round_one,
    round_three,
    round_two,
    seed,
    standings,
)
from tests.jobs.test_playoffs_feed import build as build_playoffs

TOP = ALL[0]
BOTTOM = ALL[15]
LABEL = "2026-27"
PLAYERS = {
    TOP: [player("101", jersey="5"), player("102", jersey="3")],
    BOTTOM: [player("201", jersey="1"), player("202", jersey="2")],
}
PERIODS = {
    "periods": [
        {"number": n, "start_elapsed_seconds": (n - 1) * 720} for n in range(1, 5)
    ],
    "end_elapsed_seconds": 2880,
}

# Group 1: the builder


def postseason(results: str = "TTTT", **changes: Any) -> list[PostseasonGame]:
    return (
        play_ins()
        + both(round_one)
        + both(round_two)
        + both(round_three)
        + finals(results, **changes)
    )


def playoffs_of(
    results: str = "TTTT",
    *,
    mvp: bool = True,
    awards: SeasonAwards | None = None,
    **changes: Any,
) -> PlayoffsFeed:
    roster = {
        pid: (code, entry)
        for code, entries in PLAYERS.items()
        for pid, entry in ((e.player_id, e) for e in entries)
    }
    found = awards
    if found is None and mvp:
        found = SeasonAwards(awards=[award(AwardCode.FINALS_MVP, ["101"])])
    return build_playoffs(
        postseason(results, **changes),
        players=roster,
        awards=found,
        standing=standings(changes={BOTTOM: {"wins": 58, "losses": 24}}),
    )


def leader(code: str, player_id: str) -> Leader:
    return Leader(
        player_id=player_id,
        display_name=f"Example {player_id}",
        team_code=code,
        photo_url=None,
        points=20,
        rebounds=5,
        assists=4,
    )


def detail() -> GameDetail:
    stats = {
        "field_goal_pct": 0.5,
        "three_point_pct": 0.4,
        "rebounds": 40,
        "assists": 20,
        "turnovers": 10,
    }
    return GameDetail.model_validate(
        {
            "leaders": Leaders(away=leader(BOTTOM, "201"), home=leader(TOP, "101")),
            "team_stats": {"away": stats, "home": stats},
        }
    )


def box_line(player_id: str, points: int) -> dict[str, Any]:
    zeros = dict.fromkeys(
        (
            "field_goals_made",
            "field_goals_attempted",
            "three_points_made",
            "three_points_attempted",
            "free_throws_made",
            "free_throws_attempted",
            "offensive_rebounds",
            "defensive_rebounds",
            "rebounds",
            "assists",
            "turnovers",
            "steals",
            "blocks",
            "fouls",
        ),
        0,
    )
    return zeros | {
        "player_id": player_id,
        "display_name": f"Example {player_id}",
        "starter": True,
        "minutes": "30",
        "plus_minus": 0,
        "photo_url": None,
        "points": points,
    }


def team_box(*lines: dict[str, Any]) -> dict[str, Any]:
    totals = {k: v for k, v in box_line("x", 0).items() if k in box_line("x", 0)}
    for name in ("player_id", "display_name", "starter", "minutes", "plus_minus"):
        totals.pop(name)
    totals.pop("photo_url")
    totals |= {"field_goal_pct": 0.5, "three_point_pct": 0.4, "free_throw_pct": 0.8}
    return {"players": list(lines), "totals": totals}


def sections(
    home: float = 0.8333,
    *,
    top_points: int | None = None,
    curve: bool = True,
) -> GameDetailSections:
    data: dict[str, Any] = {"venue": {"name": "Example Arena"}}
    if curve:
        data["win_probability"] = [
            {"elapsed_seconds": 0, "home_win_probability": 0.5},
            {"elapsed_seconds": 1440, "home_win_probability": home},
        ]
        data["win_probability_periods"] = PERIODS
    if top_points is not None:
        data["box_score"] = {
            "away": team_box(box_line("201", 10)),
            "home": team_box(box_line("101", top_points)),
        }
    return GameDetailSections.model_validate(data)


def stat_line(points: float, *, season: str = LABEL, **changes: Any) -> StatLine:
    values: dict[str, Any] = {
        "season": season,
        "games_played": 6,
        "field_goals": "8.0-16.0",
        "field_goal_pct": 50.0,
        "three_points": "2.0-5.0",
        "three_point_pct": 40.0,
        "free_throws": "3.0-4.0",
        "free_throw_pct": 75.0,
        "offensive_rebounds": 1.0,
        "defensive_rebounds": 4.0,
        "rebounds": 5.0,
        "assists": 4.0,
        "blocks": 1.0,
        "steals": 1.0,
        "fouls": 2.0,
        "turnovers": 2.0,
        "points": points,
    }
    return StatLine.model_validate(values | changes)


def stats_of(points: float, **changes: Any) -> PlayerStats:
    return PlayerStats(per_game=[stat_line(points, **changes)])


def record() -> TeamPostseasonRecord:
    return TeamPostseasonRecord(overall="16-6", home="9-2", road="7-4")


def team_stats(**changes: Any) -> TeamPostseasonStats:
    values: dict[str, Any] = {
        "points": 112.4,
        "rebounds": 44.0,
        "assists": 26.0,
        "blocks": 5.0,
        "steals": 7.0,
        "field_goal_pct": 47.2,
        "effective_fg_pct": 54.9,
        "technical_fouls": 3.0,
        "games_played": 22,
    }
    return TeamPostseasonStats.model_validate(values | changes)


def final_ids(feed: PlayoffsFeed) -> list[str]:
    finals_series = next(s for s in feed.bracket if s.id is SeriesId.FINALS)
    return [g.id for g in finals_series.games if g.status is GameStatus.FINAL]


def sources(feed: PlayoffsFeed | None = None, **changes: Any) -> FinalsSources:
    found = feed or playoffs_of()
    ids = final_ids(found)
    values: dict[str, Any] = {
        "playoffs": found,
        "rosters": PLAYERS,
        "details": {i: detail() for i in ids},
        "sections": {i: sections() for i in ids},
        "plays": {i: [] for i in ids},
        "player_stats": {"101": stats_of(28.5), "102": stats_of(10.0)},
        "records": {TOP: record(), BOTTOM: record()},
        "team_stats": {TOP: team_stats(), BOTTOM: team_stats()},
    }
    return FinalsSources(**(values | changes))


def built(feed: PlayoffsFeed | None = None, **changes: Any) -> PlayoffsFinalsFeed:
    return build_finals_feed(sources(feed, **changes))


def averages_of(feed: PlayoffsFinalsFeed) -> list[RosterAverages]:
    """The averages of a current feed, which always has them."""
    assert feed.averages is not None
    return feed.averages


def failing(feed: PlayoffsFeed | None = None, **changes: Any) -> str:
    with pytest.raises(FinalsBuildError) as raised:
        build_finals_feed(sources(feed, **changes))
    return raised.value.reason


# Games


def test_the_games_are_the_final_finals_games_in_number_order() -> None:
    feed = built(playoffs_of("TBT", scheduled=2))

    assert [g.game.number for g in feed.games] == [1, 2, 3]
    assert all(g.game.status is GameStatus.FINAL for g in feed.games)
    assert feed.games[0].game.id == "finals-1"
    assert feed.games[0].game.score is not None
    assert feed.status is SeriesStatus.IN_PROGRESS
    assert feed.champion is None


def test_games_not_played_are_absent() -> None:
    feed = built(playoffs_of("TT", scheduled=5))

    assert [g.game.number for g in feed.games] == [1, 2]


def test_an_overtime_game_keeps_overtime() -> None:
    games = postseason("TTT")
    index = next(i for i, g in enumerate(games) if g.game.id == "finals-2")
    games[index] = games[index].model_copy(update={"period": 5})
    plain = playoffs_of("TTT")
    overtime = build_playoffs(games, players={}, awards=None)

    assert [g.overtime for g in _finals_games(plain)] == [False, False, False]
    assert [g.overtime for g in _finals_games(overtime)] == [False, True, False]


def _finals_games(feed: PlayoffsFeed) -> list[Any]:
    return next(s for s in feed.bracket if s.id is SeriesId.FINALS).games


def test_the_leaders_come_from_the_detail() -> None:
    feed = built()

    leaders = feed.games[0].leaders
    assert leaders is not None
    assert (leaders.home.player_id, leaders.away.player_id) == ("101", "201")


def test_a_failed_detail_nulls_the_leaders_the_curve_and_the_deficit_not_the_score() -> (
    None
):
    base = playoffs_of()
    feed = built(
        base,
        details=dict.fromkeys(final_ids(base)),
        sections=dict.fromkeys(final_ids(base)),
        plays=dict.fromkeys(final_ids(base)),
    )

    for entry in feed.games:
        assert entry.leaders is None
        assert entry.win_probability is None
        assert entry.largest_deficit is None
        assert entry.game.score is not None


# Curve team


def test_the_curve_team_is_the_champion_when_the_series_is_complete() -> None:
    assert built(playoffs_of("TTTT")).curve_team == TOP
    assert built(playoffs_of("BBBB")).curve_team == BOTTOM
    assert built(playoffs_of("BBBB")).champion == BOTTOM


def test_the_curve_team_is_the_leader_in_the_series() -> None:
    assert built(playoffs_of("TBBB", scheduled=1)).curve_team == BOTTOM
    assert built(playoffs_of("TTB", scheduled=1)).curve_team == TOP


def test_the_curve_team_is_the_top_side_at_two_wins_each() -> None:
    assert built(playoffs_of("TBTB", scheduled=1)).curve_team == TOP


def test_the_curve_is_the_home_value_for_a_home_curve_team_and_one_minus_it_away() -> (
    None
):
    feed = built()

    home_game = feed.games[0]  # the curve team (top) is home in game 1
    away_game = feed.games[2]  # and away in game 3
    assert home_game.win_probability is not None
    assert away_game.win_probability is not None
    assert [p.win_probability for p in home_game.win_probability.points] == [
        0.5,
        0.833,
    ]
    assert [p.win_probability for p in away_game.win_probability.points] == [
        0.5,
        0.167,
    ]
    assert home_game.win_probability.periods.end_elapsed_seconds == 2880


def test_no_win_probability_gives_a_null_curve() -> None:
    base = playoffs_of()
    feed = built(base, sections={i: sections(curve=False) for i in final_ids(base)})

    assert all(g.win_probability is None for g in feed.games)


# Largest deficit


def plays(*rows: tuple[int, int, int]) -> list[PlayScore]:
    return [
        PlayScore(elapsed_seconds=s, home_score=h, away_score=a) for s, h, a in rows
    ]


def test_the_largest_deficit_is_the_most_points_behind_at_the_first_play_reaching_it() -> (
    None
):
    rows = plays((30, 0, 2), (120, 3, 12), (600, 40, 50), (700, 45, 55), (800, 60, 50))
    feed = built(plays={"finals-1": rows})

    deficit = feed.games[0].largest_deficit
    assert deficit is not None
    assert (deficit.points, deficit.elapsed_seconds) == (10, 600)


def test_the_deficit_is_the_away_curve_teams_when_it_is_away() -> None:
    rows = plays((30, 5, 2), (120, 20, 8), (200, 22, 9), (900, 30, 40))
    feed = built(plays={"finals-3": rows})

    deficit = feed.games[2].largest_deficit
    assert deficit is not None
    assert (deficit.points, deficit.elapsed_seconds) == (13, 200)


def test_the_deficit_is_null_when_the_team_never_trailed_or_no_play_has_scores() -> (
    None
):
    ahead = plays((30, 2, 0), (120, 9, 8))
    feed = built(plays={"finals-1": ahead, "finals-2": [], "finals-3": None})

    assert feed.games[0].largest_deficit is None
    assert feed.games[1].largest_deficit is None
    assert feed.games[2].largest_deficit is None


# Finals MVP


def test_the_finals_mvp_has_the_averages_of_the_season_row() -> None:
    mvp = built().finals_mvp

    assert mvp is not None
    assert (mvp.player_id, mvp.name, mvp.team_code) == (
        "101",
        "Example Player101",
        TOP,
    )
    assert str(mvp.photo_url) == "https://example.com/101.png"
    assert (mvp.games, mvp.points, mvp.rebounds, mvp.assists) == (6, 28.5, 5.0, 4.0)


def test_the_best_game_is_the_most_points_and_a_tie_goes_to_the_earliest_game() -> None:
    base = playoffs_of()
    ids = final_ids(base)
    box = {
        i: sections(top_points=p) for i, p in zip(ids, (30, 35, 35, 20), strict=True)
    }

    mvp = built(base, sections=box).finals_mvp

    assert mvp is not None and mvp.best_game is not None
    assert (mvp.best_game.game_id, mvp.best_game.number, mvp.best_game.points) == (
        "finals-2",
        2,
        35,
    )


def test_the_best_game_is_null_when_no_box_score_has_the_player() -> None:
    mvp = built().finals_mvp

    assert mvp is not None and mvp.best_game is None


def test_the_finals_mvp_is_null_with_no_award_or_no_awards() -> None:
    other = SeasonAwards(awards=[award(AwardCode.MVP, ["101"])])

    assert built(playoffs_of(awards=other)).finals_mvp is None
    assert built(playoffs_of(mvp=False)).finals_mvp is None


def test_the_mvp_values_are_null_with_no_season_row_or_a_failed_read() -> None:
    wrong = {"101": stats_of(28.5, season="2025-26")}
    for found in (wrong, {"101": None}, {}):
        mvp = built(player_stats=found).finals_mvp
        assert mvp is not None
        assert (mvp.games, mvp.points, mvp.rebounds, mvp.assists) == (
            None,
            None,
            None,
            None,
        )


# Road


def test_the_road_has_the_seed_the_records_and_the_series() -> None:
    road = built().road

    assert [r.team.code for r in road] == [TOP, BOTTOM]
    assert (road[0].seed, road[0].regular_season, road[0].postseason) == (
        1,
        "60-22",
        "16-6",
    )
    assert (road[1].seed, road[1].regular_season) == (1, "58-24")
    first = road[0].series[0]
    assert first.round == 1
    assert first.opponent.code == seed(EAST, 8)
    assert (first.opponent_seed, first.wins, first.losses) == (8, 4, 0)
    assert first.result is GameResult.WIN
    assert [s.round for s in road[0].series] == [1, 2, 3, 4]
    assert road[0].series[3].opponent.code == BOTTOM
    assert road[1].series[3].result is GameResult.LOSS


def test_the_finals_in_progress_has_no_result() -> None:
    road = built(playoffs_of("TBT", scheduled=2)).road

    last = road[0].series[3]
    assert (last.wins, last.losses, last.result) == (2, 1, None)
    assert road[1].series[3].result is None


def test_a_failed_record_read_gives_a_null_postseason_record() -> None:
    road = built(records={TOP: None, BOTTOM: record()}).road

    assert road[0].postseason is None
    assert road[1].postseason == "16-6"


# Head to head


def test_the_head_to_head_has_8_bars_in_order_with_percentages_as_fractions() -> None:
    head = built(
        records={
            TOP: TeamPostseasonRecord(overall="16-6", home="9-2", road="7-4"),
            BOTTOM: TeamPostseasonRecord(overall="16-5", home="9-2", road="7-3"),
        }
    ).head_to_head

    assert [bar.stat for bar in head.bars] == list(HeadToHeadStat)
    bar = {b.stat: b for b in head.bars}
    assert [v.value for v in bar[HeadToHeadStat.FIELD_GOAL_PCT].values] == [
        pytest.approx(0.472),
        pytest.approx(0.472),
    ]
    assert bar[HeadToHeadStat.POINTS].values[0].value == 112.4
    assert [(r.team_code, r.record) for r in head.records] == [
        (TOP, "16-6"),
        (BOTTOM, "16-5"),
    ]


def test_a_failed_record_read_gives_a_null_head_to_head_record() -> None:
    head = built(records={TOP: None, BOTTOM: record()}).head_to_head

    assert head.records[0].record is None
    assert head.records[1].record == "16-6"


def test_the_higher_value_is_better_and_technical_fouls_the_lower() -> None:
    head = built(
        team_stats={
            TOP: team_stats(points=120.0, technical_fouls=1.0),
            BOTTOM: team_stats(points=110.0, technical_fouls=4.0),
        }
    ).head_to_head

    bar = {b.stat: b for b in head.bars}
    assert bar[HeadToHeadStat.POINTS].better == TOP
    assert bar[HeadToHeadStat.TECHNICAL_FOULS].better == TOP
    flipped = built(
        team_stats={
            TOP: team_stats(technical_fouls=5.0),
            BOTTOM: team_stats(technical_fouls=2.0),
        }
    ).head_to_head
    assert {b.stat: b for b in flipped.bars}[HeadToHeadStat.TECHNICAL_FOULS].better == (
        BOTTOM
    )


def test_an_equal_value_has_no_better_team() -> None:
    bar = {b.stat: b for b in built().head_to_head.bars}

    assert all(b.better is None for b in bar.values())


def test_a_failed_stats_read_gives_null_values_and_no_better() -> None:
    head = built(team_stats={TOP: None, BOTTOM: team_stats()}).head_to_head

    for bar in head.bars:
        assert bar.values[0].value is None
        assert bar.values[1].value is not None
        assert bar.better is None


# Averages


def test_the_averages_list_each_roster_player_in_jersey_order() -> None:
    averages = averages_of(
        built(
            player_stats={
                "101": stats_of(28.5, field_goal_pct=51.0),
                "102": stats_of(10.0),
                "201": stats_of(5.0),
                "202": stats_of(7.0),
            }
        )
    )

    assert [a.team_code for a in averages] == [TOP, BOTTOM]
    assert [p.player_id for p in averages[0].players] == ["102", "101"]
    first = averages[0].players[1]
    assert (first.points, first.rebounds, first.assists, first.blocks) == (
        28.5,
        5.0,
        4.0,
        1.0,
    )
    assert first.field_goal_pct == pytest.approx(0.51)
    assert [p.player_id for p in averages[1].players] == ["201", "202"]


def test_a_player_without_stats_has_null_values_and_sits_at_the_end() -> None:
    players = averages_of(built(player_stats={"101": stats_of(28.5), "102": None}))[
        0
    ].players

    assert [p.player_id for p in players] == ["101", "102"]
    assert players[1].points is None and players[1].field_goal_pct is None


# Errors


def test_a_non_numeric_jersey_fails_the_build() -> None:
    odd = {TOP: [player("101", jersey="x1")], BOTTOM: PLAYERS[BOTTOM]}

    assert failing(rosters=odd) == "jersey number 'x1' is not a number"


def test_an_invalid_feed_fails_the_build_with_the_first_location() -> None:
    reason = failing(team_stats={TOP: team_stats(points=-5.0), BOTTOM: None})

    assert reason.startswith("invalid feed: 1 errors, first at")


def test_a_finals_with_no_game_fails_the_build() -> None:
    empty = build_playoffs(
        play_ins() + both(round_one) + both(round_two) + both(round_three)
    )

    assert failing(empty) == "the Finals has no game"


# Group 2: the kind

FINALS_KIND = KIND


class FinalsKit(PlayoffsKit):
    """The playoffs finals kind over the playoffs kit, with fake adapters that
    count their calls."""

    def __init__(self, path: Path) -> None:
        super().__init__(path)
        stars: Any = self.stars
        stars.roster_entries = self.roster_entries
        stars.player_team = self.player_team
        self.fresh: dict[str, Freshness] = {}
        self.line_of: dict[str, StatLine | None] = {}
        self.plays_of: dict[str, list[PlayScore]] = {}
        self.finals = PlayoffsFinalsFeeds(
            self.settings,
            self.store,
            self.client,
            self.cache,
            cast(GamesJob, self.games),
            cast(StarsJob, self.stars),
            self.playoffs,
            fetch_game_detail=self.fetch_game_detail,
            fetch_game_detail_sections=self.fetch_game_detail_sections,
            fetch_play_scores=self.fetch_play_scores,
            fetch_player_stats=self.fetch_player_stats,
            fetch_team_postseason_record=self.fetch_finals_record,
            fetch_team_postseason_stats=self.fetch_team_postseason_stats,
        )
        self.load(postseason())

    def roster_entries(self) -> dict[str, list[RosterEntry]]:
        return {
            TOP: [*PLAYERS[TOP], player("103", jersey="9")],
            BOTTOM: list(PLAYERS[BOTTOM]),
            ALL[1]: [player("301", jersey="4")],
        }

    def player_team(self, player_id: str) -> str | None:
        return {"103": ALL[2], "301": ALL[1]}.get(
            player_id, TOP if player_id.startswith("1") else BOTTOM
        )

    async def fetch_season_awards(
        self, client: SourceClient, season: int, settings: Settings
    ) -> SeasonAwards:
        self.read("awards")
        return SeasonAwards(awards=[award(AwardCode.FINALS_MVP, ["101"])])

    async def fetch_game_detail(
        self, client: SourceClient, game_id: str, settings: Settings, fresh: Freshness
    ) -> GameDetail:
        self.read(f"detail/{game_id}")
        self.fresh[f"detail/{game_id}"] = fresh
        return detail()

    async def fetch_game_detail_sections(
        self, client: SourceClient, game_id: str, settings: Settings, fresh: Freshness
    ) -> GameDetailSections:
        self.read(f"sections/{game_id}")
        self.fresh[f"sections/{game_id}"] = fresh
        return sections()

    async def fetch_play_scores(
        self, client: SourceClient, game_id: str, settings: Settings, fresh: Freshness
    ) -> list[PlayScore]:
        self.read(f"plays/{game_id}")
        self.fresh[f"plays/{game_id}"] = fresh
        return self.plays_of.get(game_id, [])

    async def fetch_player_stats(
        self, client: SourceClient, player_id: str, settings: Settings, **query: Any
    ) -> PlayerStats:
        assert query == {"playoffs": True}
        self.read(f"player/{player_id}")
        return stats_of(10.0)

    async def fetch_finals_record(
        self, client: SourceClient, team: str, season: int, settings: Settings
    ) -> TeamPostseasonRecord:
        self.read(f"finals-record/{team}")
        return record()

    async def fetch_team_postseason_stats(
        self, client: SourceClient, team: str, season: int, settings: Settings
    ) -> TeamPostseasonStats:
        self.read(f"stats/{team}")
        return team_stats()

    async def serve_finals(self, at: dt.datetime | None = None) -> bytes:
        await self.serve(at)
        body = await self.cache.serve(KIND, FEED_ID)
        await self.settle()
        return body

    def stored_finals(self) -> PlayoffsFinalsFeed | None:
        body = read_by_id(self.path, KIND, FEED_ID)
        return None if body is None else PlayoffsFinalsFeed.model_validate_json(body)

    def finals_build(self) -> dt.datetime | None:
        state = self.store.feed_build(KIND, FEED_ID)
        return None if state is None else state.last_build


@pytest.fixture
def kit(tmp_path: Path) -> FinalsKit:
    return FinalsKit(tmp_path)


@pytest.mark.anyio
async def test_an_id_other_than_league_answers_unknown_and_nothing_is_read(
    kit: FinalsKit,
) -> None:
    for feed_id in ("LEAGUE", "finals", ""):
        assert kit.finals.check(feed_id) is IdStatus.UNKNOWN
        with pytest.raises(UnknownFeedError):
            await kit.cache.serve(KIND, feed_id)

    assert kit.calls == []


@pytest.mark.anyio
async def test_with_no_stored_playoffs_feed_it_answers_not_ready(
    kit: FinalsKit,
) -> None:
    assert kit.finals.check(FEED_ID) is IdStatus.NOT_READY
    with pytest.raises(FeedUnavailableError):
        await kit.cache.serve(KIND, FEED_ID)

    assert kit.calls == []


@pytest.mark.anyio
async def test_a_finals_with_no_game_answers_unknown_and_nothing_is_read(
    kit: FinalsKit,
) -> None:
    kit.load(play_ins() + both(round_one))
    await kit.serve()
    kit.calls.clear()

    assert kit.finals.check(FEED_ID) is IdStatus.UNKNOWN
    with pytest.raises(UnknownFeedError):
        await kit.cache.serve(KIND, FEED_ID)
    assert kit.calls == []


@pytest.mark.anyio
async def test_a_playoffs_feed_of_another_season_answers_unknown(
    kit: FinalsKit,
) -> None:
    await kit.serve()
    kit.stars.season = 2028

    assert kit.finals.check(FEED_ID) is IdStatus.UNKNOWN


@pytest.mark.anyio
async def test_no_feed_is_built_stored_or_fetched_without_a_request(
    kit: FinalsKit,
) -> None:
    await kit.settle()

    assert kit.calls == []
    assert kit.stored_finals() is None
    assert kit.store.feed_build_ids(KIND) == set()


@pytest.mark.anyio
async def test_a_request_builds_a_stale_playoffs_feed_first_and_stores_the_finals_feed(
    kit: FinalsKit,
) -> None:
    kit.load(postseason("TBT", scheduled=2))
    await kit.serve()
    kit.store.record_build(playoffs_feed.KIND, FEED_ID, NOW - 8 * FEED_LIFETIME)

    body = await kit.cache.serve(KIND, FEED_ID)
    await kit.settle()

    feed = PlayoffsFinalsFeed.model_validate_json(body)
    assert feed == kit.stored_finals()
    assert kit.called("standings") == 2
    assert kit.called("detail/") == 3
    assert kit.called("sections/") == 3
    assert kit.called("plays/") == 3
    assert kit.called("finals-record/") == 2
    assert kit.called("stats/") == 2
    assert kit.finals_build() == NOW

    again = await kit.cache.serve(KIND, FEED_ID)

    assert again == body
    assert kit.called("detail/") == 3


@pytest.mark.anyio
async def test_each_roster_player_is_read_once_and_a_player_who_changed_team_is_left_out(
    kit: FinalsKit,
) -> None:
    await kit.serve_finals()

    reads = sorted(n for n in kit.calls if n.startswith("player/"))
    assert reads == ["player/101", "player/102", "player/201", "player/202"]
    stored = kit.stored_finals()
    assert stored is not None
    assert [p.player_id for p in averages_of(stored)[0].players] == ["102", "101"]


@pytest.mark.anyio
async def test_the_mvp_off_the_rosters_is_read_once(kit: FinalsKit) -> None:
    stars: Any = kit.stars
    stars.roster_entries = lambda: {
        TOP: [player("102", jersey="3")],
        BOTTOM: [player("201", jersey="1")],
        ALL[1]: [player("101", jersey="3")],
    }
    stars.player_team = lambda pid: {"101": ALL[1]}.get(
        pid, TOP if pid[0] == "1" else BOTTOM
    )

    await kit.serve_finals()

    assert sorted(n for n in kit.calls if n.startswith("player/")) == [
        "player/101",
        "player/102",
        "player/201",
    ]


@pytest.mark.anyio
async def test_the_game_reads_get_the_final_time_as_freshness_when_known_else_1_hour(
    kit: FinalsKit,
) -> None:
    kit.store.set_final_time("finals-2", NOW.date(), NOW - 2 * HOUR)

    await kit.serve_finals()

    for name in ("detail", "sections", "plays"):
        assert kit.fresh[f"{name}/finals-2"] == NOW - 2 * HOUR
        assert kit.fresh[f"{name}/finals-1"] == HOUR


@pytest.mark.anyio
async def test_a_failed_build_keeps_and_serves_the_stored_feed_and_is_not_retried_for_10_minutes(
    kit: FinalsKit,
) -> None:
    kit.load(postseason("TBT", scheduled=2))
    first = await kit.serve_finals()
    built_at = kit.finals_build()
    kit.stars.season = None
    kit.clock[0] = NOW + FEED_LIFETIME

    body = await kit.serve_finals()
    state = kit.store.feed_build(KIND, FEED_ID)

    assert body == first
    assert kit.finals_build() == built_at
    assert state is not None and state.last_failure == NOW + FEED_LIFETIME
    assert state.last_failure_reason == "season not known yet"
    calls = len(kit.calls)

    await kit.serve_finals(NOW + FEED_LIFETIME + RETRY_AFTER - SECOND)

    assert len(kit.calls) == calls


@pytest.mark.anyio
async def test_a_failed_read_only_nulls_its_part(kit: FinalsKit) -> None:
    kit.failing |= {"detail/finals-1", "player/201", "stats/" + BOTTOM}

    await kit.serve_finals()

    stored = kit.stored_finals()
    assert stored is not None
    assert stored.games[0].leaders is None and stored.games[1].leaders is not None
    assert averages_of(stored)[1].players[-1].points is None
    assert stored.head_to_head.bars[0].better is None


def fresh_state(kit: FinalsKit) -> tuple[PlayoffsFinalsFeed, dt.datetime]:
    stored = kit.stored_finals()
    built_at = kit.finals_build()
    assert stored is not None and built_at is not None
    return stored, built_at


@pytest.mark.anyio
async def test_a_feed_is_fresh_before_a_final_game_plus_1_hour_and_stale_at_it(
    kit: FinalsKit,
) -> None:
    kit.load(postseason("TBT", scheduled=2))
    await kit.serve_finals()
    feed, built_at = fresh_state(kit)
    kit.store.set_final_time("finals-2", built_at.date(), built_at + 30 * 60 * SECOND)
    two = built_at + 30 * 60 * SECOND + HOUR

    assert kit.finals.is_fresh(feed, built_at, two - SECOND)
    assert not kit.finals.is_fresh(feed, built_at, two)


@pytest.mark.anyio
async def test_a_feed_is_stale_once_the_playoffs_feed_is_rebuilt_and_at_7_days(
    kit: FinalsKit,
) -> None:
    kit.load(postseason("TBT", scheduled=2))
    await kit.serve_finals()
    feed, built_at = fresh_state(kit)

    assert kit.finals.is_fresh(feed, built_at, built_at + FEED_LIFETIME - SECOND)
    assert not kit.finals.is_fresh(feed, built_at, built_at + FEED_LIFETIME)
    kit.store.record_build(playoffs_feed.KIND, FEED_ID, built_at + SECOND)
    assert not kit.finals.is_fresh(feed, built_at, built_at + 2 * SECOND)


@pytest.mark.anyio
async def test_a_complete_feed_is_kept_while_its_season_is_current(
    kit: FinalsKit,
) -> None:
    await kit.serve_finals()
    feed, built_at = fresh_state(kit)
    assert feed.status is SeriesStatus.COMPLETE
    kit.store.record_build(playoffs_feed.KIND, FEED_ID, built_at + SECOND)
    later = built_at + 2 * FEED_LIFETIME

    assert kit.finals.is_fresh(feed, built_at, later)
    kit.stars.season = None
    assert kit.finals.is_fresh(feed, built_at, later)
    kit.stars.season = 2028
    assert not kit.finals.is_fresh(feed, built_at, later)


@pytest.mark.anyio
async def test_highlights_and_detail_available_are_added_when_served_and_not_stored(
    kit: FinalsKit,
) -> None:
    clip = Highlight(
        title="Example clip",
        channel="Example channel",
        thumbnail_url=HttpUrl("https://example.com/thumb.jpg"),
        embed_url=HttpUrl("https://example.com/embed"),
    )
    kit.store.set_highlight("finals-2", clip)
    kit.games.loaded = [_scoreboard_game("finals-1")]

    body = await kit.serve_finals()

    served = PlayoffsFinalsFeed.model_validate_json(body)
    assert [g.highlights for g in served.games] == [None, [clip], None, None]
    assert [g.game.detail_available for g in served.games] == [
        True,
        False,
        False,
        False,
    ]
    stored = kit.stored_finals()
    assert stored is not None
    assert all(g.highlights is None for g in stored.games)
    assert not any(g.game.detail_available for g in stored.games)


def _scoreboard_game(game_id: str) -> Any:
    from tests.jobs.test_playoffs_feed import board

    return board(game_id, TOP, BOTTOM, NOW)


def test_the_cleanup_keeps_league(kit: FinalsKit) -> None:
    assert kit.finals.keep(FEED_ID)
    assert not kit.finals.keep("other")


@pytest.mark.anyio
async def test_serve_with_reads_only_the_highlights_of_the_finals_games(
    kit: FinalsKit, monkeypatch: pytest.MonkeyPatch
) -> None:
    clip = Highlight(
        title="Example clip",
        channel="Example channel",
        thumbnail_url=HttpUrl("https://example.com/thumb.jpg"),
        embed_url=HttpUrl("https://example.com/embed"),
    )
    kit.store.set_highlight("finals-2", clip)
    kit.store.set_highlight("other", clip)
    seen: list[list[str]] = []
    real = kit.store.highlights_for

    def spy(game_ids: Iterable[str]) -> dict[str, Highlight]:
        ids = list(game_ids)
        seen.append(ids)
        return real(ids)

    def boom() -> dict[str, Highlight]:
        raise AssertionError("every highlight was loaded")

    monkeypatch.setattr(kit.store, "highlights_for", spy)
    monkeypatch.setattr(kit.store, "highlights", boom)

    served = PlayoffsFinalsFeed.model_validate_json(await kit.serve_finals())

    assert len(seen) == 1 and "other" not in seen[0]
    assert "finals-2" in seen[0]
    assert [g.highlights for g in served.games] == [None, [clip], None, None]
