# api/tests/jobs/test_season_player_feed.py
#
# Tests for the player feed of a past season and its feed kind.
#
# Tested:
# - The builder takes the game log, the last five games, the summary (ranks null), the averages and the milestones of that season from the two career stats, and takes the team given
# - The builder takes the career seasons, sets the season label, leaves the injury, next game and live block null, and the number, the draft and the awards null (ADR 0059)
# - A season with no game log has a null game log, no last games and a null team, and the feed still validates
# - The newest team id skips an All-Star game, a preseason game and a team outside the 30
# - The kind: the game log carries the season, the career stats do not, and no season stats, draft, awards, standings or roster read is sent
# - The kind: an id on a current roster or in the stored past feeds is known; any other id, an id with a trailing newline, 1993, the current season, a future season and an ill-formed id answer unknown with no source request; an unknown current season is not ready
# - The kind: an id no stored past data knows is not ready until the rosters are fetched, then unknown with no source request; an id known from stored past data never waits
# - The kind: the team is named from the stored names run of the season and is null without it, and a null team is named when served once the names are stored
# - The kind: the opponents of the game log are named from the game log payload with no season names read, and every log game has detail available and is registered
# - The kind: the feed is built once and kept across a simulated restart and years later
# - The kind: the built feed carries the current build version, a stored feed of an older or missing version is rebuilt on its next request, and one of the current version is served with no source request (ADR 0053)
# - The kind: the career rows carry the season codes of the stored franchise names when served, with no season team read per row; a list stored later reaches the next serve with no player rebuild; a missing list gives null entries and a serve never starts a names build (ADR 0055, ADR 0065)
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
from app.feeds.team import NameRun, TeamNames
from app.jobs.on_demand import (
    SEASON_BUILD_VERSION,
    FeedCache,
    FeedUnavailableError,
    IdStatus,
    UnknownFeedError,
    with_build_version,
)
from app.jobs.past_player_ids import PastPlayerIds
from app.jobs.player_feed import PlayerBuildError
from app.jobs.season_player_feed import (
    KIND,
    SeasonPlayerFeeds,
    build_season_player_feed,
    newest_team_id,
)
from app.jobs.stars import StarsJob
from app.jobs.team_names import KIND as NAMES_KIND
from app.jobs.team_names import SeasonIdentity, TeamNamesFeeds
from app.settings import Settings
from app.sources.http import SourceClient, SourceError, create_client
from app.sources.player_draft import PlayerAthlete
from app.sources.player_gamelog import PlayerGameLog
from app.sources.player_stats import PlayerStats
from app.sources.season_team import SeasonTeam
from app.sources.teams import SeasonTeamName
from app.storage.feeds import publish_by_id, read_by_id
from app.storage.state import StateStore
from tests.jobs.test_player_feed import (
    line,
    log_game,
    misc,
    player,
    totals_line,
)

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
        misc=[misc("2003-04", double_doubles=11), misc("2002-03")],
        career_per_game=line(None, games_played=514, games_started=514),
        career_totals=totals_line(None, field_goals="5052-10778"),
        career_misc=misc(None, double_doubles=273),
    )


