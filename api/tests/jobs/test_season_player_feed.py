# api/tests/jobs/test_season_player_feed.py
#
# Tests for the player feed of a past season and its feed kind.
#
# Tested:
# - The builder takes the game log, the last five games, the summary (ranks null), the averages and the milestones of that season, and names the team for that season
# - The builder takes the career seasons and awards, sets the season label and leaves the injury, next game and live block null
# - A season with no game log has a null game log, no last games and a null team, and the feed still validates
# - The newest team id skips an All-Star game, a preseason game and a team outside the 30
# - The kind: the game log and the stats of the season carry the season, the career stats do not, and the team is read for the season of the newest game
# - The kind: an id on a current roster or in the stored past feeds is known; any other id, an id with a trailing newline, 1993, the current season, a future season and an ill-formed id answer unknown with no source request; an unknown current season and rosters not yet fetched are not ready
# - The number is the jersey of that season's box scores, null when they carry none, never the athlete's
# - The opponents of the game log are named by that season's team object, and every log game has detail available and is registered
# - The kind: the feed is built once and kept across a simulated restart and years later
# - The kind: the built feed carries the current build version, a stored feed of an older or missing version is rebuilt on its next request, and one of the current version is served with no source request (ADR 0053)
# - The kind: a failed build with nothing stored answers unavailable
#
# What is covered:
# - Pure conversions: happy path, edges and errors; the built feed validates
# - Feed kind: success publishes a valid feed, failure with nothing stored is unavailable, kept for good
#
# Run with: cd api && .venv/bin/python -m pytest tests/jobs/test_season_player_feed.py
#
# SEE: api/app/jobs/season_player_feed.py

import asyncio
import datetime as dt
from pathlib import Path
from typing import Any, cast

import pytest

from app.feeds.games import Team
from app.feeds.player import PastPlayerFeed
from app.jobs.on_demand import (
    SEASON_BUILD_VERSION,
    FeedCache,
    FeedUnavailableError,
    IdStatus,
    UnknownFeedError,
)
from app.jobs.past_player_ids import PastPlayerIds
from app.jobs.player_feed import PlayerBuildError
from app.jobs.season_player_feed import (
    KIND,
    SeasonPlayerFeeds,
    build_season_player_feed,
    newest_team_id,
)
from app.jobs.season_rosters import SeasonRosters
from app.jobs.stars import StarsJob
from app.jobs.team_names import TeamNamesFeeds
from app.settings import Settings
from app.sources.division_standings import DivisionStandings
from app.sources.game_detail import BoxScoreRosterEntry, GamePlayers
from app.sources.http import Freshness, SourceClient, SourceError, create_client
from app.sources.player_draft import DraftPick, PlayerAthlete
from app.sources.player_gamelog import PlayerGameLog
from app.sources.player_overview import ProviderAward
from app.sources.player_stats import PlayerStats
from app.sources.season_team import SeasonTeam
from app.sources.team_schedule import SeasonSchedule
from app.storage.feeds import publish_by_id, read_by_id
from app.storage.state import StateStore
from tests.jobs.test_player_feed import (
    line,
    log_game,
    misc,
    player,
    standings,
    totals_line,
)
from tests.jobs.test_team_feed import played, season

NOW = dt.datetime(2026, 10, 8, 15, 0, tzinfo=dt.UTC)
YEARS = dt.timedelta(days=365 * 5)
LABEL = "2003-04"


def day(number: int) -> dt.datetime:
    return dt.datetime(2003, 11, number, 1, 30, tzinfo=dt.UTC)


def athlete(active: bool = False) -> PlayerAthlete:
    return PlayerAthlete(
        active=active, entry=player("77", birth_date=dt.date(1978, 3, 4))
    )


def career_stats() -> PlayerStats:
    return PlayerStats(
        per_game=[line("2003-04", points=21.44), line("2002-03", points=18.0)],
        totals=[totals_line("2003-04"), totals_line("2002-03")],
        misc=[misc("2003-04"), misc("2002-03")],
        career_per_game=line(None, games_played=514, games_started=514),
        career_totals=totals_line(None, field_goals="5052-10778"),
        career_misc=misc(None, double_doubles=273),
    )


