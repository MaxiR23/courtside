# api/tests/jobs/test_season_playoffs_feed.py
#
# Tests for the playoffs feed of a past season and its feed kind.
#
# Tested:
# - past_season_status through check: 1993, abc, 02025, 2025 with a trailing newline, the current season and a future season are unknown; 1994 and the season before the current one are known; an unknown current season is not ready for a well-formed id from 1994
# - target: the current season maps to the current playoffs feed, a past season to the season kind, and an unknown current season to the season kind
# - The kind: a past season builds a valid complete feed, reading the standings, 20 team schedules, the play-in window and days, the leaders, the awards, the Finals game players and one athlete read per leader and winner, and no postseason window, team info or roster (ADR 0058, ADR 0061)
# - The kind: a season before 2021 reads 16 team schedules and no play-in; a seedless standings reads the best records
# - The kind: the league sides are named from the standings payload with the season code and the historical flag, and name_sides is never called (ADR 0054, ADR 0058)
# - The kind: the leaders and award winners carry the season code of their team (ADR 0055)
# - The kind: an award of six winners, a tie, is stored with all six in the source order (ADR 0055)
# - The kind: leader and award names, photos and team links come from the player identities (ADR 0061)
# - The kind: a player whose athlete read fails is kept with his id and a dash
# - The kind: the leaders hold three per category; award winners past the declared maximum of 52 are shown with a dash and no photo, are not read and log one warning (ADR 0066)
# - The kind: a second build within 30 days reads no cached player; only the top three leaders of a category are read (ADR 0066)
# - The kind: a 2005 build names the leaders of the nine categories and the fourteen awards
# - The kind: the colors come from the cached team info and are null without it
# - The kind: the built feed carries BUILD_VERSION, a stored feed of an older, newer or missing version is rebuilt on its next request, and one of BUILD_VERSION is served with no source request (ADR 0053)
# - The kind: the feed is stored under season-playoffs and rebuilt only for another version: a second request, a request years later and a restart all serve with no source call; nothing is written under playoffs
# - The kind: a leaders or awards read that answers 404 is null; any other failure answers unavailable and stores nothing
# - The kind: a derivation that does not give 8-4-2-1 answers unavailable, stores nothing and logs the reason
# - The kind: a postseason that is not complete answers unavailable and stores nothing
# - The kind: a season without seeds has null side seeds
# - The kind: an invalid id answers unknown and a not ready season answers unavailable, with no source request
# - The kind: detailAvailable is false; the cleanup keeps it
# - Resolved colors (ADR 0072): a past feed is served with the series pairs and the champion's color, a historical side and a historical champion get null, and a stored feed written without the keys is served with them and no source request
# - The kind: a stored feed whose champion still carries the retired record, home, road and point differential is served without them, with no source request, and stored_player_ids reads it (ADR 0073)
# - The kind: a 2005 build whose schedules are read by the real adapter and send no name key builds the complete feed
# - The kind: a 2005 build from schedules that carry no series object and empty notes (seasonType and winner flags only) reaches the complete state with the derived series, Finals line and champion
# - schedule_teams and finals_games
# - The builder with no postseason window dates the postseason from the play-in window or the games
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
import json
import logging
from collections.abc import Iterator
from pathlib import Path
from typing import Any, cast

import pytest
import respx

from app.feeds.game_detail import Conference
from app.feeds.opponent import TeamColors
from app.feeds.playoffs import (
    AwardCode,
    LeaderCategory,
    PlayoffsFeed,
    PlayoffsState,
    SeriesId,
)
from app.feeds.team import NameRun, TeamNames
from app.jobs.on_demand import (
    SEASON_BUILD_VERSION,
    FeedCache,
    FeedUnavailableError,
    IdStatus,
    UnknownFeedError,
    with_build_version,
)
from app.jobs.player_identities import PlayerIdentities
from app.jobs.playoffs_feed import FEED_ID as PLAYOFFS_ID
from app.jobs.playoffs_feed import KIND as PLAYOFFS_KIND
from app.jobs.playoffs_feed import (
    PlayoffsBuildError,
    PlayoffsSources,
    build_playoffs_feed,
    with_accents,
)
from app.jobs.season_playoffs_feed import (
    BUILD_VERSION,
    KIND,
    LEADER_READS,
    MAX_AWARD_WINNERS,
    READ_BUDGET,
    SeasonPlayoffsFeeds,
    finals_games,
    schedule_teams,
    stored_player_ids,
)
from app.jobs.stars import StarsJob
from app.jobs.team_names import KIND as NAMES_KIND
from app.jobs.team_names import TeamNamesFeeds
from app.settings import Settings
from app.sources.division_standings import DivisionStandings
from app.sources.game_detail import BoxScoreRosterEntry, GamePlayers
from app.sources.http import SourceClient, SourceError, create_client
from app.sources.player_draft import PlayerAthlete
from app.sources.postseason_leaders import LeaderEntry, PostseasonLeaders
from app.sources.postseason_scoreboard import (
    PostseasonGame,
    fetch_postseason_schedule,
)
from app.sources.season_awards import AwardWinnerRef, SeasonAwards
from app.sources.season_types import SeasonWindow
from app.sources.team_info import TeamInfo
from app.sources.team_schedule import PROVIDER_CODES, season_schedule_url
from app.sources.teams import PROVIDER_IDS, TEAM_CODES
from app.storage.feeds import publish_by_id, read_by_id
from app.storage.state import StateStore, TeamIdentity
from tests.jobs.fake_season_teams import FakeSeasonTeams, league_sides
from tests.jobs.test_playoffs_feed import (
    ALL,
    EAST,
    NOW,
    PLAY_IN_WINDOW,
    POSTSEASON_WINDOW,
    TODAY,
    WEST,
    FakeStars,
    award,
    past_games,
    play_ins,
    player,
    post,
    seed,
    series_games,
    standings,
    without_rounds,
)
from tests.jobs.test_team_feed import info
from tests.sources.test_postseason_scoreboard import (
    SCHEDULE_FIXTURES,
    SCHEDULE_TEMPLATE,
)

