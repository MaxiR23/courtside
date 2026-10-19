# api/tests/jobs/test_season_team_feed.py
#
# Tests for the team feed of a past season and its feed kind.
#
# Tested:
# - The builder sets that season's name and city, the record of that season's standing (a 7th division place, the play-in position null before 2021 and set from 2021) and the schedule with the regular season and the playoffs group
# - The builder sets a null roster and null leaders, and the colors from the team info or null without it (ADR 0059)
# - Opponents are named by the names given with their season code and the historical flag, and every final game has detail available
# - The header carries the season code and the historical flag, none without an identity
# - The kind: a header whose season object differs from the current season's is historical with its season code
# - The builder sets the arena, coach, injuries, next game, Cup and titles to null, and the feed validates as a past team feed
# - The builder fails for a team with no standing
# - The kind: a missing season team answers unknown after one read, and a second request answers unknown with no read
# - The kind: an inactive team object answers the feed with that season's name, city and code
# - The kind: 1993-okc, 2004-okc with a trailing newline, the current season, a future season, abc-okc, 2004-OKC and an unknown team answer unknown with no source request, and an unknown current season is not ready
# - The kind: the season is sent to the season reads and the schedules are read by id first
# - The kind: the colors come from the cached team info with no team info request, and are null without it
# - The kind: the dates of the final games are registered with no box score read
# - The kind: the opponents and the header are named from the payloads and the stored names with no season names read
# - The kind: the names are built first and the stored feed carries them; serving sets the latest stored names
# - The kind: a names list of another or no version makes the feed stale and is rebuilt first; one of the current version leaves it fresh (ADR 0055)
# - The kind: the feed is never rebuilt, also after a simulated restart and years later
# - The kind: the built feed carries the current build version, a stored feed of an older or missing version is rebuilt on its next request, and one of the current version is served with no source request (ADR 0053)
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
    with_build_version,
)
from app.jobs.season_team_feed import (
    KIND,
    SeasonTeamFeeds,
    build_season_team_feed,
)
from app.jobs.stars import StarsJob
from app.jobs.team_feed import TeamBuildError
from app.jobs.team_names import SeasonIdentity, TeamNamesFeeds
from app.settings import Settings
from app.sources import season_team as season_team_adapter
from app.sources.division_standings import DivisionStandings
from app.sources.http import SourceClient, SourceError, create_client
from app.sources.season_team import SeasonTeam
from app.sources.team_info import PROVIDER_CODES, TeamInfo
from app.sources.team_schedule import SeasonSchedule
from app.sources.teams import SeasonTeamName
from app.storage.feeds import publish_by_id, read_by_id
from app.storage.state import StateStore
from tests.jobs.test_team_feed import (
    game,
    info,
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


TEAM_INFO = info()


def opponent_name() -> SeasonTeamName:
    return SeasonTeamName(
        abbreviation="SAS", name="Harbor Rays", location="San Antonio"
    )


def regular_schedule() -> SeasonSchedule:
    return season(played("g1", GAME_TIME)).model_copy(
        update={"teams": {"SAS": opponent_name()}}
    )


def playoffs_schedule() -> SeasonSchedule:
    return season(played("g2", PLAYOFF_TIME, playoffs=True))


def build(
    *,
    code: str = "OKC",
    end_year: int = 2004,
    entry_changes: dict[str, Any] | None = None,
    names: list[NameRun] | None = None,
    opponent_names: dict[str, SeasonIdentity] | None = None,
    identity: SeasonIdentity | None = None,
    team_info: TeamInfo | None = TEAM_INFO,
) -> PastTeamFeed:
    entry = standing(code, division_order=7, **(entry_changes or {}))
    return build_season_team_feed(
        code,
        end_year,
        season_team(),
        team_info,
        standings(entry, season=end_year),
        regular_schedule(),
        playoffs_schedule(),
        names,
        opponent_names,
        identity,
    )


def test_the_builder_sets_the_name_and_city_of_that_season_and_the_colors_of_the_team_info() -> (
    None
):
    feed = build()

    assert (feed.city, feed.name) == ("Seattle", "Harbor Gulls")
    assert feed.code == "OKC"
    assert feed.season == "2003-04"
    assert feed.colors is not None
    assert (feed.colors.primary, feed.colors.secondary) == ("#007ac1", "#ef3b24")


def test_the_builder_sets_null_colors_without_team_info() -> None:
    assert build(team_info=None).colors is None


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


def test_the_builder_sets_null_roster_and_leaders() -> None:
    feed = build()

    assert feed.roster is None
    assert feed.leaders is None
    PastTeamFeed.model_validate_json(feed.model_dump_json())


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
        season(played("g1", GAME_TIME), game("g0", GAME_TIME)),
        season(),
    )

    assert feed.schedule is not None
    available = {g.game_id: g.detail_available for g in feed.schedule.groups[0].games}
    assert available == {"g0": False, "g1": True}