def season_stats(points: float = 21.44) -> PlayerStats:
    return PlayerStats(
        per_game=[line(LABEL, points=points)],
        totals=[totals_line(LABEL)],
        misc=[misc(LABEL, double_doubles=11)],
        career_per_game=line(None, games_played=514, games_started=514),
        career_totals=totals_line(None, field_goals="5052-10778"),
        career_misc=misc(None, double_doubles=273),
    )


def season_log() -> PlayerGameLog:
    games = [
        log_game(
            f"g{n}",
            day(n),
            team_id="29",
            opponent={"code": "SAS", "name": None, "city": None, "guest": False},
        )
        for n in range(1, 8)
    ]
    return PlayerGameLog(season=LABEL, games=games)


def team() -> Team:
    return Team(code="MEM", name="Lakeside Pines", city="Vancouver")


def build(
    *,
    log: PlayerGameLog | None = None,
    season_regular: PlayerStats | None = None,
    season_playoffs: PlayerStats | None = None,
    the_team: Team | None = None,
    draft: DraftPick | None = None,
    provided: list[ProviderAward] | None = None,
    jersey: str | None = None,
    opponent_names: dict[str, tuple[str, str]] | None = None,
) -> PastPlayerFeed:
    return build_season_player_feed(
        "77",
        2004,
        athlete(),
        the_team,
        standings(),
        draft,
        provided or [],
        log or season_log(),
        career_stats(),
        PlayerStats(),
        season_regular or season_stats(),
        season_playoffs or PlayerStats(),
        jersey,
        opponent_names,
    )


def test_the_builder_takes_the_game_log_and_the_last_five_games_of_that_season() -> (
    None
):
    feed = build(the_team=team())

    assert feed.game_log is not None
    assert feed.game_log.season == LABEL
    assert len(feed.game_log.entries) == 7
    assert [g.game_id for g in feed.last_games] == ["g7", "g6", "g5", "g4", "g3"]
    assert all(g.detail_available for g in feed.last_games)
    assert all(e.detail_available for e in feed.game_log.entries)


def test_the_number_is_the_jersey_of_that_seasons_box_scores_and_never_the_athletes() -> (
    None
):
    assert athlete().entry.jersey is not None
    assert build(jersey="12").number == "12"
    assert build(jersey=None).number is None


def test_the_opponents_of_the_game_log_are_named_by_that_seasons_team_object() -> None:
    feed = build(opponent_names={"SAS": ("Harbor Gulls", "Seattle")})

    assert feed.game_log is not None
    assert {
        (e.opponent.code, e.opponent.name, e.opponent.city)
        for e in feed.game_log.entries
        if e.opponent is not None
    } == {("SAS", "Harbor Gulls", "Seattle")}


def test_the_summary_is_that_seasons_row_with_null_ranks() -> None:
    feed = build()

    assert feed.summary is not None
    assert feed.summary.season == LABEL
    assert feed.summary.points.value == 21.4
    assert feed.summary.points.rank is None
    assert feed.summary.field_goal_pct.rank is None
    assert feed.summary.field_goal_pct.value == 0.476


def test_the_averages_and_milestones_are_that_seasons_rows_and_the_career() -> None:
    feed = build(season_playoffs=season_stats(30.0))

    assert feed.averages.regular is not None
    assert (feed.averages.regular.season, feed.averages.regular.points) == (
        LABEL,
        21.44,
    )
    assert feed.averages.playoffs is not None
    assert feed.averages.playoffs.points == 30.0
    assert feed.averages.career is not None and feed.averages.career.games_played == 514
    assert feed.milestones is not None
    assert feed.milestones.season == LABEL
    assert feed.milestones.current.double_doubles == 11
    assert feed.milestones.career.double_doubles == 273


def test_the_builder_names_the_team_and_takes_the_career_seasons_and_awards() -> None:
    feed = build(
        the_team=team(),
        provided=[
            ProviderAward(name="All-Star", display_count="2x", seasons=[2003, 2004])
        ],
    )

    assert feed.team == team()
    assert [row.season for row in feed.seasons.regular.per_game] == [
        "2003-04",
        "2002-03",
    ]
    assert feed.profile.seasons == 2
    assert [(a.name, a.count) for a in feed.awards] == [("All-Star", 2)]
    assert feed.season_label == LABEL
    assert (feed.injury, feed.next_game, feed.live) == (None, None, None)
    assert feed.active is False
    assert feed.profile.age == 25