YEARS = dt.timedelta(days=365 * 5)
CHAMPION = seed(EAST, 1)
RUNNER_UP = seed(WEST, 1)
FINALS = ["finals-1", "finals-2", "finals-3", "finals-4", "finals-5"]
PLAYERS_OF = {CHAMPION: range(1, 7), RUNNER_UP: range(7, 13)}
EASTERN_OFFSET = dt.timezone(dt.timedelta(hours=-4))


def box_entry(player_id: str, name: str | None = None) -> BoxScoreRosterEntry:
    return BoxScoreRosterEntry(
        player_id=player_id,
        display_name=name or f"Box Example Player{player_id}",
        jersey="1",
        position_abbreviation=None,
        headshot_url=f"https://example.com/{player_id}.png",
    )


def past_leaders(count: int = 5) -> PostseasonLeaders:
    """The leaders of the nine categories, each with the team link of a past
    leader: the player n is on the n-th team of the East."""
    return PostseasonLeaders(
        categories={
            category: [
                LeaderEntry(
                    player_id=str(n),
                    value=f"{30 - n}.0",
                    team_code=seed(EAST, n),
                )
                for n in range(1, count + 1)
            ]
            for category in LeaderCategory
        }
    )


def athlete_of(player_id: str) -> PlayerAthlete:
    return PlayerAthlete(
        active=False,
        entry=player(
            player_id,
            display_name=f"Identity Player{player_id}",
            headshot_url=f"https://example.com/h/{player_id}.png",
        ),
    )


class SeasonPlayoffsKit:
    """The season playoffs kind over one client and one clock, with fake adapters
    that record their calls in self.calls, raise a timeout on the names in
    self.failing and answer 404 on the names in self.not_found. The player
    identities are read as "athlete/{id}"."""

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
        self.calls: list[str] = []
        self.failing: set[str] = set()
        self.not_found: set[str] = set()
        self.games: list[PostseasonGame] = []
        self.standing: DivisionStandings | None = None
        self.awards_source: SeasonAwards | None = None
        self.leaders_source: PostseasonLeaders | None = None
        # Player ids added to the box score of each Finals side.
        self.extra_players: dict[str, list[str]] = {}
        self.stars = FakeStars()
        self.cache = FeedCache(path, self.store, clock=lambda: self.clock[0])
        self.season_teams = FakeSeasonTeams()
        self.load(past_games())
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
        self.identities = PlayerIdentities(
            self.settings,
            self.store,
            self.client,
            fetch_player_athlete=self.fetch_player_athlete,
        )
        self.season_playoffs = SeasonPlayoffsFeeds(
            self.settings,
            self.store,
            self.client,
            self.cache,
            cast(StarsJob, self.stars),
            self.team_names,
            self.identities,
            fetch_season_type=self.fetch_season_type,
            fetch_postseason_games=self.fetch_postseason_games,
            fetch_postseason_schedule=self.fetch_postseason_schedule,
            fetch_division_standings=self.fetch_division_standings,
            fetch_postseason_leaders=self.fetch_postseason_leaders,
            fetch_season_awards=self.fetch_season_awards,
            fetch_game_players=self.fetch_game_players,
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
        self.games = list(games)

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
        fresh: Any = None,
    ) -> list[PostseasonGame]:
        self.read(f"day/{day.isoformat()}/{by_id_first}")
        return [
            g
            for g in self.games
            if g.game.start_time.astimezone(EASTERN_OFFSET).date() == day
        ]

    async def fetch_postseason_schedule(
        self, client: SourceClient, code: str, season: int, settings: Settings
    ) -> list[PostseasonGame]:
        self.read(f"schedule/{code}/{season}")
        return [
            g
            for g in self.games
            if g.season_type == 3 and code in (g.game.home.code, g.game.away.code)
        ]

    async def fetch_division_standings(
        self, client: SourceClient, settings: Settings, *, season: int | None = None
    ) -> DivisionStandings:
        self.read(f"standings/{season}")
        return self.standing or standings(season=season or 2027)

    async def fetch_team_info(
        self, client: SourceClient, code: str, settings: Settings
    ) -> TeamInfo:
        """For the current playoffs feed, which the router tests build over this
        kit; a past build never calls it."""
        self.read(f"info/{code}")
        return info()

    async def fetch_postseason_leaders(
        self, client: SourceClient, season: int, settings: Settings
    ) -> PostseasonLeaders:
        self.read(f"leaders/{season}")
        return self.leaders_source or past_leaders()

    async def fetch_season_awards(
        self, client: SourceClient, season: int, settings: Settings
    ) -> SeasonAwards:
        self.read(f"awards/{season}")
        return self.awards_source or SeasonAwards(
            awards=[award(AwardCode.MVP, ["1"], team_code=CHAMPION)]
        )

    async def fetch_player_athlete(
        self, client: SourceClient, player_id: str, settings: Settings
    ) -> PlayerAthlete:
        self.read(f"athlete/{player_id}")
        return athlete_of(player_id)

    async def fetch_game_players(
        self, client: SourceClient, game_id: str, settings: Settings, fresh: object
    ) -> GamePlayers:
        self.read(f"players/{game_id}")
        return GamePlayers(
            teams={
                code: [
                    box_entry(str(n))
                    for n in [*numbers, *self.extra_players.get(code, [])]
                ]
                for code, numbers in PLAYERS_OF.items()
            }
        )

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


