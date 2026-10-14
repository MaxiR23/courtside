# api/tests/jobs/test_all_star_feed.py
#
# Tests for the All-Star feed builder and its feed kind.
#
# Tested:
# - parse_note: the round with and without a format suffix, and an unknown note
# - format_line: "1 period · 12 min", "4 periods · 12 min", "First to 40 · Untimed", "First to 40", none
# - edition_state: before with no games and with scheduled games only, live with one live game and with one final and one scheduled, after with all final, a canceled game ignored
# - Placements: 2 teams, 3 teams in a round robin with a Championship, 4 teams with semifinals, so far and yet to play while the Championship is not final, a team-less Championship flagged to be determined and not placed
# - Game contents: both box scores with jersey, position and league team, the six team statistics with the better side and a tie with none, the leaders, the Top 5 order with a tie keeping the source order, a player in no roster with a null league team, null colors on a failed team info read, the live status text, clock and period as the view returns them, the overtime flag
# - MVP: from the All-Star MVP award with one line per game and the day totals, none without the award, with a failed awards read and with no box row
# - Recap: the previous edition's champion, Championship score, MVP, date and venue; none when not discovered, when its day read failed and when its Championship is not final
# - Counts, default game, next game, leading side, top points and team results: the pure functions and the fields of a before, live and after feed
# - Previous edition: every game, its teams and MVP as the after view, none when the recap is none or a game is not final, no MVP without the award, carried by a before feed, highlights added when served and no read added
# - The format line, venue and teams of a before feed
# - Errors: an invalid feed is wrapped in a build error
# - The kind: unknown for another id, not ready before the season, the rosters or the discovery when nothing is stored
# - The kind: nothing is built or read without a request, a request builds and stores, and a second reads storage
# - The kind: a failed current day answers unavailable and is not retried for 10 minutes, a failed rebuild keeps and serves the stored feed, and any other failed read only nulls its part
# - The kind: the reads get the live interval, the first-seen-final time or 1 hour as freshness, and the previous edition's day and games 24 hours
# - The kind: every game final with summaries cached while live, the kept feed comes from a read after the first-seen-final time
# - The kind: the first-seen-final time is stored by the first build that sees the game final and never overwritten
# - The kind: highlights are added when served and not stored
# - The kind: expiry (live 30 seconds and a stale request waits for the rebuild, the edition's date 30 seconds, before until the discovery runs, after held 30 seconds until a build 1 hour after the latest first-seen-final time and then kept while the season is current)
# - The kind: the cleanup keeps league
#
# What is covered:
# - Pure conversions: happy path, edges and errors; the built feed validates
# - Feed kind: success publishes a valid feed, failure keeps the last valid feed, expiry edges
#
# Fake adapters and a fake clock are passed to the builder and the kind, so no
# test uses a real source or the real clock. Clubs, players, broadcasters and
# arenas are invented.
#
# Run with: cd api && .venv/bin/python -m pytest tests/jobs/test_all_star_feed.py
#
# SEE: api/app/jobs/all_star_feed.py

import asyncio
import datetime as dt
from collections.abc import Iterator, Mapping, Sequence
from pathlib import Path
from typing import Any, cast

import pytest
import respx
from pydantic import HttpUrl

from app.feeds.all_star import (
    AllStarFeed,
    AllStarState,
    Broadcast,
    BroadcastKind,
    PlacementKind,
    Top5Row,
)
from app.feeds.game_detail import (
    BoxScore,
    BoxScorePlayer,
    BoxScoreTotals,
    DetailGameTeamStats,
    DetailTeamStats,
    GameResult,
    TeamBoxScore,
    TeamStatLeaders,
    Venue,
)
from app.feeds.games import (
    GameStatus,
    GameTeamStats,
    Highlight,
    Leader,
    Leaders,
    Score,
    TeamStats,
)
from app.feeds.opponent import Side
from app.feeds.playoffs import AwardCode
from app.jobs.all_star_discovery import AllStarDiscovery
from app.jobs.all_star_feed import (
    FEED_ID,
    FINAL_HOLD,
    KIND,
    PREVIOUS_FRESH,
    UNPLAYED_FRESH,
    AllStarBuildError,
    AllStarFeeds,
    AllStarSources,
    build_all_star_feed,
    default_game,
    edition_counts,
    edition_state,
    format_line,
    leading,
    league_team,
    next_game,
    parse_note,
    placements,
    previous_edition,
    team_stats,
    top5,
    winner,
)
from app.jobs.games import LIVE_INTERVAL, GamesJob
from app.jobs.on_demand import (
    RETRY_AFTER,
    FeedCache,
    FeedUnavailableError,
    IdStatus,
    UnknownFeedError,
)
from app.jobs.stars import StarsJob
from app.settings import Settings
from app.sources.all_star_detail import AllStarDetailExtras
from app.sources.all_star_scoreboard import AllStarScoreboardGame, AllStarSide
from app.sources.game_detail import GameDetail, GameDetailSections
from app.sources.http import Freshness, SourceClient, SourceError, create_client
from app.sources.season_awards import (
    AwardWinnerRef,
    SeasonAward,
    SeasonAwards,
)
from app.sources.team_info import TeamInfo
from app.storage.feeds import read_by_id
from app.storage.state import StateStore

DAY = dt.date(2027, 2, 14)
PREVIOUS_DAY = dt.date(2026, 2, 15)
TIP = dt.datetime(2027, 2, 15, 1, 0, tzinfo=dt.UTC)
NOW = dt.datetime(2027, 2, 14, 15, 0, tzinfo=dt.UTC)
SECOND = dt.timedelta(seconds=1)
ROUND_ROBIN = "NBA All-Star - Round Robin"
CHAMPIONSHIP = "NBA All-Star - Championship"
SEMIFINALS = "NBA All-Star - Semifinals First team to 40 points wins - Untimed"

STR = AllStarSide(code="STR", name="Team Stripes", city=None)
WAV = AllStarSide(code="WAV", name="Team Waves", city=None)
PKS = AllStarSide(code="PKS", name="Team Peaks", city=None)
DNS = AllStarSide(code="DNS", name="Team Dunes", city=None)

# Group 1: the helpers


def game(
    game_id: str,
    away: AllStarSide | None,
    home: AllStarSide | None,
    *,
    status: GameStatus = GameStatus.FINAL,
    score: tuple[int, int] | None = None,
    note: str | None = ROUND_ROBIN,
    minutes: int = 0,
    period: int | None = None,
    clock: str | None = None,
    status_text: str | None = None,
) -> AllStarScoreboardGame:
    in_play = status in (GameStatus.LIVE, GameStatus.FINAL)
    points = score if score is not None else ((21, 18) if in_play else None)
    return AllStarScoreboardGame(
        id=game_id,
        start_time=TIP + dt.timedelta(minutes=minutes),
        status=status,
        status_text=status_text,
        period=period if period is not None else (1 if in_play else None),
        clock=clock,
        score=None if points is None else Score(away=points[0], home=points[1]),
        note=note,
        venue="Example Arena",
        away=away,
        home=home,
    )


def line(
    player_id: str,
    name: str,
    points: int = 10,
    rebounds: int = 3,
    assists: int = 2,
    three: int = 2,
) -> BoxScorePlayer:
    return BoxScorePlayer(
        player_id=player_id,
        display_name=name,
        starter=True,
        minutes="10",
        plus_minus=1,
        photo_url=HttpUrl(f"https://example.com/photos/{player_id}.png"),
        points=points,
        field_goals_made=4,
        field_goals_attempted=8,
        three_points_made=three,
        three_points_attempted=4,
        free_throws_made=0,
        free_throws_attempted=0,
        offensive_rebounds=1,
        defensive_rebounds=rebounds - 1,
        rebounds=rebounds,
        assists=assists,
        turnovers=1,
        steals=1,
        blocks=0,
        fouls=1,
    )


def totals(three: int = 4) -> BoxScoreTotals:
    return BoxScoreTotals(
        points=20,
        field_goals_made=8,
        field_goals_attempted=16,
        three_points_made=three,
        three_points_attempted=8,
        free_throws_made=0,
        free_throws_attempted=0,
        offensive_rebounds=2,
        defensive_rebounds=4,
        rebounds=6,
        assists=4,
        turnovers=2,
        steals=2,
        blocks=0,
        fouls=2,
        field_goal_pct=0.5,
        three_point_pct=0.5,
        free_throw_pct=0.0,
    )


def stat(**changes: Any) -> DetailTeamStats:
    values: dict[str, Any] = {
        "field_goal_pct": 0.5,
        "three_point_pct": 0.3,
        "rebounds": 10,
        "assists": 5,
        "turnovers": 3,
        "free_throw_pct": 0.8,
        "steals": 2,
        "blocks": 1,
    }
    values.update(changes)
    return DetailTeamStats(**values)


