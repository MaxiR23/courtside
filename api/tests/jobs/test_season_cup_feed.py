# api/tests/jobs/test_season_cup_feed.py
#
# Tests for the Cup feed of a past season and its feed kind.
#
# Tested:
# - past_cup_season_status: 2023, 1994, abc, 02025, 2025 with a trailing newline, the current season and a future season are unknown; 2024 and the season before the current one are known; an unknown current season is not ready for a well-formed id from 2024 and a season before 2024 stays unknown
# - target: the current season maps to the current Cup feed, a past season to the season kind, and an unknown current season to the season kind
# - The kind: a past season builds a valid complete feed with the champion and the bracket scores, reading the sources with the season and the schedules by provider id first
# - The kind: season 2024 with In-Season Tournament notes (group play included, every group game counted) and two quarterfinals sharing a seed builds as complete, the quarterfinals placed by start time (ADR 0053)
# - The kind: the built feed carries the current build version, a stored feed of an older or missing version is rebuilt on its next request, and one of the current version is served with no source request (ADR 0053)
# - The kind: the feed is stored under season-cup and rebuilt only for another version: a second request, a request years later and a restart all serve with no source call
# - The kind: the league sides are named from the names the schedules give the teams with the season code and the historical flag, and name_sides is never called (ADR 0054, ADR 0058)
# - The kind: the build declares 44 reads and sends no calendar, scoreboard day or game detail request (ADR 0058)
# - The kind: building it writes nothing under the current Cup feed
# - The kind: a Cup that is not complete answers unavailable and stores nothing
# - The kind: a failed read with nothing stored answers unavailable
# - The kind: an invalid id answers unknown and a not ready season answers unavailable, with no source request
# - The kind: detailAvailable is false
# - The kind: the cleanup keeps it
# - The current feed carries the stored previous champion as the defending champion, builds a missing previous feed first and stores it, and builds with a null one when there is no previous Cup or the previous build fails (retried only after 10 minutes)
# - A past feed carries the champion of the stored feed of the season before with no read, and null when it is not stored or for the first Cup
# - previous_cup names the season before from the second Cup
#
# What is covered:
# - Pure status logic: happy path, edges and errors
# - Feed kind: success publishes a valid feed, failure with nothing stored is unavailable, kept for good
#
# Fake adapters and a fake clock are passed to the kind, so no test uses a real
# source or the real clock.
#
# Run with: cd api && .venv/bin/python -m pytest tests/jobs/test_season_cup_feed.py
#
# SEE: api/app/jobs/season_cup_feed.py

import datetime as dt
import json
from collections.abc import Iterator
from pathlib import Path
from typing import cast

import pytest
import respx

from app.feeds.cup import CupFeed, CupStage, StageStatus
from app.feeds.game_detail import Conference
from app.feeds.games import CupRound
from app.jobs.cup_feed import CODES
from app.jobs.cup_feed import FEED_ID as CUP_FEED_ID
from app.jobs.cup_feed import KIND as CUP_KIND
from app.jobs.on_demand import (
    SEASON_BUILD_VERSION,
    FeedCache,
    FeedUnavailableError,
    IdStatus,
    UnknownFeedError,
)
from app.jobs.season_cup_feed import (
    KIND,
    READ_BUDGET,
    SeasonCupFeeds,
    past_cup_season_status,
)
from app.jobs.stars import StarsJob
from app.jobs.team_names import TeamNamesFeeds
from app.settings import Settings
from app.sources.cup import CupTable
from app.sources.http import SourceClient
from app.sources.team_schedule import ScheduledGame, SeasonSchedule
from app.sources.teams import SeasonTeamName
from app.storage.feeds import publish_by_id, read_by_id
from tests.jobs.fake_season_teams import FakeSeasonTeams, league_sides
from tests.jobs.test_cup_feed import (
    NOW,
    all_final,
    group_pairs,
    knockouts,
    schedules_of,
    shared_seed_cup,
)
from tests.jobs.test_cup_matchup_feed import MatchupKit

YEARS = dt.timedelta(days=365 * 5)


