# api/tests/jobs/test_cup_matchup_feed.py
#
# Tests for the Cup matchup feed builder and its feed kind.
#
# Tested:
# - The header: a final game with its score, winner and status, and a scheduled game with no score or winner
# - The sides: projected teams during group play, known teams not projected, and a side with no team that has only its label and rule
# - The path: every Cup game of the team by start time with the result and scores only when final
# - The injuries are the team's entries of the league injuries
# - The roster is ordered by number with the team feed fields and status, and the player card fields
# - The starters: the rank 1 player of each position, a player at two positions once, a missing position, an id off the roster and a failed depth chart
# - The leaders: the leader of each stat, every tied leader, no leader for a player without averages or a team without averages
# - The averages are rounded to one decimal and null without averages
# - The championship does not count in the standings
# - A non-numeric jersey and an invalid feed fail the build
# - The kind: an id outside the seven slots answers unknown with no read
# - The kind: it answers not ready with no season and nothing stored
# - The kind: no matchup is built, stored or fetched without a request
# - The kind: a request builds the Cup feed first and stores the matchup, and a second request reads storage
# - The kind: a side with no team reads no roster, schedule or injuries
# - The kind: a failed Cup feed, roster, injuries or schedule read, or a Cup feed of another season, fails the build and is not retried for 10 minutes
# - The kind: a failed rebuild keeps and serves the stored feed
# - The kind: a failed averages read builds with no averages and a failed depth chart read builds with no starter
# - The kind: fresh before a final game of either team plus 1 hour and stale at it, a final game of another team does not expire it
# - The kind: stale once the Cup feed is rebuilt after the build, and fresh before 7 days and stale at 7 days
# - The kind: detailAvailable is set when served from the loaded games and not stored
# - The kind: the cleanup keeps the seven slots
#
# What is covered:
# - Pure conversions: happy path, edges and errors; the built feed validates
# - Feed kind: success publishes a valid feed, failure keeps the last valid feed, expiry edges
#
# Fake adapters and a fake clock are passed to the builder and the kind, so no
# test uses a real source or the real clock.
#
# Run with: cd api && .venv/bin/python -m pytest tests/jobs/test_cup_matchup_feed.py
#
# SEE: api/app/jobs/cup_matchup_feed.py

import datetime as dt
from collections.abc import Iterator, Mapping, Sequence
from pathlib import Path
from typing import cast

import pytest
import respx

from app.feeds.cup import SlotId
from app.feeds.cup_matchup import CupMatchupFeed
from app.feeds.game_detail import GameResult, InjuryStatus
from app.feeds.games import CupRound, GameStatus
from app.jobs.cup_feed import FEED_ID as CUP_FEED_ID
from app.jobs.cup_feed import KIND as CUP_KIND
from app.jobs.cup_matchup_feed import (
    KIND,
    SLOT_IDS,
    CupMatchupFeeds,
    MatchupBuildError,
    MatchupSources,
    build_matchup_feed,
)
from app.jobs.on_demand import (
    RETRY_AFTER,
    FeedUnavailableError,
    IdStatus,
    UnknownFeedError,
)
from app.jobs.stars import StarsJob
from app.settings import Settings
from app.sources.depth_chart import DepthChart
from app.sources.http import SourceClient
from app.sources.league_injuries import LeagueInjuries
from app.sources.team_players import PlayerAverages, Roster
from app.sources.team_schedule import SeasonSchedule
from app.storage.feeds import read_by_id
from tests.jobs.test_cup_feed import (
    HOUR,
    NOW,
    SECOND,
    CupKit,
    Pair,
    all_final,
    group_pairs,
    knockouts,
    schedules_of,
    scoreboard,
    slot,
)
from tests.jobs.test_cup_feed import build as build_cup
from tests.jobs.test_team_feed import injuries, player, report, roster

DAY = dt.timedelta(days=1)

# Group 1: the builder


def averages(*rows: tuple[str, float, float, float]) -> list[PlayerAverages]:
    return [
        PlayerAverages(player_id=i, points=p, rebounds=r, assists=a)
        for i, p, r, a in rows
    ]


