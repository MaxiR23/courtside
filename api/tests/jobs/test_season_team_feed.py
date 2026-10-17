# api/tests/jobs/test_season_team_feed.py
#
# Tests for the team feed of a past season and its feed kind.
#
# Tested:
# - The builder sets that season's name and city, the record of that season's standing (a 7th division place, the play-in position null before 2021 and set from 2021), the leaders of that season, the roster of the box-score players (jersey and position or null, every other field null, status active) and the schedule with the regular season and the playoffs group
# - A leader with no position keeps a null position
# - Opponents are named by that season's team object, and every final game has detail available
# - The builder sets the arena, coach, injuries, next game, Cup and titles to null, and the feed validates as a past team feed
# - The builder fails for a team with no standing
# - The kind: a missing season team answers unknown after one read, and a second request answers unknown with no read
# - The kind: an inactive team object answers the feed with that season's name, city and code
# - The kind: 1993-okc, 2004-okc with a trailing newline, the current season, a future season, abc-okc, 2004-OKC and an unknown team answer unknown with no source request, and an unknown current season is not ready
# - The kind: the season is sent to the season reads, the schedules are read by id first and the leaders have no fallback
# - The kind: the names are built first and the stored feed carries them; serving sets the latest stored names
# - The kind: the feed is never rebuilt, also after a simulated restart and years later
# - The kind: the built feed carries the current build version, a stored feed of an older or missing version is rebuilt on its next request, and one of the current version is served with no source request (ADR 0053)
# - The kind: the roster comes from the box scores of the final games, each read once
# - The kind: a failed build with nothing stored answers unavailable
#
# What is covered:
# - Pure conversions: happy path, edges and errors; the built feed validates
# - Feed kind: success publishes a valid feed, failure with nothing stored is unavailable, kept for good
#
# Run with: cd api && .venv/bin/python -m pytest tests/jobs/test_season_team_feed.py
#
# SEE: api/app/jobs/season_team_feed.py

import asyncio
import datetime as dt
import json
from pathlib import Path
from typing import Any, cast

import pytest
import respx

from app.feeds.team import NameRun, PastTeamFeed, TeamNames
from app.jobs.on_demand import (
    SEASON_BUILD_VERSION,
    FeedCache,
    FeedUnavailableError,
    IdStatus,
    UnknownFeedError,
)
from app.jobs.season_rosters import SeasonRosters
from app.jobs.season_team_feed import (
    KIND,
    SeasonTeamFeeds,
    build_season_team_feed,
)
from app.jobs.stars import StarsJob
from app.jobs.team_feed import TeamBuildError
from app.jobs.team_names import TeamNamesFeeds
from app.settings import Settings
from app.sources import season_team as season_team_adapter
from app.sources.division_standings import DivisionStandings
from app.sources.game_detail import BoxScoreRosterEntry, GamePlayers
from app.sources.http import Freshness, SourceClient, SourceError, create_client
from app.sources.season_team import SeasonTeam
from app.sources.team_info import TeamInfo
from app.sources.team_players import PlayerAverages, SeasonLeaders
from app.sources.team_schedule import SeasonSchedule
from app.storage.feeds import publish_by_id, read_by_id
from app.storage.state import StateStore
from tests.jobs.test_team_feed import (
    game,
    info,
    leaders,
    played,
    season,
    standing,
    standings,
)

NOW = dt.datetime(2026, 10, 8, 15, 0, tzinfo=dt.UTC)
YEARS = dt.timedelta(days=365 * 5)
GAME_TIME = dt.datetime(2003, 11, 2, 3, 0, tzinfo=dt.UTC)
PLAYOFF_TIME = dt.datetime(2004, 4, 22, 1, 0, tzinfo=dt.UTC)


def season_team() -> SeasonTeam:
    return SeasonTeam(
        team_id="25",
        abbreviation="SEA",
        display_name="Seattle Harbor Gulls",
        name="Harbor Gulls",
        location="Seattle",
    )


def box_entry(
    player_id: str,
    jersey: str | None,
    position: str | None = "PG",
) -> BoxScoreRosterEntry:
    return BoxScoreRosterEntry(
        player_id=player_id,
        display_name=f"Player {player_id}",
        jersey=jersey,
        position_abbreviation=position,
        headshot_url=f"https://example.com/{player_id}.png",
    )


def past_roster() -> list[BoxScoreRosterEntry]:
    return [box_entry("1", "2"), box_entry("2", "9", None)]


def averages() -> SeasonLeaders:
    return leaders(("1", 21.44, 5.0, 7.0), ("2", 9.0, 8.26, 1.0), season=2004)