def sections(
    away: Sequence[BoxScorePlayer],
    home: Sequence[BoxScorePlayer],
    *,
    away_stats: DetailTeamStats | None = None,
    home_stats: DetailTeamStats | None = None,
    away_three: int = 4,
    home_three: int = 2,
) -> GameDetailSections:
    return GameDetailSections(
        venue=Venue(name="Example Arena", city="Exampleton"),
        team_stats=DetailGameTeamStats(
            away=away_stats or stat(),
            home=home_stats or stat(),
            leaders=TeamStatLeaders(
                field_goal_pct=None,
                three_point_pct=None,
                free_throw_pct=None,
                rebounds=None,
                assists=None,
                turnovers=None,
                steals=None,
                blocks=None,
            ),
        ),
        box_score=BoxScore(
            away=TeamBoxScore(players=list(away), totals=totals(away_three)),
            home=TeamBoxScore(players=list(home), totals=totals(home_three)),
        ),
    )


def leader(player_id: str, name: str) -> Leader:
    return Leader(
        player_id=player_id,
        display_name=name,
        team_code="STR",
        photo_url=None,
        points=12,
        rebounds=4,
        assists=3,
    )


def detail() -> GameDetail:
    team = TeamStats(
        field_goal_pct=0.5,
        three_point_pct=0.3,
        rebounds=10,
        assists=5,
        turnovers=3,
    )
    return GameDetail(
        leaders=Leaders(
            away=leader("1001", "Ada Example"), home=leader("2001", "Cy Placeholder")
        ),
        team_stats=GameTeamStats(away=team, home=team),
    )


def extras(**changes: Any) -> AllStarDetailExtras:
    values: dict[str, Any] = {
        "regulation_periods": 1,
        "regulation_seconds": 720.0,
        "attendance": 18500,
        "broadcasts": [
            Broadcast(name="Example Network", kind=BroadcastKind.TV),
            Broadcast(name="Example Stream", kind=BroadcastKind.STREAMING),
        ],
        "jerseys": {"1001": "7", "2001": "3"},
        "positions": {"1001": "G", "2001": "C"},
    }
    values.update(changes)
    return AllStarDetailExtras(**values)


def info(color: str = "007AC1") -> TeamInfo:
    return TeamInfo(
        location="Example City",
        name="Example Club",
        color=color,
        alternate_color="FFFFFF",
        venue_name="Example Arena",
    )


def award(player_id: str, code: AwardCode = AwardCode.ALL_STAR_MVP) -> SeasonAwards:
    return SeasonAwards(
        awards=[
            SeasonAward(
                code=code,
                team=None,
                winners=[AwardWinnerRef(player_id=player_id, team_code=None)],
            )
        ]
    )


# The players of each side, by player id: 1001 and 1002 are Team Stripes, 2001 and
# 2002 Team Waves, 3001 and 3002 Team Peaks and 4001 Team Dunes.
SIDE_PLAYERS: dict[str, list[tuple[str, str, int, int, int]]] = {
    "STR": [("1001", "Ada Example", 12, 4, 3), ("1002", "Ben Sample", 8, 5, 1)],
    "WAV": [("2001", "Cy Placeholder", 15, 2, 2), ("2002", "Dee Invented", 5, 6, 3)],
    "PKS": [("3001", "Eli Made-Up", 9, 3, 3), ("3002", "Fay Sketch", 4, 1, 1)],
    "DNS": [("4001", "Gus Imagined", 11, 7, 2)],
}


def players_of(side: AllStarSide | None) -> list[BoxScorePlayer]:
    if side is None or side.code is None:
        return []
    return [
        line(pid, name, points, rebounds, assists)
        for pid, name, points, rebounds, assists in SIDE_PLAYERS[side.code]
    ]


def sections_of(match: AllStarScoreboardGame) -> GameDetailSections:
    return sections(players_of(match.away), players_of(match.home))


def sources(
    games: Sequence[AllStarScoreboardGame],
    *,
    sections_by_id: Mapping[str, GameDetailSections | None] | None = None,
    extras_by_id: Mapping[str, AllStarDetailExtras | None] | None = None,
    **changes: Any,
) -> AllStarSources:
    values: dict[str, Any] = {
        "year": 2027,
        "edition_date": DAY,
        "games": games,
        "details": {g.id: detail() for g in games},
        "sections": (
            sections_by_id
            if sections_by_id is not None
            else {g.id: sections_of(g) for g in games if g.away and g.home}
        ),
        "extras": (
            extras_by_id
            if extras_by_id is not None
            else {g.id: extras() for g in games}
        ),
        "colors": {"BOS": info(), "LAL": info("552583")},
        "player_teams": {"1001": "BOS", "2001": "LAL"},
        "awards": None,
        "previous": None,
    }
    values.update(changes)
    return AllStarSources(**values)


def build(games: Sequence[AllStarScoreboardGame], **changes: Any) -> AllStarFeed:
    return build_all_star_feed(sources(games, **changes))


def round_robin(final: bool = True) -> list[AllStarScoreboardGame]:
    """Three teams: Team Stripes beats Team Waves and Team Peaks, Team Waves
    beats Team Peaks, then the Championship between Stripes and Waves."""
    return [
        game("g1", STR, WAV, score=(21, 18), minutes=0),
        game("g2", PKS, STR, score=(17, 20), minutes=30),
        game("g3", WAV, PKS, score=(22, 19), minutes=60),
        game(
            "g4",
            STR,
            WAV,
            note=CHAMPIONSHIP,
            minutes=90,
            status=GameStatus.FINAL if final else GameStatus.SCHEDULED,
            score=(25, 23) if final else None,
        ),
    ]


def semifinals() -> list[AllStarScoreboardGame]:
    return [
        game("s1", STR, WAV, note=SEMIFINALS, score=(40, 32), minutes=0),
        game("s2", PKS, DNS, note=SEMIFINALS, score=(30, 40), minutes=30),
        game("c1", STR, DNS, note=CHAMPIONSHIP, score=(25, 27), minutes=60),
    ]


def kinds(
    games: Sequence[AllStarScoreboardGame],
) -> dict[str, tuple[PlacementKind, str | None]]:
    return placements(games)


# Group 2: the pure helpers


def test_parse_note_gives_the_round_with_no_suffix() -> None:
    assert parse_note(ROUND_ROBIN) == ("Round Robin", None)
    assert parse_note(CHAMPIONSHIP) == ("Championship", None)


def test_parse_note_gives_the_round_and_the_format_suffix() -> None:
    assert parse_note(SEMIFINALS) == (
        "Semifinals",
        "First team to 40 points wins - Untimed",
    )


def test_parse_note_of_an_unknown_note_or_no_note_is_none() -> None:
    assert parse_note("East 1st Round - Game 1") == (None, None)
    assert parse_note("") == (None, None)
    assert parse_note(None) == (None, None)


def test_format_line_of_one_period_of_twelve_minutes() -> None:
    assert format_line(None, extras()) == "1 period · 12 min"


def test_format_line_of_four_periods() -> None:
    four = extras(regulation_periods=4)

    assert format_line(None, four) == "4 periods · 12 min"


def test_format_line_of_a_fractional_number_of_minutes() -> None:
    assert format_line(None, extras(regulation_seconds=90.0)) == "1 period · 1.5 min"


def test_format_line_of_a_first_to_suffix_untimed() -> None:
    suffix = "First team to 40 points wins - Untimed"

    assert format_line(suffix, extras()) == "First to 40 · Untimed"


def test_format_line_of_a_first_to_suffix_without_untimed() -> None:
    assert format_line("First team to 40 points wins", None) == "First to 40"


def test_format_line_is_none_with_no_suffix_and_no_format() -> None:
    assert format_line(None, None) is None
    assert format_line(None, extras(regulation_periods=None)) is None
    assert format_line(None, extras(regulation_seconds=None)) is None


def test_the_state_is_before_with_no_games_and_with_scheduled_games_only() -> None:
    scheduled = [game("a", STR, WAV, status=GameStatus.SCHEDULED)]

    assert edition_state([]) is AllStarState.BEFORE
    assert edition_state(scheduled) is AllStarState.BEFORE


def test_the_state_is_live_with_one_live_game() -> None:
    live = [game("a", STR, WAV, status=GameStatus.LIVE)]

    assert edition_state(live) is AllStarState.LIVE


def test_the_state_is_live_with_one_final_and_one_scheduled_game() -> None:
    games = [game("a", STR, WAV), game("b", PKS, STR, status=GameStatus.SCHEDULED)]

    assert edition_state(games) is AllStarState.LIVE


def test_the_state_is_after_when_every_game_is_final() -> None:
    assert edition_state(round_robin()) is AllStarState.AFTER


def test_a_canceled_game_is_ignored_by_the_state() -> None:
    games = [game("a", STR, WAV), game("b", PKS, STR, status=GameStatus.CANCELED)]

    assert edition_state(games) is AllStarState.AFTER


