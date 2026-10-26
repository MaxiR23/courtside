# api/tests/jobs/test_power_ranking_feed.py
#
# Tests for the power ranking feed builder and its feed kind.
#
# Tested:
# - Order: 30 teams given shuffled come out by rank, and a tie keeps the provider's order and its absolute rank with tied true
# - Texts: the rating, offense and defense are signed with + and U+2212 and zero is unsigned, ratingNegative only for a negative rating, the record and the rounded projected record are wins-losses, the chance texts are kept as sent
# - playoffsLow: true for 9.9% and <0.1%, false for 10.0% and >99.9%
# - titleShare: 1 for the highest title chance, the ratio for the others, never over 1 when the rank 1 team is not the highest, 0 for all when every chance is 0
# - Names: the name and city of each team come together from its stored standings row, else its cached team info, null with neither
# - Unavailable with no teams: an empty rating, 29 or 31 teams, a repeated code, any other missing value, a rank out of range and a chance text that does not parse
# - Window: unavailable the day before the regular season starts and the day after it ends, available on its first and last day (US Eastern); the season label
# - Kind: an id other than league is unknown, not ready before the season is known; one season type read and two page reads per build; outside the regular season unavailable with no index read; a page budget of 1 fails the build; a failed read with nothing stored is unavailable and not retried for 10 minutes; a failed rebuild keeps the stored feed; fresh until the US Eastern day change when every name is filled in, and for 1 hour when a name is null; the build names the teams from the stored standings feed, warms it when none of the season is stored (another season, an invalid file) and never awaits it, and not outside the regular season; names fill in on the first request after 1 hour; with or without standings a build reads one season type and two index pages; logos, colors and accents are added when served and never stored; the cleanup keeps league
#
# What is covered:
# - Pure logic happy path, edge and error cases; job success, failure and expiry
#
# The clubs are made up. Every source read goes through a counted respx route.
#
# Run with: cd api && .venv/bin/python -m pytest tests/jobs/test_power_ranking_feed.py
#
# SEE: api/app/jobs/power_ranking_feed.py, docs/api/power-ranking.md,
# docs/adr/0078-power-ranking-names-from-the-stored-standings-feed.md

import asyncio
import datetime as dt
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any, cast

import httpx
import pytest
import respx
from pydantic import HttpUrl

from app.feeds.game_detail import Conference
from app.feeds.opponent import TeamColors, TeamLogo
from app.feeds.power_ranking import PowerRankingFeed, PowerRankingState
from app.feeds.standings import (
    ConferenceGroup,
    StandingsColors,
    StandingsFeed,
    StandingsRow,
    StandingsState,
)
from app.jobs import power_ranking_feed
from app.jobs.on_demand import (
    FeedCache,
    FeedKind,
    FeedUnavailableError,
    IdStatus,
    UnknownFeedError,
)
from app.jobs.power_ranking_feed import (
    FEED_ID,
    KIND,
    PowerRankingBuildError,
    PowerRankingFeeds,
    build_power_ranking_feed,
    chance_is_low,
    in_regular_season,
)
from app.jobs.stars import StarsJob
from app.settings import Settings
from app.sources.http import SourceClient, create_client, get_json
from app.sources.power_index import PowerIndex, PowerIndexTeam
from app.sources.season_types import SeasonWindow
from app.sources.team_info import TeamInfo
from app.sources.teams import team_code_of_id
from app.storage.feeds import publish_by_id, read_by_id
from app.storage.state import StateStore, TeamIdentity

SOURCE = "https://example.com/source/"
SEASON = 2027
D = dt.date
HOUR = dt.timedelta(hours=1)
TODAY = dt.date(2027, 1, 20)
NOW = dt.datetime(2027, 1, 20, 17, 0, tzinfo=dt.UTC)
CODES = [team_code_of_id(str(number), source="test") for number in range(1, 31)]
# The regular season: October 22 (22:00 US Eastern, already October 23 in UTC) to April 12.
WINDOW = SeasonWindow(
    season_type=2,
    start=dt.datetime(2026, 10, 23, 2, 0, tzinfo=dt.UTC),
    end=dt.datetime(2027, 4, 12, 23, 0, tzinfo=dt.UTC),
)


