# api/app/jobs/power_ranking_feed.py
#
# Power ranking feed builder and kind: the 30 teams by rank with every value decided
# here. The builder is a pure function from the date, the regular-season window, the
# power index, the stored standings rows and the cached team infos to the feed; it
# reads no clock and no source. The feed is decided in ADR 0075 and ADR 0078.
#
# The feed is available only between the start and the end of the regular season, both
# inclusive as US Eastern dates. Outside that window the feed is unavailable with no
# teams and the index is not read. Inside it the feed is available only when the index
# holds exactly 30 distinct teams, every one with a rank from 1 to 30, a rating, an
# offense, a defense, a record, a projected record and both chances (value and display
# text), and every playoffs chance text parses; anything else is unavailable.
#
# Teams are ordered by rank, and a tie keeps the provider's order and its absolute rank
# with tied true. The rating, offense and defense are signed one-decimal texts with the
# minus sign U+2212 (zero has no sign). The projected record is the rounded projected
# wins and losses. The two chances keep the provider's display texts. playoffsLow is
# read from the playoffs display text (under 10). titleShare is the title chance over the
# highest title chance of the 30, 0 for all when that is 0. The name and city of a team
# come together from the stored standings feed of the current season (read from disk,
# no request), else from the cached team info (no request), else null. When the build
# has teams and no standings feed of the season is stored, the build warms it and
# never waits for it.
#
# PowerRankingFeeds is the feed kind of the on-demand cache: the only id is "league",
# the feed is stored at feeds/power-ranking/league.json only when requested, and it
# answers 503 (not ready) until the stars job knows the season. The feed expires at the
# first US Eastern day change after the build, and 1 hour after the build when any
# team has a null name. A stale feed is served at once and rebuilt in the background.
# The feed is never deleted. A failed
# season type or index read fails the build: the cache keeps and serves the stored feed.
#
# SEE: docs/api/power-ranking.md, docs/adr/0075-power-ranking-feed.md,
# docs/adr/0078-power-ranking-names-from-the-stored-standings-feed.md,
# docs/source-rules.md

import datetime as dt
from collections.abc import Awaitable, Callable, Mapping

from pydantic import ValidationError

from app.feeds.power_ranking import (
    PowerRankingFeed,
    PowerRankingIdentity,
    PowerRankingState,
    PowerRankingTeam,
)
from app.feeds.standings import StandingsFeed, StandingsRow
from app.jobs import standings_feed
from app.jobs.on_demand import FeedCache, FeedKind, IdStatus
from app.jobs.playoffs_feed import FetchSeasonType
from app.jobs.standings_feed import signed_per_game
from app.jobs.stars import StarsJob
from app.jobs.team_feed import eastern_date, season_label
from app.jobs.team_identity import resolved_color, team_colors
from app.settings import Settings
from app.sources import power_index, season_types, team_info
from app.sources.http import ReadBudget, SourceClient, within_budget
from app.sources.power_index import PowerIndex, PowerIndexTeam
from app.sources.season_types import REGULAR_SEASON, SeasonWindow
from app.sources.team_info import TeamInfo
from app.storage.feeds import read_by_id
from app.storage.state import StateStore

KIND = "power-ranking"
FEED_ID = "league"
# The most source reads one build sends (ADR 0075): the regular-season window, then
# the index pages.
SEASON_TYPE_READS = 1
PAGE_READS = power_index.MAX_PAGES
# A chance under this many percent is low.
LOW_CHANCE = 10.0
# A feed with a team whose name is null expires this long after its build, so the
# names fill in once the standings feed is stored (ADR 0078).
NAMELESS_FRESH_FOR = dt.timedelta(hours=1)

FetchPowerIndex = Callable[[SourceClient, int, Settings], Awaitable[PowerIndex]]