def test_the_opponents_are_named_by_that_seasons_team_object() -> None:
    feed = build(
        opponent_names={"SAS": SeasonIdentity("Harbor Gulls", "Seattle", "SEA", True)}
    )

    assert feed.schedule is not None
    opponents = {
        (
            g.opponent.code,
            g.opponent.name,
            g.opponent.city,
            g.opponent.season_code,
            g.opponent.historical,
        )
        for group in feed.schedule.groups
        for g in group.games
    }
    assert opponents == {("SAS", "Harbor Gulls", "Seattle", "SEA", True)}


def test_a_historical_header_carries_its_season_code_and_the_flag() -> None:
    feed = build(identity=SeasonIdentity("Harbor Gulls", "Seattle", "SEA", True))

    assert (feed.code, feed.season_code, feed.historical) == ("OKC", "SEA", True)


def test_a_header_that_kept_its_name_is_not_historical() -> None:
    feed = build(identity=SeasonIdentity("Thunder", "Oklahoma City", "OKC", False))

    assert (feed.season_code, feed.historical) == ("OKC", False)


def test_a_header_built_with_no_identity_has_no_season_code() -> None:
    feed = build()

    assert (feed.season_code, feed.historical) == (None, False)


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
        self.settings = Settings(  # type: ignore[call-arg]
            _env_file=None,
            data_dir=path,
            team_info_url="https://example.com/teams/{team}/info",
        )
        self.client = create_client(self.store, clock=lambda: self.clock[0])
        self.stars = FakeStars()
        self.calls: list[str] = []
        self.name_reads = 0
        self.missing = False
        self.failing = False
        self.opponent_names: dict[str, SeasonTeam] = {}
        self.current_teams: dict[str, SeasonTeam] = {}
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
        self.teams = SeasonTeamFeeds(
            self.settings,
            self.store,
            self.client,
            self.cache,
            cast(StarsJob, self.stars),
            self.names,
            fetch_season_team=self.fetch_season_team,
            fetch_division_standings=self.fetch_division_standings,
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
        if end_year == 2027 and code in self.current_teams:
            return self.current_teams[code]
        return self.opponent_names.get(code, season_team())

    async def fetch_division_standings(
        self, client: SourceClient, settings: Settings, *, season: int | None = None
    ) -> DivisionStandings:
        self.calls.append(f"standings/{season}")
        if self.failing:
            raise SourceError("test", "standings are down")
        return standings(standing("OKC", division_order=7), season=season or 0)

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
    assert feed.roster is None and feed.leaders is None
    assert "standings/2004" in kit.calls
    assert "schedule/OKC/2004/False/True" in kit.calls
    assert "schedule/OKC/2004/True/True" in kit.calls
    assert not any(call.startswith(("players/", "averages/")) for call in kit.calls)


def seed_team_info(kit: SeasonTeamKit) -> None:
    body = {
        "team": {
            "location": "Oklahoma City",
            "name": "Thunder",
            "color": "007ac1",
            "alternateColor": "ef3b24",
            "franchise": {"venue": {"fullName": "Example Arena"}},
        }
    }
    kit.store.set_source_entry(
        f"https://example.com/teams/{PROVIDER_CODES['OKC']}/info",
        json.dumps(body),
        NOW,
    )


@pytest.mark.anyio
async def test_the_colors_come_from_the_cached_team_info_and_are_null_without_it(
    tmp_path: Path,
) -> None:
    (tmp_path / "without").mkdir()
    (tmp_path / "with").mkdir()
    without = SeasonTeamKit(tmp_path / "without")
    with_info = SeasonTeamKit(tmp_path / "with")
    seed_team_info(with_info)

    bare = PastTeamFeed.model_validate_json(await without.serve("2004-okc"))
    colored = PastTeamFeed.model_validate_json(await with_info.serve("2004-okc"))

    assert bare.colors is None
    assert colored.colors is not None and colored.colors.primary == "#007ac1"
    assert not any(call.startswith("info/") for call in with_info.calls)


@pytest.mark.anyio
async def test_the_final_games_dates_are_registered_with_no_box_score_read(
    kit: SeasonTeamKit,
) -> None:
    await kit.serve("2004-okc")

    assert kit.store.past_game_date("g1", at=NOW) == dt.date(2003, 11, 1)
    assert kit.store.past_game_date("g2", at=NOW) == dt.date(2004, 4, 21)
    assert not any(call.startswith("players/") for call in kit.calls)


@pytest.mark.anyio
async def test_the_opponents_and_the_header_are_named_from_the_payloads_and_the_stored_names_with_no_season_names_read(
    kit: SeasonTeamKit,
) -> None:
    # The franchise names are stored: the stored list is "today" for the payload.
    await kit.names.build("sas")
    kit.calls.clear()

    async def forbidden(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("season_names must not be read")

    kit.names.season_names = forbidden  # type: ignore[method-assign]
    feed = PastTeamFeed.model_validate_json(await kit.serve("2004-okc"))

    assert feed.schedule is not None
    sides = {
        (g.opponent.name, g.opponent.city)
        for group in feed.schedule.groups
        for g in group.games
    }
    assert sides == {("Harbor Rays", "San Antonio")}
    assert (feed.season_code, feed.historical) == ("SEA", False)
    assert kit.calls.count("season-team/SAS/2004") == 0


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
async def test_the_kind_marks_a_header_that_differs_from_the_current_season_historical(
    kit: SeasonTeamKit,
) -> None:
    kit.current_teams = {
        "OKC": SeasonTeam(
            team_id="25",
            abbreviation="OKC",
            display_name="Oklahoma City Thunder",
            name="Thunder",
            location="Oklahoma City",
        )
    }

    feed = PastTeamFeed.model_validate_json(await kit.serve("2004-okc"))

    assert (feed.code, feed.season_code, feed.historical) == ("OKC", "SEA", True)


@pytest.mark.anyio
async def test_the_names_are_built_first_and_the_stored_feed_carries_them(
    kit: SeasonTeamKit,
) -> None:
    body = await kit.serve("2004-okc")

    # The other seasons of the names, with no read of the build itself (ADR 0059).
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
    publish_by_id(
        kit.path,
        "team-names",
        TeamNames,
        "okc",
        with_build_version(TeamNames(runs=newer)),
    )

    served = PastTeamFeed.model_validate_json(await kit.serve("2004-okc"))

    assert [r.name for r in served.names] == ["Storm"]
    stored = kit.stored("2004-okc")
    assert stored is not None and [r.name for r in stored.names] == ["Harbor Gulls"]


@pytest.mark.anyio
@pytest.mark.parametrize("version", [None, SEASON_BUILD_VERSION + 1])
async def test_a_names_list_of_another_version_makes_the_feed_stale_and_is_rebuilt_first(
    kit: SeasonTeamKit, version: int | None
) -> None:
    await kit.serve("2004-okc")
    old = [
        NameRun.model_validate(
            {"from": 1994, "to": None, "name": "Storm", "location": "S", "code": "SEA"}
        )
    ]
    publish_by_id(
        kit.path,
        "team-names",
        TeamNames,
        "okc",
        TeamNames(runs=old, build_version=version),
    )
    kit.calls.clear()

    await kit.serve("2004-okc", NOW + dt.timedelta(days=1))

    assert any(call.startswith("season-team/") for call in kit.calls)
    assert kit.names.outdated("okc") is False
    names = kit.names.stored("okc")
    assert names is not None and [r.name for r in names] == ["Harbor Gulls"]
    stored = kit.stored("2004-okc")
    assert stored is not None and [r.name for r in stored.names] == ["Harbor Gulls"]


@pytest.mark.anyio
async def test_a_names_list_of_the_current_version_leaves_the_feed_fresh(
    kit: SeasonTeamKit,
) -> None:
    await kit.serve("2004-okc")
    kit.calls.clear()

    await kit.serve("2004-okc", NOW + dt.timedelta(days=1))

    assert kit.calls == []


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


@pytest.mark.anyio
async def test_serving_a_feed_keeps_the_rows_of_its_games_past_the_daily_prune(
    kit: SeasonTeamKit,
) -> None:
    day = dt.timedelta(days=1)
    await kit.serve("2004-okc", NOW)
    await kit.serve("2004-okc", NOW + 89 * day)

    kit.store.prune_past_games(NOW + 91 * day - 90 * day)

    assert kit.store.past_game_date("g1", at=NOW + 91 * day) == dt.date(2003, 11, 1)
    assert kit.store.past_game_date("g2", at=NOW + 91 * day) == dt.date(2004, 4, 21)


@pytest.mark.anyio
async def test_a_feed_not_served_in_90_days_loses_the_rows_of_its_games(
    kit: SeasonTeamKit,
) -> None:
    day = dt.timedelta(days=1)
    await kit.serve("2004-okc", NOW)

    kit.store.prune_past_games(NOW + 91 * day - 90 * day)

    assert kit.store.past_game_date("g1", at=NOW + 91 * day) is None


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
