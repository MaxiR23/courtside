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
# - At most MAX_GAME_READS games are read at once
#
# What is covered:
# - Roster union and field precedence: happy path, edges and errors
# - Reuse: the state, the stored past game detail and the shared read
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
from app.jobs.on_demand import SEASON_BUILD_VERSION, with_build_version
from app.jobs.season_rosters import MAX_GAME_READS, SeasonRosters
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
        return self.playoffs if playoffs else self.regular

    async def fetch_players(
        self, client: SourceClient, game_id: str, settings: Settings, fresh: Freshness
    ) -> GamePlayers:
        self.reads.append(game_id)
        self.running += 1
        self.peak = max(self.peak, self.running)
        try:
            if self.delay:
                await asyncio.sleep(0)
                await asyncio.sleep(0)
            if game_id in self.failing:
                raise SourceError("test", "summary is down")
            return self.by_game[game_id]
        finally:
            self.running -= 1

    def rosters(self) -> SeasonRosters:
        return SeasonRosters(
            self.settings,
            self.store,
            cast(SourceClient, object()),
            fetch_season_schedule=self.fetch_schedule,
            fetch_game_players=self.fetch_players,
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


@pytest.mark.anyio
async def test_at_most_max_game_reads_games_are_read_at_once(kit: Kit) -> None:
    ids = [f"x{n}" for n in range(MAX_GAME_READS * 3)]
    kit.regular = season(
        *(played(i, FIRST + dt.timedelta(days=n)) for n, i in enumerate(ids))
    )
    kit.playoffs = season()
    kit.by_game = {i: players(OKC=[entry(i)]) for i in ids}
    kit.delay = True

    roster = await kit.rosters().roster("OKC", 2004)

    assert len(roster) == len(ids)
    assert kit.peak == MAX_GAME_READS