def test_the_winner_is_the_side_with_the_higher_final_score() -> None:
    assert winner(game("a", STR, WAV, score=(21, 18))) is Side.AWAY
    assert winner(game("a", STR, WAV, score=(18, 21))) is Side.HOME
    assert winner(game("a", STR, WAV, score=(20, 20))) is None
    assert winner(game("a", STR, WAV, status=GameStatus.LIVE)) is None
    assert winner(game("a", STR, WAV, status=GameStatus.SCHEDULED)) is None


def test_two_teams_have_a_champion_and_a_runner_up() -> None:
    games = [game("c", STR, WAV, note=CHAMPIONSHIP, score=(30, 25))]

    assert kinds(games) == {
        "STR": (PlacementKind.CHAMPION, None),
        "WAV": (PlacementKind.RUNNER_UP, None),
    }


def test_three_teams_in_a_round_robin_eliminate_the_third_with_the_round_label() -> (
    None
):
    assert kinds(round_robin()) == {
        "STR": (PlacementKind.CHAMPION, None),
        "WAV": (PlacementKind.RUNNER_UP, None),
        "PKS": (PlacementKind.ELIMINATED, "Round Robin"),
    }


def test_four_teams_with_semifinals_eliminate_the_losers_with_the_semifinals_label() -> (
    None
):
    assert kinds(semifinals()) == {
        "STR": (PlacementKind.RUNNER_UP, None),
        "WAV": (PlacementKind.ELIMINATED, "Semifinals"),
        "PKS": (PlacementKind.ELIMINATED, "Semifinals"),
        "DNS": (PlacementKind.CHAMPION, None),
    }


def test_teams_are_so_far_or_yet_to_play_while_the_championship_is_not_final() -> None:
    games = [
        game("g1", STR, WAV, score=(21, 18)),
        game("g2", PKS, STR, status=GameStatus.SCHEDULED),
        game(
            "c", None, None, note=CHAMPIONSHIP, status=GameStatus.SCHEDULED, minutes=90
        ),
    ]

    assert kinds(games) == {
        "STR": (PlacementKind.SO_FAR, None),
        "WAV": (PlacementKind.SO_FAR, None),
        "PKS": (PlacementKind.YET_TO_PLAY, None),
    }


def test_a_final_championship_without_a_decided_winner_places_nobody() -> None:
    games = [game("c", STR, WAV, note=CHAMPIONSHIP, score=(20, 20))]

    assert kinds(games) == {
        "STR": (PlacementKind.SO_FAR, None),
        "WAV": (PlacementKind.SO_FAR, None),
    }


def test_a_team_without_a_round_label_is_not_eliminated() -> None:
    games = [
        game("g1", PKS, STR, note=None, score=(10, 20)),
        game("c", STR, WAV, note=CHAMPIONSHIP, score=(30, 25), minutes=90),
    ]

    assert kinds(games)["PKS"] == (PlacementKind.SO_FAR, None)


def live_day() -> list[AllStarScoreboardGame]:
    """Semifinals: one final, one live, one scheduled, then a Championship."""
    return [
        game("s1", STR, WAV, note=SEMIFINALS, score=(40, 32), minutes=0),
        game(
            "s2",
            PKS,
            DNS,
            note=SEMIFINALS,
            status=GameStatus.LIVE,
            score=(30, 12),
            minutes=30,
        ),
        game(
            "c1",
            None,
            None,
            note=CHAMPIONSHIP,
            status=GameStatus.SCHEDULED,
            minutes=60,
        ),
    ]


def test_edition_counts_count_games_teams_final_and_live() -> None:
    assert edition_counts(round_robin(final=False)) == {
        "games": 4,
        "teams": 3,
        "final": 3,
        "live": 0,
    }
    assert edition_counts(live_day()) == {
        "games": 3,
        "teams": 4,
        "final": 1,
        "live": 1,
    }
    assert edition_counts([]) == {"games": 0, "teams": 0, "final": 0, "live": 0}


def test_the_default_game_is_the_championship_after() -> None:
    assert default_game(round_robin(), AllStarState.AFTER) == "g4"


def test_the_default_game_is_the_first_live_game_while_live() -> None:
    assert default_game(live_day(), AllStarState.LIVE) == "s2"


def test_the_default_game_between_games_is_the_first_not_final() -> None:
    games = [
        game("a", STR, WAV),
        game("b", PKS, STR, status=GameStatus.SCHEDULED, minutes=30),
        game("c", WAV, PKS, status=GameStatus.SCHEDULED, minutes=60),
    ]

    assert default_game(games, AllStarState.LIVE) == "b"


def test_the_default_game_without_a_championship_after_is_the_first_game() -> None:
    games = [game("a", STR, WAV), game("b", PKS, STR, minutes=30)]

    assert default_game(games, AllStarState.AFTER) == "a"


def test_the_default_game_is_none_without_games() -> None:
    assert default_game([], AllStarState.BEFORE) is None


def test_the_next_game_is_the_first_scheduled_after_the_default_while_live() -> None:
    games = live_day()

    assert next_game(games, AllStarState.LIVE, "s2") == "c1"
    between = [
        game("a", STR, WAV),
        game("b", PKS, STR, status=GameStatus.SCHEDULED, minutes=30),
        game("c", WAV, PKS, status=GameStatus.SCHEDULED, minutes=60),
    ]
    assert next_game(between, AllStarState.LIVE, "b") == "c"


def test_there_is_no_next_game_after_or_with_no_scheduled_game() -> None:
    assert next_game(round_robin(), AllStarState.AFTER, "g4") is None
    assert next_game(round_robin(), AllStarState.BEFORE, None) is None
    only = [game("a", STR, WAV, status=GameStatus.LIVE)]
    assert next_game(only, AllStarState.LIVE, "a") is None
    solo = [game("a", STR, WAV, status=GameStatus.SCHEDULED)]
    assert next_game(solo, AllStarState.LIVE, "a") is None


def test_leading_is_the_higher_score_of_a_live_game_and_none_on_a_tie_or_final() -> (
    None
):
    live = GameStatus.LIVE
    assert leading(game("a", STR, WAV, status=live, score=(5, 3))) is Side.AWAY
    assert leading(game("a", STR, WAV, status=live, score=(3, 5))) is Side.HOME
    assert leading(game("a", STR, WAV, status=live, score=(4, 4))) is None
    assert leading(game("a", STR, WAV, score=(5, 3))) is None
    assert leading(game("a", STR, WAV, status=GameStatus.SCHEDULED)) is None


def row(player_id: str, points: int, rebounds: int = 0, assists: int = 0) -> Top5Row:
    return Top5Row(
        player_id=player_id,
        name="Ada Example",
        photo_url=None,
        side=Side.AWAY,
        league_team=None,
        points=points,
        rebounds=rebounds,
        assists=assists,
    )


def test_top5_sorts_by_points_then_rebounds_plus_assists() -> None:
    rows = [row("a", 10, 1, 1), row("b", 20), row("c", 10, 3, 3), row("d", 5)]

    assert [r.player_id for r in top5(rows)] == ["b", "c", "a", "d"]


def test_top5_keeps_the_source_order_on_a_tie_and_the_first_five() -> None:
    rows = [row(str(n), 10, 2, 2) for n in range(7)]

    assert [r.player_id for r in top5(rows)] == ["0", "1", "2", "3", "4"]


def test_team_stats_has_the_six_stats_with_the_better_side_and_none_on_a_tie() -> None:
    found = sections(
        [line("1", "A")],
        [line("2", "B")],
        away_stats=stat(field_goal_pct=0.6, rebounds=12, assists=5, steals=1, blocks=3),
        home_stats=stat(field_goal_pct=0.4, rebounds=9, assists=5, steals=4, blocks=1),
        away_three=3,
        home_three=5,
    )

    rows = team_stats(found)

    assert rows is not None
    assert [(r["stat"], r["away"], r["home"], r["better"]) for r in rows] == [
        ("field_goal_pct", 0.6, 0.4, Side.AWAY),
        ("three_points_made", 3.0, 5.0, Side.HOME),
        ("rebounds", 12.0, 9.0, Side.AWAY),
        ("assists", 5.0, 5.0, None),
        ("steals", 1.0, 4.0, Side.HOME),
        ("blocks", 3.0, 1.0, Side.AWAY),
    ]


def test_team_stats_is_none_without_the_sections_or_the_box_score() -> None:
    bare = GameDetailSections(venue=Venue(name="Example Arena"))

    assert team_stats(None) is None
    assert team_stats(bare) is None


def test_league_team_is_found_by_id_with_its_colors_or_none() -> None:
    found = league_team("1001", {"1001": "BOS"}, {"BOS": info()})
    unknown = league_team("9", {"1001": "BOS"}, {"BOS": info()})
    no_info = league_team("1001", {"1001": "BOS"}, {})

    assert found is not None and found.code == "BOS"
    assert found.colors.primary == "#007AC1" and found.colors.secondary == "#FFFFFF"
    assert unknown is None
    assert no_info is not None and no_info.colors.primary is None