def schedule_payload(games: list[PostseasonGame]) -> dict[str, Any]:
    """The provider payload of a team schedule for these games, each side in the
    team shape of a recorded schedule: no name key, a display name and a
    location."""
    recorded = json.loads(
        (SCHEDULE_FIXTURES / "det-2005-playoffs.json").read_text(encoding="utf-8")
    )
    shape = recorded["events"][0]["competitions"][0]["competitors"][0]["team"]
    assert set(shape) == {
        "id",
        "abbreviation",
        "displayName",
        "location",
        "shortDisplayName",
        "logos",
        "links",
    }

    def team(side: Any) -> dict[str, Any]:
        return {
            **shape,
            "id": PROVIDER_IDS[side.code],
            "abbreviation": PROVIDER_CODES.get(side.code, side.code),
            "displayName": f"{side.city} {side.name}",
            "location": side.city,
            "shortDisplayName": side.name,
            "logos": [],
            "links": [],
        }

    events = []
    for item in games:
        game = item.game
        final = game.status.value == "final"
        competition: dict[str, Any] = {
            "venue": {"fullName": game.venue},
            "status": {
                "type": {
                    "state": "post" if final else "pre",
                    "completed": final,
                },
                "period": item.period or 0,
            },
            "competitors": [
                {
                    "homeAway": place,
                    "winner": final
                    and game.score is not None
                    and getattr(game.score, place)
                    > getattr(game.score, "away" if place == "home" else "home"),
                    **(
                        {"score": {"value": float(getattr(game.score, place))}}
                        if final and game.score is not None
                        else {}
                    ),
                    "team": team(getattr(game, place)),
                }
                for place in ("home", "away")
            ],
            "notes": [{"headline": item.note or ""}],
            "broadcasts": (
                [{"media": {"shortName": game.broadcast}}] if game.broadcast else []
            ),
        }
        if item.competition_type:
            competition["type"] = {"abbreviation": item.competition_type}
        if item.series is not None:
            competition["series"] = {
                "summary": item.series.summary,
                "completed": item.series.completed,
                "totalCompetitions": item.series.total_games,
                "competitors": [
                    {"id": PROVIDER_IDS[code], "wins": wins}
                    for code, wins in item.series.wins.items()
                ],
            }
        event: dict[str, Any] = {
            "id": game.id,
            "date": game.start_time.isoformat(),
            "competitions": [competition],
        }
        if item.season_type is not None:
            event["seasonType"] = {"type": item.season_type}
        events.append(event)
    return {"events": events}


class RealScheduleKit(SeasonPlayoffsKit):
    """The season playoffs kit whose postseason schedules go through the real
    adapter, over payloads in the team shape of a recorded schedule."""

    def __init__(self, path: Path) -> None:
        super().__init__(path)
        self.settings = self.settings.model_copy(
            update={"team_schedule_url": SCHEDULE_TEMPLATE}
        )
        self.start()

    async def fetch_postseason_schedule(
        self, client: SourceClient, code: str, season: int, settings: Settings
    ) -> list[PostseasonGame]:
        self.read(f"schedule/{code}/{season}")
        games = [
            g
            for g in self.games
            if g.season_type == 3 and code in (g.game.home.code, g.game.away.code)
        ]
        respx.get(season_schedule_url(code, season, settings, playoffs=True)).respond(
            json=schedule_payload(games)
        )
        return await fetch_postseason_schedule(client, code, season, settings)


def named_standings(season: int, **changes: Any) -> DivisionStandings:
    """Standings whose payload names every team "Harbor Gulls" of "Seattle" with
    the provider abbreviation SEA."""
    return standings(
        season=season,
        changes={
            code: {
                "abbreviation": "SEA",
                "name": "Harbor Gulls",
                "location": "Seattle",
                **changes,
            }
            for code in ALL
        },
    )


@pytest.fixture(autouse=True)
def no_network() -> Iterator[None]:
    with respx.mock:
        yield


@pytest.fixture
def kit(tmp_path: Path) -> SeasonPlayoffsKit:
    return SeasonPlayoffsKit(tmp_path)


@pytest.mark.anyio
async def test_a_2005_build_whose_schedules_send_no_name_key_builds_the_feed(
    tmp_path: Path,
) -> None:
    kit = RealScheduleKit(tmp_path)

    feed = PlayoffsFeed.model_validate_json(await kit.serve_season("2005"))

    assert feed.state is PlayoffsState.COMPLETE
    assert feed.champion is not None and str(feed.champion.team.code) == CHAMPION
    assert kit.called("schedule/") == 16
    assert read_by_id(kit.path, KIND, "2005") is not None


EAST_2005 = [
    "ATL",
    "BOS",
    "BKN",
    "CHA",
    "CHI",
    "CLE",
    "DET",
    "IND",
    "MIA",
    "MIL",
    "NYK",
    "ORL",
    "PHI",
    "TOR",
    "WAS",
]
WEST_2005 = [
    "DAL",
    "DEN",
    "GSW",
    "HOU",
    "LAC",
    "LAL",
    "MEM",
    "MIN",
    "NOP",
    "OKC",
    "PHX",
    "POR",
    "SAC",
    "SAS",
    "UTA",
]
SEEDS_2005 = {
    EAST: ["MIA", "DET", "BOS", "CHI", "WAS", "IND", "PHI", "BKN"],
    WEST: ["PHX", "SAS", "OKC", "DAL", "HOU", "SAC", "DEN", "MEM"],
}