def entry(position: int, **changes: object) -> PowerIndexTeam:
    rank = position + 1
    values: dict[str, object] = {
        "code": CODES[position],
        "rank": rank,
        "tied": False,
        "rating": 8.0 - rank * 0.5,
        "offense": 4.0,
        "defense": -1.04,
        "wins": 60 - rank,
        "losses": 20 + rank,
        "projected_wins": 60.4,
        "projected_losses": 21.6,
        "playoffs": 90.0,
        "title": 30.0 / rank,
        "playoffs_text": "90.0%",
        "title_text": f"{30.0 / rank:.1f}%",
    }
    values.update(changes)
    return PowerIndexTeam.model_validate(values)


def index_of(**changes: object) -> PowerIndex:
    return PowerIndex(teams=[entry(position, **changes) for position in range(30)])


def varied(position: int, **changes: object) -> PowerIndex:
    teams = [entry(number) for number in range(30)]
    teams[position] = entry(position, **changes)
    return PowerIndex(teams=teams)


def build(
    index: PowerIndex | None,
    today: dt.date = TODAY,
    standings: dict[str, StandingsRow] | None = None,
) -> PowerRankingFeed:
    return build_power_ranking_feed(SEASON, today, WINDOW, index, {}, standings)


def row_of(number: int, code: str) -> StandingsRow:
    return StandingsRow(
        code=code,
        city=f"City {number}",
        name=f"Club {number}",
        colors=StandingsColors(primary=None, secondary=None),
        seed=None,
        clinch=None,
        wins=0,
        losses=0,
        pct=None,
        games_behind=None,
        streak=None,
        home=None,
        away=None,
        last_ten="0-0",
        division="0-0",
        conference="0-0",
        points_for=None,
        points_against=None,
        differential=None,
        total=None,
    )


def standings_of(
    season: str = "2026-27", named: Iterable[str] = CODES
) -> StandingsFeed:
    codes = list(named)
    rows = [row_of(number, code) for number, code in enumerate(codes, start=1)]
    return StandingsFeed(
        season=season,
        state=StandingsState.REGULAR,
        games_played=0,
        conferences=[
            ConferenceGroup(
                key=Conference.EAST,
                name="Eastern Conference",
                team_count=len(rows[:15]),
                teams=rows[:15],
            ),
            ConferenceGroup(
                key=Conference.WEST,
                name="Western Conference",
                team_count=len(rows[15:]),
                teams=rows[15:],
            ),
        ],
        divisions=[],
    )


def rows_of(feed: StandingsFeed) -> dict[str, StandingsRow]:
    return {row.code: row for group in feed.conferences for row in group.teams}


def info(name: str, location: str) -> TeamInfo:
    return TeamInfo(location=location, name=name, color="112233")


# The builder


def test_orders_the_teams_by_rank_whatever_the_given_order() -> None:
    shuffled = PowerIndex(teams=list(reversed(index_of().teams)))

    feed = build(shuffled)

    assert feed.state is PowerRankingState.AVAILABLE
    assert [team.rank for team in feed.teams] == list(range(1, 31))
    assert feed.teams[0].team.code == CODES[0]


def test_a_tie_keeps_the_provider_order_and_the_absolute_rank() -> None:
    teams = index_of().teams
    teams[3] = entry(3, rank=3, tied=True)
    teams[2] = entry(2, tied=True)
    feed = build(PowerIndex(teams=[teams[3], teams[2], *teams[:2], *teams[4:]]))

    ranks = [(team.rank, team.team.code, team.tied) for team in feed.teams[2:4]]
    assert ranks == [(3, CODES[3], True), (3, CODES[2], True)]


def test_signs_the_ratings_with_the_minus_sign_and_leaves_zero_unsigned() -> None:
    feed = build(varied(1, rating=-2.14, offense=0.04, defense=7.26))

    team = feed.teams[1]
    assert (team.rating, team.rating_negative) == ("−2.1", True)
    assert (team.offense, team.defense) == ("0.0", "+7.3")
    assert feed.teams[0].rating == "+7.5" and not feed.teams[0].rating_negative
    assert "−" == team.rating[0] and team.rating[0] != "-"


def test_writes_the_record_and_the_rounded_projected_record() -> None:
    team = build(varied(0, projected_wins=59.6, projected_losses=22.4)).teams[0]

    assert team.record == "59-21"
    assert team.projected == "60-22"