def chart(**positions: list[str]) -> DepthChart:
    return DepthChart.model_validate({"positions": positions})


def build(
    slot_id: SlotId = SlotId.EAST_QF_1,
    pairs: Sequence[Pair] | None = None,
    *,
    rosters: Mapping[str, Roster] | None = None,
    league: LeagueInjuries | None = None,
    team_averages: Mapping[str, Sequence[PlayerAverages] | None] | None = None,
    charts: Mapping[str, DepthChart | None] | None = None,
    schedules: Mapping[str, SeasonSchedule] | None = None,
    now: dt.datetime = NOW,
) -> CupMatchupFeed:
    played = [*group_pairs(all_final()), *knockouts(1, 1)] if pairs is None else pairs
    cup = build_cup(played)
    chosen = slot(cup, slot_id)
    codes = [
        side.team.code
        for side in (chosen.top, chosen.bottom)
        if side.team is not None and side.team.code is not None
    ] + [
        side.projected.team.code
        for side in (chosen.top, chosen.bottom)
        if side.projected is not None and side.projected.team.code is not None
    ]
    return build_matchup_feed(
        MatchupSources(
            season=cup.season,
            slot=chosen,
            rosters={code: roster() for code in codes} | dict(rosters or {}),
            schedules=schedules or schedules_of(played),
            injuries=league or injuries(),
            averages=team_averages or {},
            charts=charts or {},
        ),
        now=now,
    )


def test_a_final_game_fills_the_header_with_its_score_winner_and_status() -> None:
    feed = build()

    assert (feed.id, feed.round, feed.season) == (
        SlotId.EAST_QF_1,
        CupRound.QUARTERFINALS,
        "2026-27",
    )
    assert feed.game is not None
    assert feed.game.status is GameStatus.FINAL
    assert feed.game.score is not None
    assert (feed.game.score.home, feed.game.score.away) == (100, 90)
    assert feed.game.winner is not None and feed.game.winner.value == "home"
    cup_game = slot(build_cup([*group_pairs(all_final()), *knockouts(1, 1)]), feed.id)
    assert feed.game == cup_game.game


def test_a_scheduled_game_not_started_has_no_score_or_winner() -> None:
    feed = build(pairs=[*group_pairs(all_final()), *knockouts(1, 0)])

    assert feed.game is not None
    assert feed.game.status is GameStatus.SCHEDULED
    assert (feed.game.score, feed.game.winner) == (None, None)


def test_an_unscheduled_slot_in_group_play_has_projected_teams() -> None:
    feed = build(pairs=group_pairs({key: 3 for key in all_final()}))

    assert feed.game is None
    for side, code in ((feed.top, "ATL"), (feed.bottom, "BOS")):
        assert (side.known, side.projected) == (False, True)
        assert side.team is not None and side.team.code == code
        assert side.details is not None


def test_an_unscheduled_slot_with_known_teams_has_them_not_projected() -> None:
    feed = build(pairs=group_pairs(all_final()))

    assert feed.game is None
    for side in (feed.top, feed.bottom):
        assert (side.known, side.projected) == (True, False)
        assert side.details is not None


def test_a_side_with_no_team_has_only_its_label_and_rule() -> None:
    feed = build(SlotId.EAST_SF, group_pairs(all_final()))

    for side in (feed.top, feed.bottom):
        assert (side.known, side.projected) == (False, False)
        assert (side.team, side.details) == (None, None)
        assert side.label.key.value == "quarterfinal_winner"
        assert side.rule.value == "quarterfinal_winner"