# Group 3: the builder


def test_a_before_feed_has_the_date_and_the_venue_and_no_games_or_teams() -> None:
    games = [game("g1", None, None, status=GameStatus.SCHEDULED, note=CHAMPIONSHIP)]

    feed = build(games)

    assert feed.state is AllStarState.BEFORE
    assert feed.year == 2027
    assert feed.edition.date == DAY
    assert feed.edition.venue == Venue(name="Example Arena")
    assert feed.edition.games == [] and feed.edition.teams == []
    assert feed.edition.format_line is None
    assert feed.mvp is None


def test_a_before_feed_with_no_edition_has_no_date_and_no_venue() -> None:
    feed = build([], edition_date=None)

    assert feed.state is AllStarState.BEFORE
    assert feed.edition.date is None and feed.edition.venue is None


def test_a_before_feed_never_has_an_mvp_even_with_an_award() -> None:
    feed = build([], awards=award("1001"))

    assert feed.mvp is None


def test_an_after_feed_has_the_games_in_start_order_and_the_teams_in_order_of_appearance() -> (
    None
):
    feed = build(list(reversed(round_robin())))

    assert feed.state is AllStarState.AFTER
    assert [g.id for g in feed.edition.games] == ["g1", "g2", "g3", "g4"]
    assert [t.team.code for t in feed.edition.teams] == ["STR", "WAV", "PKS"]
    placed = {t.team.code: t for t in feed.edition.teams}
    assert [(t.wins, t.losses) for t in placed.values()] == [(3, 0), (1, 2), (0, 2)]
    assert placed["PKS"].placement.kind is PlacementKind.ELIMINATED
    assert placed["PKS"].placement.round_label == "Round Robin"
    assert placed["STR"].team.guest is True


def test_a_canceled_game_and_a_repeated_game_id_are_dropped() -> None:
    games = [
        *round_robin(),
        game("g9", PKS, WAV, status=GameStatus.CANCELED, minutes=120),
        game("g1", STR, WAV, minutes=0),
    ]

    feed = build(games)

    assert [g.id for g in feed.edition.games] == ["g1", "g2", "g3", "g4"]


def test_a_live_feed_has_the_games_not_final_with_no_winner() -> None:
    games = [
        game("g1", STR, WAV),
        game("g2", PKS, STR, status=GameStatus.SCHEDULED, minutes=30),
    ]

    feed = build(games)

    assert feed.state is AllStarState.LIVE
    assert [g.winner for g in feed.edition.games] == [Side.AWAY, None]
    assert {t.team.code: t.placement.kind for t in feed.edition.teams} == {
        "STR": PlacementKind.SO_FAR,
        "WAV": PlacementKind.SO_FAR,
        "PKS": PlacementKind.YET_TO_PLAY,
    }


def test_a_team_less_championship_is_to_be_determined_and_places_no_team() -> None:
    games = [
        game("g1", STR, WAV),
        game(
            "c", None, None, note=CHAMPIONSHIP, status=GameStatus.SCHEDULED, minutes=90
        ),
    ]

    feed = build(games)

    championship = feed.edition.games[1]
    assert championship.to_be_determined is True
    assert championship.away is None and championship.home is None
    assert championship.championship is True
    assert feed.edition.games[0].to_be_determined is False
    assert [t.team.code for t in feed.edition.teams] == ["STR", "WAV"]


def test_a_game_carries_the_round_label_and_the_championship_flag() -> None:
    feed = build(round_robin())

    assert [g.round_label for g in feed.edition.games] == [
        "Round Robin",
        "Round Robin",
        "Round Robin",
        "Championship",
    ]
    assert [g.championship for g in feed.edition.games] == [False, False, False, True]


def test_the_format_line_is_the_line_of_the_first_game_that_has_one() -> None:
    feed = build(semifinals())

    assert feed.edition.format_line == "First to 40 · Untimed"
    assert build(round_robin()).edition.format_line == "1 period · 12 min"


def test_the_format_line_skips_a_game_with_no_line() -> None:
    games = round_robin()

    feed = build(
        games, extras_by_id={"g1": None, "g2": extras(), "g3": None, "g4": None}
    )

    assert feed.edition.format_line == "1 period · 12 min"
    assert build(games, extras_by_id={}).edition.format_line is None


def test_the_venue_is_the_summary_venue_else_the_scoreboard_venue() -> None:
    games = round_robin()

    from_summary = build(games)
    from_board = build(games, sections_by_id={})

    assert from_summary.edition.venue == Venue(name="Example Arena", city="Exampleton")
    assert from_board.edition.venue == Venue(name="Example Arena")


def test_each_game_carries_both_box_scores_with_jersey_position_and_league_team() -> (
    None
):
    feed = build(round_robin())

    box = feed.edition.games[0].box_score
    assert box is not None
    ada = box.away.players[0]
    assert (ada.player_id, ada.jersey, ada.position) == ("1001", "7", "G")
    assert ada.league_team is not None and ada.league_team.code == "BOS"
    assert ada.league_team.colors.primary == "#007AC1"
    assert ada.points == 12 and ada.field_goals_made == 4 and ada.fouls == 1
    assert len(box.home.players) == 2
    cy = box.home.players[0]
    assert cy.league_team is not None and cy.league_team.code == "LAL"
    assert box.away.totals.three_points_made == 4


def test_a_box_score_player_in_no_roster_has_a_null_league_team() -> None:
    feed = build(round_robin())

    box = feed.edition.games[0].box_score
    assert box is not None
    assert box.away.players[1].player_id == "1002"
    assert box.away.players[1].league_team is None
    assert box.away.players[1].jersey is None and box.away.players[1].position is None


def test_colors_are_null_when_the_team_info_read_failed() -> None:
    feed = build(round_robin(), colors={"BOS": None, "LAL": None})

    ada = feed.edition.games[0].box_score.away.players[0]  # type: ignore[union-attr]
    assert ada.league_team is not None
    assert ada.league_team.colors.primary is None
    assert ada.league_team.colors.secondary is None


def test_the_roster_of_a_team_is_its_box_rows_across_games_without_repeats() -> None:
    feed = build(round_robin())

    stripes = feed.edition.teams[0]
    assert [t.player_id for t in stripes.roster] == ["1001", "1002"]
    assert stripes.roster[0].name == "Ada Example"
    assert stripes.roster[0].league_team is not None
    assert [t.player_id for t in feed.edition.teams[1].roster] == ["2001", "2002"]


def test_a_game_carries_the_team_statistics_and_the_leaders_and_the_top5() -> None:
    feed = build(round_robin())

    first = feed.edition.games[0]
    assert first.team_stats is not None
    assert [s.stat.value for s in first.team_stats] == [
        "field_goal_pct",
        "three_points_made",
        "rebounds",
        "assists",
        "steals",
        "blocks",
    ]
    assert first.team_stats[1].better is Side.AWAY
    assert first.team_stats[0].better is None
    assert first.leaders is not None
    assert first.leaders.away.player_id == "1001"
    assert first.leaders.home.player_id == "2001"
    assert [r.player_id for r in first.top5] == ["2001", "1001", "1002", "2002"]
    assert first.top5[0].side is Side.HOME
    assert first.top5[0].league_team is not None


def test_a_failed_read_only_nulls_its_part() -> None:
    games = round_robin()

    feed = build(games, details={}, sections_by_id={}, extras_by_id={})

    first = feed.edition.games[0]
    assert first.leaders is None and first.box_score is None
    assert first.team_stats is None and first.top5 == []
    assert first.attendance is None and first.broadcasts == []
    assert first.overtime is False
    assert feed.state is AllStarState.AFTER


def test_the_attendance_and_the_broadcasts_come_from_the_extras() -> None:
    first = build(round_robin()).edition.games[0]

    assert first.attendance == 18500
    assert [(b.name, b.kind) for b in first.broadcasts] == [
        ("Example Network", BroadcastKind.TV),
        ("Example Stream", BroadcastKind.STREAMING),
    ]


def test_a_live_game_passes_the_status_text_clock_and_period_as_the_view_returns_them() -> (
    None
):
    live = game(
        "g1",
        STR,
        WAV,
        status=GameStatus.LIVE,
        score=(12, 9),
        period=2,
        clock="0:08",
        status_text="Q2 8.3",
    )

    feed = build([live])

    shown = feed.edition.games[0]
    assert (shown.status_text, shown.clock, shown.period) == ("Q2 8.3", "0:08", 2)
    assert shown.score == Score(away=12, home=9)
    assert shown.winner is None and feed.state is AllStarState.LIVE