def regular_schedule() -> SeasonSchedule:
    return season(played("g1", GAME_TIME))


def playoffs_schedule() -> SeasonSchedule:
    return season(played("g2", PLAYOFF_TIME, playoffs=True))


def build(
    *,
    code: str = "OKC",
    end_year: int = 2004,
    entry_changes: dict[str, Any] | None = None,
    names: list[NameRun] | None = None,
    opponent_names: dict[str, tuple[str, str]] | None = None,
    roster: list[BoxScoreRosterEntry] | None = None,
    season_leaders: SeasonLeaders | None = None,
) -> PastTeamFeed:
    entry = standing(code, division_order=7, **(entry_changes or {}))
    return build_season_team_feed(
        code,
        end_year,
        season_team(),
        info(),
        standings(entry, season=end_year),
        past_roster() if roster is None else roster,
        season_leaders or averages(),
        regular_schedule(),
        playoffs_schedule(),
        names,
        opponent_names,
    )


def test_the_builder_sets_the_name_and_city_of_that_season_and_todays_colors() -> None:
    feed = build()

    assert (feed.city, feed.name) == ("Seattle", "Harbor Gulls")
    assert feed.code == "OKC"
    assert feed.season == "2003-04"
    assert (feed.colors.primary, feed.colors.secondary) == ("#007ac1", "#ef3b24")


def test_the_builder_sets_the_record_of_that_seasons_standing_with_a_7th_division_place() -> (
    None
):
    feed = build()

    assert feed.record.season == "2003-04"
    assert (feed.record.wins, feed.record.losses) == (30, 10)
    assert feed.record.division_rank == 7


@pytest.mark.parametrize(("end_year", "has_playoff"), [(2020, False), (2021, True)])
def test_the_play_in_position_is_null_before_2021_and_set_from_2021(
    end_year: int, has_playoff: bool
) -> None:
    feed = build(end_year=end_year)

    assert (feed.record.playoff is not None) is has_playoff
    assert feed.record.conference_rank == 1


def test_the_builder_sets_the_leaders_of_that_season_with_no_fallback_label() -> None:
    feed = build()

    assert feed.leaders.season == "2003-04"
    assert feed.leaders.points is not None
    assert (feed.leaders.points.player_id, feed.leaders.points.value) == ("1", 21.4)
    assert feed.leaders.rebounds is not None
    assert feed.leaders.rebounds.player_id == "2"


def test_the_roster_lists_the_box_score_players_with_jersey_and_position_or_null_and_every_other_field_null() -> (
    None
):
    feed = build()

    assert [p.status for p in feed.roster] == ["active", "active"]
    first, second = feed.roster
    assert (first.id, first.name, first.number, first.position) == (
        "1",
        "Player 1",
        "2",
        "PG",
    )
    assert str(first.photo_url) == "https://example.com/1.png"
    assert (second.number, second.position) == ("9", None)
    for row in feed.roster:
        assert (
            row.height,
            row.weight,
            row.age,
            row.birth_date,
            row.birthplace,
            row.college,
            row.experience,
        ) == (None,) * 7


def test_the_roster_is_in_jersey_order_with_a_player_without_a_jersey_last() -> None:
    feed = build(
        roster=[box_entry("3", None), box_entry("2", "9"), box_entry("1", "2")]
    )

    assert [p.id for p in feed.roster] == ["1", "2", "3"]


def test_a_leader_with_no_position_keeps_a_null_position() -> None:
    feed = build(
        season_leaders=leaders(("2", 30.0, 1.0, 1.0), ("1", 5.0, 9.0, 2.0), season=2004)
    )

    assert feed.leaders.points is not None
    assert (feed.leaders.points.player_id, feed.leaders.points.position) == ("2", None)
    assert feed.leaders.points.number == "9"
    assert feed.leaders.rebounds is not None
    assert feed.leaders.rebounds.position == "PG"


def test_a_leader_who_is_not_in_the_box_score_roster_is_left_out() -> None:
    feed = build(season_leaders=leaders(("77", 30.0, 1.0, 1.0), season=2004))

    assert feed.leaders.points is None


def test_the_schedule_has_the_regular_season_and_the_playoffs_group() -> None:
    feed = build()

    assert feed.schedule is not None
    assert [group.key for group in feed.schedule.groups] == ["2003-11", "playoffs"]
    assert feed.schedule.default_group == "playoffs"
    assert all(
        game.detail_available and not game.is_next
        for group in feed.schedule.groups
        for game in group.games
    )


