# api/app/jobs/season_all_star_feed.py
#
# All-Star feed of a past season (ADR 0047): the All-Star feed's shape, built by
# the All-Star feed builder from the sources of that season. The edition of a
# season is the stored all_star_editions row when there is one; otherwise it is
# the first February day (US Eastern) of that season's calendar, read in order
# with the All-Star scoreboard view, that has All-Star games, which is then
# stored. A season with none is remembered in memory as having no edition (a
# 404 with no further read, until a restart). The build declares a read budget of
# READ_BUDGET source reads and stops at the first day with All-Star games. The
# previous edition reads nothing: it is taken from the stored feed of the season
# before when that one is stored and after, else it is null (ADR 0058). A game detail, sections,
# extras or season awards read that answers 404 only nulls its part; any other
# failed read fails the build, because the feed is kept for good. League teams
# are null (no roster of that season is read) and no per-game highlight is set;
# the stored edition video is added when served as editionHighlight, and an
# edition served with none starts one on-demand search (ADR 0065).
# The sections, extras and awards are read by read_edition_mvp_inputs, shared
# with the current feed's previous edition (ADR 0056).
# A past All-Star feed is stored only when it builds as after: any other state
# fails the build, logs the reason and stores nothing.
#
# SeasonAllStarFeeds is the feed kind of the on-demand cache: the id is the
# season's end year, the feed is stored at feeds/season-all-star/{season}.json
# only when requested. A season is valid from 1994 to the season before the
# current one (past_season_status). The current season is resolved before the
# cache (target) to the current All-Star feed. A feed is built once and kept
# (rule G): it is deleted with its build row when not served in 90 days and rebuilt on
# its next request (ADR 0063), and rebuilt otherwise only when its build version
# is not the current one (ADR 0053).
#
# SEE: docs/api/all-star.md, docs/adr/0047-season-all-star-feed.md,
# docs/adr/0058-bounded-past-competition-reads.md,
# docs/adr/0048-highlights-backfill-and-edition-video.md,
# docs/adr/0065-background-work-limited-to-games-highlights-and-stars.md,
# docs/adr/0056-paced-past-builds-and-one-edition-mvp-path.md,
# api/app/jobs/all_star_feed.py

import asyncio
import datetime as dt
import logging
from collections.abc import Sequence

from pydantic import ValidationError

from app.feeds.all_star import AllStarFeed, AllStarState
from app.feeds.calendar import FIRST_SEASON
from app.feeds.games import GameStatus
from app.jobs import all_star_feed
from app.jobs.all_star_edition_videos import AllStarEditionVideos
from app.jobs.all_star_feed import (
    PREVIOUS_FRESH,
    AllStarBuildError,
    AllStarSources,
    FetchAwards,
    FetchDay,
    FetchDetail,
    FetchExtras,
    FetchSections,
    _none_on_404,
    _Reads,
    build_all_star_feed,
    edition_games,
    read_edition_mvp_inputs,
)
from app.jobs.calendar_feed import FetchSeasonCalendar
from app.jobs.games import eastern_date
from app.jobs.on_demand import (
    FeedCache,
    FeedKind,
    IdStatus,
    UnknownFeedError,
    is_current_build,
    with_build_version,
)
from app.jobs.season_standings_feed import past_season_status
from app.jobs.stars import StarsJob
from app.settings import Settings
from app.sources import (
    all_star_detail,
    all_star_scoreboard,
    game_detail,
    season_awards,
    season_calendar,
)
from app.sources.all_star_scoreboard import AllStarScoreboardGame
from app.sources.http import ReadBudget, SourceClient, within_budget
from app.storage.feeds import read_by_id
from app.storage.state import StateStore

logger = logging.getLogger(__name__)

KIND = "season-all-star"
FEBRUARY = 2
# The most source reads one build sends (ADR 0058): 1 calendar + 29 February days
# + 4 game details of the edition + 26 awards (the index and 25 documents).
READ_BUDGET = 60

