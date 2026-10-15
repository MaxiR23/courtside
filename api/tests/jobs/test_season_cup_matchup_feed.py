# api/tests/jobs/test_season_cup_matchup_feed.py
#
# Tests for the Cup matchup feed builder of a past season and its feed kind.
#
# Tested:
# - The builder: each side has its team, not projected, the path of its Cup games in start order with results and scores, and empty injuries and roster
# - The builder: a side with no team has no details
# - The builder: an invalid feed fails with the first location
# - target: the current season maps to the current matchup feed, a past season to the season kind
# - The kind: an id outside the seven slots, a season outside 2024 to the season before the current one and an ill-formed id answer unknown with no read, and an unknown current season answers not ready
# - The kind: a request builds the season Cup first, then the matchup of each of the seven slots, reading only the two teams' season schedules by provider id first and no roster, injuries, averages or depth chart
# - The kind: the feed is kept: a second request, a request years later and a restart serve with no source call
# - The kind: a failed schedule read or a season Cup that cannot be built answers unavailable and stores nothing
# - The kind: the cleanup keeps it
#
# What is covered:
# - Pure conversions: happy path, an edge (a side with no team) and an error (invalid feed)
# - Feed kind: success publishes a valid feed, failure with nothing stored is unavailable, kept for good
#
# Fake adapters and a fake clock are passed to the builder and the kind, so no
# test uses a real source or the real clock.
#
# Run with: cd api && .venv/bin/python -m pytest tests/jobs/test_season_cup_matchup_feed.py
#
# SEE: api/app/jobs/season_cup_matchup_feed.py

import datetime as dt
from pathlib import Path

import pytest

from app.feeds.cup import SlotId
from app.feeds.cup_matchup import CupMatchupFeed
from app.feeds.games import CupRound, GameStatus
from app.jobs.cup_matchup_feed import KIND as CURRENT_KIND
from app.jobs.cup_matchup_feed import SLOT_IDS, MatchupBuildError
from app.jobs.on_demand import FeedUnavailableError, IdStatus, UnknownFeedError
from app.jobs.season_cup_feed import KIND as CUP_KIND
from app.jobs.season_cup_matchup_feed import (
    KIND,
    SeasonCupMatchupFeeds,
    build_past_matchup_feed,
)
from app.jobs.stars import StarsJob
from app.storage.feeds import read_by_id
from tests.jobs.test_cup_feed import (
    NOW,
    all_final,
    group_pairs,
    knockouts,
    schedules_of,
    slot,
)
from tests.jobs.test_cup_feed import build as build_cup
from tests.jobs.test_season_cup_feed import SeasonCupKit

YEARS = dt.timedelta(days=365 * 5)
EAST_QF_1 = SlotId.EAST_QF_1.value


def build(slot_id: SlotId = SlotId.EAST_QF_1, finals: int = 1) -> CupMatchupFeed:
    played = [*group_pairs(all_final()), *knockouts(1, finals)]
    cup = build_cup(played)
    return build_past_matchup_feed(cup.season, slot(cup, slot_id), schedules_of(played))


def test_each_side_has_its_team_and_path_with_empty_injuries_and_roster() -> None:
    feed = build()

    assert (feed.id, feed.round, feed.season) == (
        SlotId.EAST_QF_1,
        CupRound.QUARTERFINALS,
        "2026-27",
    )
    for side, code, result in ((feed.top, "ATL", "win"), (feed.bottom, "BOS", "loss")):
        assert side.team is not None and side.team.code == code
        assert side.projected is False
        assert side.details is not None
        assert (side.details.injuries, side.details.roster) == ([], [])
        starts = [game.start_time for game in side.details.path]
        assert starts == sorted(starts) and len(starts) == 5
        last = side.details.path[-1]
        assert last.stage is CupRound.QUARTERFINALS
        assert last.status is GameStatus.FINAL
        assert last.result is not None and last.result.value == result
        assert last.detail_available is False
    assert feed.game is not None and feed.game.status is GameStatus.FINAL


def test_a_side_with_no_team_has_no_details() -> None:
    played = group_pairs(all_final())
    cup = build_cup(played)

    feed = build_past_matchup_feed(
        cup.season, slot(cup, SlotId.EAST_SF), schedules_of(played)
    )

    assert feed.top.team is None and feed.top.details is None
    assert feed.bottom.team is None and feed.bottom.details is None


def test_an_invalid_feed_fails_with_the_first_location() -> None:
    played = [*group_pairs(all_final()), *knockouts(1, 1)]
    cup = build_cup(played)

    with pytest.raises(MatchupBuildError, match="invalid feed: .* first at season"):
        build_past_matchup_feed("", slot(cup, SlotId.EAST_QF_1), schedules_of(played))


