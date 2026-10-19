# api/tests/jobs/test_cup_feed.py
#
# Tests for the Cup feed builder and its feed kind.
#
# Tested:
# - Groups not drawn: stage draw, no teams or rows, and the group round is next
# - A draw with no table rows: stage draw, teams listed, no rows, empty wild cards and the first group game date
# - Partial group play: stage group, games final per group, games played and the stage statuses
# - All group games final with no quarterfinal scheduled: stage group, quarterfinal sides known, no quarterfinal dates
# - Each knockout stage: quarterfinals, semifinals and championship, with the rounds before it complete
# - A round with fewer than its full games, all final, is not final
# - A complete Cup has the champion and four complete stages
# - Missing table values are null, and a row with no clinch has a null tag
# - The wild card standings of each conference, ranked from the fourth row
# - Unscheduled knockout slots carry their labels, rules and the current leaders with their records
# - Known sides carry their standing (seed, group and record), a semifinal side its winner's, and a projected or empty side has none
# - A final game keeps its period and a scheduled game has none
# - Scheduled knockout games replace the projections, matched to the quarterfinal slots by seed
# - A past Cup places the quarterfinals of a conference by start time with null seed labels, builds as complete when two quarterfinals share a seed and its semifinal links both, and fails with three quarterfinals in a conference (ADR 0053)
# - Two quarterfinals in one slot, a knockout team outside the draw and a bad streak fail the build
# - The championship counts outside the standings and both final rounds are on a neutral court
# - A game seen from both teams is listed once with both sides' names, and a team no schedule shows has a null name
# - Stage dates are the first and last US Eastern dates of the round, null with no games
# - Stage counts per round and the games by day in start order
# - Wraps an invalid feed in a build error
# - The kind: an id other than league answers unknown with no build
# - The kind: it answers not ready with no season and nothing stored
# - The kind: no feed is built, stored or fetched without a request
# - The kind: a request builds and stores the feed and a second request reads storage
# - The kind: a failed group or conference read with nothing stored answers unavailable and is not retried for 10 minutes
# - The kind: a failed rebuild of a stale feed keeps and serves the stored feed
# - The kind: a schedule cached 2 hours ago is read from the cache except for a team with a game today in the games job's shown games, and before the games job's first run every schedule keeps the 1 hour freshness (ADR 0066)
# - The kind: a failed schedule is skipped when every drawn team still has its 4 group games, and fails the build otherwise
# - The kind: fresh before a final Cup game plus 1 hour and stale at it, and a final game outside the Cup does not expire it
# - The kind: fresh before 7 days and stale at 7 days
# - The kind: a complete feed stays fresh past 7 days and after later final Cup games, and is stale once the season changes
# - The kind: detailAvailable is set when served from the loaded games and not stored
# - The kind: the cleanup keeps league
# - The kind: it reads the stored feed, and none when missing or invalid
#
# What is covered:
# - Pure conversions: happy path, edges and errors; the built feed validates
# - Feed kind: success publishes a valid feed, failure keeps the last valid feed, expiry edges
#
# Fake adapters and a fake clock are passed to the builder and the kind, so no
# test uses a real source or the real clock.
#
# Run with: cd api && .venv/bin/python -m pytest tests/jobs/test_cup_feed.py
#
# SEE: api/app/jobs/cup_feed.py

import asyncio
import datetime as dt
from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import Any, cast

import pytest
import respx

from app.feeds.cup import (
    BracketSlot,
    CupFeed,
    CupStage,
    CupTag,
    SlotId,
    SlotRule,
    StageStatus,
)
from app.feeds.game_detail import Conference
from app.feeds.games import (
    CupRound,
    GameCup,
    GameStatus,
    GameTeam,
    LineScore,
    Score,
)
from app.feeds.opponent import Opponent
from app.jobs.cup_feed import (
    CODES,
    FEED_ID,
    KIND,
    SCHEDULE_FRESH,
    CupBuildError,
    CupFeeds,
    CupSources,
    build_cup_feed,
)
from app.jobs.games import GamesJob
from app.jobs.on_demand import (
    RETRY_AFTER,
    FeedCache,
    FeedUnavailableError,
    IdStatus,
    UnknownFeedError,
)
from app.jobs.stars import StarsJob
from app.jobs.team_feed import FEED_LIFETIME
from app.settings import Settings
from app.sources.cup import GROUP_IDS, CupTable, CupTableRow
from app.sources.game_detail import GameDetail
from app.sources.http import (
    Freshness,
    SourceClient,
    SourceError,
    create_client,
    get_json,
)
from app.sources.scoreboard import ScoreboardGame
from app.sources.team_schedule import ScheduledGame, SeasonSchedule
from app.storage.feeds import read_by_id
from app.storage.state import StateStore

EAST, WEST = Conference.EAST, Conference.WEST
GROUPS: dict[tuple[Conference, str], list[str]] = {
    (EAST, "A"): ["ATL", "BOS", "BKN", "CHA", "CHI"],
    (EAST, "B"): ["CLE", "DET", "IND", "MIA", "MIL"],
    (EAST, "C"): ["NYK", "ORL", "PHI", "TOR", "WAS"],
    (WEST, "A"): ["DAL", "DEN", "GSW", "HOU", "LAC"],
    (WEST, "B"): ["LAL", "MEM", "MIN", "NOP", "OKC"],
    (WEST, "C"): ["PHX", "POR", "SAC", "SAS", "UTA"],
}
# Seeds 1 to 3, the wild card, then the rest, as the conference tables list them.
ORDER = {
    EAST: [
        "ATL",
        "CLE",
        "NYK",
        "BOS",
        "BKN",
        "CHA",
        "CHI",
        "DET",
        "IND",
        "MIA",
        "MIL",
        "ORL",
        "PHI",
        "TOR",
        "WAS",
    ],
    WEST: [
        "DAL",
        "LAL",
        "PHX",
        "DEN",
        "GSW",
        "HOU",
        "LAC",
        "MEM",
        "MIN",
        "NOP",
        "OKC",
        "POR",
        "SAC",
        "SAS",
        "UTA",
    ],
}
NOTES = {
    CupRound.GROUP: "NBA Cup - Group Play",
    CupRound.QUARTERFINALS: "NBA Cup - Quarterfinals",
    CupRound.SEMIFINALS: "NBA Cup - Semifinals",
    CupRound.CHAMPIONSHIP: "NBA Cup Championship",
}
# 18:00 US Eastern on the first day of group play.
BASE = dt.datetime(2026, 11, 3, 23, 0, tzinfo=dt.UTC)
DAY = dt.timedelta(days=1)
HOUR = dt.timedelta(hours=1)
SCHEDULE_URL = "https://example.com/schedule/"
SECOND = dt.timedelta(seconds=1)
NOW = dt.datetime(2026, 12, 1, 15, 0, tzinfo=dt.UTC)