def standings_2005() -> DivisionStandings:
    """The 2004-05 standings: the conferences of today, seeds 1 to 8 as set."""
    changes: dict[str, dict[str, Any]] = {}
    for conference, codes in ((EAST, EAST_2005), (WEST, WEST_2005)):
        seeded = SEEDS_2005[conference]
        others = [code for code in codes if code not in seeded]
        for place, code in enumerate(seeded + others, start=1):
            changes[code] = {
                "conference": conference,
                "conference_order": place,
                "playoff_seed": place if code in seeded else None,
            }
    return standings(season=2005, changes=changes)


def games_2005() -> list[PostseasonGame]:
    """The 15 series of 2005 as schedule games: season type 3, no competition
    type, no series object, a note only on the Finals games. Each series lists
    the higher seed, the lower seed, the winner and the loser's wins; the loser
    wins first, the winner clinches last."""
    rounds = {
        1: [
            ("MIA", "BKN", "MIA", 0),
            ("CHI", "WAS", "WAS", 2),
            ("BOS", "IND", "IND", 3),
            ("DET", "PHI", "DET", 1),
            ("PHX", "MEM", "PHX", 0),
            ("DAL", "HOU", "DAL", 3),
            ("OKC", "SAC", "OKC", 1),
            ("SAS", "DEN", "SAS", 1),
        ],
        2: [
            ("MIA", "WAS", "MIA", 0),
            ("DET", "IND", "DET", 2),
            ("PHX", "DAL", "PHX", 2),
            ("SAS", "OKC", "SAS", 2),
        ],
        3: [("MIA", "DET", "DET", 3), ("PHX", "SAS", "SAS", 1)],
        4: [("DET", "SAS", "SAS", 3)],
    }
    starts = {
        1: dt.datetime(2005, 4, 23, 23, 0, tzinfo=dt.UTC),
        2: dt.datetime(2005, 5, 7, 23, 0, tzinfo=dt.UTC),
        3: dt.datetime(2005, 5, 22, 23, 0, tzinfo=dt.UTC),
        4: dt.datetime(2005, 6, 9, 23, 0, tzinfo=dt.UTC),
    }
    games = []
    for round_, series in rounds.items():
        for high, low, winner, loser_wins in series:
            loser = low if winner == high else high
            results = [loser] * loser_wins + [winner] * 4
            for number, won in enumerate(results, start=1):
                home, away = (high, low) if number in (1, 2, 5, 7) else (low, high)
                games.append(
                    post(
                        f"{high}-{low}-{number}",
                        home,
                        away,
                        starts[round_] + (number - 1) * dt.timedelta(days=1),
                        scores=(100, 90) if won == home else (90, 100),
                        note="FINALS" if round_ == 4 else None,
                    )
                )
    return games


@pytest.mark.anyio
async def test_a_2005_build_from_schedules_with_no_series_and_empty_notes_reaches_the_complete_state(
    tmp_path: Path,
) -> None:
    kit = RealScheduleKit(tmp_path)
    kit.standing = standings_2005()
    kit.load(games_2005())

    feed = PlayoffsFeed.model_validate_json(await kit.serve_season("2005"))

    assert feed.state is PlayoffsState.COMPLETE and feed.play_in is None
    assert kit.called("schedule/") == 16
    bracket = {x.id: x for x in feed.bracket}
    rounds = [x.round for x in feed.bracket]
    assert [rounds.count(n) for n in (1, 2, 3, 4)] == [8, 4, 2, 1]
    assert all(
        x.top.team is not None and x.bottom.team is not None for x in bracket.values()
    )
    first_round = {
        str(side.team.code)
        for x in feed.bracket
        if x.round == 1
        for side in (x.top, x.bottom)
        if side.team is not None
    }
    assert first_round == set(SEEDS_2005[EAST] + SEEDS_2005[WEST])
    expected = {
        "east-r1-1": "MIA",
        "east-r1-2": "WAS",
        "east-r1-3": "IND",
        "east-r1-4": "DET",
        "east-r2-1": "MIA",
        "east-r2-2": "DET",
        "east-r3": "DET",
        "west-r1-1": "PHX",
        "west-r1-2": "DAL",
        "west-r1-3": "OKC",
        "west-r1-4": "SAS",
        "west-r2-1": "PHX",
        "west-r2-2": "SAS",
        "west-r3": "SAS",
        "finals": "SAS",
    }
    assert {x.id.value: x.winner for x in feed.bracket} == expected
    finals = bracket[SeriesId.FINALS]
    assert (finals.top.team.code, finals.top.wins) == ("DET", 3)  # type: ignore[union-attr]
    assert (finals.bottom.team.code, finals.bottom.wins) == ("SAS", 4)  # type: ignore[union-attr]
    assert finals.summary == "SAS wins series 4-3"
    assert feed.finals_game == 7 and feed.finals_summary == "SAS wins series 4-3"
    assert feed.champion is not None and str(feed.champion.team.code) == "SAS"
    assert (feed.champion.wins, feed.champion.losses) == (4, 3)
    assert read_by_id(kit.path, KIND, "2005") is not None


FOURTEEN_AWARDS = [
    (AwardCode.MVP, 1, None),
    (AwardCode.DPOY, 1, None),
    (AwardCode.ROY, 1, None),
    (AwardCode.SIXTH_MAN, 1, None),
    (AwardCode.MIP, 1, None),
    (AwardCode.FINALS_MVP, 1, None),
    (AwardCode.ALL_STAR_MVP, 1, None),
    (AwardCode.ALL_NBA, 5, 1),
    (AwardCode.ALL_NBA, 5, 2),
    (AwardCode.ALL_NBA, 5, 3),
    (AwardCode.ALL_ROOKIE, 5, 1),
    (AwardCode.ALL_ROOKIE, 5, 2),
    (AwardCode.ALL_DEFENSIVE, 5, 1),
    (AwardCode.ALL_DEFENSIVE, 5, 2),
]


