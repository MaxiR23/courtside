# api/tests/jobs/test_season_playoffs_feed.py
#
# Tests for the playoffs feed of a past season and its feed kind.
#
# Tested:
# - past_season_status through check: 1993, abc, 02025, 2025 with a trailing newline, the current season and a future season are unknown; 1994 and the season before the current one are known; an unknown current season is not ready for a well-formed id from 1994
# - target: the current season maps to the current playoffs feed, a past season to the season kind, and an unknown current season to the season kind
# - The kind: a past season builds a valid complete feed, reading every source with the season, the days by provider id first and the season rosters, and the leaders and awards name players of those rosters
# - The kind: a player on two rosters belongs, in leaders and awards, to the team of his newest game, whatever the code order
# - The kind: the leader and award names come from the box-score rosters, and a roster read that fails, also with a 404, fails the build
# - The kind: the built feed carries the current build version, a stored feed of an older or missing version is rebuilt on its next request, and one of the current version is served with no source request (ADR 0053)
# - The kind: the feed is stored under season-playoffs and rebuilt only for another version: a second request, a request years later and a restart all serve with no source call; nothing is written under playoffs
# - The kind: season 2020 sends no play-in read and has a null play-in; season 2021 reads it
# - The kind: a leaders, awards or champion record read that answers 404 is null; any other failure answers unavailable and stores nothing
# - The kind: a team info failure only nulls the colors
# - The kind: a derivation that does not give 8-4-2-1 answers unavailable, stores nothing and logs the reason
# - The kind: a postseason that is not complete answers unavailable and stores nothing
# - The kind: a season without seeds has null side seeds
# - The kind: an invalid id answers unknown and a not ready season answers unavailable, with no source request
# - The kind: detailAvailable is false; the cleanup keeps it
#
# What is covered:
# - Pure status logic: happy path, edges and errors
# - Feed kind: success publishes a valid feed, failure with nothing stored is unavailable, kept for good
#
# Fake adapters and a fake clock are passed to the kind, so no test uses a real
# source or the real clock.
#
# Run with: cd api && .venv/bin/python -m pytest tests/jobs/test_season_playoffs_feed.py
#
# SEE: api/app/jobs/season_playoffs_feed.py

import asyncio
import datetime as dt
import logging
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import cast

import pytest
import respx

from app.feeds.playoffs import AwardCode, PlayoffsFeed, PlayoffsState, SeriesId
from app.jobs.on_demand import (
    SEASON_BUILD_VERSION,
    FeedCache,
    FeedUnavailableError,
    IdStatus,
    UnknownFeedError,
)
from app.jobs.playoffs_feed import FEED_ID as PLAYOFFS_ID
from app.jobs.playoffs_feed import KIND as PLAYOFFS_KIND
from app.jobs.season_playoffs_feed import KIND, SeasonPlayoffsFeeds
from app.jobs.season_rosters import SeasonRosters
from app.jobs.stars import StarsJob
from app.jobs.team_feed import player_name
from app.settings import Settings
from app.sources.division_standings import DivisionStandings
from app.sources.game_detail import BoxScoreRosterEntry
from app.sources.http import SourceClient, SourceError, create_client
from app.sources.postseason_leaders import PostseasonLeaders
from app.sources.postseason_scoreboard import PostseasonGame
from app.sources.season_awards import SeasonAwards
from app.sources.season_types import SeasonWindow
from app.sources.team_info import TeamInfo
from app.sources.team_players import RosterEntry
from app.sources.team_postseason import TeamPostseasonRecord
from app.storage.feeds import publish_by_id, read_by_id
from app.storage.state import StateStore
from tests.jobs.test_playoffs_feed import (
    ALL,
    EAST,
    NOW,
    PLAY_IN_WINDOW,
    POSTSEASON_WINDOW,
    FakeStars,
    award,
    leaders_source,
    past_games,
    play_ins,
    roster,
    seed,
    series_games,
    standings,
    without_rounds,
)
from tests.jobs.test_team_feed import info

YEARS = dt.timedelta(days=365 * 5)
CHAMPION = seed(EAST, 1)


class FakeRosters:
    """The box-score rosters of a season: the players of the fixture roster, named
    "Box <name>" so a name can only come from here."""

    def __init__(
        self,
        kit: SeasonPlayoffsKit,
        prefix: str,
        source: Callable[[str], list[RosterEntry]],
    ) -> None:
        self.kit = kit
        self.prefix = prefix
        self.source = source

    async def roster(self, code: str, season: int) -> list[BoxScoreRosterEntry]:
        self.kit.read(f"{self.prefix}/{code}/{season}")
        return [
            BoxScoreRosterEntry(
                player_id=entry.player_id,
                display_name=f"Box {player_name(entry)}",
                jersey=entry.jersey,
                position_abbreviation=None,
                headshot_url=entry.headshot_url,
            )
            for entry in self.source(code)
        ]


