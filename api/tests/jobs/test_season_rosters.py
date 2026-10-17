# api/tests/jobs/test_season_rosters.py
#
# Tests for the box-score roster of a team in a past season.
#
# Tested:
# - The roster is exactly the team's players of its final regular-season and playoff games, in jersey order
# - Jersey and position come from the newest game with a value; name and photo from the newest game
# - Each entry carries the start of its newest game
# - A game stored in the state is reused with no read
# - A stored past game detail is reused with no read and its players have no jersey
# - A stored game and a stored past game detail of an older or missing build version are read again, and a stored game carries the current version (ADR 0055)
# - A game read for one team is not read again for its opponent, also when both rosters are asked at once
# - A failed game read fails the roster, and a failed schedule read too
# - The dates of the final games are registered, and only the final ones
# - Game summaries are read one at a time with the configured pause, also for two rosters asked at once
# - A zero pause never sleeps, and a read after an idle time longer than the pause does not wait
# - A 429 or 503 answer stops the roster with the reason "rate limited", logs it and reads no further game
# - Every read is held for the retry window after a rate limit, also for another roster, and then reads again
# - Another error status fails the roster and holds nothing
#
# What is covered:
# - Roster union and field precedence: happy path, edges and errors
# - Reuse: the state, the stored past game detail and the shared read
# - Pacing: pause, one pacer for every build, rate limit and its hold
#
# Run with: cd api && .venv/bin/python -m pytest tests/jobs/test_season_rosters.py
#
# SEE: api/app/jobs/season_rosters.py

import asyncio
import datetime as dt
from pathlib import Path
from typing import Any, cast

import pytest

from app.jobs import past_game_detail_feed
from app.jobs.on_demand import RETRY_AFTER, SEASON_BUILD_VERSION, with_build_version
from app.jobs.season_rosters import SeasonRosters
from app.settings import Settings
from app.sources.game_detail import BoxScoreRosterEntry, GamePlayers
from app.sources.http import Freshness, SourceClient, SourceError
from app.sources.team_schedule import SeasonSchedule
from app.storage.feeds import publish_by_id
from app.storage.state import StateStore
from tests.jobs.test_past_game_detail_feed import full_sections, past_game
from tests.jobs.test_team_feed import game, played, season

FIRST = dt.datetime(2003, 11, 2, 3, 0, tzinfo=dt.UTC)
SECOND = dt.datetime(2003, 12, 2, 3, 0, tzinfo=dt.UTC)
PLAYOFFS = dt.datetime(2004, 4, 22, 1, 0, tzinfo=dt.UTC)
FUTURE = dt.datetime(2004, 4, 30, 1, 0, tzinfo=dt.UTC)


def entry(
    player_id: str,
    name: str | None = None,
    jersey: str | None = None,
    position: str | None = None,
    photo: str | None = None,
) -> BoxScoreRosterEntry:
    return BoxScoreRosterEntry(
        player_id=player_id,
        display_name=name or f"Player {player_id}",
        jersey=jersey,
        position_abbreviation=position,
        headshot_url=photo,
    )


def players(**teams: list[BoxScoreRosterEntry]) -> GamePlayers:
    return GamePlayers(teams=teams)


class Kit:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.store = StateStore(path)
        self.store.migrate()
        self.settings = Settings(_env_file=None, data_dir=path)  # type: ignore[call-arg]
        self.regular = season(played("g1", FIRST), played("g2", SECOND))
        self.playoffs = season(played("g3", PLAYOFFS, playoffs=True))
        self.by_game: dict[str, GamePlayers] = {}
        self.reads: list[str] = []
        self.schedule_calls: list[tuple[str, bool]] = []
        self.failing: set[str] = set()
        self.running = 0
        self.peak = 0
        self.delay = False
        self.now = dt.datetime(2026, 10, 17, 12, 0, tzinfo=dt.UTC)
        self.sleeps: list[float] = []
        self.spans: list[tuple[str, dt.datetime, dt.datetime]] = []
        self.status: dict[str, int] = {}
        self.schedules: dict[tuple[str, bool], SeasonSchedule] = {}

    def clock(self) -> dt.datetime:
        return self.now

    async def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += dt.timedelta(seconds=seconds)

    async def fetch_schedule(
        self,
        client: SourceClient,
        code: str,
        year: int,
        settings: Settings,
        *,
        playoffs: bool,
        by_id_first: bool = False,
    ) -> SeasonSchedule:
        assert by_id_first
        self.schedule_calls.append((code, playoffs))
        if (code, playoffs) in self.schedules:
            return self.schedules[(code, playoffs)]
        return self.playoffs if playoffs else self.regular

    async def fetch_players(
        self, client: SourceClient, game_id: str, settings: Settings, fresh: Freshness
    ) -> GamePlayers:
        self.reads.append(game_id)
        self.running += 1
        self.peak = max(self.peak, self.running)
        started = self.now
        try:
            if self.delay:
                await asyncio.sleep(0)
                await asyncio.sleep(0)
            if game_id in self.status:
                raise SourceError(
                    "test",
                    f"responded with status {self.status[game_id]}",
                    status_code=self.status[game_id],
                    request_failed=True,
                )
            if game_id in self.failing:
                raise SourceError("test", "summary is down")
            return self.by_game[game_id]
        finally:
            self.running -= 1
            self.spans.append((game_id, started, self.now))

    def rosters(self) -> SeasonRosters:
        return SeasonRosters(
            self.settings,
            self.store,
            cast(SourceClient, object()),
            fetch_season_schedule=self.fetch_schedule,
            fetch_game_players=self.fetch_players,
            clock=self.clock,
            sleep=self.sleep,
        )