@pytest.mark.parametrize(
    "text", ["2023", "1994", "abc", "02025", "2025\n", "", "2027", "2028"]
)
def test_an_ill_formed_early_current_or_future_season_is_unknown(text: str) -> None:
    assert past_cup_season_status(text, 2027) is IdStatus.UNKNOWN


def test_the_first_cup_season_and_the_season_before_the_current_one_are_known() -> None:
    assert past_cup_season_status("2024", 2027) is IdStatus.KNOWN
    assert past_cup_season_status("2026", 2027) is IdStatus.KNOWN


def test_an_unknown_current_season_is_not_ready_from_the_first_cup_season() -> None:
    assert past_cup_season_status("2025", None) is IdStatus.NOT_READY
    assert past_cup_season_status("2023", None) is IdStatus.UNKNOWN
    assert past_cup_season_status("abc", None) is IdStatus.UNKNOWN


class SeasonCupKit(MatchupKit):
    """The matchup kit plus the past season Cup kind, with fake adapters that
    record their calls in self.calls."""

    def __init__(self, path: Path) -> None:
        super().__init__(path)
        self.pairs = [*group_pairs(all_final()), *knockouts(3, 3)]
        self.seasons: list[int] = []
        self.past_flags: list[bool] = []
        self.season_teams = FakeSeasonTeams()
        # The names every schedule payload gives the teams it holds.
        self.payload_names: dict[str, SeasonTeamName] = {}
        self.register()

    def register(self) -> None:
        self.team_names = TeamNamesFeeds(
            self.settings,
            self.store,
            self.client,
            self.cache,
            cast(StarsJob, self.stars),
            fetch_season_team=self.season_teams.fetch,
        )
        self.season_cups = SeasonCupFeeds(
            self.settings,
            self.store,
            self.client,
            self.cache,
            cast(StarsJob, self.stars),
            self.team_names,
            fetch_group_teams=self.fetch_group_teams,
            fetch_group_table=self.fetch_past_table,
            fetch_conference_table=self.fetch_past_conference,
            fetch_season_schedule=self.fetch_past_schedule,
        )
        self.previous.target = self.season_cups

    def start(self) -> None:
        """A new cache and kind over the same data directory: a restart."""
        self.cache = FeedCache(self.path, self.store, clock=lambda: self.clock[0])
        self.register()

    async def fetch_past_table(
        self,
        client: SourceClient,
        season: int,
        conference: Conference,
        letter: str,
        settings: Settings,
    ) -> CupTable:
        self.seasons.append(season)
        return await self.fetch_group_table(
            client, season, conference, letter, settings
        )

    async def fetch_past_conference(
        self,
        client: SourceClient,
        season: int,
        conference: Conference,
        settings: Settings,
    ) -> CupTable:
        self.seasons.append(season)
        return await self.fetch_conference_table(client, season, conference, settings)

    async def fetch_past_schedule(
        self,
        client: SourceClient,
        team: str,
        season: int,
        settings: Settings,
        *,
        playoffs: bool,
        by_id_first: bool = False,
    ) -> SeasonSchedule:
        self.read(f"p-schedule/{team}/{season}/{by_id_first}")
        self.past_flags.append(by_id_first)
        found = schedules_of(self.pairs).get(team, SeasonSchedule(games=[]))
        return found.model_copy(update={"teams": dict(self.payload_names)})

    async def serve_season(self, season: str, at: dt.datetime | None = None) -> bytes:
        if at is not None:
            self.clock[0] = at
        body = await self.cache.serve(KIND, season)
        await self.settle()
        return body


@pytest.fixture(autouse=True)
def no_network() -> Iterator[None]:
    with respx.mock:
        yield


@pytest.fixture
def kit(tmp_path: Path) -> SeasonCupKit:
    return SeasonCupKit(tmp_path)


def test_the_current_season_maps_to_the_current_cup_feed(kit: SeasonCupKit) -> None:
    assert kit.season_cups.target("2027") == (CUP_KIND, CUP_FEED_ID)
    assert kit.season_cups.target("2025") == (KIND, "2025")
    assert kit.season_cups.target("abc") == (KIND, "abc")


def test_an_unknown_current_season_maps_to_the_season_kind(kit: SeasonCupKit) -> None:
    kit.stars.season = None

    assert kit.season_cups.target("2027") == (KIND, "2027")