@pytest.mark.anyio
async def test_a_2005_build_names_leaders_in_all_nine_categories_and_the_fourteen_awards(
    tmp_path: Path,
) -> None:
    kit = RealScheduleKit(tmp_path)
    kit.standing = standings_2005()
    kit.load(games_2005())
    ids = iter(range(100, 1000))
    kit.awards_source = SeasonAwards(
        awards=[
            award(
                code,
                [str(next(ids)) for _ in range(count)],
                team,
                team_code=seed(WEST, 1),
            )
            for code, count, team in FOURTEEN_AWARDS
        ]
    )

    feed = PlayoffsFeed.model_validate_json(await kit.serve_season("2005"))

    assert feed.leaders is not None and feed.awards is not None
    assert [g.category for g in feed.leaders] == list(LeaderCategory)
    assert all(len(g.leaders) == 3 for g in feed.leaders)
    assert len(feed.awards) == 14
    winners = [w for a in feed.awards for w in a.winners]
    assert len(winners) == 1 * 7 + 5 * 7
    assert all(w.name == f"Identity Player{w.player_id}" for w in winners)
    assert {str(w.team_code) for w in winners} == {seed(WEST, 1)}
    mvp = next(a for a in feed.awards if a.code is AwardCode.MVP)
    assert mvp.winners[0].name == "Identity Player100"


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
async def test_the_league_sides_are_named_from_the_standings_payload_and_name_sides_is_never_called(
    kit: SeasonPlayoffsKit,
) -> None:
    kit.standing = named_standings(2025)

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
async def test_a_side_whose_name_differs_from_the_stored_one_today_is_historical_with_the_payload_code(
    kit: SeasonPlayoffsKit,
) -> None:
    kit.standing = named_standings(2025)
    for code in ALL:
        publish_by_id(
            kit.path,
            NAMES_KIND,
            TeamNames,
            code.lower(),
            with_build_version(
                TeamNames(
                    runs=[
                        NameRun.model_validate(
                            {
                                "from": 1994,
                                "to": None,
                                "name": "Thunder",
                                "location": "Oklahoma City",
                                "code": code,
                            }
                        )
                    ]
                )
            ),
        )

    sides = league_sides(json.loads(await kit.serve_season("2025")))

    assert sides
    assert {(s["seasonCode"], s["historical"]) for s in sides} == {("SEA", True)}


@pytest.mark.anyio
async def test_a_side_with_the_name_of_today_keeps_the_standard_code(
    kit: SeasonPlayoffsKit,
) -> None:
    kit.standing = named_standings(2025, abbreviation="GS")
    for code in ALL:
        publish_by_id(
            kit.path,
            NAMES_KIND,
            TeamNames,
            code.lower(),
            with_build_version(
                TeamNames(
                    runs=[
                        NameRun.model_validate(
                            {
                                "from": 1994,
                                "to": None,
                                "name": "Harbor Gulls",
                                "location": "Seattle",
                                "code": "GSW",
                            }
                        )
                    ]
                )
            ),
        )

    sides = league_sides(json.loads(await kit.serve_season("2025")))

    assert {(s["seasonCode"], s["historical"]) for s in sides} == {("GSW", False)}


@pytest.mark.anyio
async def test_the_leaders_and_award_winners_carry_the_season_code_of_their_team(
    kit: SeasonPlayoffsKit,
) -> None:
    kit.standing = named_standings(2025)

    feed = PlayoffsFeed.model_validate_json(await kit.serve_season("2025"))

    assert feed.leaders is not None and feed.awards is not None
    leaders = [row for group in feed.leaders for row in group.leaders]
    winners = [w for award in feed.awards for w in award.winners]
    assert leaders and winners
    assert {row.season_code for row in leaders} == {"SEA"}
    assert {w.season_code for w in winners if w.team_code} == {"SEA"}


@pytest.mark.anyio
async def test_a_past_season_builds_a_valid_complete_feed_reading_only_its_declared_sources(
    kit: SeasonPlayoffsKit,
) -> None:
    body = await kit.serve_season("2025")

    feed = PlayoffsFeed.model_validate_json(body)
    assert feed.season == "2024-25"
    assert feed.state is PlayoffsState.COMPLETE
    assert feed.champion is not None and str(feed.champion.team.code) == CHAMPION
    assert feed.leaders is not None and feed.leaders[0].leaders
    assert feed.awards is not None and feed.awards[0].winners
    assert kit.calls.count("standings/2025") == 1
    assert kit.called("schedule/") == 20
    assert kit.called("type/") == 1 and "type/2025/5" in kit.calls
    days = [n for n in kit.calls if n.startswith("day/")]
    assert len(days) == 5 and all(n.endswith("/True") for n in days)
    assert not any(n.startswith("record/") for n in kit.calls)
    assert "leaders/2025" in kit.calls and "awards/2025" in kit.calls
    assert sorted(n for n in kit.calls if n.startswith("players/")) == [
        f"players/{game_id}" for game_id in FINALS
    ]
    athletes = sorted(n for n in kit.calls if n.startswith("athlete/"))
    assert athletes == [f"athlete/{n}" for n in range(1, 4)]
    assert len(kit.calls) - len(athletes) <= READ_BUDGET


def served_equals_stored(kit: SeasonPlayoffsKit, served: bytes) -> bool:
    """The served feed is the stored one plus its resolved colors (ADR 0072)."""
    body = read_by_id(kit.path, KIND, "2025")
    assert body is not None
    stored = PlayoffsFeed.model_validate_json(body)
    return with_accents(stored, {}) == PlayoffsFeed.model_validate_json(served)


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
    assert served_equals_stored(kit, first)