@pytest.fixture
def kit(tmp_path: Path) -> Kit:
    built = Kit(tmp_path)
    built.by_game = {
        "g1": players(OKC=[entry("1", jersey="7", position="PG"), entry("2")]),
        "g2": players(OKC=[entry("1", jersey="7", position="PG")], DEN=[entry("9")]),
        "g3": players(OKC=[entry("3", jersey="3")]),
    }
    return built


@pytest.mark.anyio
async def test_the_roster_is_exactly_the_teams_players_of_its_final_games(
    kit: Kit,
) -> None:
    kit.regular = season(*kit.regular.games, game("g4", FUTURE))
    kit.by_game["g4"] = players(OKC=[entry("99")])

    roster = await kit.rosters().roster("OKC", 2004)

    assert [e.player_id for e in roster] == ["3", "1", "2"]
    assert "g4" not in kit.reads
    assert sorted(kit.schedule_calls) == [("OKC", False), ("OKC", True)]


@pytest.mark.anyio
async def test_jersey_and_position_come_from_the_newest_game_with_a_value_and_name_and_photo_from_the_newest_game(
    kit: Kit,
) -> None:
    kit.by_game["g1"] = players(
        OKC=[entry("1", "Old Name", "5", "SG", "https://example.com/old.png")]
    )
    kit.by_game["g2"] = players(
        OKC=[entry("1", "New Name", None, "PG", "https://example.com/new.png")]
    )
    kit.by_game["g3"] = players(OKC=[entry("1", "Newest Name", None, None, None)])

    roster = await kit.rosters().roster("OKC", 2004)

    assert len(roster) == 1
    assert roster[0].display_name == "Newest Name"
    assert roster[0].headshot_url is None
    assert roster[0].jersey == "5"
    assert roster[0].position_abbreviation == "PG"


@pytest.mark.anyio
async def test_each_entry_carries_the_start_of_its_newest_game(kit: Kit) -> None:
    roster = await kit.rosters().roster("OKC", 2004)

    assert {e.player_id: e.last_played for e in roster} == {
        "1": SECOND,
        "2": FIRST,
        "3": PLAYOFFS,
    }


@pytest.mark.anyio
async def test_a_game_stored_in_the_state_is_reused_with_no_read(kit: Kit) -> None:
    await kit.rosters().roster("OKC", 2004)
    assert sorted(kit.reads) == ["g1", "g2", "g3"]
    kit.reads.clear()

    roster = await kit.rosters().roster("OKC", 2004)

    assert kit.reads == []
    assert [e.player_id for e in roster] == ["3", "1", "2"]


@pytest.mark.anyio
async def test_a_stored_past_game_detail_is_reused_with_no_read_and_its_players_have_no_jersey(
    kit: Kit,
) -> None:
    detail = with_build_version(
        past_game_detail_feed.build_past_game_detail_feed(
            past_game("g1"), full_sections()
        )
    )
    assert publish_by_id(
        kit.path, past_game_detail_feed.KIND, type(detail), "g1", detail
    )

    roster = await kit.rosters().roster("OKC", 2004)

    assert sorted(kit.reads) == ["g2", "g3"]
    by_id = {e.player_id: e for e in roster}
    assert by_id["p1"].display_name == "First Last"
    assert by_id["p1"].jersey is None
    assert by_id["p1"].position_abbreviation is None
    assert by_id["p1"].headshot_url == "https://example.com/photo.png"
    stored = kit.store.past_game_players("g1")
    assert stored is not None and "First Last" in stored