def test_keeps_the_chance_texts_as_sent() -> None:
    team = build(varied(0, playoffs_text=">99.9%", title_text="<0.1%")).teams[0]

    assert (team.playoffs, team.title) == (">99.9%", "<0.1%")


@pytest.mark.parametrize(
    ("text", "low"),
    [("9.9%", True), ("<0.1%", True), ("10.0%", False), (">99.9%", False)],
)
def test_playoffs_low_is_read_from_the_display_text(text: str, low: bool) -> None:
    team = build(varied(0, playoffs_text=text)).teams[0]

    assert team.playoffs_low is low
    assert chance_is_low(text) is low


def test_a_chance_text_that_does_not_parse_has_no_answer() -> None:
    assert chance_is_low("n/a") is None


def test_the_highest_title_chance_has_a_share_of_1_and_the_others_their_ratio() -> None:
    feed = build(index_of())

    assert feed.teams[0].title_share == 1.0
    assert feed.teams[1].title_share == pytest.approx(0.5)


def test_a_share_is_never_over_1_when_the_rank_1_team_is_not_the_highest() -> None:
    feed = build(varied(4, title=60.0, title_text="60.0%"))

    shares = {team.rank: team.title_share for team in feed.teams}
    assert shares[5] == 1.0
    assert shares[1] == pytest.approx(0.5)
    assert max(shares.values()) == 1.0


def test_every_share_is_0_when_every_title_chance_is_0() -> None:
    feed = build(index_of(title=0.0, title_text="0.0%"))

    assert {team.title_share for team in feed.teams} == {0.0}


def test_names_each_team_from_its_cached_info_and_gives_null_with_none() -> None:
    infos: dict[str, TeamInfo | None] = {
        CODES[0]: info("Rivers", "Riverton"),
        CODES[1]: None,
    }

    feed = build_power_ranking_feed(SEASON, D(2027, 1, 20), WINDOW, index_of(), infos)

    first, second, third = feed.teams[:3]
    assert (first.team.name, first.team.city) == ("Rivers", "Riverton")
    assert (second.team.name, second.team.city) == (None, None)
    assert (third.team.name, third.team.city) == (None, None)


def test_names_each_team_from_the_stored_standings_rows_first() -> None:
    rows = {code: row_of(n, code) for n, code in enumerate(CODES[:2], start=1)}
    infos: dict[str, TeamInfo | None] = {
        CODES[0]: info("Rivers", "Riverton"),
        CODES[2]: info("Lakes", "Lakeside"),
    }

    feed = build_power_ranking_feed(
        SEASON, D(2027, 1, 20), WINDOW, index_of(), infos, rows
    )

    first, second, third, fourth = feed.teams[:4]
    assert (first.team.name, first.team.city) == ("Club 1", "City 1")
    assert (second.team.name, second.team.city) == ("Club 2", "City 2")
    assert (third.team.name, third.team.city) == ("Lakes", "Lakeside")
    assert (fourth.team.name, fourth.team.city) == (None, None)


@pytest.mark.parametrize(
    "index",
    [
        None,
        PowerIndex(teams=[]),
        PowerIndex(teams=index_of().teams[:29]),
        PowerIndex(teams=[*index_of().teams, entry(0)]),
        PowerIndex(teams=[*index_of().teams[:29], entry(0)]),
        varied(0, rating=None),
        varied(1, offense=None),
        varied(2, defense=None),
        varied(3, wins=None),
        varied(4, losses=None),
        varied(5, projected_wins=None),
        varied(6, projected_losses=None),
        varied(7, playoffs_text=None),
        varied(8, title_text=None),
        varied(9, title=None),
        varied(10, rank=None),
        varied(11, rank=0),
        varied(12, rank=31),
        varied(13, playoffs_text="n/a"),
    ],
    ids=[
        "no index",
        "empty",
        "29 teams",
        "31 teams",
        "repeated code",
        "no rating",
        "no offense",
        "no defense",
        "no wins",
        "no losses",
        "no projected wins",
        "no projected losses",
        "no playoffs text",
        "no title text",
        "no title",
        "no rank",
        "rank 0",
        "rank 31",
        "unparsable text",
    ],
)
def test_gives_unavailable_with_no_teams_when_the_index_is_not_usable(
    index: PowerIndex | None,
) -> None:
    feed = build(index)

    assert feed.state is PowerRankingState.UNAVAILABLE
    assert feed.teams == []