def playoffs_stats(points: float = 30.0) -> PlayerStats:
    return PlayerStats(
        per_game=[line(LABEL, points=points)],
        totals=[totals_line(LABEL)],
        misc=[misc(LABEL)],
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
    return PlayerGameLog(
        season=LABEL,
        games=games,
        teams={
            "SAS": SeasonTeamName(
                abbreviation="SAS", name="Harbor Rays", location="San Antonio"
            )
        },
    )


def team(season_code: str | None = None) -> Team:
    return Team(
        code="MEM", name="Lakeside Pines", city="Vancouver", season_code=season_code
    )


def build(
    *,
    log: PlayerGameLog | None = None,
    regular: PlayerStats | None = None,
    playoffs: PlayerStats | None = None,
    the_team: Team | None = None,
    opponent_names: dict[str, SeasonIdentity] | None = None,
) -> PastPlayerFeed:
    return build_season_player_feed(
        "77",
        2004,
        athlete(),
        the_team,
        log or season_log(),
        career_stats() if regular is None else regular,
        PlayerStats() if playoffs is None else playoffs,
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


def test_the_number_the_draft_and_the_awards_are_null_never_the_athletes() -> None:
    assert athlete().entry.jersey is not None

    feed = build()

    assert feed.number is None
    assert feed.profile.draft is None
    assert feed.awards is None


def test_the_opponents_of_the_game_log_are_named_by_the_names_given() -> None:
    feed = build(
        opponent_names={"SAS": SeasonIdentity("Harbor Gulls", "Seattle", "SEA", True)}
    )

    assert feed.game_log is not None
    assert {
        (
            e.opponent.code,
            e.opponent.name,
            e.opponent.city,
            e.opponent.season_code,
            e.opponent.historical,
        )
        for e in feed.game_log.entries
        if e.opponent is not None
    } == {("SAS", "Harbor Gulls", "Seattle", "SEA", True)}


def test_the_summary_is_that_seasons_row_with_null_ranks() -> None:
    feed = build()

    assert feed.summary is not None
    assert feed.summary.season == LABEL
    assert feed.summary.points.value == 21.4
    assert feed.summary.points.rank is None
    assert feed.summary.field_goal_pct.rank is None
    assert feed.summary.field_goal_pct.value == 0.476


def test_the_averages_and_milestones_come_from_the_two_career_stats() -> None:
    feed = build(playoffs=playoffs_stats(30.0))

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


def test_the_builder_takes_the_team_given_and_the_career_seasons() -> None:
    feed = build(the_team=team())

    assert feed.team == team()
    assert [row.season for row in feed.seasons.regular.per_game] == [
        "2003-04",
        "2002-03",
    ]
    assert feed.profile.seasons == 2
    assert feed.season_label == LABEL
    assert (feed.injury, feed.next_game, feed.live) == (None, None, None)
    assert feed.active is False
    assert feed.profile.age == 25


def test_a_season_with_no_game_log_has_no_game_log_no_last_games_and_no_team() -> None:
    feed = build(log=PlayerGameLog(season=None, games=[]), regular=PlayerStats())

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
            "77", 2004, no_position, None, season_log(),
            career_stats(), PlayerStats(),
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
        super().__init__(Path("unused"), StateStore(Path("unused")))
        self._given = ids

    def known(self, player_id: str) -> bool:
        return player_id in self._given

    def known_in_season(self, player_id: str) -> bool:
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
        self.season_names: dict[str, tuple[str, str]] = {}
        # The current season's team object by code, when it differs.
        self.current_names: dict[str, tuple[str, str]] = {}
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
        self.kind = SeasonPlayerFeeds(
            self.settings,
            self.store,
            self.client,
            self.cache,
            cast(StarsJob, self.stars),
            KnownIds(self.past),
            self.names,
            fetch_player_athlete=self.fetch_athlete,
            fetch_player_gamelog=self.fetch_gamelog,
            fetch_player_stats=self.fetch_stats,
        )

    def publish_names(self, code: str, runs: list[NameRun]) -> None:
        """Stores a fresh names list of the current build for a franchise."""
        publish_by_id(
            self.path,
            NAMES_KIND,
            TeamNames,
            code.lower(),
            with_build_version(TeamNames(runs=runs)),
        )
        self.store.record_build(NAMES_KIND, code.lower(), self.clock[0])

    async def fetch_athlete(
        self, client: SourceClient, player_id: str, settings: Settings
    ) -> PlayerAthlete:
        self.calls.append(f"athlete/{player_id}")
        return athlete()

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
    ) -> PlayerStats:
        self.calls.append(f"stats/{playoffs}")
        return PlayerStats() if playoffs else career_stats()

    async def fetch_season_team(
        self, client: SourceClient, code: str, season: int, settings: Settings
    ) -> SeasonTeam | None:
        self.calls.append(f"season-team/{code}/{season}")
        names = self.current_names if season == 2027 else self.season_names
        name, city = names.get(code, ("Lakeside Pines", "Vancouver"))
        return SeasonTeam(
            team_id="29",
            abbreviation="VAN",
            display_name=f"{city} {name}",
            name=name,
            location=city,
        )

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
async def test_the_game_log_carries_the_season_the_career_stats_do_not_and_no_other_read_is_sent(
    kit: SeasonPlayerKit,
) -> None:
    kit.publish_names(
        "mem",
        [
            NameRun(
                from_=1994,
                to=None,
                name="Lakeside Pines",
                location="Vancouver",
                code="VAN",
            )
        ],
    )

    feed = PastPlayerFeed.model_validate_json(await kit.serve("2004-77"))

    assert feed.season_label == LABEL
    assert feed.team == team("VAN")
    assert sorted(c for c in kit.calls if not c.startswith("season-team/")) == [
        "athlete/77",
        "gamelog/2004",
        "stats/False",
        "stats/True",
    ]


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
    assert kit.kind.check("2004-nobody") is IdStatus.NOT_READY
    assert kit.kind.check("2004-77") is IdStatus.KNOWN
    with pytest.raises(FeedUnavailableError):
        await kit.cache.serve(KIND, "2004-nobody")

    assert kit.calls == []


@pytest.mark.anyio
async def test_an_id_known_from_stored_past_data_is_known_before_the_rosters_are_fetched(
    kit: SeasonPlayerKit,
) -> None:
    kit.stars.ready = False

    assert kit.kind.check("2004-88") is IdStatus.KNOWN
    assert kit.calls == []


@pytest.mark.anyio
async def test_an_unknown_id_answers_unknown_with_no_source_request_once_the_rosters_are_fetched(
    kit: SeasonPlayerKit,
) -> None:
    kit.stars.ready = True

    assert kit.kind.check("2004-nobody") is IdStatus.UNKNOWN
    with pytest.raises(UnknownFeedError):
        await kit.cache.serve(KIND, "2004-nobody")

    assert kit.calls == []


@pytest.mark.anyio
async def test_the_feed_is_built_once_and_kept_across_a_restart_and_years_later(
    kit: SeasonPlayerKit,
) -> None:
    await kit.serve("2004-77")
    stored = read_by_id(kit.path, KIND, "2004-77")
    calls = len(kit.calls)
    await kit.serve("2004-77", NOW + YEARS)
    kit.start()
    await kit.serve("2004-77", NOW + 2 * YEARS)

    assert stored is not None
    assert len(kit.calls) == calls
    assert read_by_id(kit.path, KIND, "2004-77") == stored


def runs_of(code: str, middle: int = 2008) -> list[NameRun]:
    return [
        NameRun(
            from_=1994,
            to=middle,
            name="Harbor Gulls",
            location="Seattle",
            code=code,
        ),
        NameRun(
            from_=middle + 1,
            to=None,
            name="Thunder",
            location="Oklahoma City",
            code="OKC",
        ),
    ]


def career_codes(feed: PastPlayerFeed) -> list[list[str | None] | None]:
    rows = [*feed.seasons.regular.per_game, *feed.seasons.playoffs.per_game]
    return [row.season_codes for row in rows]


@pytest.mark.anyio
async def test_the_career_rows_carry_the_season_codes_of_the_stored_names_with_no_season_team_read(
    kit: SeasonPlayerKit,
) -> None:
    kit.publish_names("okc", runs_of("SEA"))

    feed = PastPlayerFeed.model_validate_json(await kit.serve("2004-77"))

    codes = career_codes(feed)
    assert codes and all(c == ["SEA"] for c in codes)
    assert not any(call.startswith("season-team/OKC") for call in kit.calls)
    assert kit.cache.in_flight == {}


@pytest.mark.anyio
async def test_a_names_list_stored_later_reaches_the_next_serve_with_no_player_rebuild(
    kit: SeasonPlayerKit,
) -> None:
    kit.publish_names("okc", runs_of("SEA"))
    await kit.serve("2004-77")
    stored = read_by_id(kit.path, KIND, "2004-77")
    calls = len(kit.calls)

    kit.publish_names("okc", runs_of("NJ"))
    feed = PastPlayerFeed.model_validate_json(await kit.serve("2004-77"))

    assert all(c == ["NJ"] for c in career_codes(feed))
    assert len(kit.calls) == calls
    assert read_by_id(kit.path, KIND, "2004-77") == stored


@pytest.mark.anyio
async def test_a_player_feed_serve_never_starts_a_names_build(
    kit: SeasonPlayerKit,
) -> None:
    body = await kit.cache.serve(KIND, "2004-77")
    first = PastPlayerFeed.model_validate_json(body)
    await kit.settle()

    assert career_codes(first) and all(c == [None] for c in career_codes(first))
    assert not any(call.startswith("season-team/") for call in kit.calls)
    assert not any(key[0] == "team-names" for key in kit.cache.in_flight)
    assert kit.names.stored("okc") is None
    second = PastPlayerFeed.model_validate_json(await kit.serve("2004-77"))
    assert all(c == [None] for c in career_codes(second))
    assert kit.names.stored("okc") is None


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
    await kit.serve("2004-77")
    stored = read_by_id(kit.path, KIND, "2004-77")

    kit.cache.cleanup()

    assert stored is not None
    assert read_by_id(kit.path, KIND, "2004-77") == stored


@pytest.mark.anyio
async def test_number_draft_and_awards_are_null_and_no_draft_awards_standings_or_roster_read(
    kit: SeasonPlayerKit,
) -> None:
    feed = PastPlayerFeed.model_validate_json(await kit.serve("2004-77"))

    assert athlete().entry.jersey is not None
    assert (feed.number, feed.profile.draft, feed.awards) == (None, None, None)
    assert not any(
        call.startswith(("draft", "awards", "standings", "schedule", "players"))
        for call in kit.calls
    )


@pytest.mark.anyio
async def test_the_summary_averages_and_milestones_come_from_the_two_career_stats_reads(
    kit: SeasonPlayerKit,
) -> None:
    feed = PastPlayerFeed.model_validate_json(await kit.serve("2004-77"))

    assert feed.summary is not None and feed.summary.points.value == 21.4
    assert feed.averages.regular is not None
    assert feed.averages.regular.season == LABEL
    assert feed.milestones is not None
    assert feed.milestones.current.double_doubles == 11


@pytest.mark.anyio
async def test_the_team_is_named_from_the_stored_names_run_of_the_season_and_null_without_it(
    kit: SeasonPlayerKit,
) -> None:
    kit.publish_names(
        "mem",
        [
            NameRun(
                from_=1994,
                to=2004,
                name="Lakeside Pines",
                location="Vancouver",
                code="VAN",
            ),
            NameRun(from_=2005, to=None, name="Bears", location="Memphis", code="MEM"),
        ],
    )

    named = PastPlayerFeed.model_validate_json(await kit.serve("2004-77"))
    assert named.team == team("VAN")


@pytest.mark.anyio
async def test_a_season_with_no_stored_names_run_has_a_null_team(
    kit: SeasonPlayerKit,
) -> None:
    feed = PastPlayerFeed.model_validate_json(await kit.cache.serve(KIND, "2004-77"))
    await kit.settle()

    stored = read_by_id(kit.path, KIND, "2004-77")
    assert stored is not None
    assert PastPlayerFeed.model_validate_json(stored).team is None
    assert feed.team is None


@pytest.mark.anyio
async def test_a_null_team_is_named_when_served_once_the_names_are_stored(
    kit: SeasonPlayerKit,
) -> None:
    first = PastPlayerFeed.model_validate_json(await kit.cache.serve(KIND, "2004-77"))
    await kit.settle()
    assert first.team is None
    kit.publish_names("okc", runs_of("SEA"))
    calls = len(kit.calls)

    served = PastPlayerFeed.model_validate_json(await kit.serve("2004-77"))

    assert served.team == Team(
        code="OKC", name="Harbor Gulls", city="Seattle", season_code="SEA"
    )
    assert len(kit.calls) == calls
    stored = read_by_id(kit.path, KIND, "2004-77")
    assert (
        stored is not None and PastPlayerFeed.model_validate_json(stored).team is None
    )


@pytest.mark.anyio
async def test_the_opponents_are_named_from_the_game_log_payload_with_no_season_names_read(
    kit: SeasonPlayerKit,
) -> None:
    kit.publish_names(
        "sas",
        [NameRun(from_=1994, to=None, name="Rays", location="San Antonio", code="SAS")],
    )

    feed = PastPlayerFeed.model_validate_json(await kit.serve("2004-77"))

    assert feed.game_log is not None
    assert {
        (e.opponent.code, e.opponent.name, e.opponent.city, e.opponent.historical)
        for e in feed.game_log.entries
        if e.opponent is not None
    } == {("SAS", "Harbor Rays", "San Antonio", True)}
    assert not any(call.startswith("season-team/SAS") for call in kit.calls)


@pytest.mark.anyio
async def test_every_log_game_has_detail_available_and_is_registered(
    kit: SeasonPlayerKit,
) -> None:
    feed = PastPlayerFeed.model_validate_json(await kit.serve("2004-77"))

    assert feed.game_log is not None
    assert all(e.detail_available for e in feed.game_log.entries)
    for n in range(1, 8):
        # 01:30 UTC is the evening of the day before on the US Eastern calendar.
        assert kit.store.past_game_date(f"g{n}", at=NOW) == dt.date(
            2003, 10, 31
        ) + dt.timedelta(days=n - 1)
    assert feed.build_version == SEASON_BUILD_VERSION


@pytest.mark.anyio
async def test_serving_a_feed_keeps_the_rows_of_its_games_past_the_daily_prune(
    kit: SeasonPlayerKit,
) -> None:
    day = dt.timedelta(days=1)
    await kit.serve("2004-77")
    await kit.serve("2004-77", NOW + 89 * day)

    kit.store.prune_past_games(NOW + 91 * day - 90 * day)

    for n in range(1, 8):
        assert kit.store.past_game_date(f"g{n}", at=NOW + 91 * day) is not None


@pytest.mark.anyio
async def test_a_feed_not_served_in_90_days_loses_the_rows_of_its_games(
    kit: SeasonPlayerKit,
) -> None:
    day = dt.timedelta(days=1)
    await kit.serve("2004-77")

    kit.store.prune_past_games(NOW + 91 * day - 90 * day)

    assert kit.store.past_game_date("g1", at=NOW + 91 * day) is None


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