def test_a_season_with_no_game_log_has_no_game_log_no_last_games_and_no_team() -> None:
    feed = build(log=PlayerGameLog(season=None, games=[]), season_regular=PlayerStats())

    assert feed.game_log is None
    assert feed.last_games == []
    assert feed.team is None
    assert feed.summary is None
    assert feed.milestones is None
    assert feed.averages.regular is None
    PastPlayerFeed.model_validate_json(feed.model_dump_json())


def test_the_builder_fails_for_a_player_without_a_position() -> None:
    no_position = PlayerAthlete(
        active=True, entry=player("77", position_name=None, position_abbreviation=None)
    )

    with pytest.raises(PlayerBuildError):
        build_season_player_feed(
            "77", 2004, no_position, None, standings(), None, [], season_log(),
            career_stats(), PlayerStats(), season_stats(), PlayerStats(),
        )  # fmt: skip


def test_the_newest_team_id_skips_all_star_preseason_and_a_team_outside_the_30() -> (
    None
):
    opponent: dict[str, Any] = {
        "code": "SAS",
        "name": None,
        "city": None,
        "guest": False,
    }
    games = [
        log_game("a", day(1), team_id="29", opponent=opponent),
        log_game("b", day(2), team_id="99", opponent=opponent),
        log_game("c", day(3), team_id="25", opponent=opponent, preseason=True),
        log_game("d", day(4), team_id="25", opponent=None, note="NBA All-Star Game"),
        log_game("e", day(5), team_id=None, opponent=opponent),
    ]

    assert newest_team_id(PlayerGameLog(season=LABEL, games=games)) == "29"
    assert newest_team_id(PlayerGameLog(season=None, games=[])) is None


class FakeStars:
    def __init__(self) -> None:
        self.season: int | None = 2027
        self.ready = True
        self.on_roster: set[str] = set()

    def current_season(self) -> int | None:
        return self.season

    def rosters_ready(self) -> bool:
        return self.ready

    def player_team(self, player_id: str) -> str | None:
        return "OKC" if player_id in self.on_roster else None


class KnownIds(PastPlayerIds):
    def __init__(self, ids: set[str]) -> None:
        super().__init__(Path("unused"))
        self._given = ids

    def known(self, player_id: str) -> bool:
        return player_id in self._given


class SeasonPlayerKit:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.clock = [NOW]
        self.store = StateStore(path)
        self.store.migrate()
        self.settings = Settings(_env_file=None, data_dir=path)  # type: ignore[call-arg]
        self.client = create_client(self.store, clock=lambda: self.clock[0])
        self.stars = FakeStars()
        self.stars.on_roster.add("77")
        self.past: set[str] = {"88"}
        self.calls: list[str] = []
        self.failing = False
        self.jersey: str | None = "12"
        self.season_names: dict[str, tuple[str, str]] = {}
        self.start()

    def start(self) -> None:
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
        self.kind = SeasonPlayerFeeds(
            self.settings,
            self.store,
            self.client,
            self.cache,
            cast(StarsJob, self.stars),
            KnownIds(self.past),
            self.names,
            self.rosters,
            fetch_player_athlete=self.fetch_athlete,
            fetch_division_standings=self.fetch_standings,
            fetch_player_draft=self.fetch_draft,
            fetch_player_awards=self.fetch_awards,
            fetch_player_gamelog=self.fetch_gamelog,
            fetch_player_stats=self.fetch_stats,
        )

    async def fetch_athlete(
        self, client: SourceClient, player_id: str, settings: Settings
    ) -> PlayerAthlete:
        self.calls.append(f"athlete/{player_id}")
        return athlete()

    async def fetch_standings(
        self, client: SourceClient, settings: Settings
    ) -> DivisionStandings:
        self.calls.append("standings")
        return standings()

    async def fetch_draft(
        self, client: SourceClient, player_id: str, settings: Settings
    ) -> DraftPick | None:
        self.calls.append("draft")
        return None

    async def fetch_awards(
        self, client: SourceClient, player_id: str, settings: Settings
    ) -> list[ProviderAward]:
        self.calls.append("awards")
        return []

    async def fetch_gamelog(
        self,
        client: SourceClient,
        player_id: str,
        settings: Settings,
        *,
        season: int | None = None,
    ) -> PlayerGameLog:
        self.calls.append(f"gamelog/{season}")
        if self.failing:
            raise SourceError("test", "game log is down")
        return season_log()

    async def fetch_stats(
        self,
        client: SourceClient,
        player_id: str,
        settings: Settings,
        *,
        playoffs: bool,
        season: int | None = None,
    ) -> PlayerStats:
        self.calls.append(f"stats/{playoffs}/{season}")
        if playoffs:
            return PlayerStats()
        return season_stats() if season is not None else career_stats()

    async def fetch_season_team(
        self, client: SourceClient, code: str, season: int, settings: Settings
    ) -> SeasonTeam | None:
        self.calls.append(f"season-team/{code}/{season}")
        name, city = self.season_names.get(code, ("Lakeside Pines", "Vancouver"))
        return SeasonTeam(
            team_id="29",
            abbreviation="VAN",
            display_name=f"{city} {name}",
            name=name,
            location=city,
        )

    async def fetch_season_schedule(
        self,
        client: SourceClient,
        code: str,
        season_year: int,
        settings: Settings,
        *,
        playoffs: bool,
        by_id_first: bool = False,
    ) -> SeasonSchedule:
        self.calls.append(f"schedule/{code}/{season_year}/{playoffs}")
        if playoffs:
            return season()
        return season(*(played(f"g{n}", day(n)) for n in range(1, 8)))

    async def fetch_game_players(
        self, client: SourceClient, game_id: str, settings: Settings, fresh: Freshness
    ) -> GamePlayers:
        self.calls.append(f"players/{game_id}")
        entry = BoxScoreRosterEntry(
            player_id="77",
            display_name="Player 77",
            jersey=self.jersey,
            position_abbreviation="PG",
            headshot_url=None,
        )
        return GamePlayers(teams={"MEM": [entry]})

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