def test_the_path_lists_every_cup_game_of_the_team_by_start_time_with_w_l_and_scores() -> (
    None
):
    pairs = [*group_pairs(all_final()), *knockouts(1, 0)]
    feed = build(pairs=pairs)

    assert feed.top.details is not None
    path = feed.top.details.path
    ids = [game.game_id for game in path]
    assert ids == ["eastA0", "eastA1", "eastA2", "eastA3", "qe1"]
    assert path == sorted(path, key=lambda game: game.start_time)
    first = path[0]
    assert first.stage is CupRound.GROUP and first.is_home is True
    assert first.status is GameStatus.FINAL
    assert (first.result, first.team_score, first.opponent_score) == (
        GameResult.WIN,
        100,
        90,
    )
    assert first.opponent.code == "BOS" and first.detail_available is False
    last = path[-1]
    assert last.stage is CupRound.QUARTERFINALS
    assert (last.status, last.result) == (GameStatus.SCHEDULED, None)
    assert (last.team_score, last.opponent_score) == (None, None)
    assert feed.bottom.details is not None
    away = feed.bottom.details.path[0]
    assert away.is_home is False
    assert (away.result, away.team_score, away.opponent_score) == (
        GameResult.LOSS,
        90,
        100,
    )


def test_the_path_leaves_out_games_that_are_not_in_the_cup() -> None:
    pairs = [*group_pairs(all_final()), *knockouts(1, 1)]
    pairs[0]["ATL"].note = "Regular season"
    feed = build(pairs=pairs)

    assert feed.top.details is not None
    assert "eastA0" not in [game.game_id for game in feed.top.details.path]


def test_injuries_are_the_teams_entries_of_the_league_injuries() -> None:
    league = injuries(
        ATL=[report("1", InjuryStatus.OUT, name="Hurt")],
        BOS=[report("9", InjuryStatus.PROBABLE, name="Other")],
    )

    feed = build(rosters={"ATL": roster(player("1", "7"))}, league=league)

    assert feed.top.details is not None and feed.bottom.details is not None
    assert [(i.player_id, i.name) for i in feed.top.details.injuries] == [("1", "Hurt")]
    assert feed.top.details.injuries[0].number == "7"
    assert [i.name for i in feed.bottom.details.injuries] == ["Other"]
    assert feed.top.details.roster[0].status == InjuryStatus.OUT


def test_the_roster_is_ordered_by_number_with_the_team_feed_fields_and_status() -> None:
    entries = (
        player("3", None),
        player("2", "10"),
        player("1", "2"),
    )

    feed = build(rosters={"ATL": roster(*entries)})

    assert feed.top.details is not None
    assert [p.id for p in feed.top.details.roster] == ["1", "2", "3"]
    assert [p.number for p in feed.top.details.roster] == ["2", "10", None]
    assert {p.status for p in feed.top.details.roster} == {"active"}


def test_the_player_card_fields_and_a_player_without_photo() -> None:
    late = dt.datetime(2026, 10, 9, 2, 0, tzinfo=dt.UTC)
    entries = (
        player("1", "2", birth_date=dt.date(2000, 10, 9)),
        player("2", "3", headshot_url=None),
    )

    feed = build(rosters={"ATL": roster(*entries)}, now=late)

    assert feed.top.details is not None
    card, bare = feed.top.details.roster
    assert card.age == 25 and card.birth_date == dt.date(2000, 10, 9)
    assert (card.height, card.weight) == ("6' 6\"", 195)
    assert card.birthplace == "Toronto, ON"
    assert (card.college, card.experience) == ("Kentucky", 9)
    assert str(card.photo_url) == "https://example.com/1.png"
    assert bare.photo_url is None


def test_marks_the_rank_one_player_of_each_of_the_five_positions() -> None:
    entries = tuple(player(str(i), str(i)) for i in range(1, 8))
    positions = chart(pg=["1", "7"], sg=["2"], sf=["3"], pf=["4", "1"], c=["5", "6"])

    feed = build(rosters={"ATL": roster(*entries)}, charts={"ATL": positions})

    assert feed.top.details is not None
    starters = {p.id for p in feed.top.details.roster if p.starter}
    assert starters == {"1", "2", "3", "4", "5"}


def test_marks_a_player_rank_one_in_two_positions_once() -> None:
    entries = tuple(player(str(i), str(i)) for i in range(1, 5))
    positions = chart(pg=["1"], sg=["1"], sf=["2"])

    feed = build(rosters={"ATL": roster(*entries)}, charts={"ATL": positions})

    assert feed.top.details is not None
    assert [p.id for p in feed.top.details.roster if p.starter] == ["1", "2"]


