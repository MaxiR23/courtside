# api/app/jobs/season_playoffs_finals_feed.py
#
# Playoffs finals feed of a past season (ADR 0046): the playoffs finals feed's
# shape, built by the playoffs finals builder from the stored season playoffs
# feed and the reads of that season, under a declared read budget of READ_BUDGET
# source reads (ADR 0058): the game detail of each Finals game (its sections and
# plays share its reads), and the postseason record and statistics of each
# finalist. It reads no roster and no per-player statistics. On a past season no
# read carries a postseason average, so `averages` is null and the Finals MVP's
# averages are null (ADR 0058); the best game still comes from the Finals box
# scores. The game details resolve the sides by provider id first; the details,
# sections, plays, team records and team statistics are null when the source
# answers 404 and any other failed read fails the build, because the feed is kept
# for good. A read past the budget or a rate limit (429, 503) fails the build and
# stores nothing. Stored highlights are added when served, never stored (ADR
# 0048), and detailAvailable is false.
#
# SeasonPlayoffsFinalsFeeds is the feed kind of the on-demand cache: the id is
# the season's end year, the feed is stored at
# feeds/season-playoffs-finals/{season}.json only when requested and the season
# playoffs feed is built first when it is missing. The current season is
# resolved before the cache (target) to the current playoffs finals feed. A feed
# is built once and kept (rule G): it is never deleted, and rebuilt only when its
# build version is not the current one (ADR 0053). Its league sides take the
# names, season codes and historical flags of the stored season playoffs feed's
# sides (identities_of), with no read (ADR 0054, ADR 0058).
#
# SEE: docs/api/playoffs.md, docs/adr/0046-season-playoffs-feeds.md,
# docs/adr/0048-highlights-backfill-and-edition-video.md,
# docs/adr/0058-bounded-past-competition-reads.md,
# api/app/jobs/playoffs_finals_feed.py

import asyncio
import datetime as dt
import functools
from collections.abc import Awaitable, Callable

from app.feeds.games import GameStatus
from app.feeds.playoffs_finals import PlayoffsFinalsFeed
from app.jobs import playoffs_finals_feed, season_playoffs_feed
from app.jobs.on_demand import (
    FeedCache,
    FeedKind,
    IdStatus,
    is_current_build,
    with_build_version,
)
from app.jobs.playoffs_finals_feed import (
    UNPLAYED_FRESH,
    FetchPlays,
    FetchRecord,
    FetchSections,
    FetchTeamStats,
    FinalsBuildError,
    FinalsSources,
    build_finals_feed,
    finals_series,
)
from app.jobs.season_playoffs_feed import SeasonPlayoffsFeeds, none_on_404
from app.jobs.season_standings_feed import past_season_status
from app.jobs.stars import StarsJob
from app.jobs.team_feed import season_label
from app.jobs.team_names import identities_of, named_sides
from app.settings import Settings
from app.sources import (
    finals_plays,
    game_detail,
    team_postseason,
)
from app.sources.game_detail import GameDetail
from app.sources.http import ReadBudget, SourceClient, within_budget
from app.storage.feeds import read_by_id
from app.storage.state import StateStore

KIND = "season-playoffs-finals"
# The most source reads one build sends (ADR 0058): 2 finalist records + 2
# finalist team statistics + 7 Finals game details.
READ_BUDGET = 11

FetchSeasonDetail = Callable[..., Awaitable[GameDetail]]