def test_the_overtime_flag_comes_from_a_period_beyond_the_regulation_periods() -> None:
    games = [
        game("g1", STR, WAV, period=1),
        game("g2", PKS, STR, period=2, minutes=30),
        game("g3", WAV, PKS, period=2, status=GameStatus.SCHEDULED, minutes=60),
    ]

    feed = build(games)

    assert [g.overtime for g in feed.edition.games] == [False, True, False]


def test_the_overtime_flag_is_false_without_a_known_format() -> None:
    games = [game("g1", STR, WAV, period=3)]

    feed = build(games, extras_by_id={"g1": extras(regulation_periods=None)})

    assert feed.edition.games[0].overtime is False


def test_the_mvp_has_one_line_per_game_and_the_day_totals() -> None:
    feed = build(round_robin(), awards=award("1001"))

    mvp = feed.mvp
    assert mvp is not None
    assert (mvp.player_id, mvp.name, mvp.jersey) == ("1001", "Ada Example", "7")
    assert mvp.league_team is not None and mvp.league_team.code == "BOS"
    assert [line.game_id for line in mvp.lines] == ["g1", "g2", "g4"]
    assert [line.result for line in mvp.lines] == [
        GameResult.WIN,
        GameResult.WIN,
        GameResult.WIN,
    ]
    assert [(line.team_score, line.opponent_score) for line in mvp.lines] == [
        (21, 18),
        (20, 17),
        (25, 23),
    ]
    assert [line.opponent.code for line in mvp.lines] == ["WAV", "PKS", "WAV"]
    assert [line.round_label for line in mvp.lines] == [
        "Round Robin",
        "Round Robin",
        "Championship",
    ]
    assert (mvp.totals.games, mvp.totals.points) == (3, 36)
    assert (mvp.totals.rebounds, mvp.totals.assists) == (12, 9)


def test_an_mvp_on_the_losing_side_has_a_loss() -> None:
    feed = build(round_robin(), awards=award("2002"))

    mvp = feed.mvp
    assert mvp is not None
    assert [line.game_id for line in mvp.lines] == ["g1", "g3", "g4"]
    assert [line.result for line in mvp.lines] == [
        GameResult.LOSS,
        GameResult.WIN,
        GameResult.LOSS,
    ]


def test_the_mvp_is_none_without_the_award_with_another_award_and_with_a_failed_read() -> (
    None
):
    assert build(round_robin()).mvp is None
    assert build(round_robin(), awards=award("1001", AwardCode.MVP)).mvp is None
    assert build(round_robin(), awards=SeasonAwards(awards=[])).mvp is None


def test_the_mvp_is_none_when_he_has_no_box_row() -> None:
    assert build(round_robin(), awards=award("9999")).mvp is None
    assert build(round_robin(), awards=award("1001"), sections_by_id={}).mvp is None


def test_the_mvp_has_no_line_for_a_game_he_did_not_finish() -> None:
    games = round_robin(final=False)

    feed = build(games, awards=award("1001"))

    assert feed.mvp is not None
    assert [line.game_id for line in feed.mvp.lines] == ["g1", "g2"]


def previous_sources(**changes: Any) -> AllStarSources:
    games = [
        game("p1", STR, WAV, score=(21, 18)),
        game("p2", WAV, PKS, note=CHAMPIONSHIP, score=(20, 22), minutes=30),
    ]
    values: dict[str, Any] = {
        "year": 2026,
        "edition_date": PREVIOUS_DAY,
        "awards": award("3001"),
    }
    values.update(changes)
    return sources(games, **values)


def test_the_recap_has_the_championship_result_the_mvp_the_date_and_the_venue() -> None:
    feed = build(round_robin(), previous=previous_sources())

    recap = feed.previous
    assert recap is not None
    assert recap.year == 2026 and recap.date == PREVIOUS_DAY
    assert recap.venue == Venue(name="Example Arena", city="Exampleton")
    champion = recap.championship
    assert champion.game_id == "p2"
    assert (champion.away.code, champion.home.code) == ("WAV", "PKS")
    assert (champion.score.away, champion.score.home) == (20, 22)
    assert champion.winner is Side.HOME
    assert champion.overtime is False
    assert recap.mvp is not None
    assert recap.mvp.player_id == "3001"
    assert recap.mvp.totals.games == 1


def test_the_recap_has_no_mvp_without_the_award() -> None:
    feed = build(round_robin(), previous=previous_sources(awards=None))

    assert feed.previous is not None and feed.previous.mvp is None


def test_the_recap_is_none_when_not_discovered() -> None:
    assert build(round_robin(), previous=None).previous is None
    assert (
        build(round_robin(), previous=previous_sources(edition_date=None)).previous
        is None
    )


def test_the_recap_is_none_when_the_day_has_no_games() -> None:
    feed = build(
        round_robin(), previous=sources([], year=2026, edition_date=PREVIOUS_DAY)
    )

    assert feed.previous is None


def test_the_recap_is_none_when_the_championship_is_not_final() -> None:
    games = [
        game("p1", STR, WAV, score=(21, 18)),
        game(
            "p2", WAV, PKS, note=CHAMPIONSHIP, status=GameStatus.SCHEDULED, minutes=30
        ),
    ]
    previous = sources(games, year=2026, edition_date=PREVIOUS_DAY)

    assert build(round_robin(), previous=previous).previous is None


def box_of(feed: AllStarFeed, game_id: str, side: str) -> list[tuple[str, bool]]:
    found = next(g for g in feed.edition.games if g.id == game_id)
    assert found.box_score is not None
    team = getattr(found.box_score, side)
    return [(p.player_id, p.top_points) for p in team.players]


def test_top_points_marks_every_tied_top_scorer_of_each_team() -> None:
    games = [game("g1", STR, WAV)]
    tied = sections(
        [line("1001", "Ada Example", 12), line("1002", "Ben Sample", 12)],
        [line("2001", "Cy Placeholder", 15), line("2002", "Dee Invented", 5)],
    )

    feed = build(games, sections_by_id={"g1": tied})

    assert box_of(feed, "g1", "away") == [("1001", True), ("1002", True)]
    assert box_of(feed, "g1", "home") == [("2001", True), ("2002", False)]


def test_top_points_marks_nobody_in_a_team_with_no_points() -> None:
    games = [game("g1", STR, WAV)]
    nothing = sections(
        [line("1001", "Ada Example", 0), line("1002", "Ben Sample", 0)],
        [line("2001", "Cy Placeholder", 3)],
    )

    feed = build(games, sections_by_id={"g1": nothing})

    assert box_of(feed, "g1", "away") == [("1001", False), ("1002", False)]
    assert box_of(feed, "g1", "home") == [("2001", True)]


def results_of(feed: AllStarFeed, code: str) -> list[Any]:
    found = next(t for t in feed.edition.teams if t.team.code == code)
    return found.results


def test_team_results_are_its_final_games_in_start_order_with_overtime() -> None:
    games = round_robin()
    games[3] = games[3].model_copy(update={"period": 2})

    feed = build(games)

    stripes = results_of(feed, "STR")
    assert [(r.game_id, r.result, r.team_score, r.opponent_score) for r in stripes] == [
        ("g1", GameResult.WIN, 21, 18),
        ("g2", GameResult.WIN, 20, 17),
        ("g4", GameResult.WIN, 25, 23),
    ]
    assert [r.round_label for r in stripes] == [
        "Round Robin",
        "Round Robin",
        "Championship",
    ]
    assert [r.overtime for r in stripes] == [False, False, True]
    assert [r.opponent.code for r in stripes] == ["WAV", "PKS", "WAV"]
    peaks = results_of(feed, "PKS")
    assert [(r.game_id, r.result) for r in peaks] == [
        ("g2", GameResult.LOSS),
        ("g3", GameResult.LOSS),
    ]
    teams = {t.team.code: t for t in feed.edition.teams}
    assert (teams["STR"].wins, teams["STR"].losses) == (3, 0)
    assert (teams["PKS"].wins, teams["PKS"].losses) == (0, 2)


def test_team_results_skip_games_not_final() -> None:
    feed = build(round_robin(final=False))

    assert [r.game_id for r in results_of(feed, "STR")] == ["g1", "g2"]
    assert [r.game_id for r in results_of(feed, "WAV")] == ["g1", "g3"]


def test_a_before_feed_has_zero_counts_and_no_default_game() -> None:
    games = [game("g1", None, None, status=GameStatus.SCHEDULED, note=CHAMPIONSHIP)]

    feed = build(games)

    assert feed.edition.counts.model_dump() == {
        "games": 0,
        "teams": 0,
        "final": 0,
        "live": 0,
    }
    assert feed.edition.default_game_id is None


def test_a_live_feed_carries_counts_default_next_and_leading() -> None:
    feed = build(live_day())

    edition = feed.edition
    assert edition.counts.model_dump() == {
        "games": 3,
        "teams": 4,
        "final": 1,
        "live": 1,
    }
    assert edition.default_game_id == "s2"
    assert [g.is_next for g in edition.games] == [False, False, True]
    assert [g.leading for g in edition.games] == [None, Side.AWAY, None]