Pair = dict[str, ScheduledGame]


def opponent(code: str) -> Opponent:
    return Opponent(code=code, name=f"Team {code}", city=f"City {code}", guest=False)


def cup_row(code: str, wins: int = 0, losses: int = 0, **changes: Any) -> CupTableRow:
    data: dict[str, Any] = {
        "code": code,
        "wins": wins,
        "losses": losses,
        "position": None,
        "games_behind": None,
        "differential": None,
        "point_differential": None,
        "points_for": None,
        "points_against": None,
        "streak": None,
        "ot_wins": None,
        "ot_losses": None,
        "clincher": None,
        "home": None,
        "road": None,
    }
    data.update(changes)
    return CupTableRow.model_validate(data)


def pair(
    game_id: str,
    stage: CupRound,
    home: str,
    away: str,
    start: dt.datetime,
    *,
    scores: tuple[int, int] | None = None,
    note: str | None = None,
    period: int | None = None,
) -> Pair:
    """A game as each of its two teams' schedules shows it: home score first."""
    played = scores is not None
    views: Pair = {}
    for code, other, is_home in ((home, away, True), (away, home, False)):
        mine, theirs = (
            ((scores[0], scores[1]) if is_home else (scores[1], scores[0]))
            if scores
            else (None, None)
        )
        views[code] = ScheduledGame(
            game_id=game_id,
            start_time=start,
            opponent=opponent(other),
            is_home=is_home,
            state="post" if played else "pre",
            completed=played,
            won=None if scores is None else mine > theirs,  # type: ignore[operator]
            team_score=mine,
            opponent_score=theirs,
            note=note or NOTES[stage],
            broadcast="TV" if stage is not CupRound.GROUP else None,
            arena="Arena",
            city="Town",
            playoffs=False,
            period=period if played else None,
        )
    return views


def group_pairs(finals: dict[tuple[Conference, str], int], skip: int = 0) -> list[Pair]:
    """The 10 games of each group: the first finals[group] are final, home team wins."""
    pairs: list[Pair] = []
    for key, codes in GROUPS.items():
        games = [(a, b) for i, a in enumerate(codes) for b in codes[i + 1 :]]
        for number, (home, away) in enumerate(games):
            if skip and key == (EAST, "A") and number < skip:
                continue
            scores = (100, 90) if number < finals.get(key, 0) else None
            pairs.append(
                pair(
                    f"{key[0].value}{key[1]}{number}",
                    CupRound.GROUP,
                    home,
                    away,
                    BASE + (number % 10) * DAY,
                    scores=scores,
                )
            )
    return pairs


def all_final() -> dict[tuple[Conference, str], int]:
    return {key: 10 for key in GROUPS}


def knockouts(scheduled: int, finals: int) -> list[Pair]:
    """The knockout games of the first `scheduled` rounds after the group round
    (1 quarterfinals, 2 semifinals, 3 championship), the first `finals` final."""
    plan = [
        (CupRound.QUARTERFINALS, "qe1", "ATL", "BOS"),
        (CupRound.QUARTERFINALS, "qe2", "CLE", "NYK"),
        (CupRound.QUARTERFINALS, "qw1", "DAL", "DEN"),
        (CupRound.QUARTERFINALS, "qw2", "LAL", "PHX"),
        (CupRound.SEMIFINALS, "se", "ATL", "CLE"),
        (CupRound.SEMIFINALS, "sw", "DAL", "LAL"),
        (CupRound.CHAMPIONSHIP, "final", "DAL", "ATL"),
    ]
    rounds = [CupRound.QUARTERFINALS, CupRound.SEMIFINALS, CupRound.CHAMPIONSHIP]
    pairs = []
    for number, (stage, game_id, home, away) in enumerate(plan):
        index = rounds.index(stage)
        if index >= scheduled:
            continue
        pairs.append(
            pair(
                game_id,
                stage,
                home,
                away,
                BASE + (20 + number) * DAY,
                scores=(100, 90) if index < finals else None,
            )
        )
    return pairs


def schedules_of(pairs: Sequence[Pair]) -> dict[str, SeasonSchedule]:
    games: dict[str, list[ScheduledGame]] = {}
    for views in pairs:
        for code, view in views.items():
            games.setdefault(code, []).append(view)
    return {code: SeasonSchedule(games=listed) for code, listed in games.items()}


def group_table(codes: Sequence[str], **changes: Any) -> CupTable:
    return CupTable(
        rows=[
            cup_row(code, 4 - i, i, position=i + 1, **changes)
            for i, code in enumerate(codes)
        ]
    )