def test_only_a_final_game_has_detail_available() -> None:
    feed = build_season_team_feed(
        "OKC",
        2004,
        season_team(),
        info(),
        standings(standing("OKC", division_order=7), season=2004),
        past_roster(),
        averages(),
        season(played("g1", GAME_TIME), game("g0", GAME_TIME)),
        season(),
    )

    assert feed.schedule is not None
    available = {g.game_id: g.detail_available for g in feed.schedule.groups[0].games}
    assert available == {"g0": False, "g1": True}


def test_the_opponents_are_named_by_that_seasons_team_object() -> None:
    feed = build(opponent_names={"SAS": ("Harbor Gulls", "Seattle")})

    assert feed.schedule is not None
    opponents = {
        (g.opponent.code, g.opponent.name, g.opponent.city)
        for group in feed.schedule.groups
        for g in group.games
    }
    assert opponents == {("SAS", "Harbor Gulls", "Seattle")}


def test_the_builder_sets_the_blocks_of_today_to_null_and_the_names_given() -> None:
    names = [
        NameRun.model_validate(
            {"from": 1994, "to": None, "name": "Harbor", "location": "S", "code": "SEA"}
        )
    ]

    feed = build(names=names)

    assert feed.arena is None and feed.coach is None and feed.injuries is None
    assert feed.next_game is None and feed.cup is None and feed.titles is None
    assert feed.names == names
    PastTeamFeed.model_validate_json(feed.model_dump_json())


def test_the_builder_fails_for_a_team_with_no_standing() -> None:
    with pytest.raises(TeamBuildError) as raised:
        build_season_team_feed(
            "SAS",
            2004,
            season_team(),
            info(),
            standings(season=2004),
            past_roster(),
            averages(),
            regular_schedule(),
            playoffs_schedule(),
        )

    assert raised.value.reason == "team SAS has no standing"


class FakeStars:
    def __init__(self) -> None:
        self.season: int | None = 2027

    def current_season(self) -> int | None:
        return self.season