@pytest.mark.anyio
@pytest.mark.parametrize("version", [None, SEASON_BUILD_VERSION + 1])
async def test_a_stored_past_game_detail_of_an_older_or_missing_version_is_not_reused(
    kit: Kit, version: int | None
) -> None:
    detail = past_game_detail_feed.build_past_game_detail_feed(
        past_game("g1"), full_sections()
    ).model_copy(update={"build_version": version})
    assert publish_by_id(
        kit.path, past_game_detail_feed.KIND, type(detail), "g1", detail
    )

    await kit.rosters().roster("OKC", 2004)

    assert sorted(kit.reads) == ["g1", "g2", "g3"]


@pytest.mark.anyio
async def test_a_stored_game_carries_the_current_build_version(kit: Kit) -> None:
    await kit.rosters().roster("OKC", 2004)

    stored = kit.store.past_game_players("g1")
    assert stored is not None
    assert GamePlayers.model_validate_json(stored).build_version == SEASON_BUILD_VERSION


@pytest.mark.anyio
@pytest.mark.parametrize("version", [None, SEASON_BUILD_VERSION + 1])
async def test_a_stored_game_of_an_older_or_missing_version_is_read_again(
    kit: Kit, version: int | None
) -> None:
    await kit.rosters().roster("OKC", 2004)
    for game_id in ("g1", "g2", "g3"):
        stored = kit.store.past_game_players(game_id)
        assert stored is not None
        old = GamePlayers.model_validate_json(stored).model_copy(
            update={"build_version": version}
        )
        kit.store.set_past_game_players(
            game_id, dt.date(2004, 1, 1), old.model_dump_json()
        )
    kit.reads.clear()

    await kit.rosters().roster("OKC", 2004)

    assert sorted(kit.reads) == ["g1", "g2", "g3"]
    stored = kit.store.past_game_players("g1")
    assert stored is not None
    assert GamePlayers.model_validate_json(stored).build_version == SEASON_BUILD_VERSION


@pytest.mark.anyio
async def test_a_game_read_for_one_team_is_not_read_again_for_its_opponent(
    kit: Kit,
) -> None:
    rosters = kit.rosters()
    kit.delay = True

    okc, den = await asyncio.gather(
        rosters.roster("OKC", 2004), rosters.roster("DEN", 2004)
    )

    assert sorted(kit.reads) == ["g1", "g2", "g3"]
    assert [e.player_id for e in okc] == ["3", "1", "2"]
    assert [e.player_id for e in den] == ["9"]
    await rosters.roster("DEN", 2004)
    assert sorted(kit.reads) == ["g1", "g2", "g3"]


@pytest.mark.anyio
async def test_a_failed_game_read_fails_the_roster(kit: Kit) -> None:
    kit.failing = {"g2"}

    with pytest.raises(SourceError):
        await kit.rosters().roster("OKC", 2004)


@pytest.mark.anyio
async def test_a_failed_schedule_read_fails_the_roster(kit: Kit) -> None:
    async def failing(*args: Any, **kwargs: Any) -> SeasonSchedule:
        raise SourceError("test", "schedule is down")

    rosters = SeasonRosters(
        kit.settings,
        kit.store,
        cast(SourceClient, object()),
        fetch_season_schedule=failing,
        fetch_game_players=kit.fetch_players,
        clock=kit.clock,
        sleep=kit.sleep,
    )

    with pytest.raises(SourceError):
        await rosters.roster("OKC", 2004)


@pytest.mark.anyio
async def test_the_dates_of_the_final_games_are_registered(kit: Kit) -> None:
    kit.regular = season(*kit.regular.games, game("g4", FUTURE))

    await kit.rosters().roster("OKC", 2004)

    assert kit.store.past_game_date("g1") == dt.date(2003, 11, 1)
    assert kit.store.past_game_date("g3") == dt.date(2004, 4, 21)
    assert kit.store.past_game_date("g4") is None


def many_games(kit: Kit, count: int) -> list[str]:
    ids = [f"x{n}" for n in range(count)]
    kit.regular = season(
        *(played(i, FIRST + dt.timedelta(days=n)) for n, i in enumerate(ids))
    )
    kit.playoffs = season()
    kit.by_game = {i: players(OKC=[entry(i)]) for i in ids}
    return ids