def test_an_after_feed_has_the_championship_as_default_and_no_next_game() -> None:
    feed = build(round_robin())

    assert feed.edition.default_game_id == "g4"
    assert not any(g.is_next for g in feed.edition.games)


def full_previous(**changes: Any) -> AllStarSources:
    return previous_sources(**changes)


def test_the_previous_edition_has_every_game_its_teams_and_its_mvp() -> None:
    feed = build(round_robin(), previous=full_previous())

    earlier = feed.previous_edition
    assert earlier is not None
    assert earlier.date == PREVIOUS_DAY
    assert earlier.venue == Venue(name="Example Arena", city="Exampleton")
    assert earlier.format_line == "1 period · 12 min"
    assert [g.id for g in earlier.games] == ["p1", "p2"]
    assert all(g.box_score is not None and g.top5 for g in earlier.games)
    assert all(g.team_stats is not None for g in earlier.games)
    kinds_of = {t.team.code: t.placement.kind for t in earlier.teams}
    assert kinds_of == {
        "STR": PlacementKind.ELIMINATED,
        "WAV": PlacementKind.RUNNER_UP,
        "PKS": PlacementKind.CHAMPION,
    }
    assert earlier.mvp is not None and feed.previous is not None
    assert earlier.mvp == feed.previous.mvp
    assert earlier.counts.model_dump() == {
        "games": 2,
        "teams": 3,
        "final": 2,
        "live": 0,
    }


def test_the_previous_edition_has_its_counts_default_game_and_results() -> None:
    feed = build(round_robin(), previous=full_previous())

    earlier = feed.previous_edition
    assert earlier is not None
    assert earlier.default_game_id == "p2"
    wave = next(t for t in earlier.teams if t.team.code == "WAV")
    assert [(r.game_id, r.result) for r in wave.results] == [
        ("p1", GameResult.LOSS),
        ("p2", GameResult.LOSS),
    ]
    assert not any(g.is_next for g in earlier.games)


def test_the_previous_edition_is_none_when_the_recap_is_none() -> None:
    assert build(round_robin(), previous=None).previous_edition is None
    undiscovered = full_previous(edition_date=None)
    assert build(round_robin(), previous=undiscovered).previous_edition is None
    empty = sources([], year=2026, edition_date=PREVIOUS_DAY)
    assert build(round_robin(), previous=empty).previous_edition is None
    unplayed = [
        game("p1", STR, WAV, score=(21, 18)),
        game(
            "p2", WAV, PKS, note=CHAMPIONSHIP, status=GameStatus.SCHEDULED, minutes=30
        ),
    ]
    scheduled = sources(unplayed, year=2026, edition_date=PREVIOUS_DAY)
    assert build(round_robin(), previous=scheduled).previous_edition is None
    assert previous_edition(None) is None


def test_the_previous_edition_is_none_when_a_game_is_not_final() -> None:
    games = [
        game("p1", STR, WAV, score=(21, 18)),
        game("p2", WAV, PKS, note=CHAMPIONSHIP, score=(20, 22), minutes=30),
        game("p3", STR, PKS, status=GameStatus.SCHEDULED, minutes=60),
    ]
    previous = sources(games, year=2026, edition_date=PREVIOUS_DAY)

    feed = build(round_robin(), previous=previous)

    assert feed.previous is not None
    assert feed.previous_edition is None


def test_the_previous_edition_has_no_mvp_without_the_award() -> None:
    feed = build(round_robin(), previous=full_previous(awards=None))

    assert feed.previous_edition is not None
    assert feed.previous_edition.mvp is None


def test_a_before_feed_carries_the_previous_edition() -> None:
    games = [game("g1", None, None, status=GameStatus.SCHEDULED, note=CHAMPIONSHIP)]

    feed = build(games, previous=full_previous())

    assert feed.state is AllStarState.BEFORE
    assert feed.previous_edition is not None
    assert len(feed.previous_edition.games) == 2


def test_an_invalid_feed_is_wrapped_in_a_build_error() -> None:
    broken = game("g1", STR, WAV, minutes=0, score=(21, 18))
    broken = broken.model_copy(update={"score": None})

    with pytest.raises(AllStarBuildError) as raised:
        build([broken])

    assert raised.value.reason.startswith("invalid feed: ")


# Group 4: the kind


class FakeStars:
    def __init__(self) -> None:
        self.season: int | None = 2027
        self.ready = True

    def current_season(self) -> int | None:
        return self.season

    def rosters_ready(self) -> bool:
        return self.ready

    def player_team(self, player_id: str) -> str | None:
        return {"1001": "BOS", "2001": "LAL"}.get(player_id)


class FakeGames:
    pass