Edition = tuple[dt.date, list[AllStarScoreboardGame]]


def february_days(moments: Sequence[dt.datetime], season: int) -> list[dt.date]:
    """The sorted, unique US Eastern dates of the moments that fall in February
    of the season's end year."""
    return sorted(
        {
            day
            for day in (eastern_date(moment) for moment in moments)
            if day.year == season and day.month == FEBRUARY
        }
    )


def with_stored_previous(feed: AllStarFeed, stored: AllStarFeed | None) -> AllStarFeed:
    """The feed with the previous edition taken from the stored feed of the
    season before, which is already the recap and the after view of that edition.
    The feed as it is when there is none, it is not after, or it has no final
    championship game with its sides, score and winner."""
    if stored is None or stored.state is not AllStarState.AFTER:
        return feed
    final = next((g for g in stored.edition.games if g.championship), None)
    if (
        final is None
        or final.status is not GameStatus.FINAL
        or final.away is None
        or final.home is None
        or final.score is None
        or final.winner is None
        or stored.edition.date is None
    ):
        return feed
    edition = stored.edition.model_dump(by_alias=False)
    edition["edition_highlight"] = None
    mvp = None if stored.mvp is None else stored.mvp.model_dump(by_alias=False)
    try:
        return AllStarFeed.model_validate(
            {
                **feed.model_dump(by_alias=False),
                "previous": {
                    "year": stored.year,
                    "date": stored.edition.date,
                    "venue": edition["venue"],
                    "championship": {
                        "game_id": final.id,
                        "away": final.away.model_dump(by_alias=False),
                        "home": final.home.model_dump(by_alias=False),
                        "score": final.score.model_dump(by_alias=False),
                        "winner": final.winner,
                        "overtime": final.overtime,
                    },
                    "mvp": mvp,
                },
                "previous_edition": {**edition, "mvp": mvp},
            }
        )
    except ValidationError:
        return feed