class SeasonMatchupKit(SeasonCupKit):
    def register(self) -> None:
        super().register()
        self.season_matchups = SeasonCupMatchupFeeds(
            self.settings,
            self.store,
            self.client,
            self.cache,
            self.stars_job,
            self.season_cups,
            fetch_season_schedule=self.fetch_past_schedule,
        )

    @property
    def stars_job(self) -> StarsJob:
        return self.stars  # type: ignore[return-value]

    async def serve_slot(
        self, feed_id: str = f"2025-{EAST_QF_1}", at: dt.datetime | None = None
    ) -> bytes:
        if at is not None:
            self.clock[0] = at
        body = await self.cache.serve(KIND, feed_id)
        await self.settle()
        return body


@pytest.fixture
def kit(tmp_path: Path) -> SeasonMatchupKit:
    return SeasonMatchupKit(tmp_path)


def test_the_current_season_maps_to_the_current_matchup_feed(
    kit: SeasonMatchupKit,
) -> None:
    assert kit.season_matchups.target("2027", EAST_QF_1) == (CURRENT_KIND, EAST_QF_1)
    assert kit.season_matchups.target("2025", EAST_QF_1) == (
        KIND,
        "2025-east-qf-1",
    )


@pytest.mark.anyio
@pytest.mark.parametrize(
    "feed_id",
    [
        "2025-east-qf-3",
        "2025-league",
        "2025-EAST-QF-1",
        "2025-east-qf-1\n",
        "2023-east-qf-1",
        "2027-east-qf-1",
        "abc",
        "",
    ],
)
async def test_an_invalid_id_answers_unknown_with_no_read(
    kit: SeasonMatchupKit, feed_id: str
) -> None:
    assert kit.season_matchups.check(feed_id) is IdStatus.UNKNOWN
    with pytest.raises(UnknownFeedError):
        await kit.cache.serve(KIND, feed_id)

    assert kit.calls == []


@pytest.mark.anyio
async def test_an_unknown_current_season_answers_not_ready_with_no_read(
    kit: SeasonMatchupKit,
) -> None:
    kit.stars.season = None

    assert kit.season_matchups.check(f"2025-{EAST_QF_1}") is IdStatus.NOT_READY
    with pytest.raises(FeedUnavailableError):
        await kit.cache.serve(KIND, f"2025-{EAST_QF_1}")

    assert kit.calls == []


@pytest.mark.anyio
async def test_a_request_builds_the_season_cup_then_each_slot_reading_only_schedules(
    kit: SeasonMatchupKit,
) -> None:
    body = await kit.serve_slot()

    feed = CupMatchupFeed.model_validate_json(body)
    assert (feed.id, feed.season) == (SlotId.EAST_QF_1, "2024-25")
    assert read_by_id(kit.path, CUP_KIND, "2025") is not None
    assert read_by_id(kit.path, KIND, f"2025-{EAST_QF_1}") == body
    assert kit.stored() is None

    before = len(kit.calls)
    for slot_id in sorted(SLOT_IDS):
        feed_id = f"2025-{slot_id}"
        slot_feed = CupMatchupFeed.model_validate_json(await kit.serve_slot(feed_id))
        assert slot_feed.id.value == slot_id
        assert read_by_id(kit.path, KIND, feed_id) is not None

    extra = kit.calls[before:]
    assert extra and all(name.startswith("p-schedule/") for name in extra)
    assert all(name.endswith("/2025/True") for name in extra)
    for prefix in ("roster/", "injuries", "averages/", "chart/", "m-schedule/"):
        assert kit.called(prefix) == 0


@pytest.mark.anyio
async def test_a_stored_feed_is_never_rebuilt_even_years_later_or_after_a_restart(
    kit: SeasonMatchupKit,
) -> None:
    first = await kit.serve_slot()
    calls = list(kit.calls)
    second = await kit.serve_slot()
    later = await kit.serve_slot(at=NOW + YEARS)
    kit.start()
    restarted = await kit.serve_slot(at=NOW + 2 * YEARS)

    assert first == second == later == restarted
    assert kit.calls == calls


@pytest.mark.anyio
async def test_a_failed_schedule_read_answers_unavailable_and_stores_nothing(
    kit: SeasonMatchupKit,
) -> None:
    await kit.serve_season("2025")
    kit.failing = {"p-schedule/ATL/2025/True"}

    with pytest.raises(FeedUnavailableError):
        await kit.serve_slot()

    assert read_by_id(kit.path, KIND, f"2025-{EAST_QF_1}") is None


@pytest.mark.anyio
async def test_a_season_cup_that_cannot_be_built_answers_unavailable(
    kit: SeasonMatchupKit,
) -> None:
    kit.pairs = [*group_pairs(all_final()), *knockouts(2, 2)]

    with pytest.raises(FeedUnavailableError):
        await kit.serve_slot()

    assert read_by_id(kit.path, CUP_KIND, "2025") is None
    assert read_by_id(kit.path, KIND, f"2025-{EAST_QF_1}") is None


@pytest.mark.anyio
async def test_the_cleanup_keeps_the_feed(kit: SeasonMatchupKit) -> None:
    body = await kit.serve_slot()

    kit.cache.cleanup()

    assert read_by_id(kit.path, KIND, f"2025-{EAST_QF_1}") == body