def test_a_missing_position_marks_no_one_in_its_place() -> None:
    entries = tuple(player(str(i), str(i)) for i in range(1, 5))
    positions = chart(pg=["1"], c=["2"])

    feed = build(rosters={"ATL": roster(*entries)}, charts={"ATL": positions})

    assert feed.top.details is not None
    assert [p.id for p in feed.top.details.roster if p.starter] == ["1", "2"]


def test_a_rank_one_id_off_the_roster_marks_no_one() -> None:
    entries = tuple(player(str(i), str(i)) for i in range(1, 4))
    positions = chart(pg=["99", "1"], sg=["2"])

    feed = build(rosters={"ATL": roster(*entries)}, charts={"ATL": positions})

    assert feed.top.details is not None
    assert [p.id for p in feed.top.details.roster if p.starter] == ["2"]


@pytest.mark.parametrize(
    "failed", [None, DepthChart(positions={})], ids=["failed", "empty"]
)
def test_a_failed_depth_chart_marks_no_starter(failed: DepthChart | None) -> None:
    feed = build(charts={"ATL": failed})

    assert feed.top.details is not None
    assert not any(p.starter for p in feed.top.details.roster)


def test_marks_the_leader_of_each_stat() -> None:
    entries = tuple(player(str(i), str(i)) for i in range(1, 4))
    rows = averages(("1", 25.0, 3.0, 2.0), ("2", 10.0, 11.0, 2.0), ("3", 9.0, 4.0, 8.0))

    feed = build(rosters={"ATL": roster(*entries)}, team_averages={"ATL": rows})

    assert feed.top.details is not None
    leaders = {p.id: p.leader for p in feed.top.details.roster}
    assert (leaders["1"].points, leaders["1"].rebounds, leaders["1"].assists) == (
        True,
        False,
        False,
    )
    assert leaders["2"].rebounds is True and leaders["2"].points is False
    assert leaders["3"].assists is True and leaders["3"].points is False


def test_marks_every_tied_leader() -> None:
    entries = tuple(player(str(i), str(i)) for i in range(1, 4))
    rows = averages(
        ("1", 20.04, 3.0, 2.0), ("2", 19.96, 3.0, 2.5), ("3", 5.0, 1.0, 2.0)
    )

    feed = build(rosters={"ATL": roster(*entries)}, team_averages={"ATL": rows})

    assert feed.top.details is not None
    leaders = {p.id: p.leader for p in feed.top.details.roster}
    assert leaders["1"].points and leaders["2"].points and not leaders["3"].points
    assert leaders["1"].rebounds and leaders["2"].rebounds


def test_a_player_with_null_averages_never_leads() -> None:
    entries = tuple(player(str(i), str(i)) for i in range(1, 3))
    rows = averages(("1", 0.0, 0.0, 0.0), ("77", 40.0, 40.0, 40.0))

    feed = build(rosters={"ATL": roster(*entries)}, team_averages={"ATL": rows})

    assert feed.top.details is not None
    one, two = feed.top.details.roster
    assert two.averages is None
    assert not (two.leader.points or two.leader.rebounds or two.leader.assists)
    assert one.leader.points and one.leader.rebounds and one.leader.assists


@pytest.mark.parametrize("found", [None, []], ids=["failed read", "empty"])
def test_a_team_with_no_averages_marks_no_leader(
    found: list[PlayerAverages] | None,
) -> None:
    feed = build(team_averages={"ATL": found})

    assert feed.top.details is not None
    for p in feed.top.details.roster:
        assert p.averages is None
        assert not (p.leader.points or p.leader.rebounds or p.leader.assists)


def test_averages_are_rounded_to_one_decimal_and_null_without_averages() -> None:
    entries = (player("1", "1"), player("2", "2"))
    rows = averages(("1", 20.149, 5.05, 3.96))

    feed = build(rosters={"ATL": roster(*entries)}, team_averages={"ATL": rows})

    assert feed.top.details is not None
    one, two = feed.top.details.roster
    assert one.averages is not None
    assert (one.averages.points, one.averages.rebounds, one.averages.assists) == (
        20.1,
        5.0,
        4.0,
    )
    assert two.averages is None