@pytest.mark.anyio
async def test_building_a_past_playoffs_feed_writes_nothing_under_the_current_feed(
    kit: SeasonPlayoffsKit,
) -> None:
    await kit.serve_season("2025")

    assert read_by_id(kit.path, PLAYOFFS_KIND, PLAYOFFS_ID) is None
    assert not (kit.path / "feeds" / PLAYOFFS_KIND).exists()
    assert kit.store.feed_build_ids(PLAYOFFS_KIND) == set()


@pytest.mark.anyio
async def test_a_season_before_2021_reads_16_schedules_and_no_play_in(
    kit: SeasonPlayoffsKit,
) -> None:
    feed = PlayoffsFeed.model_validate_json(await kit.serve_season("2020"))

    assert feed.play_in is None
    assert kit.called("schedule/") == 16
    assert kit.called("type/") == 0 and kit.called("day/") == 0


@pytest.mark.anyio
async def test_the_first_play_in_season_reads_the_play_in_window_and_its_days(
    kit: SeasonPlayoffsKit,
) -> None:
    kit.load(play_ins() + past_games())

    feed = PlayoffsFeed.model_validate_json(await kit.serve_season("2021"))

    assert "type/2021/5" in kit.calls
    assert kit.called("schedule/") == 20 and kit.called("day/") == 5
    assert feed.play_in is not None and len(feed.play_in) == 2


@pytest.mark.anyio
@pytest.mark.parametrize("name", ["leaders/2025", "awards/2025"])
async def test_a_leaders_or_awards_read_that_answers_404_is_null(
    kit: SeasonPlayoffsKit, name: str
) -> None:
    kit.not_found = {name}

    feed = PlayoffsFeed.model_validate_json(await kit.serve_season("2025"))

    assert feed.champion is not None
    assert (feed.leaders is None) == name.startswith("leaders")
    assert (feed.awards is None) == name.startswith("awards")