@pytest.fixture
def kit(tmp_path: Path) -> SeasonPlayerKit:
    return SeasonPlayerKit(tmp_path)


@pytest.mark.anyio
async def test_the_game_log_and_the_stats_of_the_season_carry_the_season_and_the_team_is_named_for_it(
    kit: SeasonPlayerKit,
) -> None:
    feed = PastPlayerFeed.model_validate_json(await kit.serve("2004-77"))

    assert feed.season_label == LABEL
    assert feed.team == team()
    assert "gamelog/2004" in kit.calls
    assert "stats/False/2004" in kit.calls and "stats/True/2004" in kit.calls
    assert "stats/False/None" in kit.calls and "stats/True/None" in kit.calls
    assert "season-team/MEM/2004" in kit.calls
    assert "standings" in kit.calls


@pytest.mark.anyio
async def test_an_id_on_a_roster_or_in_the_past_feeds_is_known(
    kit: SeasonPlayerKit,
) -> None:
    assert kit.kind.check("2004-77") is IdStatus.KNOWN
    assert kit.kind.check("1994-88") is IdStatus.KNOWN
    assert kit.kind.check("2026-77") is IdStatus.KNOWN
    assert kit.kind.check("2004-nobody") is IdStatus.UNKNOWN
    assert kit.calls == []


@pytest.mark.anyio
@pytest.mark.parametrize(
    "feed_id",
    [
        "1993-77",
        "2027-77",
        "2028-77",
        "abc-77",
        "2004",
        "2004-",
        "2004-7-7",
        "",
        "2004-77\n",
    ],
)
async def test_an_invalid_early_current_or_future_id_answers_unknown_with_no_source_request(
    kit: SeasonPlayerKit, feed_id: str
) -> None:
    with pytest.raises(UnknownFeedError):
        await kit.cache.serve(KIND, feed_id)

    assert kit.calls == []


@pytest.mark.anyio
async def test_an_unknown_current_season_or_rosters_not_fetched_are_not_ready(
    kit: SeasonPlayerKit,
) -> None:
    kit.stars.season = None
    assert kit.kind.check("2004-77") is IdStatus.NOT_READY
    assert kit.kind.check("1993-77") is IdStatus.UNKNOWN
    kit.stars.season = 2027
    kit.stars.ready = False
    assert kit.kind.check("2004-88") is IdStatus.NOT_READY
    assert kit.kind.check("2004-77") is IdStatus.KNOWN
    with pytest.raises(FeedUnavailableError):
        await kit.cache.serve(KIND, "2004-88")

    assert kit.calls == []