def test_the_championship_does_not_count_in_the_standings() -> None:
    feed = build(SlotId.FINAL, [*group_pairs(all_final()), *knockouts(3, 2)])

    assert feed.conference is None
    assert feed.game is not None
    assert feed.game.stage is CupRound.CHAMPIONSHIP
    assert feed.game.counts_in_standings is False


def test_a_non_numeric_jersey_fails_the_build() -> None:
    with pytest.raises(MatchupBuildError, match="jersey number 'x' is not a number"):
        build(rosters={"ATL": roster(player("1", "x"))})


def test_an_invalid_feed_fails_the_build_with_the_first_location() -> None:
    schedules = schedules_of([*group_pairs(all_final()), *knockouts(1, 1)])
    for view in schedules["ATL"].games:
        if view.game_id == "eastA0":
            view.team_score = None

    with pytest.raises(
        MatchupBuildError, match=r"invalid feed: 1 errors, first at top.details.path"
    ):
        build(schedules=schedules)


# Group 2: the kind

FEED_LIFETIME = dt.timedelta(days=7)
EAST_QF_1 = SlotId.EAST_QF_1.value


class MatchupKit(CupKit):
    """The Cup kit plus the matchup kind, with fake adapters that record their
    calls in self.calls and raise on the names in self.failing."""

    def __init__(self, path: Path) -> None:
        super().__init__(path)
        self.pairs = [*group_pairs(all_final()), *knockouts(1, 0)]
        self.rosters: dict[str, Roster] = {}
        self.averages: dict[str, list[PlayerAverages]] = {}
        self.charts: dict[str, DepthChart] = {}
        self.matchups = CupMatchupFeeds(
            self.settings,
            self.store,
            self.client,
            self.cache,
            self.games,
            cast(StarsJob, self.stars),
            self.cup,
            fetch_roster=self.fetch_roster,
            fetch_season_schedule=self.fetch_matchup_schedule,
            fetch_league_injuries=self.fetch_league_injuries,
            fetch_season_averages=self.fetch_season_averages,
            fetch_depth_chart=self.fetch_depth_chart,
        )

    def team_roster(self, code: str) -> Roster:
        found = self.rosters.get(code) or roster(
            player(f"{code}1", "1"), player(f"{code}2", "2")
        )
        return found.model_copy(update={"team_id": f"id-{code}"})

    async def fetch_roster(
        self, client: SourceClient, code: str, settings: Settings
    ) -> Roster:
        self.read(f"roster/{code}")
        return self.team_roster(code)

    async def fetch_matchup_schedule(
        self,
        client: SourceClient,
        code: str,
        season: int,
        settings: Settings,
        *,
        playoffs: bool,
    ) -> SeasonSchedule:
        self.read(f"m-schedule/{code}")
        return schedules_of(self.pairs).get(code, SeasonSchedule(games=[]))

    async def fetch_league_injuries(
        self, client: SourceClient, settings: Settings
    ) -> LeagueInjuries:
        self.read("injuries")
        return injuries(ATL=[report("ATL1", InjuryStatus.OUT, name="Hurt")])

    async def fetch_season_averages(
        self, client: SourceClient, team_id: str, season: int, settings: Settings
    ) -> list[PlayerAverages]:
        self.read(f"averages/{team_id}")
        return self.averages.get(team_id.removeprefix("id-"), [])

    async def fetch_depth_chart(
        self, client: SourceClient, code: str, season: int, settings: Settings
    ) -> DepthChart:
        self.read(f"chart/{code}")
        return self.charts.get(code, DepthChart(positions={}))

    async def matchup(
        self, slot_id: str = EAST_QF_1, at: dt.datetime | None = None
    ) -> bytes:
        if at is not None:
            self.clock[0] = at
        body = await self.cache.serve(KIND, slot_id)
        await self.settle()
        return body

    def stored_matchup(self, slot_id: str = EAST_QF_1) -> CupMatchupFeed | None:
        body = read_by_id(self.path, KIND, slot_id)
        return None if body is None else CupMatchupFeed.model_validate_json(body)

    def matchup_build(self, slot_id: str = EAST_QF_1) -> dt.datetime | None:
        state = self.store.feed_build(KIND, slot_id)
        return None if state is None else state.last_build