@pytest.mark.parametrize(
    ("today", "available"),
    [
        (D(2026, 10, 21), False),
        (D(2026, 10, 22), True),
        (D(2027, 4, 12), True),
        (D(2027, 4, 13), False),
    ],
)
def test_is_available_from_the_first_to_the_last_day_of_the_regular_season(
    today: dt.date, available: bool
) -> None:
    feed = build(index_of(), today)

    assert (feed.state is PowerRankingState.AVAILABLE) is available
    assert in_regular_season(today, WINDOW) is available


def test_is_unavailable_with_no_window() -> None:
    feed = build_power_ranking_feed(SEASON, D(2027, 1, 20), None, index_of(), {})

    assert feed.state is PowerRankingState.UNAVAILABLE


def test_labels_the_season() -> None:
    assert build(index_of()).season == "2026-27"


def test_wraps_an_invalid_feed_in_the_build_error() -> None:
    with pytest.raises(PowerRankingBuildError) as raised:
        build_power_ranking_feed(-1, D(2027, 1, 20), WINDOW, index_of(), {})

    assert raised.value.reason.startswith("invalid feed: 1 errors, first at season")


# The kind


class RecordingCache(FeedCache):
    """A feed cache that records the warm calls."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.warmed: list[tuple[str, str]] = []

    def warm(self, kind: str, feed_id: str) -> None:
        self.warmed.append((kind, feed_id))
        super().warm(kind, feed_id)


class StubStars:
    def __init__(self) -> None:
        self.season: int | None = SEASON
        self.identities: dict[str, TeamIdentity] = {}

    def current_season(self) -> int | None:
        return self.season

    def team_identities(self) -> dict[str, TeamIdentity]:
        return dict(self.identities)


class PowerRankingKit:
    """A feed cache and the power ranking kind over one client and one clock.

    Both fake adapters read through the source cache from counted respx routes, so
    route calls are real source requests.
    """

    def __init__(self, path: Path, now: dt.datetime = NOW) -> None:
        self.path = path
        self.clock = [now]
        self.store = StateStore(path)
        self.store.migrate()
        self.settings = Settings(_env_file=None, data_dir=path)  # type: ignore[call-arg]
        self.client = create_client(self.store, clock=lambda: self.clock[0])
        self.requests: list[str] = []
        self.failing: set[str] = set()
        self.window: SeasonWindow = WINDOW
        self.index = index_of()
        respx.get(url__startswith=SOURCE).mock(side_effect=self.answer)
        self.stars = StubStars()
        self.standings_build = False
        self.blocking = False
        self.release = asyncio.Event()
        self.standings_built: list[str] = []
        self.cache = RecordingCache(
            path,
            self.store,
            clock=lambda: self.clock[0],
            identities=self.stars.team_identities,
        )
        self.cache.register(
            FeedKind(
                "standings",
                StandingsFeed,
                check=self.check_standings,
                build=self.build_standings,
                is_fresh=lambda feed, built_at, now: False,
                keep=lambda feed_id: True,
            )
        )
        self.feeds = PowerRankingFeeds(
            self.settings,
            self.store,
            self.client,
            self.cache,
            cast(StarsJob, self.stars),
            fetch_season_type=self.fetch_season_type,
            fetch_power_index=self.fetch_power_index,
        )

    def check_standings(self, feed_id: str) -> IdStatus:
        return IdStatus.KNOWN if self.standings_build else IdStatus.UNKNOWN

    async def build_standings(self, feed_id: str) -> StandingsFeed:
        self.standings_built.append(feed_id)
        if self.blocking:
            await self.release.wait()
        return standings_of()

    def store_standings(self, feed: StandingsFeed) -> None:
        publish_by_id(self.path, "standings", StandingsFeed, "league", feed)

    def answer(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path.removeprefix("/source/")
        self.requests.append(path)
        if path.split("/")[0] in self.failing or path in self.failing:
            return httpx.Response(500)
        return httpx.Response(200, json={"ok": True})

    def requested(self, prefix: str) -> int:
        return sum(1 for name in self.requests if name.startswith(prefix))

    async def fetch_season_type(
        self, client: SourceClient, season: int, season_type: int, settings: Settings
    ) -> SeasonWindow:
        await get_json(client, SOURCE + "types", source="test", fresh=HOUR)
        return self.window

    async def fetch_power_index(
        self, client: SourceClient, season: int, settings: Settings
    ) -> PowerIndex:
        for page in (1, 2):
            await get_json(client, SOURCE + f"index/{page}", source="test", fresh=HOUR)
        return self.index

    async def serve(self, at: dt.datetime | None = None) -> bytes:
        if at is not None:
            self.clock[0] = at
        body = await self.cache.serve(KIND, FEED_ID)
        await self.settle()
        return body

    async def settle(self) -> None:
        while self.cache.in_flight:
            await next(iter(self.cache.in_flight.values()))
            await asyncio.sleep(0)
        await asyncio.sleep(0)

    def stored(self) -> PowerRankingFeed | None:
        body = read_by_id(self.path, KIND, FEED_ID)
        return None if body is None else PowerRankingFeed.model_validate_json(body)


@pytest.fixture(autouse=True)
def no_network() -> Iterator[None]:
    with respx.mock:
        yield


@pytest.fixture
def kit(tmp_path: Path) -> PowerRankingKit:
    return PowerRankingKit(tmp_path)


def test_check_answers_unknown_for_another_id_and_not_ready_before_the_season(
    kit: PowerRankingKit,
) -> None:
    for feed_id in ("LEAGUE", "okc", ""):
        assert kit.feeds.check(feed_id) is IdStatus.UNKNOWN
    assert kit.feeds.check(FEED_ID) is IdStatus.KNOWN
    kit.stars.season = None
    assert kit.feeds.check(FEED_ID) is IdStatus.NOT_READY


@pytest.mark.anyio
async def test_nothing_is_built_stored_or_fetched_without_a_request(
    kit: PowerRankingKit, tmp_path: Path
) -> None:
    kit.cache.cleanup()
    await kit.settle()

    assert kit.requests == []
    assert not (tmp_path / "feeds" / KIND).exists()

    with pytest.raises(UnknownFeedError):
        await kit.cache.serve(KIND, "okc")
    kit.stars.season = None
    with pytest.raises(FeedUnavailableError):
        await kit.cache.serve(KIND, FEED_ID)
    assert kit.requests == []


@pytest.mark.anyio
async def test_a_build_without_a_season_is_a_build_error(kit: PowerRankingKit) -> None:
    kit.stars.season = None

    with pytest.raises(PowerRankingBuildError) as raised:
        await kit.feeds.build(FEED_ID)

    assert raised.value.reason == "season not known yet"


@pytest.mark.anyio
async def test_a_request_in_the_regular_season_stores_an_available_feed(
    kit: PowerRankingKit, tmp_path: Path
) -> None:
    feed = PowerRankingFeed.model_validate_json(await kit.serve())

    assert feed.state is PowerRankingState.AVAILABLE and len(feed.teams) == 30
    assert (tmp_path / "feeds" / "power-ranking" / "league.json").is_file()
    assert kit.requested("types") == 1
    assert kit.requested("index/") == 2


@pytest.mark.anyio
async def test_a_request_outside_the_regular_season_stores_unavailable_with_no_index_read(
    kit: PowerRankingKit,
) -> None:
    kit.window = SeasonWindow(
        season_type=2,
        start=dt.datetime(2027, 10, 20, 0, 0, tzinfo=dt.UTC),
        end=dt.datetime(2028, 4, 10, 0, 0, tzinfo=dt.UTC),
    )

    feed = PowerRankingFeed.model_validate_json(await kit.serve())

    assert feed.state is PowerRankingState.UNAVAILABLE and feed.teams == []
    assert kit.requested("types") == 1
    assert kit.requested("index/") == 0


@pytest.mark.anyio
async def test_a_page_budget_of_1_fails_the_build_and_stores_nothing(
    kit: PowerRankingKit, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(power_ranking_feed, "PAGE_READS", 1)

    with pytest.raises(FeedUnavailableError):
        await kit.cache.serve(KIND, FEED_ID)
    await kit.settle()

    assert kit.requested("index/") == 1
    assert kit.stored() is None
    state = kit.store.feed_build(KIND, FEED_ID)
    assert state is not None and state.last_failure_reason is not None
    assert "read budget of 1 reached" in state.last_failure_reason


@pytest.mark.anyio
@pytest.mark.parametrize("failing", ["types", "index"])
async def test_a_failed_read_with_nothing_stored_is_unavailable_and_not_retried_for_10_minutes(
    kit: PowerRankingKit, failing: str
) -> None:
    kit.failing.add(failing)

    with pytest.raises(FeedUnavailableError):
        await kit.cache.serve(KIND, FEED_ID)
    await kit.settle()
    sent = len(kit.requests)
    kit.clock[0] = NOW + dt.timedelta(minutes=9)
    with pytest.raises(FeedUnavailableError):
        await kit.cache.serve(KIND, FEED_ID)
    await kit.settle()

    assert sent > 0 and len(kit.requests) == sent
    assert kit.stored() is None


@pytest.mark.anyio
async def test_a_failed_rebuild_keeps_and_serves_the_stored_feed(
    kit: PowerRankingKit,
) -> None:
    first = await kit.serve()
    kit.failing.add("index")

    second = await kit.serve(NOW + 2 * 24 * HOUR)
    third = await kit.serve(NOW + 2 * 24 * HOUR + dt.timedelta(minutes=11))

    assert second == first and third == first
    state = kit.store.feed_build(KIND, FEED_ID)
    assert state is not None and state.last_failure_reason is not None


@pytest.mark.anyio
@pytest.mark.parametrize(
    "built_at",
    [
        dt.datetime(2027, 1, 20, 18, 0, tzinfo=dt.UTC),
        dt.datetime(2027, 1, 20, 23, 59, tzinfo=dt.UTC),
    ],
    ids=["afternoon", "just before midnight UTC"],
)
async def test_is_fresh_until_the_us_eastern_day_changes(
    kit: PowerRankingKit, built_at: dt.datetime
) -> None:
    feed = build(index_of(), standings=rows_of(standings_of()))
    midnight = dt.datetime(2027, 1, 21, 5, 0, tzinfo=dt.UTC)

    assert kit.feeds.is_fresh(feed, built_at, built_at + 2 * HOUR)
    assert kit.feeds.is_fresh(feed, built_at, midnight - dt.timedelta(seconds=1))
    assert not kit.feeds.is_fresh(feed, built_at, midnight)
    assert kit.feeds.keep(FEED_ID) and not kit.feeds.keep("other")


@pytest.mark.anyio
async def test_a_served_feed_carries_logos_colors_and_accents_and_the_stored_file_does_not(
    kit: PowerRankingKit,
) -> None:
    kit.stars.identities = {
        CODES[0]: TeamIdentity(
            code=CODES[0],
            logo=TeamLogo(light=HttpUrl("https://example.com/a.svg"), dark=None),
            colors=TeamColors(primary="#AA5500", secondary=None),
        )
    }

    served = PowerRankingFeed.model_validate_json(await kit.serve())
    stored = kit.stored()

    first = served.teams[0].team
    assert first.logo is not None and first.colors is not None
    assert first.accent == "#AA5500"
    other = served.teams[1].team
    assert other.logo is None and other.colors is None and other.accent is None
    assert stored is not None
    kept = stored.teams[0].team
    assert kept.logo is None and kept.colors is None and kept.accent is None


@pytest.mark.anyio
async def test_the_cleanup_keeps_league(kit: PowerRankingKit) -> None:
    await kit.serve()

    kit.cache.cleanup()
    await kit.settle()

    assert kit.stored() is not None


@pytest.mark.parametrize(
    ("named", "after_a_day"), [(CODES, True), (CODES[:29], False)], ids=["all", "29"]
)
def test_a_feed_with_a_null_name_is_fresh_before_1_hour_and_not_after(
    kit: PowerRankingKit, named: list[str], after_a_day: bool
) -> None:
    feed = build(index_of(), standings=rows_of(standings_of(named=named)))

    assert kit.feeds.is_fresh(feed, NOW, NOW + HOUR - dt.timedelta(seconds=1))
    assert kit.feeds.is_fresh(feed, NOW, NOW + HOUR) is after_a_day


def test_an_unavailable_feed_stays_fresh_for_the_day(kit: PowerRankingKit) -> None:
    feed = build(None)

    assert feed.teams == []
    assert kit.feeds.is_fresh(feed, NOW, NOW + 2 * HOUR)


@pytest.mark.anyio
async def test_a_build_names_the_teams_from_the_stored_standings_feed(
    kit: PowerRankingKit,
) -> None:
    kit.store_standings(standings_of())

    feed = PowerRankingFeed.model_validate_json(await kit.serve())

    assert [(t.team.name, t.team.city) for t in feed.teams] == [
        (f"Club {n}", f"City {n}") for n in range(1, 31)
    ]
    assert ("standings", "league") not in kit.cache.warmed


@pytest.mark.anyio
async def test_a_stored_standings_feed_of_another_season_is_not_used_and_is_warmed(
    kit: PowerRankingKit,
) -> None:
    kit.store_standings(standings_of(season="2025-26"))

    feed = PowerRankingFeed.model_validate_json(await kit.serve())

    assert {team.team.name for team in feed.teams} == {None}
    assert ("standings", "league") in kit.cache.warmed


@pytest.mark.anyio
async def test_an_invalid_stored_standings_file_gives_null_names_and_a_warm(
    kit: PowerRankingKit, tmp_path: Path
) -> None:
    folder = tmp_path / "feeds" / "standings"
    folder.mkdir(parents=True)
    (folder / "league.json").write_bytes(b"{}")

    feed = PowerRankingFeed.model_validate_json(await kit.serve())

    assert feed.state is PowerRankingState.AVAILABLE
    assert {team.team.name for team in feed.teams} == {None}
    assert ("standings", "league") in kit.cache.warmed


@pytest.mark.anyio
async def test_the_build_never_awaits_the_standings_build(
    kit: PowerRankingKit,
) -> None:
    kit.standings_build = True
    kit.blocking = True

    body = await kit.cache.serve(KIND, FEED_ID, wait=1.0)

    feed = PowerRankingFeed.model_validate_json(body)
    assert feed.state is PowerRankingState.AVAILABLE
    assert {team.team.name for team in feed.teams} == {None}
    assert kit.stored() is not None
    assert ("standings", "league") in kit.cache.in_flight
    assert not kit.release.is_set()
    assert kit.standings_built == ["league"]
    kit.release.set()
    await kit.settle()


@pytest.mark.anyio
async def test_names_fill_in_on_the_first_request_after_1_hour_once_standings_are_stored(
    kit: PowerRankingKit,
) -> None:
    first = await kit.serve()
    kit.store_standings(standings_of())
    sent = len(kit.requests)

    same = await kit.serve(NOW + dt.timedelta(minutes=30))
    assert same == first and len(kit.requests) == sent

    old = await kit.serve(NOW + HOUR)
    stored = kit.stored()
    assert old == first
    assert stored is not None
    assert {team.team.name for team in stored.teams} == {
        f"Club {n}" for n in range(1, 31)
    }

    later = PowerRankingFeed.model_validate_json(await kit.serve(NOW + 2 * HOUR))
    assert later.teams[0].team.name is not None


@pytest.mark.anyio
@pytest.mark.parametrize("stored", [True, False])
async def test_a_build_reads_one_season_type_and_at_most_two_index_pages_with_or_without_standings(
    kit: PowerRankingKit, stored: bool
) -> None:
    kit.standings_build = True
    if stored:
        kit.store_standings(standings_of())

    await kit.serve()

    assert kit.requested("types") == 1
    assert kit.requested("index/") == 2
    assert all(name.startswith(("types", "index/")) for name in kit.requests)


@pytest.mark.anyio
async def test_outside_the_regular_season_no_standings_warm(
    kit: PowerRankingKit,
) -> None:
    kit.standings_build = True
    kit.window = SeasonWindow(
        season_type=2,
        start=dt.datetime(2027, 10, 20, 0, 0, tzinfo=dt.UTC),
        end=dt.datetime(2028, 4, 10, 0, 0, tzinfo=dt.UTC),
    )

    await kit.serve()

    assert kit.cache.warmed == []
    assert kit.standings_built == []