class SeasonTeamKit:
    """The names kind and the season team kind over one client and one clock,
    with fake adapters that count their calls."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.clock = [NOW]
        self.store = StateStore(path)
        self.store.migrate()
        self.settings = Settings(_env_file=None, data_dir=path)  # type: ignore[call-arg]
        self.client = create_client(self.store, clock=lambda: self.clock[0])
        self.stars = FakeStars()
        self.calls: list[str] = []
        self.name_reads = 0
        self.missing = False
        self.failing = False
        self.opponent_names: dict[str, SeasonTeam] = {}
        self.start()

    def start(self) -> None:
        """A new cache and kinds over the same data directory: a restart."""
        self.cache = FeedCache(self.path, self.store, clock=lambda: self.clock[0])
        self.names = TeamNamesFeeds(
            self.settings,
            self.store,
            self.client,
            self.cache,
            cast(StarsJob, self.stars),
            fetch_season_team=self.fetch_season_team,
        )
        self.rosters = SeasonRosters(
            self.settings,
            self.store,
            self.client,
            fetch_season_schedule=self.fetch_season_schedule,
            fetch_game_players=self.fetch_game_players,
        )
        self.teams = SeasonTeamFeeds(
            self.settings,
            self.store,
            self.client,
            self.cache,
            cast(StarsJob, self.stars),
            self.names,
            self.rosters,
            fetch_season_team=self.fetch_season_team,
            fetch_team_info=self.fetch_team_info,
            fetch_division_standings=self.fetch_division_standings,
            fetch_season_averages=self.fetch_season_averages,
            fetch_season_schedule=self.fetch_season_schedule,
        )

    async def fetch_season_team(
        self, client: SourceClient, code: str, end_year: int, settings: Settings
    ) -> SeasonTeam | None:
        self.calls.append(f"season-team/{code}/{end_year}")
        if end_year != 2004:
            self.name_reads += 1
        if self.missing:
            return None
        return self.opponent_names.get(code, season_team())

    async def fetch_team_info(
        self, client: SourceClient, code: str, settings: Settings
    ) -> TeamInfo:
        self.calls.append(f"info/{code}")
        if self.failing:
            raise SourceError("test", "team info is down")
        return info()

    async def fetch_division_standings(
        self, client: SourceClient, settings: Settings, *, season: int | None = None
    ) -> DivisionStandings:
        self.calls.append(f"standings/{season}")
        return standings(standing("OKC", division_order=7), season=season or 0)

    async def fetch_game_players(
        self, client: SourceClient, game_id: str, settings: Settings, fresh: Freshness
    ) -> GamePlayers:
        self.calls.append(f"players/{game_id}")
        return GamePlayers(teams={"OKC": past_roster()})

    async def fetch_season_averages(
        self, client: SourceClient, team_id: str, end_year: int, settings: Settings
    ) -> list[PlayerAverages]:
        self.calls.append(f"averages/{team_id}/{end_year}")
        return averages().players

    async def fetch_season_schedule(
        self,
        client: SourceClient,
        code: str,
        end_year: int,
        settings: Settings,
        *,
        playoffs: bool,
        by_id_first: bool = False,
    ) -> SeasonSchedule:
        self.calls.append(f"schedule/{code}/{end_year}/{playoffs}/{by_id_first}")
        return playoffs_schedule() if playoffs else regular_schedule()

    async def settle(self) -> None:
        while self.cache.in_flight:
            await next(iter(self.cache.in_flight.values()))
            await asyncio.sleep(0)
        await asyncio.sleep(0)

    async def serve(self, feed_id: str, at: dt.datetime | None = None) -> bytes:
        if at is not None:
            self.clock[0] = at
        body = await self.cache.serve(KIND, feed_id)
        await self.settle()
        return body

    def stored(self, feed_id: str) -> PastTeamFeed | None:
        body = read_by_id(self.path, KIND, feed_id)
        return None if body is None else PastTeamFeed.model_validate_json(body)


@pytest.fixture
def kit(tmp_path: Path) -> SeasonTeamKit:
    return SeasonTeamKit(tmp_path)


@pytest.mark.anyio
async def test_a_request_builds_a_valid_feed_with_the_season_reads_by_id_first(
    kit: SeasonTeamKit,
) -> None:
    feed = PastTeamFeed.model_validate_json(await kit.serve("2004-okc"))

    assert feed.season == "2003-04"
    assert (feed.city, feed.name) == ("Seattle", "Harbor Gulls")
    assert "standings/2004" in kit.calls
    assert sorted(c for c in kit.calls if c.startswith("players/")) == [
        "players/g1",
        "players/g2",
    ]
    assert "averages/25/2004" in kit.calls
    assert "schedule/OKC/2004/False/True" in kit.calls
    assert "schedule/OKC/2004/True/True" in kit.calls


@pytest.mark.anyio
async def test_a_missing_season_team_answers_unknown_after_one_read_and_then_with_none(
    kit: SeasonTeamKit,
) -> None:
    kit.missing = True

    with pytest.raises(UnknownFeedError):
        await kit.serve("2004-okc")
    after_first = list(kit.calls)
    with pytest.raises(UnknownFeedError):
        await kit.serve("2004-okc")

    # One read of the season's team object by the kind, one by the names build.
    assert after_first.count("season-team/OKC/2004") == 2
    assert kit.calls == after_first
    assert kit.stored("2004-okc") is None
    assert kit.store.feed_build("season-teams", "2004-okc") is None
    assert not any(call.startswith("standings") for call in kit.calls)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "feed_id",
    [
        "1993-okc",
        "2027-okc",
        "2028-okc",
        "abc-okc",
        "2004-OKC",
        "2004-xyz",
        "2004",
        "",
        "2004-okc\n",
    ],
)
async def test_an_invalid_early_current_future_or_unknown_id_answers_unknown_with_no_source_request(
    kit: SeasonTeamKit, feed_id: str
) -> None:
    assert kit.teams.check(feed_id) is IdStatus.UNKNOWN
    with pytest.raises(UnknownFeedError):
        await kit.cache.serve(KIND, feed_id)

    assert kit.calls == []


@pytest.mark.anyio
async def test_an_unknown_current_season_is_not_ready(kit: SeasonTeamKit) -> None:
    kit.stars.season = None

    assert kit.teams.check("2004-okc") is IdStatus.NOT_READY
    assert kit.teams.check("1993-okc") is IdStatus.UNKNOWN
    with pytest.raises(FeedUnavailableError):
        await kit.cache.serve(KIND, "2004-okc")

    assert kit.calls == []


@pytest.mark.anyio
async def test_the_names_are_built_first_and_the_stored_feed_carries_them(
    kit: SeasonTeamKit,
) -> None:
    body = await kit.serve("2004-okc")

    assert kit.name_reads == 2027 - 1994 + 1 - 1
    feed = PastTeamFeed.model_validate_json(body)
    assert [(r.from_, r.to, r.name) for r in feed.names] == [
        (1994, None, "Harbor Gulls")
    ]
    stored = kit.stored("2004-okc")
    assert stored is not None and stored.names == feed.names


@pytest.mark.anyio
async def test_serving_sets_the_latest_stored_names(kit: SeasonTeamKit) -> None:
    await kit.serve("2004-okc")
    newer = [
        NameRun.model_validate(
            {"from": 1994, "to": None, "name": "Storm", "location": "S", "code": "SEA"}
        )
    ]
    publish_by_id(kit.path, "team-names", TeamNames, "okc", TeamNames(runs=newer))

    served = PastTeamFeed.model_validate_json(await kit.serve("2004-okc"))

    assert [r.name for r in served.names] == ["Storm"]
    stored = kit.stored("2004-okc")
    assert stored is not None and [r.name for r in stored.names] == ["Harbor Gulls"]


@pytest.mark.anyio
async def test_the_feed_is_never_rebuilt_even_after_a_restart_or_years_later(
    kit: SeasonTeamKit,
) -> None:
    first = await kit.serve("2004-okc")
    calls = len(kit.calls)
    await kit.serve("2004-okc", NOW + YEARS)
    kit.start()
    await kit.serve("2004-okc", NOW + 2 * YEARS)

    assert len(kit.calls) == calls
    assert read_by_id(kit.path, KIND, "2004-okc") is not None
    assert first


@pytest.mark.anyio
async def test_a_failed_build_with_nothing_stored_answers_unavailable(
    kit: SeasonTeamKit,
) -> None:
    kit.failing = True

    with pytest.raises(FeedUnavailableError):
        await kit.serve("2004-okc")

    assert kit.stored("2004-okc") is None


@pytest.mark.anyio
async def test_the_cleanup_keeps_the_feed(kit: SeasonTeamKit) -> None:
    await kit.serve("2004-okc")

    kit.cache.cleanup()

    assert kit.stored("2004-okc") is not None


INACTIVE = (
    Path(__file__).parent.parent
    / "sources"
    / "fixtures"
    / "season_team"
    / "inactive.json"
)


@pytest.mark.anyio
async def test_an_inactive_team_object_answers_the_feed_with_that_seasons_name_city_and_code(
    tmp_path: Path,
) -> None:
    kit = SeasonTeamKit(tmp_path)
    kit.settings = Settings(  # type: ignore[call-arg]
        _env_file=None,
        data_dir=tmp_path,
        season_team_url="https://example.com/seasons/{season}/teams/{team_id}",
    )
    kit.fetch_season_team = season_team_adapter.fetch_season_team  # type: ignore[method-assign,assignment]
    kit.start()
    body = json.loads(INACTIVE.read_text(encoding="utf-8"))
    assert body["isActive"] is False

    with respx.mock as mock:
        mock.get(url__regex=r"https://example\.com/seasons/\d+/teams/\d+").respond(
            json=body
        )
        feed = PastTeamFeed.model_validate_json(await kit.serve("2004-okc"))

    assert (feed.city, feed.name, feed.code) == ("Seattle", "Harbor Gulls", "OKC")


@pytest.mark.anyio
async def test_the_built_feed_carries_the_current_build_version(
    kit: SeasonTeamKit,
) -> None:
    await kit.serve("2004-okc")

    stored = kit.stored("2004-okc")
    assert stored is not None and stored.build_version == SEASON_BUILD_VERSION


@pytest.mark.anyio
@pytest.mark.parametrize("version", [None, SEASON_BUILD_VERSION + 1])
async def test_a_stored_feed_with_an_older_or_missing_version_is_rebuilt_on_its_next_request(
    kit: SeasonTeamKit, version: int | None
) -> None:
    await kit.serve("2004-okc")
    stored = kit.stored("2004-okc")
    assert stored is not None
    old = stored.model_copy(update={"build_version": version})
    publish_by_id(kit.path, KIND, PastTeamFeed, "2004-okc", old)
    kit.calls.clear()

    served = PastTeamFeed.model_validate_json(await kit.serve("2004-okc", NOW + YEARS))

    assert served.build_version == version
    assert any(call.startswith("standings/") for call in kit.calls)
    rebuilt = kit.stored("2004-okc")
    assert rebuilt is not None and rebuilt.build_version == SEASON_BUILD_VERSION


@pytest.mark.anyio
async def test_a_stored_feed_with_the_current_version_is_served_with_no_source_request(
    kit: SeasonTeamKit,
) -> None:
    await kit.serve("2004-okc")
    kit.calls.clear()

    await kit.serve("2004-okc", NOW + YEARS)

    assert kit.calls == []