class SeasonPlayoffsFinalsFeeds:
    def __init__(
        self,
        settings: Settings,
        store: StateStore,
        client: SourceClient,
        cache: FeedCache,
        stars: StarsJob,
        playoffs: SeasonPlayoffsFeeds,
        *,
        fetch_game_detail: FetchSeasonDetail = game_detail.fetch_game_detail,
        fetch_game_detail_sections: FetchSections = (
            game_detail.fetch_past_game_detail_sections
        ),
        fetch_play_scores: FetchPlays = finals_plays.fetch_play_scores,
        fetch_team_postseason_record: FetchRecord = (
            team_postseason.fetch_team_postseason_record
        ),
        fetch_team_postseason_stats: FetchTeamStats = (
            team_postseason.fetch_team_postseason_stats
        ),
    ) -> None:
        self._settings = settings
        self._store = store
        self._client = client
        self._stars = stars
        self._playoffs = playoffs
        self._fetch_game_detail = fetch_game_detail
        self._fetch_game_detail_sections = fetch_game_detail_sections
        self._fetch_play_scores = fetch_play_scores
        self._fetch_team_postseason_record = fetch_team_postseason_record
        self._fetch_team_postseason_stats = fetch_team_postseason_stats
        cache.register(self.kind())

    def check(self, season: str) -> IdStatus:
        return past_season_status(season, self._stars.current_season())

    def target(self, season: str) -> tuple[str, str]:
        """The (kind, id) a route season maps to: the current season is the
        current playoffs finals feed."""
        current = self._stars.current_season()
        if current is not None and season == str(current):
            return playoffs_finals_feed.KIND, playoffs_finals_feed.FEED_ID
        return KIND, season

    def depends_on(self, season: str) -> tuple[str, str] | None:
        return (season_playoffs_feed.KIND, season)

    async def build(self, season: str) -> PlayoffsFinalsFeed:
        return await within_budget(
            ReadBudget(READ_BUDGET),
            f"season playoffs finals: {season}",
            lambda: self._build(season),
        )

    async def _build(self, season: str) -> PlayoffsFinalsFeed:
        year = int(season)
        stored = self._playoffs.stored(season)
        if stored is None:
            raise FinalsBuildError("season playoffs feed is not stored")
        if stored.season != season_label(year):
            raise FinalsBuildError("playoffs feed is of another season")
        series = finals_series(stored)
        top, bottom = series.top.team, series.bottom.team
        assert top is not None and bottom is not None
        codes = [str(top.code), str(bottom.code)]
        game_ids = [g.id for g in series.games if g.status is GameStatus.FINAL]
        client, settings = self._client, self._settings
        detail = functools.partial(self._fetch_game_detail, by_id_first=True)
        details, sections, plays, records, team_stats = await asyncio.gather(
            asyncio.gather(
                *(
                    none_on_404(detail(client, gid, settings, UNPLAYED_FRESH))
                    for gid in game_ids
                )
            ),
            asyncio.gather(
                *(
                    none_on_404(
                        self._fetch_game_detail_sections(
                            client, gid, settings, UNPLAYED_FRESH
                        )
                    )
                    for gid in game_ids
                )
            ),
            asyncio.gather(
                *(
                    none_on_404(
                        self._fetch_play_scores(client, gid, settings, UNPLAYED_FRESH)
                    )
                    for gid in game_ids
                )
            ),
            asyncio.gather(
                *(
                    none_on_404(
                        self._fetch_team_postseason_record(client, code, year, settings)
                    )
                    for code in codes
                )
            ),
            asyncio.gather(
                *(
                    none_on_404(
                        self._fetch_team_postseason_stats(client, code, year, settings)
                    )
                    for code in codes
                )
            ),
        )
        feed = build_finals_feed(
            FinalsSources(
                playoffs=stored,
                rosters={},
                details=dict(zip(game_ids, details, strict=True)),
                sections=dict(zip(game_ids, sections, strict=True)),
                plays=dict(zip(game_ids, plays, strict=True)),
                player_stats={},
                records=dict(zip(codes, records, strict=True)),
                team_stats=dict(zip(codes, team_stats, strict=True)),
            )
        )
        # No read carries a postseason average (ADR 0058).
        feed = PlayoffsFinalsFeed.model_validate(
            {**feed.model_dump(by_alias=False), "averages": None}
        )
        return with_build_version(named_sides(feed, identities_of(stored)))

    def stored(self, season: str) -> PlayoffsFinalsFeed | None:
        """The stored playoffs finals feed of a season, or none."""
        body = read_by_id(self._settings.data_dir, KIND, season)
        if body is None:
            return None
        try:
            return PlayoffsFinalsFeed.model_validate_json(body)
        except ValueError:
            return None

    def is_fresh(
        self, feed: PlayoffsFinalsFeed, built_at: dt.datetime, now: dt.datetime
    ) -> bool:
        return is_current_build(feed)

    def serve_with(self, feed_id: str, feed: PlayoffsFinalsFeed) -> PlayoffsFinalsFeed:
        highlights = self._store.highlights()
        data = feed.model_dump(by_alias=False)
        for entry in data["games"]:
            found = highlights.get(entry["game"]["id"])
            entry["highlights"] = (
                None if found is None else [found.model_dump(by_alias=False)]
            )
        return PlayoffsFinalsFeed.model_validate(data)

    def keep(self, feed_id: str) -> bool:
        return True

    def kind(self) -> FeedKind[PlayoffsFinalsFeed]:
        return FeedKind(
            KIND,
            PlayoffsFinalsFeed,
            check=self.check,
            build=self.build,
            is_fresh=self.is_fresh,
            keep=self.keep,
            serve_with=self.serve_with,
            depends_on=self.depends_on,
        )