def gaps(kit: Kit) -> list[float]:
    return [
        (later[1] - earlier[2]).total_seconds()
        for earlier, later in zip(kit.spans, kit.spans[1:], strict=False)
    ]


@pytest.mark.anyio
async def test_games_are_read_one_at_a_time_with_the_configured_pause(
    kit: Kit,
) -> None:
    ids = many_games(kit, 6)
    kit.delay = True

    roster = await kit.rosters().roster("OKC", 2004)

    assert len(roster) == len(ids)
    assert kit.peak == 1
    assert len(kit.sleeps) == len(ids) - 1
    assert all(gap >= 0.25 for gap in gaps(kit))


@pytest.mark.anyio
async def test_two_rosters_asked_at_once_share_one_pacer(kit: Kit) -> None:
    kit.schedules = {
        ("OKC", False): season(played("g1", FIRST), played("g2", SECOND)),
        ("OKC", True): season(),
        ("DEN", False): season(played("d1", FIRST), played("d2", SECOND)),
        ("DEN", True): season(),
    }
    kit.by_game |= {
        "d1": players(DEN=[entry("8")]),
        "d2": players(DEN=[entry("9")]),
    }
    kit.delay = True
    rosters = kit.rosters()

    await asyncio.gather(rosters.roster("OKC", 2004), rosters.roster("DEN", 2004))

    assert sorted(kit.reads) == ["d1", "d2", "g1", "g2"]
    assert kit.peak == 1
    assert all(gap >= 0.25 for gap in gaps(kit))


@pytest.mark.anyio
async def test_a_zero_pause_never_sleeps(kit: Kit) -> None:
    kit.settings = Settings(  # type: ignore[call-arg]
        _env_file=None, data_dir=kit.path, source_build_pause_ms=0
    )
    many_games(kit, 4)

    await kit.rosters().roster("OKC", 2004)

    assert kit.sleeps == []


@pytest.mark.anyio
async def test_a_read_after_an_idle_time_longer_than_the_pause_does_not_wait(
    kit: Kit,
) -> None:
    rosters = kit.rosters()
    await rosters.game_players("g1", dt.date(2003, 11, 1))
    kit.now += dt.timedelta(seconds=1)

    await rosters.game_players("g2", dt.date(2003, 12, 1))

    assert kit.sleeps == []


@pytest.mark.anyio
@pytest.mark.parametrize("status", [429, 503])
async def test_a_rate_limited_read_stops_the_roster_with_no_further_game_read(
    kit: Kit, status: int, caplog: pytest.LogCaptureFixture
) -> None:
    ids = many_games(kit, 5)
    kit.status = {ids[1]: status}

    with (
        caplog.at_level("WARNING", logger="app.jobs.season_rosters"),
        pytest.raises(SourceError) as raised,
    ):
        await kit.rosters().roster("OKC", 2004)

    assert raised.value.reason == "rate limited"
    assert kit.reads == ids[:2]
    records = [r for r in caplog.records if r.name == "app.jobs.season_rosters"]
    assert len(records) == 1
    assert "rate limited" in records[0].getMessage()
    assert str(status) in records[0].getMessage()
    assert "example.com" not in records[0].getMessage()


@pytest.mark.anyio
async def test_reads_are_held_for_the_retry_window_after_a_rate_limit_also_for_another_roster(
    kit: Kit,
) -> None:
    rosters = kit.rosters()
    kit.status = {"g1": 429}
    with pytest.raises(SourceError):
        await rosters.roster("OKC", 2004)
    kit.status = {}
    reads = len(kit.reads)

    kit.now += RETRY_AFTER - dt.timedelta(seconds=1)
    with pytest.raises(SourceError) as held:
        await rosters.roster("DEN", 2004)
    assert held.value.reason == "rate limited"
    assert len(kit.reads) == reads

    kit.now += dt.timedelta(seconds=1)
    assert [e.player_id for e in await rosters.roster("DEN", 2004)] == ["9"]
    assert len(kit.reads) > reads


@pytest.mark.anyio
async def test_another_error_status_fails_the_roster_without_holding_reads(
    kit: Kit,
) -> None:
    rosters = kit.rosters()
    kit.status = {"g1": 500}
    with pytest.raises(SourceError) as failed:
        await rosters.roster("OKC", 2004)
    assert failed.value.reason != "rate limited"
    kit.status = {}

    assert [e.player_id for e in await rosters.roster("OKC", 2004)] == ["3", "1", "2"]