class SeasonPlayoffsKit:
    """The season playoffs kind over one client and one clock, with fake adapters
    that record their calls in self.calls, raise a timeout on the names in
    self.failing and answer 404 on the names in self.not_found."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.clock = [NOW]
        self.store = StateStore(path)
        self.store.migrate()
        self.settings = Settings(_env_file=None, data_dir=path)  # type: ignore[call-arg]
        self.client = create_client(self.store, clock=lambda: self.clock[0])
        self.calls: list[str] = []
        self.failing: set[str] = set()
        self.not_found: set[str] = set()
        self.days: dict[dt.date, list[PostseasonGame]] = {}
        self.standing: DivisionStandings | None = None
        self.stars = FakeStars()
        self.cache = FeedCache(path, self.store, clock=lambda: self.clock[0])
        self.load(past_games())
        self.register()

    def box_players(self, code: str) -> list[RosterEntry]:
        return [entry for c, entry in roster().values() if c == code]

    def register(self) -> None:
        self.season_playoffs = SeasonPlayoffsFeeds(
            self.settings,
            self.store,
            self.client,
            self.cache,
            cast(StarsJob, self.stars),
            cast(SeasonRosters, FakeRosters(self, "roster", self.box_players)),
            fetch_season_type=self.fetch_season_type,
            fetch_postseason_games=self.fetch_postseason_games,
            fetch_division_standings=self.fetch_division_standings,
            fetch_team_info=self.fetch_team_info,
            fetch_postseason_leaders=self.fetch_postseason_leaders,
            fetch_season_awards=self.fetch_season_awards,
            fetch_team_postseason_record=self.fetch_team_postseason_record,
        )

    def start(self) -> None:
        """A new cache and kind over the same data directory: a restart."""
        self.cache = FeedCache(self.path, self.store, clock=lambda: self.clock[0])
        self.register()

    def read(self, name: str) -> None:
        self.calls.append(name)
        if name in self.not_found:
            raise SourceError("test", f"{name} not found", status_code=404)
        if name in self.failing:
            raise SourceError("test", f"{name} is down")

    def called(self, prefix: str) -> int:
        return sum(1 for name in self.calls if name.startswith(prefix))

    def load(self, games: list[PostseasonGame]) -> None:
        self.days = {}
        for game in games:
            day = game.game.start_time.astimezone(
                dt.timezone(dt.timedelta(hours=-4))
            ).date()
            self.days.setdefault(day, []).append(game)

    async def fetch_season_type(
        self, client: SourceClient, season: int, season_type: int, settings: Settings
    ) -> SeasonWindow:
        self.read(f"type/{season}/{season_type}")
        return PLAY_IN_WINDOW if season_type == 5 else POSTSEASON_WINDOW

    async def fetch_postseason_games(
        self,
        client: SourceClient,
        day: dt.date,
        settings: Settings,
        *,
        by_id_first: bool = False,
    ) -> list[PostseasonGame]:
        self.read(f"day/{day.isoformat()}/{by_id_first}")
        return list(self.days.get(day, []))

    async def fetch_division_standings(
        self, client: SourceClient, settings: Settings, *, season: int | None = None
    ) -> DivisionStandings:
        self.read(f"standings/{season}")
        return self.standing or standings(season=season or 2027)

    async def fetch_team_info(
        self, client: SourceClient, code: str, settings: Settings
    ) -> TeamInfo:
        self.read(f"info/{code}")
        return info()

    async def fetch_postseason_leaders(
        self, client: SourceClient, season: int, settings: Settings
    ) -> PostseasonLeaders:
        self.read(f"leaders/{season}")
        return leaders_source()

    async def fetch_season_awards(
        self, client: SourceClient, season: int, settings: Settings
    ) -> SeasonAwards:
        self.read(f"awards/{season}")
        return SeasonAwards(awards=[award(AwardCode.MVP, ["1"])])

    async def fetch_team_postseason_record(
        self, client: SourceClient, team: str, season: int, settings: Settings
    ) -> TeamPostseasonRecord:
        self.read(f"record/{team}/{season}")
        return TeamPostseasonRecord(overall="16-6", home="9-2", road="7-4")

    async def settle(self) -> None:
        while self.cache.in_flight:
            await next(iter(self.cache.in_flight.values()))
            await asyncio.sleep(0)
        await asyncio.sleep(0)

    async def serve_season(self, season: str, at: dt.datetime | None = None) -> bytes:
        if at is not None:
            self.clock[0] = at
        body = await self.cache.serve(KIND, season)
        await self.settle()
        return body

    def stored(self, season: str) -> PlayoffsFeed | None:
        body = read_by_id(self.path, KIND, season)
        return None if body is None else PlayoffsFeed.model_validate_json(body)


@pytest.fixture(autouse=True)
def no_network() -> Iterator[None]:
    with respx.mock:
        yield


@pytest.fixture
def kit(tmp_path: Path) -> SeasonPlayoffsKit:
    return SeasonPlayoffsKit(tmp_path)


@pytest.mark.parametrize(
    "text", ["1993", "abc", "02025", "2025\n", "", "2027", "2028", "202"]
)
def test_an_ill_formed_early_current_or_future_season_is_unknown(
    kit: SeasonPlayoffsKit, text: str
) -> None:
    assert kit.season_playoffs.check(text) is IdStatus.UNKNOWN


def test_the_first_season_and_the_season_before_the_current_one_are_known(
    kit: SeasonPlayoffsKit,
) -> None:
    assert kit.season_playoffs.check("1994") is IdStatus.KNOWN
    assert kit.season_playoffs.check("2026") is IdStatus.KNOWN


def test_an_unknown_current_season_is_not_ready_from_1994(
    kit: SeasonPlayoffsKit,
) -> None:
    kit.stars.season = None

    assert kit.season_playoffs.check("2025") is IdStatus.NOT_READY
    assert kit.season_playoffs.check("1993") is IdStatus.UNKNOWN
    assert kit.season_playoffs.check("abc") is IdStatus.UNKNOWN


def test_the_current_season_maps_to_the_current_playoffs_feed(
    kit: SeasonPlayoffsKit,
) -> None:
    assert kit.season_playoffs.target("2027") == (PLAYOFFS_KIND, PLAYOFFS_ID)
    assert kit.season_playoffs.target("2025") == (KIND, "2025")
    assert kit.season_playoffs.target("abc") == (KIND, "abc")


def test_an_unknown_current_season_maps_to_the_season_kind(
    kit: SeasonPlayoffsKit,
) -> None:
    kit.stars.season = None

    assert kit.season_playoffs.target("2027") == (KIND, "2027")


@pytest.mark.anyio
async def test_a_past_season_builds_a_valid_complete_feed_from_the_season_sources(
    kit: SeasonPlayoffsKit,
) -> None:
    body = await kit.serve_season("2025")

    feed = PlayoffsFeed.model_validate_json(body)
    assert feed.season == "2024-25"
    assert feed.state is PlayoffsState.COMPLETE
    assert feed.champion is not None and str(feed.champion.team.code) == CHAMPION
    assert feed.champion.record == "16-6"
    assert feed.leaders is not None and feed.leaders[0].leaders
    assert feed.awards is not None and feed.awards[0].winners
    assert kit.called("standings/") == 1 and "standings/2025" in kit.calls
    assert kit.called("roster/") == 30
    assert all(n.endswith("/2025") for n in kit.calls if n.startswith("roster/"))
    days = [n for n in kit.calls if n.startswith("day/")]
    assert days and all(n.endswith("/True") for n in days)
    assert f"record/{CHAMPION}/2025" in kit.calls
    assert "leaders/2025" in kit.calls and "awards/2025" in kit.calls


@pytest.mark.anyio
async def test_a_stored_feed_is_never_rebuilt_even_years_later_or_after_a_restart(
    kit: SeasonPlayoffsKit,
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
async def test_building_a_past_playoffs_feed_writes_nothing_under_the_current_feed(
    kit: SeasonPlayoffsKit,
) -> None:
    await kit.serve_season("2025")

    assert read_by_id(kit.path, PLAYOFFS_KIND, PLAYOFFS_ID) is None
    assert not (kit.path / "feeds" / PLAYOFFS_KIND).exists()
    assert kit.store.feed_build_ids(PLAYOFFS_KIND) == set()


@pytest.mark.anyio
async def test_a_season_before_2021_sends_no_play_in_read_and_has_a_null_play_in(
    kit: SeasonPlayoffsKit,
) -> None:
    feed = PlayoffsFeed.model_validate_json(await kit.serve_season("2020"))

    assert feed.play_in is None
    assert "type/2020/3" in kit.calls
    assert kit.called("type/2020/5") == 0


@pytest.mark.anyio
async def test_the_first_play_in_season_reads_the_play_in(
    kit: SeasonPlayoffsKit,
) -> None:
    kit.load(play_ins() + past_games())

    feed = PlayoffsFeed.model_validate_json(await kit.serve_season("2021"))

    assert "type/2021/5" in kit.calls
    assert feed.play_in is not None and len(feed.play_in) == 2


@pytest.mark.anyio
@pytest.mark.parametrize(
    "name", ["leaders/2025", "awards/2025", f"record/{CHAMPION}/2025"]
)
async def test_a_leaders_awards_or_record_read_that_answers_404_is_null(
    kit: SeasonPlayoffsKit, name: str
) -> None:
    kit.not_found = {name}

    feed = PlayoffsFeed.model_validate_json(await kit.serve_season("2025"))

    assert feed.champion is not None
    assert (feed.champion.record is None) == name.startswith("record")
    assert (feed.leaders is None) == name.startswith("leaders")
    assert (feed.awards is None) == name.startswith("awards")


@pytest.mark.anyio
@pytest.mark.parametrize(
    "name",
    [
        "leaders/2025",
        "awards/2025",
        f"record/{CHAMPION}/2025",
        f"roster/{ALL[3]}/2025",
        "standings/2025",
        "type/2025/3",
    ],
)
async def test_any_other_failed_read_answers_unavailable_and_stores_nothing(
    kit: SeasonPlayoffsKit, name: str
) -> None:
    kit.failing = {name}

    with pytest.raises(FeedUnavailableError):
        await kit.serve_season("2025")

    assert read_by_id(kit.path, KIND, "2025") is None


@pytest.mark.anyio
async def test_a_failed_roster_read_fails_the_build_also_with_a_404(
    kit: SeasonPlayoffsKit,
) -> None:
    kit.not_found = {f"roster/{ALL[1]}/2025"}

    with pytest.raises(FeedUnavailableError):
        await kit.serve_season("2025")

    assert read_by_id(kit.path, KIND, "2025") is None


@pytest.mark.anyio
async def test_leader_and_award_names_come_from_the_box_score_rosters(
    kit: SeasonPlayoffsKit,
) -> None:
    feed = PlayoffsFeed.model_validate_json(await kit.serve_season("2025"))

    assert feed.leaders is not None and feed.awards is not None
    names = [row.name for group in feed.leaders for row in group.leaders]
    names += [w.name for a in feed.awards for w in a.winners]
    assert names and all(name.startswith("Box ") for name in names)
    assert feed.build_version == SEASON_BUILD_VERSION


class TradedRosters:
    """Player "1" is on two rosters: the team that sorts first has his newest game."""

    def __init__(self, kit: SeasonPlayoffsKit, newer: str, older: str) -> None:
        self.kit = kit
        self.times = {
            newer: dt.datetime(2025, 6, 1, tzinfo=dt.UTC),
            older: dt.datetime(2025, 2, 1, tzinfo=dt.UTC),
        }

    async def roster(self, code: str, season: int) -> list[BoxScoreRosterEntry]:
        entries = [
            BoxScoreRosterEntry(
                player_id=entry.player_id,
                display_name=f"Box {player_name(entry)}",
                jersey=entry.jersey,
                position_abbreviation=None,
                headshot_url=entry.headshot_url,
            )
            for entry in self.kit.box_players(code)
            if entry.player_id != "1"
        ]
        if code in self.times:
            entries.append(
                BoxScoreRosterEntry(
                    player_id="1",
                    display_name="Box Traded",
                    jersey=None,
                    position_abbreviation=None,
                    headshot_url=None,
                    last_played=self.times[code],
                )
            )
        return entries


@pytest.mark.anyio
async def test_a_player_on_two_rosters_belongs_to_the_team_of_his_newest_game(
    kit: SeasonPlayoffsKit,
) -> None:
    newer, older = "ATL", "WAS"
    assert newer < older
    kit.season_playoffs._rosters = cast(SeasonRosters, TradedRosters(kit, newer, older))

    feed = PlayoffsFeed.model_validate_json(await kit.serve_season("2025"))

    assert feed.leaders is not None and feed.awards is not None
    rows = [r for g in feed.leaders for r in g.leaders if r.player_id == "1"]
    winners = [w for a in feed.awards for w in a.winners if w.player_id == "1"]
    assert rows and winners
    assert {r.team_code for r in rows} == {newer}
    assert {w.team_code for w in winners} == {newer}


@pytest.mark.anyio
@pytest.mark.parametrize("version", [None, SEASON_BUILD_VERSION + 1])
async def test_a_stored_feed_with_an_older_or_missing_version_is_rebuilt_on_its_next_request(
    kit: SeasonPlayoffsKit, version: int | None
) -> None:
    await kit.serve_season("2025")
    stored = kit.stored("2025")
    assert stored is not None
    publish_by_id(
        kit.path,
        KIND,
        PlayoffsFeed,
        "2025",
        stored.model_copy(update={"build_version": version}),
    )
    kit.calls.clear()

    served = PlayoffsFeed.model_validate_json(
        await kit.serve_season("2025", NOW + YEARS)
    )

    assert served.build_version == version
    assert kit.called("standings/") == 1
    rebuilt = kit.stored("2025")
    assert rebuilt is not None and rebuilt.build_version == SEASON_BUILD_VERSION


@pytest.mark.anyio
async def test_a_stored_feed_with_the_current_version_is_served_with_no_source_request(
    kit: SeasonPlayoffsKit,
) -> None:
    await kit.serve_season("2025")
    kit.calls.clear()

    await kit.serve_season("2025", NOW + YEARS)

    assert kit.calls == []


@pytest.mark.anyio
async def test_a_team_info_failure_only_nulls_the_colors(
    kit: SeasonPlayoffsKit,
) -> None:
    kit.failing = {f"info/{ALL[0]}"}

    feed = PlayoffsFeed.model_validate_json(await kit.serve_season("2025"))

    team = feed.picture[0].rows[0].team
    assert str(team.code) == ALL[0] and team.colors.primary is None
    assert feed.picture[0].rows[1].team.colors.primary is not None


@pytest.mark.anyio
async def test_a_derivation_that_does_not_give_8_4_2_1_answers_unavailable_and_logs(
    kit: SeasonPlayoffsKit, caplog: pytest.LogCaptureFixture
) -> None:
    extra = series_games(seed(EAST, 9), seed(EAST, 10), 1, "T", key="x")
    kit.load(without_rounds(past_games() + extra))

    with caplog.at_level(logging.WARNING), pytest.raises(FeedUnavailableError):
        await kit.serve_season("2025")

    assert read_by_id(kit.path, KIND, "2025") is None
    messages = [r.getMessage() for r in caplog.records]
    assert any(
        "2025" in m and "derived rounds give 9-4-2-1 series, not 8-4-2-1" in m
        for m in messages
    )


@pytest.mark.anyio
async def test_a_postseason_that_is_not_complete_answers_unavailable_and_stores_nothing(
    kit: SeasonPlayoffsKit, caplog: pytest.LogCaptureFixture
) -> None:
    kit.load([g for g in past_games() if not g.game.id.startswith("finals-")])

    with caplog.at_level(logging.WARNING), pytest.raises(FeedUnavailableError):
        await kit.serve_season("2025")

    assert read_by_id(kit.path, KIND, "2025") is None


@pytest.mark.anyio
async def test_a_season_without_seeds_has_null_side_seeds(
    kit: SeasonPlayoffsKit,
) -> None:
    kit.standing = standings(
        season=2025, changes={code: {"playoff_seed": None} for code in ALL}
    )
    kit.load(without_rounds(past_games()))

    feed = PlayoffsFeed.model_validate_json(await kit.serve_season("2025"))

    assert feed.state is PlayoffsState.COMPLETE
    assert all(s.seed is None for x in feed.bracket for s in (x.top, x.bottom))
    assert next(x for x in feed.bracket if x.id is SeriesId.FINALS).games


@pytest.mark.anyio
@pytest.mark.parametrize("season", ["1993", "2027", "2028", "abc", "2025\n"])
async def test_an_invalid_id_answers_unknown_with_no_source_request(
    kit: SeasonPlayoffsKit, season: str
) -> None:
    with pytest.raises(UnknownFeedError):
        await kit.cache.serve(KIND, season)

    assert kit.calls == []


@pytest.mark.anyio
async def test_an_unknown_current_season_answers_unavailable_with_no_source_request(
    kit: SeasonPlayoffsKit,
) -> None:
    kit.stars.season = None

    with pytest.raises(FeedUnavailableError):
        await kit.cache.serve(KIND, "2025")

    assert kit.calls == []


@pytest.mark.anyio
async def test_detail_is_never_available(kit: SeasonPlayoffsKit) -> None:
    feed = PlayoffsFeed.model_validate_json(await kit.serve_season("2025"))

    assert all(game.detail_available is False for s in feed.bracket for game in s.games)


@pytest.mark.anyio
async def test_the_cleanup_keeps_the_feed(kit: SeasonPlayoffsKit) -> None:
    body = await kit.serve_season("2025")

    kit.cache.cleanup()

    assert read_by_id(kit.path, KIND, "2025") == body