def sources(
    pairs: Sequence[Pair] = (),
    *,
    drawn: bool = True,
    rows: bool = True,
    tables: dict[tuple[Conference, str], CupTable] | None = None,
    conferences: dict[Conference, CupTable] | None = None,
    past: bool = False,
) -> CupSources:
    return CupSources(
        season=2027,
        group_teams={key: (codes if drawn else []) for key, codes in GROUPS.items()},
        group_tables=tables
        if tables is not None
        else {
            key: group_table(codes) if rows else CupTable(rows=[])
            for key, codes in GROUPS.items()
        },
        conference_tables=conferences
        if conferences is not None
        else {
            conference: CupTable(
                rows=[
                    cup_row(code, 3 - i // 5, i // 5)
                    for i, code in enumerate(ORDER[conference])
                ]
            )
            if rows
            else CupTable(rows=[])
            for conference in (EAST, WEST)
        },
        schedules=schedules_of(pairs),
        past=past,
    )


def build(*args: Any, **kwargs: Any) -> CupFeed:
    return build_cup_feed(sources(*args, **kwargs))


def slot(feed: CupFeed, slot_id: SlotId) -> BracketSlot:
    return next(s for s in feed.bracket if s.id is slot_id)


# Group 1: the builder


def test_groups_not_drawn_have_the_draw_stage_and_empty_groups() -> None:
    feed = build(drawn=False, rows=False)

    assert (feed.drawn, feed.stage) == (False, CupStage.DRAW)
    assert all(g.teams == [] and g.rows == [] for g in feed.groups)
    assert [s.status for s in feed.stages] == [
        StageStatus.NEXT,
        StageStatus.UPCOMING,
        StageStatus.UPCOMING,
        StageStatus.UPCOMING,
    ]
    assert feed.first_game_date is None
    assert feed.group_games_total == 60 and feed.group_games_played == 0


def test_a_draw_with_no_table_rows_lists_the_teams_and_the_first_group_game() -> None:
    feed = build(group_pairs({}), rows=False)

    assert (feed.drawn, feed.stage) == (True, CupStage.DRAW)
    assert [t.code for t in feed.groups[0].teams] == GROUPS[(EAST, "A")]
    assert all(g.rows == [] for g in feed.groups)
    assert all(table.rows == [] for table in feed.wild_card)
    assert feed.first_game_date == dt.date(2026, 11, 3)
    assert feed.stages[0].status is StageStatus.NEXT


def test_partial_group_play_counts_the_final_games_of_each_group() -> None:
    feed = build(group_pairs({(EAST, "A"): 3, (WEST, "C"): 10}))

    assert feed.stage is CupStage.GROUP
    assert [g.games_final for g in feed.groups] == [3, 0, 0, 0, 0, 10]
    assert [g.final for g in feed.groups] == [False] * 5 + [True]
    assert feed.group_games_played == 13
    assert [s.status for s in feed.stages] == [
        StageStatus.IN_PROGRESS,
        StageStatus.NEXT,
        StageStatus.UPCOMING,
        StageStatus.UPCOMING,
    ]
    sides = slot(feed, SlotId.EAST_QF_1)
    assert sides.top.projected is not None and sides.top.known is False


def test_all_group_games_final_with_no_quarterfinal_keeps_the_group_stage() -> None:
    feed = build(group_pairs(all_final()))

    assert feed.stage is CupStage.GROUP
    assert feed.groups[0].final and feed.group_games_played == 60
    first = slot(feed, SlotId.EAST_QF_1)
    assert first.top.known and first.top.team is not None
    assert first.top.team.code == "ATL" and first.top.projected is None
    assert first.bottom.team is not None and first.bottom.team.code == "BOS"
    assert first.game is None
    assert feed.stages[1].first_date is None and feed.stages[1].last_date is None


@pytest.mark.parametrize(
    ("scheduled", "finals", "stage", "statuses"),
    [
        (1, 0, CupStage.QUARTERFINALS, "complete in_progress next upcoming"),
        (2, 1, CupStage.SEMIFINALS, "complete complete in_progress next"),
        (3, 2, CupStage.CHAMPIONSHIP, "complete complete complete in_progress"),
    ],
)
def test_each_knockout_stage_follows_the_rounds_before_it(
    scheduled: int, finals: int, stage: CupStage, statuses: str
) -> None:
    feed = build([*group_pairs(all_final()), *knockouts(scheduled, finals)])

    assert feed.stage is stage
    assert [s.status.value for s in feed.stages] == statuses.split()


def test_a_round_with_fewer_than_its_full_games_all_final_is_not_final() -> None:
    feed = build([*group_pairs(all_final(), skip=1), *knockouts(1, 0)])

    assert feed.stage is CupStage.GROUP
    assert feed.group_games_played == 59


def test_a_complete_cup_has_the_champion_and_four_complete_stages() -> None:
    feed = build([*group_pairs(all_final()), *knockouts(3, 3)])

    assert feed.stage is CupStage.COMPLETE
    assert feed.champion is not None and feed.champion.code == "DAL"
    assert [s.status for s in feed.stages] == [StageStatus.COMPLETE] * 4
    assert slot(feed, SlotId.FINAL).top.team is not None


def test_missing_table_values_are_null_and_no_clinch_has_no_tag() -> None:
    bare = {
        key: CupTable(rows=[cup_row(codes[0], 1, 0)]) for key, codes in GROUPS.items()
    }

    row = build(group_pairs({}), tables=bare).groups[0].rows[0]

    assert (row.position, row.games_behind, row.differential, row.total) == (
        None,
        None,
        None,
        None,
    )
    assert (row.streak, row.points_for, row.points_against) == (None, None, None)
    assert (row.home, row.away, row.overtime, row.tag) == (None, None, None, None)


def test_a_table_row_is_converted_to_the_contract_text_forms() -> None:
    full = cup_row(
        "ATL",
        4,
        0,
        position=1,
        games_behind="1.5",
        differential=-2.46,
        point_differential=23.0,
        points_for=412.0,
        points_against=389.0,
        streak="W4",
        ot_wins=1,
        ot_losses=0,
        clincher=CupTag.WON_GROUP,
        home="2-0",
        road="bad",
    )
    tables = {(EAST, "A"): CupTable(rows=[full])}
    tables.update({key: CupTable(rows=[]) for key in GROUPS if key != (EAST, "A")})

    row = build(group_pairs({}), tables=tables).groups[0].rows[0]

    assert row.games_behind == "1.5"
    assert row.differential is not None and row.differential.value == "−2.5"
    assert row.differential.non_negative is False
    assert row.total is not None and row.total.value == "+23"
    assert (row.points_for, row.points_against) == (412, 389)
    assert row.streak is not None and row.streak.count == 4
    assert (row.home, row.away, row.overtime) == ("2-0", None, "1-0")
    assert row.tag is CupTag.WON_GROUP


def test_the_wild_card_standings_of_each_conference_rank_from_the_fourth_row() -> None:
    conferences = {
        conference: CupTable(
            rows=[
                cup_row(
                    code,
                    3,
                    1,
                    point_differential=5.0,
                    points_for=300.0,
                    clincher=CupTag.WILD_CARD if i == 3 else None,
                )
                for i, code in enumerate(ORDER[conference])
            ]
        )
        for conference in (EAST, WEST)
    }

    feed = build(group_pairs({}), conferences=conferences)

    east, west = feed.wild_card
    assert (east.conference, west.conference) == (EAST, WEST)
    assert [r.team.code for r in east.rows][:2] == ["BOS", "BKN"]
    assert [r.rank for r in east.rows] == list(range(1, 13))
    assert east.rows[0].group is not None and east.rows[0].group.letter == "A"
    assert east.rows[0].tag is CupTag.WILD_CARD and east.rows[1].tag is None
    assert east.rows[0].total is not None and east.rows[0].total.value == "+5"
    assert west.rows[0].team.code == "DEN"


def test_unscheduled_knockout_slots_carry_labels_rules_and_the_current_leaders() -> (
    None
):
    feed = build(group_pairs({(EAST, "A"): 2}))

    assert [s.id for s in feed.bracket] == list(SlotId)
    qf1 = slot(feed, SlotId.EAST_QF_1)
    assert (qf1.top.label.key.value, qf1.top.label.seed) == ("seed", 1)
    assert qf1.top.rule is SlotRule.BEST_GROUP_WINNER
    assert qf1.top.projected is not None
    assert (qf1.top.projected.team.code, qf1.top.projected.wins) == ("ATL", 3)
    assert qf1.bottom.label.key.value == "wild_card"
    assert qf1.bottom.rule is SlotRule.BEST_NON_WINNER
    assert qf1.bottom.projected is not None and qf1.bottom.projected.team.code == "BOS"
    qf2 = slot(feed, SlotId.WEST_QF_2)
    assert (qf2.top.label.seed, qf2.bottom.label.seed) == (2, 3)
    assert qf2.top.rule is SlotRule.SECOND_BEST_GROUP_WINNER
    assert qf2.bottom.rule is SlotRule.THIRD_BEST_GROUP_WINNER
    sf = slot(feed, SlotId.EAST_SF)
    assert (sf.top.label.quarterfinal, sf.bottom.label.quarterfinal) == (1, 2)
    assert sf.top.rule is SlotRule.QUARTERFINAL_WINNER
    assert not sf.top.known and sf.top.team is None and sf.top.projected is None
    final = slot(feed, SlotId.FINAL)
    assert final.conference is None
    assert [final.top.label.conference, final.bottom.label.conference] == [EAST, WEST]
    assert final.top.rule is SlotRule.SEMIFINAL_WINNER


def test_scheduled_knockout_games_replace_the_projections_and_match_by_seed() -> None:
    swapped = pair("qe1", CupRound.QUARTERFINALS, "BOS", "ATL", BASE + 20 * DAY)
    others = [p for p in knockouts(1, 0) if "BOS" not in p and "ATL" not in p]

    feed = build([*group_pairs(all_final()), swapped, *others])

    qf1, qf2 = slot(feed, SlotId.EAST_QF_1), slot(feed, SlotId.EAST_QF_2)
    assert qf1.game is not None and qf1.game.id == "qe1"
    assert qf1.top.team is not None and qf1.top.team.code == "ATL"
    assert qf1.bottom.team is not None and qf1.bottom.team.code == "BOS"
    assert qf1.top.projected is None and qf1.top.known
    assert qf2.game is not None and qf2.game.id == "qe2"
    assert qf2.top.team is not None and qf2.top.team.code == "CLE"
    assert slot(feed, SlotId.WEST_QF_1).game is not None
    assert slot(feed, SlotId.WEST_QF_2).game is not None


def test_semifinal_and_final_sides_know_the_winners_of_final_feeders() -> None:
    feed = build([*group_pairs(all_final()), *knockouts(2, 1)])

    east_sf = slot(feed, SlotId.EAST_SF)
    assert east_sf.game is not None and east_sf.game.id == "se"
    assert east_sf.top.known and east_sf.bottom.known
    assert east_sf.top.team is not None and east_sf.top.team.code == "ATL"
    final = slot(feed, SlotId.FINAL)
    assert final.game is None and not final.top.known and final.top.team is None


def test_known_sides_carry_their_standing_and_projected_or_empty_sides_have_none() -> (
    None
):
    feed = build([*group_pairs(all_final()), *knockouts(2, 1)])

    qf1 = slot(feed, SlotId.EAST_QF_1)
    assert qf1.top.standing is not None and qf1.bottom.standing is not None
    assert (qf1.top.standing.seed, qf1.top.standing.wins) == (1, 3)
    assert (qf1.bottom.standing.seed, qf1.bottom.standing.losses) == (4, 0)
    assert qf1.top.standing.group is not None
    assert qf1.top.standing.group.conference is EAST
    sf = slot(feed, SlotId.EAST_SF)
    assert sf.top.team is not None and sf.top.standing is not None
    assert sf.top.standing.seed == 1
    assert slot(feed, SlotId.FINAL).top.standing is None

    projected = build(group_pairs({(EAST, "A"): 2}))
    top = slot(projected, SlotId.EAST_QF_1).top
    assert top.projected is not None and top.standing is None


def test_a_team_below_the_fourth_row_has_a_null_seed() -> None:
    low = ORDER[EAST][6]
    row = next(r for r in sources().conference_tables[EAST].rows if r.code == low)
    assert row is not None
    pairs = [
        *group_pairs(all_final()),
        pair("qe1", CupRound.QUARTERFINALS, "ATL", low, BASE + 20 * DAY),
    ]

    feed = build(pairs)

    bottom = slot(feed, SlotId.EAST_QF_1).bottom
    assert bottom.standing is not None and bottom.standing.seed is None


def test_a_final_game_keeps_its_period_and_a_scheduled_game_has_none() -> None:
    swapped = [
        pair(
            "final",
            CupRound.CHAMPIONSHIP,
            "DAL",
            "ATL",
            BASE + 26 * DAY,
            scores=(100, 98),
            period=5,
        ),
        pair("se", CupRound.SEMIFINALS, "ATL", "CLE", BASE + 24 * DAY),
    ]
    base = [p for p in knockouts(3, 2) if "DAL" not in p or "ATL" not in p]
    base = [p for p in base if "CLE" not in p or "ATL" not in p]

    feed = build([*group_pairs(all_final()), *base, *swapped])

    final = slot(feed, SlotId.FINAL).game
    assert final is not None and final.period == 5
    scheduled = slot(feed, SlotId.EAST_SF).game
    assert scheduled is not None and scheduled.period is None


def test_two_quarterfinals_in_one_slot_fail_the_build() -> None:
    twin = pair("qe9", CupRound.QUARTERFINALS, "ATL", "BKN", BASE + 25 * DAY)

    with pytest.raises(CupBuildError, match="two games in the slot east-qf-1"):
        build([*group_pairs(all_final()), *knockouts(1, 0), twin])


def late_early_quarterfinals() -> list[Pair]:
    """East quarterfinals whose first-seed game starts after the other one."""
    late = pair("qe1", CupRound.QUARTERFINALS, "ATL", "BOS", BASE + 30 * DAY)
    early = pair("qe2", CupRound.QUARTERFINALS, "CLE", "NYK", BASE + 21 * DAY)
    west = [p for p in knockouts(1, 0) if "DAL" in p or "LAL" in p]
    return [late, early, *west]


def test_a_past_cup_places_the_quarterfinals_of_a_conference_by_start_time_with_null_seed_labels() -> (
    None
):
    pairs = [*group_pairs(all_final()), *late_early_quarterfinals()]

    present = build(pairs)
    past = build(pairs, past=True)

    assert slot(present, SlotId.EAST_QF_1).game.id == "qe1"  # type: ignore[union-attr]
    first, second = slot(past, SlotId.EAST_QF_1), slot(past, SlotId.EAST_QF_2)
    assert first.game is not None and first.game.id == "qe2"
    assert second.game is not None and second.game.id == "qe1"
    for side in (first.top, first.bottom, second.top, second.bottom):
        assert side.label.key.value == "seed" and side.label.seed is None
        assert side.known
    assert first.top.team is not None and first.top.team.code == "CLE"
    assert second.top.team is not None and second.top.team.code == "ATL"


def shared_seed_cup() -> list[Pair]:
    """East quarterfinals that both involve a top seed or the wild card: ATL (1)
    and BOS (wild card), with the semifinal between their winners."""
    east = [
        pair(
            "qeA",
            CupRound.QUARTERFINALS,
            "ATL",
            "NYK",
            BASE + 20 * DAY,
            scores=(100, 90),
        ),
        pair(
            "qeB",
            CupRound.QUARTERFINALS,
            "BOS",
            "CLE",
            BASE + 21 * DAY,
            scores=(100, 90),
        ),
        pair(
            "se", CupRound.SEMIFINALS, "ATL", "BOS", BASE + 26 * DAY, scores=(100, 90)
        ),
    ]
    replaced = {"qe1", "qe2", "se"}
    rest = [
        p for p in knockouts(3, 3) if next(iter(p.values())).game_id not in replaced
    ]
    return [*group_pairs(all_final()), *east, *rest]


def test_a_past_cup_whose_two_quarterfinals_share_a_seed_builds_as_complete_and_its_semifinal_links_both() -> (
    None
):
    pairs = shared_seed_cup()

    with pytest.raises(CupBuildError, match="two games in the slot"):
        build(pairs)
    feed = build(pairs, past=True)

    assert feed.stage is CupStage.COMPLETE
    semifinal = slot(feed, SlotId.EAST_SF)
    assert semifinal.top.known and semifinal.bottom.known
    assert semifinal.top.team is not None and semifinal.top.team.code == "ATL"
    assert semifinal.bottom.team is not None and semifinal.bottom.team.code == "BOS"
    assert semifinal.top.label.key.value == "quarterfinal_winner"


def test_a_past_conference_with_three_quarterfinals_fails() -> None:
    third = pair("qe9", CupRound.QUARTERFINALS, "BKN", "CHA", BASE + 25 * DAY)

    with pytest.raises(CupBuildError, match="two games in the slot east-qf-2"):
        build(
            [*group_pairs(all_final()), *late_early_quarterfinals(), third],
            past=True,
        )


def test_a_knockout_team_outside_the_draw_fails_the_build() -> None:
    with pytest.raises(CupBuildError, match="not in the draw"):
        build([*knockouts(1, 0)], drawn=False, rows=False)


def test_the_championship_is_outside_the_standings_and_the_last_rounds_are_neutral() -> (
    None
):
    feed = build([*group_pairs(all_final()), *knockouts(3, 0)])

    games = {g.stage: g for day in feed.games.days for g in day.games}
    assert (
        games[CupRound.GROUP].neutral_site,
        games[CupRound.GROUP].counts_in_standings,
    ) == (
        False,
        True,
    )
    assert games[CupRound.QUARTERFINALS].neutral_site is False
    assert games[CupRound.SEMIFINALS].neutral_site is True
    assert games[CupRound.CHAMPIONSHIP].neutral_site is True
    assert games[CupRound.CHAMPIONSHIP].counts_in_standings is False
    assert games[CupRound.SEMIFINALS].counts_in_standings is True


def test_a_game_seen_from_both_teams_is_listed_once_with_both_sides_names() -> None:
    feed = build(group_pairs({(EAST, "A"): 1}))

    games = [g for day in feed.games.days for g in day.games]
    assert len([g for g in games if g.id == "eastA0"]) == 1
    first = next(g for g in games if g.id == "eastA0")
    assert (first.home.code, first.away.code) == ("ATL", "BOS")
    assert (first.home.name, first.away.name) == ("Team ATL", "Team BOS")
    assert first.score == Score(away=90, home=100)
    assert first.winner is not None and first.winner.value == "home"
    assert first.status is GameStatus.FINAL and first.detail_available is False
    assert len(games) == 60


def test_a_team_no_schedule_shows_has_a_null_name() -> None:
    feed = build(rows=False)

    team = feed.groups[0].teams[0]
    assert (team.code, team.name, team.city) == ("ATL", None, None)


def test_stage_dates_are_the_first_and_last_eastern_dates_of_the_round() -> None:
    late = BASE + dt.timedelta(
        hours=5
    )  # 04:00 UTC: still the evening before in the East
    pairs = [
        pair("g1", CupRound.GROUP, "ATL", "BOS", late),
        pair("g2", CupRound.GROUP, "CLE", "DET", BASE + 9 * DAY),
    ]

    feed = build(pairs)

    assert feed.stages[0].first_date == dt.date(2026, 11, 3)
    assert feed.stages[0].last_date == dt.date(2026, 11, 12)
    assert (feed.stages[1].first_date, feed.stages[1].last_date) == (None, None)
    assert feed.first_game_date == dt.date(2026, 11, 3)


def test_stage_counts_and_games_by_day_in_start_order() -> None:
    feed = build([*group_pairs(all_final()), *knockouts(3, 0)])

    counts = feed.games.counts
    assert (counts.all, counts.group, counts.quarterfinals) == (67, 60, 4)
    assert (counts.semifinals, counts.championship) == (2, 1)
    dates = [day.date for day in feed.games.days]
    assert dates == sorted(dates)
    for day in feed.games.days:
        starts = [(g.start_time, g.id) for g in day.games]
        assert starts == sorted(starts)


def test_a_bad_streak_in_a_table_fails_the_build() -> None:
    tables = {key: group_table(codes, streak="X9") for key, codes in GROUPS.items()}

    with pytest.raises(CupBuildError, match="streak"):
        build(tables=tables)


def test_an_invalid_feed_fails_the_build_with_the_first_location() -> None:
    tables = {
        key: group_table(codes, games_behind="1.5") for key, codes in GROUPS.items()
    }
    tables[(EAST, "A")] = CupTable(
        rows=[cup_row(code, 1, 0, position=9) for code in GROUPS[(EAST, "A")]]
    )

    with pytest.raises(CupBuildError, match="invalid feed: 5 errors, first at groups"):
        build(tables=tables)


# Group 2: the kind


def scoreboard(game_id: str, cup: bool, final: bool = True) -> ScoreboardGame:
    data: dict[str, Any] = {
        "id": game_id,
        "away": GameTeam(code="BOS", name="Celtics", city="Boston"),
        "home": GameTeam(code="ATL", name="Hawks", city="Atlanta"),
        "status": GameStatus.FINAL if final else GameStatus.SCHEDULED,
        "start_time": NOW,
        "venue": "Arena",
        "cup": GameCup(stage=CupRound.GROUP) if cup else None,
    }
    if final:
        data["line_score"] = LineScore(away=[20, 20], home=[18, 20])
        data["score"] = Score(away=40, home=38)
    return ScoreboardGame.model_validate(data)


class FakeStars:
    def __init__(self) -> None:
        self.season: int | None = 2027

    def current_season(self) -> int | None:
        return self.season


class CupKit:
    """A games job, a feed cache and the Cup kind over one client and one clock,
    with fake adapters that count their calls."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.clock = [NOW]
        self.store = StateStore(path)
        self.store.migrate()
        self.settings = Settings(_env_file=None, data_dir=path)  # type: ignore[call-arg]
        self.client = create_client(self.store, clock=lambda: self.clock[0])
        self.calls: list[str] = []
        self.failing: set[str] = set()
        # The freshness each team schedule was read with.
        self.fresh: dict[str, Any] = {}
        self.through_cache = False
        self.table_changes: dict[str, Any] = {}
        self.pairs: list[Pair] = [*group_pairs(all_final())]
        self.scoreboard: dict[dt.date, list[ScoreboardGame]] = {}
        self.stars = FakeStars()
        self.cache = FeedCache(path, self.store, clock=lambda: self.clock[0])
        self.games = GamesJob(
            self.settings,
            self.store,
            self.client,
            fetch_games=self.fetch_games,
            fetch_game_detail=self.fetch_game_detail,
        )
        self.cup = CupFeeds(
            self.settings,
            self.store,
            self.client,
            self.cache,
            self.games,
            cast(StarsJob, self.stars),
            fetch_group_teams=self.fetch_group_teams,
            fetch_group_table=self.fetch_group_table,
            fetch_conference_table=self.fetch_conference_table,
            fetch_season_schedule=self.fetch_season_schedule,
        )

    def read(self, name: str) -> None:
        self.calls.append(name)
        if name in self.failing:
            raise SourceError("test", f"{name} is down")

    def called(self, prefix: str) -> int:
        return sum(1 for name in self.calls if name.startswith(prefix))

    async def fetch_games(
        self, client: SourceClient, day: dt.date, settings: Settings
    ) -> list[ScoreboardGame]:
        return list(self.scoreboard.get(day, []))

    async def fetch_game_detail(
        self, client: SourceClient, game_id: str, settings: Settings, fresh: Freshness
    ) -> GameDetail:
        raise SourceError("test", "no detail")

    async def fetch_group_teams(
        self,
        client: SourceClient,
        season: int,
        conference: Conference,
        letter: str,
        settings: Settings,
    ) -> list[str]:
        self.read(f"teams/{conference.value}{letter}/{season}")
        return list(GROUPS[(conference, letter)])

    async def fetch_group_table(
        self,
        client: SourceClient,
        season: int,
        conference: Conference,
        letter: str,
        settings: Settings,
    ) -> CupTable:
        self.read(f"table/{conference.value}{letter}")
        return group_table(GROUPS[(conference, letter)], **self.table_changes)

    async def fetch_conference_table(
        self,
        client: SourceClient,
        season: int,
        conference: Conference,
        settings: Settings,
    ) -> CupTable:
        self.read(f"conference/{conference.value}")
        return CupTable(rows=[cup_row(code, 1, 0) for code in ORDER[conference]])

    async def fetch_season_schedule(
        self,
        client: SourceClient,
        team: str,
        season: int,
        settings: Settings,
        *,
        playoffs: bool,
        fresh: Any = None,
    ) -> SeasonSchedule:
        self.fresh[team] = fresh
        self.read(f"schedule/{team}")
        if self.through_cache:
            # Read through the shared source cache: only a stale or missing
            # entry reaches the respx route.
            await get_json(client, f"{SCHEDULE_URL}{team}", source="test", fresh=fresh)
        return schedules_of(self.pairs).get(team, SeasonSchedule(games=[]))

    async def settle(self) -> None:
        while self.cache.in_flight:
            await next(iter(self.cache.in_flight.values()))
            await asyncio.sleep(0)
        await asyncio.sleep(0)

    async def run_games(self, at: dt.datetime) -> None:
        self.clock[0] = at
        await self.games.run(at)
        await self.settle()

    async def serve(self, at: dt.datetime | None = None) -> bytes:
        if at is not None:
            self.clock[0] = at
        body = await self.cache.serve(KIND, FEED_ID)
        await self.settle()
        return body

    def stored(self) -> CupFeed | None:
        body = read_by_id(self.path, KIND, FEED_ID)
        return None if body is None else CupFeed.model_validate_json(body)

    def last_build(self) -> dt.datetime | None:
        state = self.store.feed_build(KIND, FEED_ID)
        return None if state is None else state.last_build


@pytest.fixture(autouse=True)
def no_network() -> Iterator[None]:
    with respx.mock:
        yield


@pytest.fixture
def kit(tmp_path: Path) -> CupKit:
    return CupKit(tmp_path)


def a_game_id(kit: CupKit) -> str:
    stored = kit.stored()
    assert stored is not None
    return stored.games.days[0].games[0].id


@pytest.mark.anyio
async def test_an_id_other_than_league_answers_unknown_with_no_build(
    kit: CupKit, tmp_path: Path
) -> None:
    for feed_id in ("LEAGUE", "cup", ""):
        assert kit.cup.check(feed_id) is IdStatus.UNKNOWN
        with pytest.raises(UnknownFeedError):
            await kit.cache.serve(KIND, feed_id)

    assert kit.cup.check("league") is IdStatus.KNOWN
    assert kit.calls == []
    assert not (tmp_path / "feeds" / KIND).exists()


@pytest.mark.anyio
async def test_it_answers_not_ready_with_no_season_and_nothing_stored(
    kit: CupKit,
) -> None:
    kit.stars.season = None

    assert kit.cup.check(FEED_ID) is IdStatus.NOT_READY
    with pytest.raises(FeedUnavailableError):
        await kit.cache.serve(KIND, FEED_ID)
    assert kit.calls == []

    kit.stars.season = 2027
    await kit.serve()
    kit.stars.season = None

    assert kit.cup.check(FEED_ID) is IdStatus.KNOWN


@pytest.mark.anyio
async def test_no_feed_is_built_stored_or_fetched_without_a_request(
    kit: CupKit, tmp_path: Path
) -> None:
    await kit.settle()
    await kit.run_games(NOW + HOUR)

    assert kit.calls == []
    assert kit.stored() is None
    assert kit.store.feed_build_ids(KIND) == set()


@pytest.mark.anyio
async def test_a_request_builds_and_stores_the_feed_and_a_second_request_reads_storage(
    kit: CupKit,
) -> None:
    first = await kit.serve()
    calls = list(kit.calls)
    second = await kit.serve(NOW + 30 * SECOND)

    feed = CupFeed.model_validate_json(first)
    assert (feed.season, feed.stage) == ("2026-27", CupStage.GROUP)
    assert second == first
    assert kit.calls == calls
    assert (kit.path / "feeds" / KIND / "league.json").exists()
    assert kit.last_build() == NOW
    assert kit.called("teams/") == 6 and kit.called("table/") == 6
    assert kit.called("conference/") == 2 and kit.called("schedule/") == 30
    assert len(CODES) == 30 and len(GROUP_IDS) == 6


@pytest.mark.anyio
@pytest.mark.parametrize(
    "failing", ["teams/eastA/2027", "table/westC", "conference/east"]
)
async def test_a_failed_group_or_conference_read_answers_unavailable_and_is_not_retried_for_10_minutes(
    kit: CupKit, failing: str
) -> None:
    kit.failing.add(failing)

    with pytest.raises(FeedUnavailableError):
        await kit.serve()
    await kit.settle()
    attempts = kit.called(failing)
    kit.clock[0] = NOW + RETRY_AFTER - SECOND
    with pytest.raises(FeedUnavailableError):
        await kit.serve()

    assert kit.called(failing) == attempts == 1
    assert [f.feed_id for f in kit.store.failed_feed_builds()] == ["league"]
    assert kit.stored() is None
    kit.failing.clear()
    body = await kit.serve(NOW + RETRY_AFTER)
    assert CupFeed.model_validate_json(body).drawn


@pytest.mark.anyio
async def test_a_failed_rebuild_of_a_stale_feed_keeps_and_serves_the_stored_feed(
    kit: CupKit,
) -> None:
    first = await kit.serve()
    kit.failing.add("conference/west")

    body = await kit.serve(NOW + FEED_LIFETIME)
    await kit.settle()

    assert body == first
    assert kit.called("conference/west") == 2
    assert kit.stored() is not None
    assert kit.last_build() == NOW


def seed_schedules(kit: CupKit, age: dt.timedelta) -> None:
    """Route every schedule and cache each team's schedule `age` before NOW."""
    respx.get(url__startswith=SCHEDULE_URL).respond(json={})
    kit.through_cache = True
    for code in CODES:
        kit.store.set_source_entry(f"{SCHEDULE_URL}{code}", "{}", NOW - age)


def requested_teams() -> list[str]:
    return sorted(call.request.url.path.rsplit("/", 1)[1] for call in respx.calls)


@pytest.mark.anyio
async def test_a_schedule_cached_2_hours_ago_is_read_from_the_cache_except_for_a_team_playing_today(
    kit: CupKit,
) -> None:
    seed_schedules(kit, 2 * HOUR)
    kit.scoreboard[NOW.date()] = [scoreboard("today", cup=True, final=False)]
    await kit.run_games(NOW)

    await kit.serve()

    assert requested_teams() == ["ATL", "BOS"]
    assert kit.fresh["ATL"] == kit.fresh["BOS"] == HOUR
    assert kit.fresh["OKC"] == SCHEDULE_FRESH == dt.timedelta(hours=24)


@pytest.mark.anyio
async def test_before_the_games_job_runs_every_schedule_keeps_the_1_hour_freshness(
    kit: CupKit,
) -> None:
    seed_schedules(kit, 2 * HOUR)

    await kit.serve()

    assert requested_teams() == sorted(CODES)
    assert set(kit.fresh.values()) == {HOUR}


@pytest.mark.anyio
async def test_a_failed_schedule_is_skipped_when_every_drawn_team_still_has_4_group_games(
    kit: CupKit,
) -> None:
    kit.pairs = [*group_pairs({})]
    kit.failing.add("schedule/UTA")

    feed = CupFeed.model_validate_json(await kit.serve())

    assert len([g for day in feed.games.days for g in day.games]) == 60


@pytest.mark.anyio
async def test_a_failed_schedule_fails_the_build_when_the_championship_is_final(
    kit: CupKit,
) -> None:
    kit.pairs = [*group_pairs(all_final()), *knockouts(3, 3)]
    kit.failing.update({"schedule/DAL", "schedule/ATL"})

    with pytest.raises(FeedUnavailableError):
        await kit.serve()

    assert kit.stored() is None
    reasons = [f.last_failure_reason for f in kit.store.failed_feed_builds()]
    assert reasons == ["schedule/ATL is down"]


@pytest.mark.anyio
async def test_a_failed_schedule_fails_the_build_once_a_group_row_has_a_tag(
    kit: CupKit,
) -> None:
    kit.pairs = [*group_pairs({})]
    kit.table_changes = {"clincher": CupTag.WILD_CARD}
    kit.failing.add("schedule/UTA")

    with pytest.raises(FeedUnavailableError):
        await kit.serve()

    assert kit.stored() is None


@pytest.mark.anyio
async def test_a_failed_schedule_fails_the_build_when_a_drawn_team_loses_a_group_game(
    kit: CupKit,
) -> None:
    kit.failing.update({"schedule/ATL", "schedule/BOS"})

    with pytest.raises(FeedUnavailableError):
        await kit.serve()

    assert kit.stored() is None
    reasons = [f.last_failure_reason for f in kit.store.failed_feed_builds()]
    assert reasons == ["schedule/ATL is down"]


@pytest.mark.anyio
async def test_a_feed_is_fresh_before_a_final_cup_game_plus_1_hour_and_stale_at_it(
    kit: CupKit,
) -> None:
    await kit.serve()
    game_id = a_game_id(kit)
    kit.store.set_final_time(game_id, NOW.date(), NOW + 3 * HOUR)

    await kit.serve(NOW + 4 * HOUR - SECOND)
    assert kit.called("table/eastA") == 1
    await kit.serve(NOW + 4 * HOUR)

    assert kit.called("table/eastA") == 2


@pytest.mark.anyio
async def test_a_final_game_outside_the_cup_does_not_expire_the_feed(
    kit: CupKit,
) -> None:
    await kit.serve()
    kit.scoreboard[(NOW + 2 * HOUR).date()] = [scoreboard("other", cup=False)]
    await kit.run_games(NOW + 2 * HOUR)
    assert kit.games.final_games() != []

    await kit.serve(NOW + 4 * HOUR)

    assert kit.called("table/eastA") == 1


@pytest.mark.anyio
async def test_a_loaded_final_cup_game_expires_the_feed_one_hour_after_it(
    kit: CupKit,
) -> None:
    await kit.serve()
    kit.scoreboard[(NOW + 2 * HOUR).date()] = [scoreboard("loaded-cup", cup=True)]
    await kit.run_games(NOW + 2 * HOUR)

    await kit.serve(NOW + 3 * HOUR - SECOND)
    assert kit.called("table/eastA") == 1
    await kit.serve(NOW + 3 * HOUR)

    assert kit.called("table/eastA") == 2


@pytest.mark.anyio
async def test_a_feed_is_fresh_before_7_days_and_stale_at_7_days(kit: CupKit) -> None:
    await kit.serve()

    await kit.serve(NOW + FEED_LIFETIME - SECOND)
    assert kit.called("table/eastA") == 1
    await kit.serve(NOW + FEED_LIFETIME)

    assert kit.called("table/eastA") == 2


@pytest.mark.anyio
async def test_a_complete_feed_stays_fresh_past_7_days_and_after_later_final_cup_games(
    kit: CupKit,
) -> None:
    kit.pairs = [*group_pairs(all_final()), *knockouts(3, 3)]
    await kit.serve()
    stored = kit.stored()
    assert stored is not None and stored.stage is CupStage.COMPLETE
    kit.store.set_final_time("final", NOW.date(), NOW + 2 * HOUR)

    await kit.serve(NOW + FEED_LIFETIME + 30 * DAY)

    assert kit.called("table/eastA") == 1


@pytest.mark.anyio
async def test_a_complete_feed_is_stale_once_the_current_season_is_another(
    kit: CupKit,
) -> None:
    kit.pairs = [*group_pairs(all_final()), *knockouts(3, 3)]
    await kit.serve()
    kit.stars.season = 2028

    await kit.serve(NOW + FEED_LIFETIME)

    assert kit.called("table/eastA") == 2
    assert kit.called("teams/eastA/2028") == 1


@pytest.mark.anyio
async def test_detail_availability_is_set_when_served_from_the_loaded_games_and_not_stored(
    kit: CupKit,
) -> None:
    kit.pairs = [*group_pairs(all_final()), *knockouts(1, 0)]
    await kit.serve()
    kit.scoreboard[NOW.date()] = [scoreboard("qe1", cup=True, final=False)]
    await kit.run_games(NOW)

    body = await kit.serve(NOW + 30 * SECOND)

    served = CupFeed.model_validate_json(body)
    flags = {g.id: g.detail_available for d in served.games.days for g in d.games}
    assert flags["qe1"] is True and flags["qe2"] is False
    bracketed = slot(served, SlotId.EAST_QF_1).game
    assert bracketed is not None and bracketed.detail_available is True
    stored = kit.stored()
    assert stored is not None
    assert not any(g.detail_available for d in stored.games.days for g in d.games)


@pytest.mark.anyio
async def test_the_cleanup_keeps_league(kit: CupKit) -> None:
    await kit.serve()

    kit.cache.cleanup()

    assert kit.stored() is not None
    assert kit.store.feed_build_ids(KIND) == {FEED_ID}


@pytest.mark.anyio
async def test_the_kind_reads_the_stored_feed_and_none_when_missing_or_invalid(
    kit: CupKit,
) -> None:
    assert kit.cup.stored() is None

    await kit.serve()

    stored = kit.cup.stored()
    assert stored is not None and stored == kit.stored()
    (kit.path / "feeds" / KIND / "league.json").write_text("{not json", "utf-8")
    assert kit.cup.stored() is None