@pytest.fixture(autouse=True)
def no_network() -> Iterator[None]:
    with respx.mock:
        yield


@pytest.fixture
def kit(tmp_path: Path) -> MatchupKit:
    return MatchupKit(tmp_path)


@pytest.mark.anyio
@pytest.mark.parametrize("feed_id", ["east-qf-3", "league", "EAST-QF-1", ""])
async def test_the_kind_answers_unknown_for_an_id_outside_the_seven_slots_with_no_read(
    kit: MatchupKit, tmp_path: Path, feed_id: str
) -> None:
    assert kit.matchups.check(feed_id) is IdStatus.UNKNOWN
    with pytest.raises(UnknownFeedError):
        await kit.cache.serve(KIND, feed_id)

    assert all(kit.matchups.check(slot_id) is IdStatus.KNOWN for slot_id in SLOT_IDS)
    assert len(SLOT_IDS) == 7
    assert kit.calls == []
    assert not (tmp_path / "feeds" / KIND).exists()


@pytest.mark.anyio
async def test_the_kind_answers_not_ready_with_no_season_and_nothing_stored(
    kit: MatchupKit,
) -> None:
    kit.stars.season = None

    assert kit.matchups.check(EAST_QF_1) is IdStatus.NOT_READY
    with pytest.raises(FeedUnavailableError):
        await kit.cache.serve(KIND, EAST_QF_1)
    assert kit.calls == []

    kit.stars.season = 2027
    await kit.matchup()
    kit.stars.season = None

    assert kit.matchups.check(EAST_QF_1) is IdStatus.KNOWN


@pytest.mark.anyio
async def test_no_matchup_is_built_stored_or_fetched_without_a_request(
    kit: MatchupKit,
) -> None:
    await kit.settle()
    await kit.run_games(NOW + HOUR)

    assert kit.calls == []
    assert kit.stored_matchup() is None
    assert kit.store.feed_build_ids(KIND) == set()


@pytest.mark.anyio
async def test_a_request_builds_the_cup_feed_first_then_stores_the_matchup(
    kit: MatchupKit,
) -> None:
    assert kit.stored() is None

    body = await kit.matchup()

    feed = CupMatchupFeed.model_validate_json(body)
    assert (feed.id, feed.season) == (SlotId.EAST_QF_1, "2026-27")
    assert kit.stored() is not None
    assert (kit.path / "feeds" / KIND / f"{EAST_QF_1}.json").exists()
    assert kit.stored_matchup() == feed
    assert kit.matchup_build() == NOW
    assert kit.calls.index("injuries") > kit.calls.index("table/eastA")
    assert kit.called("roster/") == 2 and kit.called("m-schedule/") == 2
    assert kit.called("averages/") == 2 and kit.called("chart/") == 2
    assert kit.called("injuries") == 1


@pytest.mark.anyio
async def test_a_second_request_reads_storage(kit: MatchupKit) -> None:
    first = await kit.matchup()
    calls = list(kit.calls)

    second = await kit.matchup(at=NOW + 30 * SECOND)

    assert second == first
    assert kit.calls == calls


@pytest.mark.anyio
async def test_a_side_with_no_team_reads_no_roster_schedule_or_injuries(
    kit: MatchupKit,
) -> None:
    await kit.serve()
    kit.calls.clear()

    body = await kit.matchup(SlotId.EAST_SF.value)

    feed = CupMatchupFeed.model_validate_json(body)
    assert (feed.top.team, feed.bottom.team) == (None, None)
    assert kit.calls == []