@pytest.mark.anyio
async def test_a_past_season_builds_a_valid_complete_feed_from_the_season_sources(
    kit: SeasonCupKit,
) -> None:
    body = await kit.serve_season("2025")

    feed = CupFeed.model_validate_json(body)
    assert feed.season == "2024-25"
    assert feed.stage is CupStage.COMPLETE
    assert feed.champion is not None and feed.champion.code == "DAL"
    final = next(slot for slot in feed.bracket if slot.id.value == "final")
    assert final.game is not None and final.game.score is not None
    assert (final.game.score.home, final.game.score.away) == (100, 90)
    assert len(feed.groups) == 6 and all(group.rows for group in feed.groups)
    assert set(kit.seasons) == {2025}
    assert kit.called("teams/") == 6 and all(
        name.endswith("/2025") for name in kit.calls if name.startswith("teams/")
    )
    assert kit.called("p-schedule/") == 30
    assert kit.past_flags and all(kit.past_flags)
    assert kit.called("schedule/") == 0


@pytest.mark.anyio
async def test_the_league_sides_are_named_from_the_schedule_payloads_and_name_sides_is_never_called(
    kit: SeasonCupKit,
) -> None:
    kit.payload_names = {
        code: SeasonTeamName(
            abbreviation="SEA", name="Harbor Gulls", location="Seattle"
        )
        for code in CODES
    }

    async def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("name_sides must not be called")

    kit.team_names.name_sides = forbidden  # type: ignore[method-assign,assignment]

    body = await kit.serve_season("2025")

    sides = league_sides(json.loads(body))
    assert sides
    for side in sides:
        assert (side["name"], side["city"]) == ("Harbor Gulls", "Seattle")
        assert (side["seasonCode"], side["historical"]) == ("SEA", False)


@pytest.mark.anyio
async def test_the_build_declares_44_reads_and_sends_no_calendar_day_or_detail_request(
    kit: SeasonCupKit,
) -> None:
    await kit.serve_season("2025")

    assert READ_BUDGET == 44
    assert kit.called("p-schedule/") + kit.called("teams/") + len(kit.seasons) <= (
        READ_BUDGET
    )
    assert not any(
        name.startswith(("calendar/", "day/", "detail/")) for name in kit.calls
    )


@pytest.mark.anyio
async def test_a_stored_feed_is_never_rebuilt_even_years_later_or_after_a_restart(
    kit: SeasonCupKit,
) -> None:
    first = await kit.serve_season("2025")
    calls = list(kit.calls)
    second = await kit.serve_season("2025")
    later = await kit.serve_season("2025", NOW + YEARS)
    kit.start()
    restarted = await kit.serve_season("2025", NOW + 2 * YEARS)

    assert first == second == later == restarted
    assert kit.calls == calls
    assert read_by_id(kit.path, KIND, "2025") == first


@pytest.mark.anyio
async def test_building_a_past_cup_writes_nothing_under_the_current_cup_feed(
    kit: SeasonCupKit,
) -> None:
    await kit.serve_season("2025")

    assert kit.stored() is None
    assert not (kit.path / "feeds" / CUP_KIND).exists()
    assert kit.store.feed_build_ids(CUP_KIND) == set()


@pytest.mark.anyio
async def test_a_cup_that_is_not_complete_answers_unavailable_and_stores_nothing(
    kit: SeasonCupKit,
) -> None:
    kit.pairs = [*group_pairs(all_final()), *knockouts(2, 2)]

    with pytest.raises(FeedUnavailableError):
        await kit.serve_season("2025")

    assert read_by_id(kit.path, KIND, "2025") is None


@pytest.mark.anyio
async def test_a_failed_read_with_nothing_stored_answers_unavailable(
    kit: SeasonCupKit,
) -> None:
    kit.failing = {"teams/eastA/2025"}

    with pytest.raises(FeedUnavailableError):
        await kit.serve_season("2025")

    assert read_by_id(kit.path, KIND, "2025") is None


@pytest.mark.anyio
@pytest.mark.parametrize("season", ["2023", "1994", "2027", "2028", "abc", "2025\n"])
async def test_an_invalid_id_answers_unknown_with_no_source_request(
    kit: SeasonCupKit, season: str
) -> None:
    with pytest.raises(UnknownFeedError):
        await kit.cache.serve(KIND, season)

    assert kit.calls == []