class SeasonAllStarFeeds:
    def __init__(
        self,
        settings: Settings,
        store: StateStore,
        client: SourceClient,
        cache: FeedCache,
        stars: StarsJob,
        *,
        fetch_season_calendar: FetchSeasonCalendar = (
            season_calendar.fetch_season_calendar
        ),
        fetch_all_star_games: FetchDay = all_star_scoreboard.fetch_all_star_games,
        fetch_game_detail: FetchDetail = game_detail.fetch_game_detail,
        fetch_game_detail_sections: FetchSections = (
            game_detail.fetch_game_detail_sections
        ),
        fetch_all_star_extras: FetchExtras = all_star_detail.fetch_all_star_extras,
        fetch_season_awards: FetchAwards = season_awards.fetch_season_awards,
        edition_videos: AllStarEditionVideos | None = None,
    ) -> None:
        self._settings = settings
        self._store = store
        self._client = client
        self._stars = stars
        self._fetch_season_calendar = fetch_season_calendar
        self._fetch_all_star_games = fetch_all_star_games
        self._fetch_game_detail = fetch_game_detail
        self._fetch_game_detail_sections = fetch_game_detail_sections
        self._fetch_all_star_extras = fetch_all_star_extras
        self._fetch_season_awards = fetch_season_awards
        self._edition_videos = edition_videos
        self._no_edition: set[int] = set()
        cache.register(self.kind())

    def check(self, season: str) -> IdStatus:
        status = past_season_status(season, self._stars.current_season())
        if (
            status is IdStatus.KNOWN
            and int(season) in self._no_edition
            and self._store.all_star_edition(int(season)) is None
        ):
            return IdStatus.UNKNOWN
        return status

    def target(self, season: str) -> tuple[str, str]:
        """The (kind, id) a route season maps to: the current season is the
        current All-Star feed."""
        current = self._stars.current_season()
        if current is not None and season == str(current):
            return all_star_feed.KIND, all_star_feed.FEED_ID
        return KIND, season

    async def _edition(self, season: int) -> Edition | None:
        """The day and games of a season's edition, or none when it has none."""
        if season < FIRST_SEASON:
            return None
        client, settings = self._client, self._settings
        record = self._store.all_star_edition(season)
        if record is None and season in self._no_edition:
            return None
        if record is not None:
            games = await self._fetch_all_star_games(
                client, record.game_date, settings, PREVIOUS_FRESH
            )
            return record.game_date, games
        moments = await self._fetch_season_calendar(client, season, settings)
        for day in february_days(moments, season):
            games = await self._fetch_all_star_games(
                client, day, settings, PREVIOUS_FRESH
            )
            if games:
                self._store.set_all_star_edition(season, day, [g.id for g in games])
                return day, games
        self._no_edition.add(season)
        logger.info("season all-star: no edition found for %d", season)
        return None

    async def _reads(
        self, season: int, games: Sequence[AllStarScoreboardGame]
    ) -> _Reads:
        client, settings = self._client, self._settings
        kept = edition_games(games)
        ids = [g.id for g in kept]
        details, mvp_inputs = await asyncio.gather(
            asyncio.gather(
                *(
                    _none_on_404(
                        self._fetch_game_detail(client, i, settings, PREVIOUS_FRESH)
                    )
                    for i in ids
                )
            ),
            read_edition_mvp_inputs(
                client,
                settings,
                season,
                games,
                fetch_game_detail_sections=self._fetch_game_detail_sections,
                fetch_all_star_extras=self._fetch_all_star_extras,
                fetch_season_awards=self._fetch_season_awards,
            ),
        )
        return _Reads(
            dict(zip(ids, details, strict=True)),
            mvp_inputs.sections,
            mvp_inputs.extras,
            mvp_inputs.awards,
            None,
        )

    async def build(self, season: str) -> AllStarFeed:
        return await within_budget(
            ReadBudget(READ_BUDGET),
            f"season all-star: {season}",
            lambda: self._build(season),
        )

    async def _build(self, season: str) -> AllStarFeed:
        year = int(season)
        found = await self._edition(year)
        if found is None:
            raise UnknownFeedError(season)
        reads = await self._reads(year, found[1])
        try:
            feed = build_all_star_feed(
                AllStarSources(
                    year=year,
                    edition_date=found[0],
                    games=found[1],
                    details=reads.details,
                    sections=reads.sections,
                    extras=reads.extras,
                    colors={},
                    player_teams={},
                    awards=reads.awards,
                    previous=None,
                )
            )
            if feed.state is not AllStarState.AFTER:
                raise AllStarBuildError(f"the {year} edition is not final")
        except AllStarBuildError as error:
            logger.warning("season all-star: %s not built: %s", season, error.reason)
            raise
        feed = with_stored_previous(feed, self.stored(str(year - 1)))
        return with_build_version(feed)

    def stored(self, season: str) -> AllStarFeed | None:
        """The stored All-Star feed of a season, or none when missing or invalid."""
        body = read_by_id(self._settings.data_dir, KIND, season)
        if body is None:
            return None
        try:
            return AllStarFeed.model_validate_json(body)
        except ValidationError:
            return None

    def is_fresh(
        self, feed: AllStarFeed, built_at: dt.datetime, now: dt.datetime
    ) -> bool:
        return is_current_build(feed)

    def keep(self, feed_id: str) -> bool:
        return True

    def serve_with(self, feed_id: str, feed: AllStarFeed) -> AllStarFeed:
        if self._edition_videos is not None:
            self._edition_videos.request_for(feed)
        return all_star_feed.with_edition_highlights(feed, self._store)

    def kind(self) -> FeedKind[AllStarFeed]:
        return FeedKind(
            KIND,
            AllStarFeed,
            check=self.check,
            build=self.build,
            is_fresh=self.is_fresh,
            keep=self.keep,
            serve_with=self.serve_with,
        )