@pytest.mark.anyio
async def test_a_failed_cup_feed_fails_the_build(kit: MatchupKit) -> None:
    kit.failing.add("conference/east")

    with pytest.raises(FeedUnavailableError):
        await kit.matchup()
    attempts = kit.called("conference/east")
    kit.clock[0] = NOW + RETRY_AFTER - SECOND
    with pytest.raises(FeedUnavailableError):
        await kit.matchup()

    assert kit.called("conference/east") == attempts == 1
    assert kit.called("roster/") == 0
    assert kit.stored_matchup() is None


@pytest.mark.anyio
@pytest.mark.parametrize("failing", ["roster/ATL", "injuries", "m-schedule/BOS"])
async def test_a_failed_read_fails_the_build_and_is_not_retried_for_10_minutes(
    kit: MatchupKit, failing: str
) -> None:
    kit.failing.add(failing)

    with pytest.raises(FeedUnavailableError):
        await kit.matchup()
    kit.clock[0] = NOW + RETRY_AFTER - SECOND
    with pytest.raises(FeedUnavailableError):
        await kit.matchup()

    assert kit.called(failing) == 1
    assert kit.stored_matchup() is None
    assert [f.feed_id for f in kit.store.failed_feed_builds()] == [EAST_QF_1]
    kit.failing.clear()
    body = await kit.matchup(at=NOW + RETRY_AFTER)
    assert CupMatchupFeed.model_validate_json(body).id is SlotId.EAST_QF_1


@pytest.mark.anyio
async def test_a_cup_feed_of_another_season_fails_the_build(kit: MatchupKit) -> None:
    await kit.serve()
    kit.stars.season = 2028

    with pytest.raises(FeedUnavailableError):
        await kit.matchup()

    reasons = [f.last_failure_reason for f in kit.store.failed_feed_builds()]
    assert reasons == ["unexpected error: MatchupBuildError"]
    assert kit.stored_matchup() is None


@pytest.mark.anyio
async def test_a_failed_rebuild_keeps_and_serves_the_stored_feed(
    kit: MatchupKit,
) -> None:
    first = await kit.matchup()
    kit.failing.add("roster/ATL")

    second = await kit.matchup(at=NOW + FEED_LIFETIME)

    assert second == first
    assert kit.called("roster/ATL") == 2
    assert kit.stored_matchup() == CupMatchupFeed.model_validate_json(first)


@pytest.mark.anyio
async def test_a_failed_averages_read_builds_with_null_averages_and_no_leader(
    kit: MatchupKit,
) -> None:
    kit.averages["ATL"] = averages(("ATL1", 20.0, 5.0, 4.0))
    kit.failing.add("averages/id-ATL")

    feed = CupMatchupFeed.model_validate_json(await kit.matchup())

    assert feed.top.details is not None
    for p in feed.top.details.roster:
        assert p.averages is None
        assert not (p.leader.points or p.leader.rebounds or p.leader.assists)


@pytest.mark.anyio
async def test_averages_and_the_depth_chart_mark_leaders_and_starters(
    kit: MatchupKit,
) -> None:
    kit.averages["ATL"] = averages(("ATL1", 20.0, 5.0, 4.0))
    kit.charts["ATL"] = chart(pg=["ATL2"])

    feed = CupMatchupFeed.model_validate_json(await kit.matchup())

    assert feed.top.details is not None
    one, two = feed.top.details.roster
    assert one.averages is not None and one.leader.points is True
    assert (one.starter, two.starter) == (False, True)


@pytest.mark.anyio
async def test_a_failed_depth_chart_read_builds_with_no_starter(
    kit: MatchupKit,
) -> None:
    kit.charts["ATL"] = chart(pg=["ATL1"])
    kit.failing.add("chart/ATL")

    feed = CupMatchupFeed.model_validate_json(await kit.matchup())

    assert feed.top.details is not None
    assert not any(p.starter for p in feed.top.details.roster)