@pytest.mark.anyio
async def test_an_unknown_current_season_answers_unavailable_with_no_source_request(
    kit: SeasonCupKit,
) -> None:
    kit.stars.season = None

    with pytest.raises(FeedUnavailableError):
        await kit.cache.serve(KIND, "2025")

    assert kit.calls == []


@pytest.mark.anyio
async def test_detail_is_never_available(kit: SeasonCupKit) -> None:
    feed = CupFeed.model_validate_json(await kit.serve_season("2025"))

    assert all(
        game.detail_available is False for d in feed.games.days for game in d.games
    )
    assert all(
        slot.game is None or slot.game.detail_available is False
        for slot in feed.bracket
    )


@pytest.mark.anyio
async def test_the_cleanup_keeps_the_feed(kit: SeasonCupKit) -> None:
    body = await kit.serve_season("2025")

    kit.cache.cleanup()

    assert read_by_id(kit.path, KIND, "2025") == body


IN_SEASON_NOTES = {
    "NBA Cup - Group Play": "NBA In-Season Tournament - Group Play",
    "NBA Cup - Quarterfinals": "NBA In-Season Tournament - Quarterfinals",
    "NBA Cup - Semifinals": "NBA In-Season Tournament - Semifinals",
    "NBA Cup Championship": "NBA In-Season Tournament Championship",
}


def in_season_tournament(
    pairs: list[dict[str, ScheduledGame]],
) -> list[dict[str, ScheduledGame]]:
    return [
        {
            code: view.model_copy(
                update={"note": IN_SEASON_NOTES.get(view.note or "", view.note)}
            )
            for code, view in views.items()
        }
        for views in pairs
    ]


@pytest.mark.anyio
async def test_season_2024_with_in_season_tournament_notes_builds_as_complete(
    kit: SeasonCupKit,
) -> None:
    kit.pairs = in_season_tournament(shared_seed_cup())

    feed = CupFeed.model_validate_json(await kit.serve_season("2024"))

    assert feed.season == "2023-24"
    assert feed.stage is CupStage.COMPLETE
    qf1 = next(s for s in feed.bracket if s.id.value == "east-qf-1")
    qf2 = next(s for s in feed.bracket if s.id.value == "east-qf-2")
    assert qf1.game is not None and qf1.game.id == "qeA"
    assert qf2.game is not None and qf2.game.id == "qeB"
    assert qf1.top.label.seed is None
    group_stage = next(e for e in feed.stages if e.stage is CupRound.GROUP)
    assert group_stage.status is StageStatus.COMPLETE


@pytest.mark.anyio
async def test_the_built_feed_carries_the_current_build_version(
    kit: SeasonCupKit,
) -> None:
    feed = CupFeed.model_validate_json(await kit.serve_season("2025"))

    assert feed.build_version == SEASON_BUILD_VERSION


@pytest.mark.anyio
@pytest.mark.parametrize("version", [None, SEASON_BUILD_VERSION + 1])
async def test_a_stored_feed_with_an_older_or_missing_version_is_rebuilt_on_its_next_request(
    kit: SeasonCupKit, version: int | None
) -> None:
    await kit.serve_season("2025")
    stored = CupFeed.model_validate_json(read_by_id(kit.path, KIND, "2025") or b"")
    publish_by_id(
        kit.path,
        KIND,
        CupFeed,
        "2025",
        stored.model_copy(update={"build_version": version}),
    )
    kit.calls.clear()

    served = CupFeed.model_validate_json(await kit.serve_season("2025", NOW + YEARS))

    assert served.build_version == version
    assert kit.called("teams/") == 6
    rebuilt = CupFeed.model_validate_json(read_by_id(kit.path, KIND, "2025") or b"")
    assert rebuilt.build_version == SEASON_BUILD_VERSION


@pytest.mark.anyio
async def test_a_stored_feed_with_the_current_version_is_served_with_no_source_request(
    kit: SeasonCupKit,
) -> None:
    await kit.serve_season("2025")
    kit.calls.clear()

    await kit.serve_season("2025", NOW + YEARS)

    assert kit.calls == []