class AllStarKit:
    """The All-Star kind over one client and one clock, with fake adapters that
    count their calls."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.clock = [NOW]
        self.store = StateStore(path)
        self.store.migrate()
        self.settings = Settings(_env_file=None, data_dir=path)  # type: ignore[call-arg]
        self.client = create_client(self.store, clock=lambda: self.clock[0])
        self.calls: list[str] = []
        self.fresh: dict[str, Freshness] = {}
        self.cached_at: dict[str, dt.datetime] = {}
        self.read_at: dict[str, dt.datetime] = {}
        self.failing: set[str] = set()
        self.days: dict[dt.date, list[AllStarScoreboardGame]] = {
            DAY: round_robin(),
            PREVIOUS_DAY: [
                game("p1", STR, WAV, score=(21, 18)),
                game("p2", WAV, PKS, note=CHAMPIONSHIP, score=(20, 22), minutes=30),
            ],
        }
        self.mvp_id = "1001"
        self.stars = FakeStars()
        self.games = FakeGames()
        self.cache = FeedCache(path, self.store, clock=lambda: self.clock[0])
        self.discovery = AllStarDiscovery(
            self.settings,
            self.store,
            self.client,
            cast(StarsJob, self.stars),
            fetch_all_star_games=self.fetch_days,
        )
        self.feeds = AllStarFeeds(
            self.settings,
            self.store,
            self.client,
            self.cache,
            cast(GamesJob, self.games),
            cast(StarsJob, self.stars),
            self.discovery,
            fetch_all_star_games=self.fetch_day,
            fetch_game_detail=self.fetch_game_detail,
            fetch_game_detail_sections=self.fetch_game_detail_sections,
            fetch_all_star_extras=self.fetch_all_star_extras,
            fetch_team_info=self.fetch_team_info,
            fetch_season_awards=self.fetch_season_awards,
        )

    def read(self, name: str) -> None:
        self.calls.append(name)
        if name in self.failing:
            raise SourceError("test", f"{name} is down")

    def called(self, prefix: str) -> int:
        return sum(1 for name in self.calls if name.startswith(prefix))

    async def fetch_days(
        self, client: SourceClient, day: dt.date, settings: Settings
    ) -> list[AllStarScoreboardGame]:
        """The reader of the discovery job: it is not counted."""
        return list(self.days.get(day, []))

    async def fetch_day(
        self, client: SourceClient, day: dt.date, settings: Settings, fresh: Freshness
    ) -> list[AllStarScoreboardGame]:
        self.read(f"day/{day.isoformat()}")
        self.fresh[f"day/{day.isoformat()}"] = fresh
        return list(self.days.get(day, []))

    def find(self, game_id: str) -> AllStarScoreboardGame:
        for found in (g for games in self.days.values() for g in games):
            if found.id == game_id:
                return found
        raise AssertionError(game_id)

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
        self.summary_read(game_id, fresh)
        return sections_of(self.find(game_id))

    def summary_read(self, game_id: str, fresh: Freshness) -> None:
        """Emulates the source cache: a cached summary is reused when fresh, else
        it is read again; read_at keeps when the summary in use was fetched."""
        now = self.clock[0]
        cached = self.cached_at.get(game_id)
        if cached is not None and (
            now - cached < fresh if isinstance(fresh, dt.timedelta) else cached >= fresh
        ):
            self.read_at[game_id] = cached
            return
        self.cached_at[game_id] = now
        self.read_at[game_id] = now

    async def fetch_all_star_extras(
        self, client: SourceClient, game_id: str, settings: Settings, fresh: Freshness
    ) -> AllStarDetailExtras:
        self.read(f"extras/{game_id}")
        self.fresh[f"extras/{game_id}"] = fresh
        return extras()

    async def fetch_team_info(
        self, client: SourceClient, code: str, settings: Settings
    ) -> TeamInfo:
        self.read(f"info/{code}")
        return info()

    async def fetch_season_awards(
        self, client: SourceClient, season: int, settings: Settings
    ) -> SeasonAwards:
        self.read(f"awards/{season}")
        return award(self.mvp_id if season == 2027 else "3001")

    async def discover(self, at: dt.datetime | None = None) -> None:
        await self.discovery.run(at or self.clock[0])

    async def settle(self) -> None:
        while self.cache.in_flight:
            await next(iter(self.cache.in_flight.values()))
            await asyncio.sleep(0)
        await asyncio.sleep(0)

    async def serve(self, at: dt.datetime | None = None) -> bytes:
        if at is not None:
            self.clock[0] = at
        body = await self.cache.serve(KIND, FEED_ID)
        await self.settle()
        return body

    def stored(self) -> AllStarFeed | None:
        body = read_by_id(self.path, KIND, FEED_ID)
        return None if body is None else AllStarFeed.model_validate_json(body)

    def last_build(self) -> dt.datetime | None:
        state = self.store.feed_build(KIND, FEED_ID)
        return None if state is None else state.last_build


@pytest.fixture(autouse=True)
def no_network() -> Iterator[None]:
    with respx.mock:
        yield


@pytest.fixture
def kit(tmp_path: Path) -> AllStarKit:
    return AllStarKit(tmp_path)


@pytest.mark.anyio
async def test_an_id_other_than_league_answers_unknown_with_no_build(
    kit: AllStarKit, tmp_path: Path
) -> None:
    await kit.discover()
    for feed_id in ("LEAGUE", "all-star", ""):
        assert kit.feeds.check(feed_id) is IdStatus.UNKNOWN
        with pytest.raises(UnknownFeedError):
            await kit.cache.serve(KIND, feed_id)

    assert kit.feeds.check("league") is IdStatus.KNOWN
    assert kit.calls == []
    assert not (tmp_path / "feeds" / KIND).exists()


@pytest.mark.anyio
async def test_it_answers_not_ready_before_the_season_the_rosters_or_the_discovery(
    kit: AllStarKit,
) -> None:
    assert kit.feeds.check(FEED_ID) is IdStatus.NOT_READY
    with pytest.raises(FeedUnavailableError):
        await kit.cache.serve(KIND, FEED_ID)

    await kit.discover()
    assert kit.feeds.check(FEED_ID) is IdStatus.KNOWN
    kit.stars.ready = False
    assert kit.feeds.check(FEED_ID) is IdStatus.NOT_READY
    kit.stars.ready = True
    kit.stars.season = None
    assert kit.feeds.check(FEED_ID) is IdStatus.NOT_READY
    assert kit.calls == []


@pytest.mark.anyio
async def test_a_stored_feed_is_served_even_when_the_season_is_not_known(
    kit: AllStarKit,
) -> None:
    await kit.discover()
    await kit.serve()
    kit.stars.season = None
    kit.stars.ready = False

    assert kit.feeds.check(FEED_ID) is IdStatus.KNOWN


@pytest.mark.anyio
async def test_no_feed_is_built_stored_or_fetched_without_a_request(
    kit: AllStarKit,
) -> None:
    await kit.discover()
    await kit.settle()

    assert kit.calls == []
    assert kit.stored() is None
    assert kit.store.feed_build_ids(KIND) == set()


@pytest.mark.anyio
async def test_a_request_builds_and_stores_and_a_second_request_reads_storage(
    kit: AllStarKit,
) -> None:
    await kit.discover()

    body = await kit.serve()

    feed = AllStarFeed.model_validate_json(body)
    assert feed == kit.stored()
    assert feed.state is AllStarState.AFTER
    assert feed.mvp is not None and feed.mvp.player_id == "1001"
    assert feed.previous is not None and feed.previous.championship.game_id == "p2"
    assert kit.last_build() == NOW
    assert kit.called("day/") == 2
    assert kit.called("detail/") == 6
    assert kit.called("sections/") == 6
    assert kit.called("extras/") == 6
    assert kit.called("info/") == 2
    assert kit.called("awards/") == 2
    calls = len(kit.calls)

    again = await kit.serve()

    assert again == body
    assert len(kit.calls) == calls


@pytest.mark.anyio
async def test_a_season_with_no_edition_builds_a_before_feed_reading_nothing_else(
    kit: AllStarKit,
) -> None:
    kit.days = {}
    await kit.discover()

    feed = AllStarFeed.model_validate_json(await kit.serve())

    assert feed.state is AllStarState.BEFORE
    assert feed.edition.date is None and feed.previous is None
    assert kit.calls == []


@pytest.mark.anyio
async def test_a_failed_current_day_answers_unavailable_and_is_not_retried_for_ten_minutes(
    kit: AllStarKit,
) -> None:
    await kit.discover()
    kit.failing = {f"day/{DAY.isoformat()}"}

    with pytest.raises(FeedUnavailableError):
        await kit.cache.serve(KIND, FEED_ID)
    await kit.settle()
    calls = len(kit.calls)

    with pytest.raises(FeedUnavailableError):
        await kit.cache.serve(KIND, FEED_ID)

    assert len(kit.calls) == calls
    assert kit.stored() is None

    kit.failing = set()
    kit.clock[0] = NOW + RETRY_AFTER
    body = await kit.serve()

    assert AllStarFeed.model_validate_json(body).state is AllStarState.AFTER


@pytest.mark.anyio
async def test_a_failed_rebuild_keeps_and_serves_the_stored_feed(
    kit: AllStarKit,
) -> None:
    await kit.discover()
    kit.days[DAY] = round_robin(final=False)
    first = await kit.serve()
    built_at = kit.last_build()
    kit.failing = {f"day/{DAY.isoformat()}"}
    kit.clock[0] = NOW + LIVE_INTERVAL + SECOND

    body = await kit.serve()

    assert body == first
    assert kit.last_build() == built_at
    state = kit.store.feed_build(KIND, FEED_ID)
    assert state is not None and state.last_failure is not None


@pytest.mark.anyio
async def test_any_other_failed_read_only_nulls_its_part(kit: AllStarKit) -> None:
    await kit.discover()
    kit.failing = {
        "detail/g1",
        "sections/g2",
        "extras/g3",
        "info/BOS",
        "awards/2027",
        f"day/{PREVIOUS_DAY.isoformat()}",
    }

    await kit.serve()

    stored = kit.stored()
    assert stored is not None
    games = stored.edition.games
    assert games[0].leaders is None and games[1].leaders is not None
    assert games[1].box_score is None and games[0].box_score is not None
    assert games[2].attendance is None and games[0].attendance == 18500
    ada = games[0].box_score.away.players[0]
    assert ada.league_team is not None and ada.league_team.colors.primary is None
    assert stored.mvp is None
    assert stored.previous is None


@pytest.mark.anyio
async def test_the_reads_get_the_live_interval_the_first_seen_final_time_or_one_hour(
    kit: AllStarKit,
) -> None:
    final_time = NOW - dt.timedelta(minutes=5)
    kit.store.record_all_star_final("g1", final_time)
    kit.days[DAY] = [
        game("g1", STR, WAV, minutes=0),
        game("g2", PKS, STR, status=GameStatus.LIVE, score=(5, 4), minutes=30),
        game("g3", WAV, PKS, status=GameStatus.SCHEDULED, minutes=60),
        game("g4", STR, WAV, minutes=90),
    ]
    await kit.discover()

    await kit.serve()

    assert kit.fresh["sections/g1"] == final_time
    assert kit.fresh["detail/g1"] == final_time
    assert kit.fresh["extras/g1"] == final_time
    assert kit.fresh["sections/g2"] == LIVE_INTERVAL
    assert kit.fresh["sections/g3"] == UNPLAYED_FRESH
    assert kit.fresh["sections/g4"] == NOW
    assert kit.store.all_star_final_time("g4") == NOW
    assert kit.store.all_star_final_time("g3") is None
    assert kit.fresh["day/2027-02-14"] == LIVE_INTERVAL


@pytest.mark.anyio
async def test_the_previous_edition_is_read_with_a_24_hour_freshness(
    kit: AllStarKit,
) -> None:
    await kit.discover()

    await kit.serve()

    assert PREVIOUS_FRESH == dt.timedelta(hours=24)
    assert kit.fresh[f"day/{PREVIOUS_DAY.isoformat()}"] == PREVIOUS_FRESH
    for name in ("detail", "sections", "extras"):
        assert kit.fresh[f"{name}/p1"] == PREVIOUS_FRESH
        assert kit.fresh[f"{name}/p2"] == PREVIOUS_FRESH
    assert kit.store.all_star_final_time("p1") is None


@pytest.mark.anyio
async def test_the_first_seen_final_time_is_stored_once_and_never_overwritten(
    kit: AllStarKit,
) -> None:
    kit.days[DAY] = round_robin(final=False)
    await kit.discover()
    await kit.serve()
    first = kit.store.all_star_final_time("g1")
    assert first == NOW and kit.store.all_star_final_time("g4") is None
    kit.days[DAY] = round_robin()

    await kit.serve(NOW + LIVE_INTERVAL + SECOND)
    await kit.serve(NOW + 2 * LIVE_INTERVAL + 2 * SECOND)

    assert kit.store.all_star_final_time("g1") == first
    assert kit.store.all_star_final_time("g4") == NOW + LIVE_INTERVAL + SECOND


@pytest.mark.anyio
async def test_a_kept_feed_of_games_cached_while_live_comes_from_a_read_after_they_ended(
    kit: AllStarKit,
) -> None:
    live = [g.model_copy(update={"status": GameStatus.LIVE}) for g in round_robin()]
    kit.days[DAY] = live
    await kit.discover()
    await kit.serve()
    assert set(kit.read_at.values()) >= {NOW}
    assert kit.stored() is not None
    ended = NOW + dt.timedelta(minutes=10)
    kit.days[DAY] = round_robin()

    await kit.serve(ended)

    stored = kit.stored()
    assert stored is not None and stored.state is AllStarState.AFTER
    for game_id in ("g1", "g2", "g3", "g4"):
        assert kit.read_at[game_id] == ended
        assert kit.store.all_star_final_time(game_id) == ended


@pytest.mark.anyio
async def test_an_after_feed_is_held_30_seconds_until_a_build_one_hour_after_the_games_ended(
    kit: AllStarKit,
) -> None:
    await kit.discover()
    feed, built_at = await stored_feed(kit)
    assert feed.state is AllStarState.AFTER and FINAL_HOLD == dt.timedelta(hours=1)
    assert kit.last_build() == NOW

    assert kit.feeds.is_fresh(feed, built_at, built_at + LIVE_INTERVAL - SECOND)
    assert not kit.feeds.is_fresh(feed, built_at, built_at + LIVE_INTERVAL)
    assert not kit.feeds.is_fresh(feed, built_at, built_at + dt.timedelta(days=30))

    early = NOW + FINAL_HOLD - SECOND
    await kit.serve(early)
    early_built = kit.last_build()
    assert early_built == early
    assert not kit.feeds.is_fresh(
        feed, early_built, early_built + dt.timedelta(days=30)
    )

    await kit.serve(NOW + FINAL_HOLD + LIVE_INTERVAL)
    kept_built = kit.last_build()
    assert kept_built == NOW + FINAL_HOLD + LIVE_INTERVAL
    assert kit.feeds.is_fresh(feed, kept_built, kept_built + dt.timedelta(days=30))


@pytest.mark.anyio
async def test_highlights_are_added_when_served_and_not_stored(
    kit: AllStarKit,
) -> None:
    clip = Highlight(
        title="Example clip",
        channel="Example channel",
        thumbnail_url=HttpUrl("https://example.com/thumb.jpg"),
        embed_url=HttpUrl("https://example.com/embed"),
    )
    kit.store.set_highlight("g2", clip)
    await kit.discover()

    body = await kit.serve()

    served = AllStarFeed.model_validate_json(body)
    assert [g.highlights for g in served.edition.games] == [None, [clip], None, None]
    stored = kit.stored()
    assert stored is not None
    assert all(g.highlights is None for g in stored.edition.games)


@pytest.mark.anyio
async def test_highlights_are_added_to_the_previous_edition_games_when_served(
    kit: AllStarKit,
) -> None:
    clip = Highlight(
        title="Example clip",
        channel="Example channel",
        thumbnail_url=HttpUrl("https://example.com/thumb.jpg"),
        embed_url=HttpUrl("https://example.com/embed"),
    )
    kit.store.set_highlight("p2", clip)
    await kit.discover()

    body = await kit.serve()

    served = AllStarFeed.model_validate_json(body)
    assert served.previous_edition is not None
    assert [g.highlights for g in served.previous_edition.games] == [None, [clip]]
    stored = kit.stored()
    assert stored is not None and stored.previous_edition is not None
    assert all(g.highlights is None for g in stored.previous_edition.games)


@pytest.mark.anyio
async def test_the_previous_edition_adds_no_read(kit: AllStarKit) -> None:
    await kit.discover()

    body = await kit.serve()

    feed = AllStarFeed.model_validate_json(body)
    assert feed.previous_edition is not None
    assert kit.called("day/") == 2
    assert kit.called("detail/") == 6
    assert kit.called("sections/") == 6
    assert kit.called("extras/") == 6
    assert kit.called("awards/") == 2
    assert kit.called("info/") == 2
    assert sum(1 for c in kit.calls if c == "sections/p2") == 1


def test_the_cleanup_keeps_league(kit: AllStarKit) -> None:
    assert kit.feeds.keep(FEED_ID)
    assert not kit.feeds.keep("other")


# Expiry (the rule G row)


async def stored_feed(kit: AllStarKit) -> tuple[AllStarFeed, dt.datetime]:
    await kit.serve()
    feed, built_at = kit.stored(), kit.last_build()
    assert feed is not None and built_at is not None
    return feed, built_at


@pytest.mark.anyio
async def test_a_live_feed_is_stale_30_seconds_after_the_build(
    kit: AllStarKit,
) -> None:
    kit.days[DAY] = round_robin(final=False)
    await kit.discover()
    feed, built_at = await stored_feed(kit)
    assert feed.state is AllStarState.LIVE

    assert kit.feeds.is_fresh(feed, built_at, built_at + LIVE_INTERVAL - SECOND)
    assert not kit.feeds.is_fresh(feed, built_at, built_at + LIVE_INTERVAL)


@pytest.mark.anyio
async def test_a_request_that_finds_a_live_feed_stale_waits_for_the_rebuild(
    kit: AllStarKit,
) -> None:
    kit.days[DAY] = round_robin(final=False)
    await kit.discover()
    first = await kit.serve()
    assert kit.feeds.wait_when_stale(FEED_ID)
    kit.days[DAY] = round_robin()

    body = await kit.serve(NOW + LIVE_INTERVAL + SECOND)

    assert body != first
    assert AllStarFeed.model_validate_json(body).state is AllStarState.AFTER
    assert kit.last_build() == NOW + LIVE_INTERVAL + SECOND


@pytest.mark.anyio
async def test_a_feed_before_the_games_on_the_date_of_the_edition_is_stale_after_30_seconds(
    kit: AllStarKit,
) -> None:
    kit.days[DAY] = [
        game("g1", STR, WAV, status=GameStatus.SCHEDULED),
        game(
            "c", None, None, status=GameStatus.SCHEDULED, note=CHAMPIONSHIP, minutes=30
        ),
    ]
    await kit.discover()
    feed, built_at = await stored_feed(kit)
    assert feed.state is AllStarState.BEFORE and feed.edition.date == DAY

    assert kit.feeds.is_fresh(feed, built_at, built_at + LIVE_INTERVAL - SECOND)
    assert not kit.feeds.is_fresh(feed, built_at, built_at + LIVE_INTERVAL)
    assert kit.feeds.wait_when_stale(FEED_ID)


@pytest.mark.anyio
async def test_a_feed_before_the_edition_is_fresh_until_the_discovery_runs_after_the_build(
    kit: AllStarKit,
) -> None:
    kit.days[DAY] = []
    await kit.discover()
    feed, built_at = await stored_feed(kit)
    assert feed.state is AllStarState.BEFORE and feed.edition.date is None
    later = built_at + dt.timedelta(hours=5)

    assert kit.feeds.is_fresh(feed, built_at, later)
    assert not kit.feeds.wait_when_stale(FEED_ID)

    kit.clock[0] = built_at + dt.timedelta(days=1)
    await kit.discover(built_at + dt.timedelta(days=1))

    assert not kit.feeds.is_fresh(feed, built_at, built_at + dt.timedelta(days=1))


@pytest.mark.anyio
async def test_a_finished_edition_is_kept_while_its_season_is_the_current_one(
    kit: AllStarKit,
) -> None:
    for game_id in ("g1", "g2", "g3", "g4"):
        kit.store.record_all_star_final(game_id, NOW - FINAL_HOLD)
    await kit.discover()
    feed, built_at = await stored_feed(kit)
    assert feed.state is AllStarState.AFTER
    later = built_at + dt.timedelta(days=400)
    kit.clock[0] = later

    assert kit.feeds.is_fresh(feed, built_at, later)
    assert not kit.feeds.wait_when_stale(FEED_ID)
    kit.stars.season = None
    assert kit.feeds.is_fresh(feed, built_at, later)
    kit.stars.season = 2027
    kit.clock[0] = later
    await kit.discover(later)
    assert kit.feeds.is_fresh(feed, built_at, later)


@pytest.mark.anyio
async def test_a_finished_edition_is_stale_once_the_season_changes(
    kit: AllStarKit,
) -> None:
    await kit.discover()
    feed, built_at = await stored_feed(kit)

    kit.stars.season = 2028

    assert not kit.feeds.is_fresh(feed, built_at, built_at + SECOND)