@pytest.mark.anyio
async def test_fresh_before_a_final_game_of_either_team_plus_1_hour_and_stale_at_it(
    kit: MatchupKit,
) -> None:
    await kit.matchup()
    kit.scoreboard[(NOW + 2 * HOUR).date()] = [scoreboard("other", cup=False)]
    await kit.run_games(NOW + 2 * HOUR)

    await kit.matchup(at=NOW + 3 * HOUR - SECOND)
    assert kit.called("roster/ATL") == 1
    await kit.matchup(at=NOW + 3 * HOUR)

    assert kit.called("roster/ATL") == 2


@pytest.mark.anyio
async def test_a_final_game_of_another_team_does_not_expire_it(
    kit: MatchupKit,
) -> None:
    west = SlotId.WEST_QF_1.value
    await kit.matchup(west)
    kit.scoreboard[(NOW + 2 * HOUR).date()] = [scoreboard("other", cup=False)]
    await kit.run_games(NOW + 2 * HOUR)
    assert kit.games.final_games() != []

    await kit.matchup(west, at=NOW + 4 * HOUR)

    assert kit.called("roster/DAL") == 1


@pytest.mark.anyio
async def test_stale_once_the_cup_feed_is_rebuilt_after_the_build(
    kit: MatchupKit,
) -> None:
    await kit.matchup()
    kit.store.set_final_time("westA0", NOW.date(), NOW + 3 * HOUR)

    await kit.serve(NOW + 4 * HOUR - SECOND)
    await kit.matchup(at=NOW + 4 * HOUR - SECOND)
    assert kit.called("table/eastA") == 1 and kit.called("roster/ATL") == 1
    await kit.serve(NOW + 4 * HOUR)
    assert kit.called("table/eastA") == 2 and kit.called("roster/ATL") == 1
    await kit.matchup(at=NOW + 4 * HOUR + SECOND)

    assert kit.called("roster/ATL") == 2
    assert kit.matchup_build() == NOW + 4 * HOUR + SECOND


@pytest.mark.anyio
async def test_a_final_path_game_expires_it_one_hour_after_it(
    kit: MatchupKit,
) -> None:
    await kit.matchup()
    kit.store.set_final_time("eastA0", NOW.date(), NOW + 3 * HOUR)

    await kit.matchup(at=NOW + 4 * HOUR - SECOND)
    assert kit.called("roster/ATL") == 1
    await kit.matchup(at=NOW + 4 * HOUR)

    assert kit.called("roster/ATL") == 2


@pytest.mark.anyio
async def test_fresh_before_7_days_and_stale_at_7_days(kit: MatchupKit) -> None:
    await kit.matchup()

    await kit.matchup(at=NOW + FEED_LIFETIME - SECOND)
    assert kit.called("roster/ATL") == 1
    await kit.matchup(at=NOW + FEED_LIFETIME)

    assert kit.called("roster/ATL") == 2


@pytest.mark.anyio
async def test_detail_available_is_set_when_served_and_not_stored(
    kit: MatchupKit,
) -> None:
    await kit.matchup()
    kit.scoreboard[NOW.date()] = [scoreboard("qe1", cup=True, final=False)]
    await kit.run_games(NOW)

    body = await kit.matchup(at=NOW + 30 * SECOND)

    served = CupMatchupFeed.model_validate_json(body)
    assert served.game is not None and served.game.detail_available is True
    assert served.top.details is not None
    flags = {g.game_id: g.detail_available for g in served.top.details.path}
    assert flags["qe1"] is True and flags["eastA0"] is False
    stored = kit.stored_matchup()
    assert stored is not None and stored.top.details is not None
    assert stored.game is not None and stored.game.detail_available is False
    assert not any(g.detail_available for g in stored.top.details.path)


@pytest.mark.anyio
async def test_the_cleanup_keeps_the_seven_slots(kit: MatchupKit) -> None:
    for slot_id in sorted(SLOT_IDS):
        await kit.matchup(slot_id)

    kit.cache.cleanup()

    assert kit.store.feed_build_ids(KIND) == SLOT_IDS
    assert all(kit.stored_matchup(slot_id) is not None for slot_id in SLOT_IDS)
    assert kit.matchups.keep("east-qf-3") is False
    assert CUP_FEED_ID == "league" and CUP_KIND == "cup"