@pytest.mark.anyio
@pytest.mark.parametrize(
    "name",
    [
        "leaders/2025",
        "awards/2025",
        f"schedule/{ALL[3]}/2025",
        "standings/2025",
        "type/2025/5",
        "players/finals-1",
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
async def test_leaders_and_award_winners_are_named_from_the_player_identities_with_their_team_links(
    kit: SeasonPlayoffsKit,
) -> None:
    kit.awards_source = SeasonAwards(
        awards=[award(AwardCode.MVP, ["3"], team_code=seed(WEST, 2))]
    )

    feed = PlayoffsFeed.model_validate_json(await kit.serve_season("2025"))

    assert feed.leaders is not None and feed.awards is not None
    for group in feed.leaders:
        assert [row.player_id for row in group.leaders] == ["1", "2", "3"]
        for row in group.leaders:
            assert row.name == f"Identity Player{row.player_id}"
            assert str(row.photo_url) == f"https://example.com/h/{row.player_id}.png"
            assert str(row.team_code) == seed(EAST, int(row.player_id))
    winner = feed.awards[0].winners[0]
    assert (winner.player_id, winner.name) == ("3", "Identity Player3")
    assert str(winner.team_code) == seed(WEST, 2)
    assert feed.build_version == BUILD_VERSION


@pytest.mark.anyio
async def test_a_player_whose_athlete_read_fails_is_kept_with_his_id_and_a_dash(
    kit: SeasonPlayoffsKit,
) -> None:
    kit.not_found = {"athlete/3"}
    kit.awards_source = SeasonAwards(
        awards=[award(AwardCode.MVP, ["3"], team_code=CHAMPION)]
    )

    feed = PlayoffsFeed.model_validate_json(await kit.serve_season("2025"))

    assert feed.leaders is not None and feed.awards is not None
    for group in feed.leaders:
        row = group.leaders[2]
        assert (row.player_id, row.rank, row.name, row.photo_url) == (
            "3",
            3,
            "\u2014",
            None,
        )
        assert str(row.team_code) == seed(EAST, 3)
    winner = feed.awards[0].winners[0]
    assert (winner.player_id, winner.name, winner.photo_url) == ("3", "\u2014", None)
    assert kit.store.player_identity("3") is None
    assert kit.store.player_identity("2") is not None


@pytest.mark.anyio
async def test_a_second_build_within_30_days_reads_no_cached_player(
    kit: SeasonPlayoffsKit,
) -> None:
    await kit.serve_season("2025")
    first = kit.called("athlete/")
    kit.calls.clear()

    await kit.serve_season("2024", NOW + dt.timedelta(days=2))

    assert first == 3 and kit.called("standings/") == 1
    assert kit.called("athlete/") == 0


@pytest.mark.anyio
async def test_only_the_top_three_leaders_of_each_category_are_resolved(
    kit: SeasonPlayoffsKit,
) -> None:
    kit.leaders_source = past_leaders(8)

    feed = PlayoffsFeed.model_validate_json(await kit.serve_season("2025"))

    assert sorted(n for n in kit.calls if n.startswith("athlete/")) == [
        f"athlete/{n}" for n in range(1, 4)
    ]
    assert feed.leaders is not None
    assert all(len(group.leaders) == 3 for group in feed.leaders)


@pytest.mark.anyio
async def test_the_leaders_hold_three_per_category(kit: SeasonPlayoffsKit) -> None:
    kit.leaders_source = past_leaders(8)

    feed = PlayoffsFeed.model_validate_json(await kit.serve_season("2025"))

    assert feed.leaders is not None
    assert [len(group.leaders) for group in feed.leaders] == [3] * len(LeaderCategory)
    assert [row.rank for row in feed.leaders[0].leaders] == [1, 2, 3]


def fifty_three_winners() -> SeasonAwards:
    """52 distinct winners in the declared shape and a 53rd, the sixth of a tie."""
    ids = iter(str(100 + n) for n in range(60))
    awards = [
        award(code, [next(ids)], team_code=seed(WEST, 1))
        for code in (
            AwardCode.MVP,
            AwardCode.DPOY,
            AwardCode.ROY,
            AwardCode.SIXTH_MAN,
            AwardCode.MIP,
            AwardCode.CPOY,
            AwardCode.FINALS_MVP,
            AwardCode.EAST_FINALS_MVP,
            AwardCode.WEST_FINALS_MVP,
            AwardCode.ALL_STAR_MVP,
            AwardCode.CUP_MVP,
            AwardCode.TWYMAN_STOKES,
        )
    ]
    awards.append(
        award(
            AwardCode.CUP_ALL_TOURNAMENT,
            [next(ids) for _ in range(5)],
            team_code=seed(WEST, 1),
        )
    )
    for code, teams in (
        (AwardCode.ALL_NBA, (1, 2, 3)),
        (AwardCode.ALL_ROOKIE, (1, 2)),
        (AwardCode.ALL_DEFENSIVE, (1, 2)),
    ):
        for team in teams:
            awards.append(
                award(
                    code,
                    [next(ids) for _ in range(5)],
                    team,
                    team_code=seed(WEST, 1),
                )
            )
    awards[-1].winners.append(
        AwardWinnerRef(player_id=next(ids), team_code=seed(WEST, 1))
    )
    return SeasonAwards(awards=awards)


@pytest.mark.anyio
async def test_award_winners_past_the_declared_maximum_are_shown_with_a_dash_and_not_read(
    kit: SeasonPlayoffsKit, caplog: pytest.LogCaptureFixture
) -> None:
    kit.awards_source = fifty_three_winners()
    kit.leaders_source = past_leaders(0)

    with caplog.at_level(logging.WARNING):
        feed = PlayoffsFeed.model_validate_json(await kit.serve_season("2025"))

    assert feed.awards is not None
    winners = [w for a in feed.awards for w in a.winners]
    assert len(winners) == MAX_AWARD_WINNERS + 1
    read = {n for n in kit.calls if n.startswith("athlete/")}
    assert len(read) == MAX_AWARD_WINNERS
    unread = [w for w in winners if f"athlete/{w.player_id}" not in read]
    assert [(w.name, w.photo_url) for w in unread] == [("\u2014", None)]
    assert any("53 award winners" in r.getMessage() for r in caplog.records)


@pytest.mark.anyio
async def test_an_award_of_six_winners_a_tie_is_stored_with_all_six_in_the_source_order(
    kit: SeasonPlayoffsKit,
) -> None:
    ids = ["3", "1", "2", "6", "5", "4"]
    kit.awards_source = SeasonAwards(awards=[award(AwardCode.ALL_DEFENSIVE, ids, 2)])

    feed = PlayoffsFeed.model_validate_json(await kit.serve_season("2025"))

    assert feed.awards is not None
    assert [w.player_id for w in feed.awards[0].winners] == ids


@pytest.mark.anyio
async def test_the_colors_come_from_the_cached_team_info_and_are_null_without_it(
    kit: SeasonPlayoffsKit,
) -> None:
    body = {
        "team": {
            "location": "Oklahoma City",
            "name": "Thunder",
            "color": "007ac1",
            "alternateColor": "ef3b24",
            "franchise": {"venue": {"fullName": "Example Arena"}},
        }
    }
    provider = {code: key for key, code in TEAM_CODES.items()}
    kit.store.set_source_entry(
        f"https://example.com/teams/{provider[ALL[0]]}/info", json.dumps(body), NOW
    )

    feed = PlayoffsFeed.model_validate_json(await kit.serve_season("2025"))

    team = feed.picture[0].rows[0].team
    assert str(team.code) == ALL[0] and team.colors.primary is not None
    assert feed.picture[0].rows[1].team.colors.primary is None
    assert kit.called("info/") == 0


@pytest.mark.anyio
@pytest.mark.parametrize("version", [None, SEASON_BUILD_VERSION, BUILD_VERSION + 1])
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
    assert rebuilt is not None and rebuilt.build_version == BUILD_VERSION


@pytest.mark.anyio
async def test_a_stored_feed_with_the_current_version_is_served_with_no_source_request(
    kit: SeasonPlayoffsKit,
) -> None:
    await kit.serve_season("2025")
    kit.calls.clear()

    await kit.serve_season("2025", NOW + YEARS)

    assert kit.calls == []


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
    assert kit.called("schedule/") == 20


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

    assert served_equals_stored(kit, body)


def conferences_of(season: DivisionStandings) -> dict[str, Conference]:
    return {code: entry.conference for code, entry in season.teams.items()}


def test_schedule_teams_takes_the_first_8_seeds_of_each_conference_before_2021_and_10_after() -> (
    None
):
    table = standings(season=2020)

    before = schedule_teams(table, 2020)
    after = schedule_teams(table, 2021)

    assert len(before) == 16 and len(after) == 20
    assert before[:8] == [seed(EAST, n) for n in range(1, 9)]
    assert before[8:] == [seed(WEST, n) for n in range(1, 9)]
    assert after[:10] == [seed(EAST, n) for n in range(1, 11)]


def test_schedule_teams_without_seeds_takes_the_best_records_and_seeds_come_first() -> (
    None
):
    seedless = standings(
        season=2020, changes={code: {"playoff_seed": None} for code in ALL}
    )
    assert schedule_teams(seedless, 2020)[:8] == [seed(EAST, n) for n in range(1, 9)]

    changes: dict[str, dict[str, Any]] = {code: {"playoff_seed": None} for code in ALL}
    changes[seed(EAST, 15)] = {"playoff_seed": 1}
    changes[seed(EAST, 14)] = {"playoff_seed": None, "wins": 80, "losses": 2}
    east = schedule_teams(standings(season=2020, changes=changes), 2020)[:8]

    assert east[:3] == [seed(EAST, 15), seed(EAST, 14), seed(EAST, 1)]


def test_finals_games_are_those_of_the_only_pair_across_the_conferences() -> None:
    found = finals_games(past_games(), conferences_of(standings()))

    assert [g.game.id for g in found] == FINALS


def test_finals_games_fail_without_or_with_two_pairs_across_the_conferences() -> None:
    table = conferences_of(standings())
    with pytest.raises(PlayoffsBuildError):
        finals_games([g for g in past_games() if "finals" not in g.game.id], table)
    second = series_games(seed(EAST, 2), seed(WEST, 2), 4, "T", key="other")
    with pytest.raises(PlayoffsBuildError):
        finals_games(past_games() + second, table)


def test_a_build_with_no_postseason_window_dates_the_postseason_from_its_games() -> (
    None
):
    games = past_games()
    values: dict[str, Any] = {
        "season": 2027,
        "today": TODAY,
        "play_in": None,
        "postseason": None,
        "standings": standings(),
        "colors": {},
        "games": games,
        "players": {},
        "leaders": None,
        "awards": None,
        "past": True,
    }

    feed = build_playoffs_feed(PlayoffsSources(**values))

    first = min(g.game.start_time.astimezone(EASTERN_OFFSET).date() for g in games)
    last = max(g.game.start_time.astimezone(EASTERN_OFFSET).date() for g in games)
    assert feed.postseason_dates.first_date == first
    assert feed.postseason_dates.last_date == last
    with pytest.raises(PlayoffsBuildError):
        build_playoffs_feed(PlayoffsSources(**{**values, "games": []}))
    windowed = build_playoffs_feed(
        PlayoffsSources(**{**values, "play_in": PLAY_IN_WINDOW})
    )
    assert windowed.postseason_dates.first_date == dt.date(2027, 4, 14)


def test_the_constants_are_the_declared_budget_and_version() -> None:
    assert LEADER_READS == 27
    assert MAX_AWARD_WINNERS == 52
    assert READ_BUDGET == 61 + 27 + 52 == 140
    assert BUILD_VERSION == SEASON_BUILD_VERSION + 1


def identities_of() -> dict[str, TeamIdentity]:
    colors = TeamColors(primary="#0077c0", secondary="#c4ced4")
    return {code: TeamIdentity(code=code, logo=None, colors=colors) for code in ALL}


def without_accents(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: without_accents(v) for k, v in value.items() if k != "accent"}
    if isinstance(value, list):
        return [without_accents(item) for item in value]
    return value


@pytest.mark.anyio
async def test_a_stored_feed_without_the_colors_is_served_with_them_and_no_request(
    kit: SeasonPlayoffsKit,
) -> None:
    kit.stars.identities = identities_of()
    await kit.serve_season("2025")
    path = kit.path / "feeds" / KIND / "2025.json"
    stripped = without_accents(json.loads(path.read_bytes()))
    path.write_text(json.dumps(stripped), encoding="utf-8")
    assert "accent" not in path.read_text(encoding="utf-8")
    kit.calls.clear()

    served = PlayoffsFeed.model_validate_json(await kit.serve_season("2025"))

    assert kit.calls == []
    assert served.champion is not None and served.champion.accent == "#0077c0"
    assert served.bracket
    for series in served.bracket:
        assert series.accent is not None
        assert series.accent.top == "#0077c0" and series.accent.bottom == "#c4ced4"


@pytest.mark.anyio
async def test_a_stored_feed_with_the_retired_champion_fields_is_served_without_them_and_no_request(
    kit: SeasonPlayoffsKit,
) -> None:
    served_first = PlayoffsFeed.model_validate_json(await kit.serve_season("2025"))
    path = kit.path / "feeds" / KIND / "2025.json"
    stored = json.loads(path.read_bytes())
    stored["champion"].update(
        {
            "record": "16-6",
            "home": "9-2",
            "road": "7-4",
            "pointDifferential": {"value": "+142", "nonNegative": True},
        }
    )
    path.write_text(json.dumps(stored), encoding="utf-8")
    kit.calls.clear()

    body = await kit.serve_season("2025")

    assert kit.calls == []
    champion = json.loads(body)["champion"]
    for key in ("record", "home", "road", "pointDifferential"):
        assert key not in champion
    expected = {
        leader.player_id
        for group in served_first.leaders or []
        for leader in group.leaders
    } | {
        winner.player_id
        for award in served_first.awards or []
        for winner in award.winners
    }
    assert stored_player_ids(path.read_bytes()) == expected


@pytest.mark.anyio
async def test_a_historical_side_and_a_historical_champion_get_null(
    kit: SeasonPlayoffsKit,
) -> None:
    await kit.serve_season("2025")
    stored = kit.stored("2025")
    assert stored is not None and stored.champion is not None
    first = stored.bracket[0]
    assert first.top.team is not None
    historical = first.model_copy(
        update={
            "top": first.top.model_copy(
                update={"team": first.top.team.model_copy(update={"historical": True})}
            )
        }
    )
    feed = stored.model_copy(
        update={
            "bracket": [historical, *stored.bracket[1:]],
            "champion": stored.champion.model_copy(
                update={
                    "team": stored.champion.team.model_copy(update={"historical": True})
                }
            ),
        }
    )

    served = with_accents(feed, identities_of())

    assert served.bracket[0].accent is not None
    assert served.bracket[0].accent.top is None
    assert served.bracket[0].accent.bottom is not None
    assert served.champion is not None and served.champion.accent is None