class PowerRankingBuildError(Exception):
    """The power ranking feed built from the fetched data is not valid."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def in_regular_season(today: dt.date, window: SeasonWindow | None) -> bool:
    """True from the start to the end of the regular season, both US Eastern dates
    inclusive; false with no window."""
    if window is None:
        return False
    return eastern_date(window.start) <= today <= eastern_date(window.end)


def chance_is_low(text: str) -> bool | None:
    """True when a chance display text is under LOW_CHANCE percent, None when the
    text does not parse."""
    number = text.removeprefix("<").removeprefix(">").removesuffix("%")
    try:
        return float(number) < LOW_CHANCE
    except ValueError:
        return None


def _complete(team: PowerIndexTeam) -> bool:
    return (
        team.rank is not None
        and 1 <= team.rank <= 30
        and team.rating is not None
        and team.offense is not None
        and team.defense is not None
        and team.wins is not None
        and team.losses is not None
        and team.projected_wins is not None
        and team.projected_losses is not None
        and team.title is not None
        and team.playoffs_text is not None
        and team.title_text is not None
        and chance_is_low(team.playoffs_text) is not None
    )


def _usable(index: PowerIndex) -> bool:
    codes = {team.code for team in index.teams}
    return (
        len(index.teams) == 30
        and len(codes) == 30
        and all(_complete(team) for team in index.teams)
    )


def _team(
    team: PowerIndexTeam, row: StandingsRow | None, info: TeamInfo | None, top: float
) -> PowerRankingTeam:
    # _complete guarantees every value read here.
    assert team.rank is not None and team.rating is not None
    assert team.offense is not None and team.defense is not None
    assert team.projected_wins is not None and team.projected_losses is not None
    assert team.title is not None
    assert team.playoffs_text is not None and team.title_text is not None
    rating = signed_per_game(team.rating)
    name: str | None
    city: str | None
    if row is not None:
        name, city = row.name, row.city
    elif info is not None:
        name, city = info.name, info.location
    else:
        name, city = None, None
    return PowerRankingTeam(
        rank=team.rank,
        tied=team.tied,
        team=PowerRankingIdentity(
            code=team.code,
            name=name,
            city=city,
        ),
        record=f"{team.wins}-{team.losses}",
        rating=rating.value,
        rating_negative=not rating.non_negative,
        offense=signed_per_game(team.offense).value,
        defense=signed_per_game(team.defense).value,
        projected=f"{round(team.projected_wins)}-{round(team.projected_losses)}",
        playoffs=team.playoffs_text,
        title=team.title_text,
        playoffs_low=bool(chance_is_low(team.playoffs_text)),
        title_share=team.title / top if top else 0.0,
    )


def build_power_ranking_feed(
    season: int,
    today: dt.date,
    window: SeasonWindow | None,
    index: PowerIndex | None,
    infos: Mapping[str, TeamInfo | None],
    standings: Mapping[str, StandingsRow] | None = None,
) -> PowerRankingFeed:
    """Build the power ranking feed; raise PowerRankingBuildError when it is not
    valid."""
    label = season_label(season)
    if not in_regular_season(today, window) or index is None or not _usable(index):
        state, teams = PowerRankingState.UNAVAILABLE, []
    else:
        ordered = sorted(
            enumerate(index.teams), key=lambda pair: (pair[1].rank or 0, pair[0])
        )
        top = max(team.title or 0.0 for team in index.teams)
        state = PowerRankingState.AVAILABLE
        rows = standings or {}
        teams = [
            _team(team, rows.get(team.code), infos.get(team.code), top)
            for _, team in ordered
        ]
    try:
        return PowerRankingFeed(season=label, state=state, teams=teams)
    except ValidationError as error:
        first = ".".join(str(part) for part in error.errors()[0]["loc"])
        raise PowerRankingBuildError(
            f"invalid feed: {error.error_count()} errors, first at {first}"
        ) from None


class PowerRankingFeeds:
    def __init__(
        self,
        settings: Settings,
        store: StateStore,
        client: SourceClient,
        cache: FeedCache,
        stars: StarsJob,
        *,
        fetch_season_type: FetchSeasonType = season_types.fetch_season_type,
        fetch_power_index: FetchPowerIndex = power_index.fetch_power_index,
    ) -> None:
        self._settings = settings
        self._store = store
        self._client = client
        self._cache = cache
        self._stars = stars
        self._fetch_season_type = fetch_season_type
        self._fetch_power_index = fetch_power_index
        cache.register(self.kind())

    def check(self, feed_id: str) -> IdStatus:
        if feed_id != FEED_ID:
            return IdStatus.UNKNOWN
        if (
            self._stars.current_season() is None
            and read_by_id(self._settings.data_dir, KIND, FEED_ID) is None
        ):
            return IdStatus.NOT_READY
        return IdStatus.KNOWN

    def _standings_rows(self, season: int) -> dict[str, StandingsRow] | None:
        """The rows of the stored standings feed of the season by code, or none when
        it is missing, invalid or of another season. Reads no source."""
        body = read_by_id(
            self._settings.data_dir, standings_feed.KIND, standings_feed.FEED_ID
        )
        if body is None:
            return None
        try:
            stored = StandingsFeed.model_validate_json(body)
        except ValidationError:
            return None
        if stored.season != season_label(season):
            return None
        return {row.code: row for group in stored.conferences for row in group.teams}

    async def build(self, feed_id: str) -> PowerRankingFeed:
        season = self._stars.current_season()
        if season is None:
            raise PowerRankingBuildError("season not known yet")
        today = eastern_date(self._client.clock())
        window = await within_budget(
            ReadBudget(SEASON_TYPE_READS, stop_on_rate_limit=False),
            "power ranking: season type",
            lambda: self._fetch_season_type(
                self._client, season, REGULAR_SEASON, self._settings
            ),
        )
        index: PowerIndex | None = None
        if in_regular_season(today, window):
            index = await within_budget(
                ReadBudget(PAGE_READS, stop_on_rate_limit=False),
                "power ranking: league",
                lambda: self._fetch_power_index(self._client, season, self._settings),
            )
        codes = [] if index is None else [team.code for team in index.teams]
        rows = self._standings_rows(season) if codes else None
        if codes and rows is None:
            self._cache.warm(standings_feed.KIND, standings_feed.FEED_ID)
        infos = {
            code: team_info.cached_team_info(self._client, code, self._settings)
            for code in codes
        }
        return build_power_ranking_feed(season, today, window, index, infos, rows)

    def is_fresh(
        self, feed: PowerRankingFeed, built_at: dt.datetime, now: dt.datetime
    ) -> bool:
        if eastern_date(now) != eastern_date(built_at):
            return False
        if any(team.team.name is None for team in feed.teams):
            return now - built_at < NAMELESS_FRESH_FOR
        return True

    def serve_with(self, feed_id: str, feed: PowerRankingFeed) -> PowerRankingFeed:
        identities = self._stars.team_identities()
        teams = [
            team.model_copy(
                update={
                    "team": team.team.model_copy(
                        update={
                            "accent": resolved_color(team_colors(team.team, identities))
                        }
                    )
                }
            )
            for team in feed.teams
        ]
        return PowerRankingFeed.model_validate(
            feed.model_copy(update={"teams": teams}).model_dump(by_alias=False)
        )

    def keep(self, feed_id: str) -> bool:
        return feed_id == FEED_ID

    def kind(self) -> FeedKind[PowerRankingFeed]:
        return FeedKind(
            KIND,
            PowerRankingFeed,
            check=self.check,
            build=self.build,
            is_fresh=self.is_fresh,
            keep=self.keep,
            serve_with=self.serve_with,
        )