HARBOR = SeasonTeamName(abbreviation="DAL", name="Harbor Gulls", location="Seattle")


def champion_of(body: bytes, key: str) -> dict[str, object]:
    found = json.loads(body)[key]
    assert isinstance(found, dict)
    return found


@pytest.mark.anyio
async def test_the_current_feed_carries_the_stored_previous_champion_as_defending_champion(
    kit: SeasonCupKit,
) -> None:
    kit.payload_names = {"DAL": HARBOR}
    previous = await kit.serve_season("2026")
    kit.calls.clear()

    body = await kit.serve()

    assert champion_of(body, "defendingChampion") == champion_of(previous, "champion")
    assert champion_of(body, "defendingChampion")["name"] == "Harbor Gulls"
    assert kit.called("p-schedule/") == 0


@pytest.mark.anyio
async def test_a_missing_previous_cup_is_built_first_and_stored(
    kit: SeasonCupKit,
) -> None:
    kit.payload_names = {"DAL": HARBOR}

    body = await kit.serve()

    stored = read_by_id(kit.path, KIND, "2026")
    assert stored is not None
    assert kit.store.feed_build(KIND, "2026") is not None
    assert champion_of(body, "defendingChampion") == champion_of(stored, "champion")
    assert kit.called("p-schedule/") == 30
    assert kit.called("schedule/") == 30


@pytest.mark.anyio
async def test_with_no_previous_cup_the_defending_champion_is_null_and_the_feed_builds(
    kit: SeasonCupKit,
) -> None:
    kit.stars.season = 2024

    body = await kit.serve()

    assert json.loads(body)["defendingChampion"] is None
    assert kit.called("p-schedule/") == 0
    assert not (kit.path / "feeds" / KIND).exists()


@pytest.mark.anyio
async def test_a_failing_previous_build_leaves_a_null_defending_champion_and_the_feed_builds(
    kit: SeasonCupKit,
) -> None:
    kit.failing = {"teams/eastA/2026"}

    body = await kit.serve()

    assert json.loads(body)["defendingChampion"] is None
    assert kit.stored() is not None
    failure = kit.store.feed_build(KIND, "2026")
    assert failure is not None and failure.last_failure_reason
    assert read_by_id(kit.path, KIND, "2026") is None
    attempts = kit.called("teams/eastA/2026")
    kit.clock[0] = kit.clock[0] + dt.timedelta(minutes=1)
    await kit.cache.serve(CUP_KIND, CUP_FEED_ID)
    await kit.settle()
    assert kit.called("teams/eastA/2026") == attempts


@pytest.mark.anyio
async def test_a_past_feed_carries_the_stored_champion_of_the_season_before(
    kit: SeasonCupKit,
) -> None:
    kit.payload_names = {"DAL": HARBOR}
    earlier = await kit.serve_season("2025")
    kit.calls.clear()

    body = await kit.serve_season("2026")

    assert champion_of(body, "defendingChampion") == champion_of(earlier, "champion")
    assert kit.called("p-schedule/") == 30
    assert not any(name.endswith("/2025") for name in kit.calls if "/" in name)


@pytest.mark.anyio
async def test_a_past_feed_without_a_stored_previous_feed_has_no_defending_champion_and_reads_nothing_for_it(
    kit: SeasonCupKit,
) -> None:
    body = await kit.serve_season("2026")

    assert json.loads(body)["defendingChampion"] is None
    assert kit.called("p-schedule/") == 30
    assert all(
        name.endswith("/2026") for name in kit.calls if name.startswith("teams/")
    )
    assert read_by_id(kit.path, KIND, "2025") is None


@pytest.mark.anyio
async def test_the_first_cup_has_no_defending_champion(kit: SeasonCupKit) -> None:
    body = await kit.serve_season("2024")

    assert json.loads(body)["defendingChampion"] is None


def test_previous_cup_names_the_season_before_from_the_second_cup(
    kit: SeasonCupKit,
) -> None:
    assert kit.season_cups.previous_cup(2027) == (KIND, "2026")
    assert kit.season_cups.previous_cup(2025) == (KIND, "2024")
    assert kit.season_cups.previous_cup(2024) is None