@pytest.mark.anyio
async def test_the_feed_is_built_once_and_kept_across_a_restart_and_years_later(
    kit: SeasonPlayerKit,
) -> None:
    first = await kit.serve("2004-77")
    calls = len(kit.calls)
    await kit.serve("2004-77", NOW + YEARS)
    kit.start()
    again = await kit.serve("2004-77", NOW + 2 * YEARS)

    assert again == first
    assert len(kit.calls) == calls
    assert read_by_id(kit.path, KIND, "2004-77") == first


@pytest.mark.anyio
async def test_a_failed_build_with_nothing_stored_answers_unavailable(
    kit: SeasonPlayerKit,
) -> None:
    kit.failing = True

    with pytest.raises(FeedUnavailableError):
        await kit.serve("2004-77")

    assert read_by_id(kit.path, KIND, "2004-77") is None


@pytest.mark.anyio
async def test_the_cleanup_keeps_the_feed(kit: SeasonPlayerKit) -> None:
    body = await kit.serve("2004-77")

    kit.cache.cleanup()

    assert read_by_id(kit.path, KIND, "2004-77") == body


@pytest.mark.anyio
async def test_the_number_is_the_jersey_of_that_seasons_box_scores(
    kit: SeasonPlayerKit,
) -> None:
    feed = PastPlayerFeed.model_validate_json(await kit.serve("2004-77"))

    assert feed.number == "12"
    assert "schedule/MEM/2004/False" in kit.calls
    assert "players/g1" in kit.calls


@pytest.mark.anyio
async def test_the_number_is_null_when_the_box_scores_carry_none_never_the_athletes(
    kit: SeasonPlayerKit,
) -> None:
    kit.jersey = None
    assert athlete().entry.jersey is not None

    feed = PastPlayerFeed.model_validate_json(await kit.serve("2004-77"))

    assert feed.number is None


@pytest.mark.anyio
async def test_the_team_and_the_opponents_are_named_by_that_seasons_team_object(
    kit: SeasonPlayerKit,
) -> None:
    kit.season_names = {"SAS": ("Harbor Gulls", "Seattle")}

    feed = PastPlayerFeed.model_validate_json(await kit.serve("2004-77"))

    assert feed.team == team()
    assert feed.game_log is not None
    assert {
        (e.opponent.code, e.opponent.name, e.opponent.city)
        for e in feed.game_log.entries
        if e.opponent is not None
    } == {("SAS", "Harbor Gulls", "Seattle")}


@pytest.mark.anyio
async def test_every_log_game_has_detail_available_and_is_registered(
    kit: SeasonPlayerKit,
) -> None:
    feed = PastPlayerFeed.model_validate_json(await kit.serve("2004-77"))

    assert feed.game_log is not None
    assert all(e.detail_available for e in feed.game_log.entries)
    for n in range(1, 8):
        # 01:30 UTC is the evening of the day before on the US Eastern calendar.
        assert kit.store.past_game_date(f"g{n}") == dt.date(
            2003, 10, 31
        ) + dt.timedelta(days=n - 1)
    assert feed.build_version == SEASON_BUILD_VERSION


@pytest.mark.anyio
@pytest.mark.parametrize("version", [None, SEASON_BUILD_VERSION + 1])
async def test_a_stored_feed_with_an_older_or_missing_version_is_rebuilt_on_its_next_request(
    kit: SeasonPlayerKit, version: int | None
) -> None:
    await kit.serve("2004-77")
    stored = PastPlayerFeed.model_validate_json(
        read_by_id(kit.path, KIND, "2004-77") or b""
    )
    old = stored.model_copy(update={"build_version": version})
    publish_by_id(kit.path, KIND, PastPlayerFeed, "2004-77", old)
    kit.calls.clear()

    served = PastPlayerFeed.model_validate_json(await kit.serve("2004-77", NOW + YEARS))

    assert served.build_version == version
    assert "gamelog/2004" in kit.calls
    rebuilt = PastPlayerFeed.model_validate_json(
        read_by_id(kit.path, KIND, "2004-77") or b""
    )
    assert rebuilt.build_version == SEASON_BUILD_VERSION


@pytest.mark.anyio
async def test_a_stored_feed_with_the_current_version_is_served_with_no_source_request(
    kit: SeasonPlayerKit,
) -> None:
    await kit.serve("2004-77")
    kit.calls.clear()

    await kit.serve("2004-77", NOW + YEARS)

    assert kit.calls == []
