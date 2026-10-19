# api/app/jobs/playoffs_finals_feed.py
#
# Playoffs finals feed builder and kind: the data of the Finals page. The
# builder is a pure function from what the adapters returned and the stored
# playoffs feed to the feed; it reads no clock and no source. Seasonal code
# stays out of the core modules (ADR 0033). The games are the Finals games of the
# stored playoffs feed that are final, in number order, each with the series
# game as the playoffs feed stores it, the leaders of its detail, the win
# probability of the curve team and the largest deficit of that team. The curve
# team is the champion when the series is complete, else the side with more wins,
# else the top side. Its win probability is the source home value when it is
# home and one minus that value otherwise, to three decimals. The largest
# deficit is the most points the curve team trailed by over the plays with both
# scores, with the game second of the first play at it, and null when it never
# trailed. The Finals MVP is the first winner of the finals_mvp award of the
# playoffs feed, with the games, points, rebounds and assists of the season row
# of the postseason player stats and the box score line with the most points
# (the earliest game on a tie). Each finalist has its road (seed, regular season
# record, postseason record and the series against a team, round by round), and
# the head to head has 8 bars from the postseason team statistics with the
# percentages as fractions; the higher value is better, except for the
# technical fouls total, where the lower is. The averages list each roster
# player (players whose team changed are left out) in jersey order with the
# postseason averages, a player with no values last; at
# most FINALS_ROSTER_READS players per finalist are read, a further one has no
# values. A failed detail, plays,
# stats or record read only nulls its part. The season unknown, no playoffs feed
# of the season, a Finals with no game or a side with no team, and an invalid
# feed, fail the build.
# PlayoffsFinalsFeeds is the feed kind of the on-demand cache: the only id is
# league, the playoffs feed is built first when it is missing or stale, and the
# feed expires 1 hour after a postseason final game that follows the build,
# when the playoffs feed is rebuilt after it, and 7 days after the build (rule
# G). Once the series is complete it is kept while its season is the current
# one. The route serves the playoffs feed first, so a missing one answers 503.
# The stored highlights and detailAvailable are added when served, never stored.
# The build runs under READ_BUDGET reads, counting reads only, and reads the
# postseason averages of at most FINALS_ROSTER_READS players per finalist (ADR 0067).
#
# SEE: docs/api/playoffs.md, docs/adr/0033-playoffs-finals-feed.md,
# api/app/jobs/playoffs_feed.py,
# docs/adr/0067-read-budgets-of-every-on-demand-build.md

import asyncio
import datetime as dt
import logging
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from app.feeds.game_detail import GameResult
from app.feeds.games import GameStatus
from app.feeds.playoffs import (
    AwardCode,
    PlayoffsFeed,
    Series,
    SeriesId,
    SeriesStatus,
    round_of_series,
)
from app.feeds.playoffs_finals import HeadToHeadStat, PlayoffsFinalsFeed
from app.jobs import playoffs_feed
from app.jobs.games import GamesJob
from app.jobs.on_demand import FeedCache, FeedKind, IdStatus
from app.jobs.playoffs_feed import PlayoffsFeeds
from app.jobs.stars import StarsJob
from app.jobs.team_feed import (
    TeamBuildError,
    feed_expired,
    player_name,
    roster_order,
    season_label,
)
from app.settings import Settings
from app.sources import finals_plays, game_detail, player_stats, team_postseason
from app.sources.finals_plays import PlayScore
from app.sources.game_detail import BoxScoreRosterEntry, GameDetail, GameDetailSections
from app.sources.http import (
    Freshness,
    ReadBudget,
    SourceClient,
    SourceError,
    within_budget,
)
from app.sources.player_stats import PlayerStats, StatLine
from app.sources.team_players import RosterEntry
from app.sources.team_postseason import TeamPostseasonRecord, TeamPostseasonStats
from app.storage.state import StateStore

logger = logging.getLogger(__name__)

KIND = "playoffs-finals"
FEED_ID = "league"
# The most roster players of one finalist whose postseason averages are
# read; a further player is listed with no values (ADR 0067).
FINALS_ROSTER_READS = 18
# The most source reads one build sends: 7 Finals games (detail, sections and
# plays share one URL) + 2 finalist records + 2 finalist team statistics +
# 2 x FINALS_ROSTER_READS player stats + 1 Finals MVP (ADR 0067).
READ_BUDGET = 7 + 2 + 2 + 2 * FINALS_ROSTER_READS + 1
ROUND_TO = 3
UNPLAYED_FRESH = dt.timedelta(hours=1)
LOWER_IS_BETTER = frozenset({HeadToHeadStat.TECHNICAL_FOULS})
PERCENT_STATS = frozenset(
    {HeadToHeadStat.FIELD_GOAL_PCT, HeadToHeadStat.EFFECTIVE_FG_PCT}
)

FetchDetail = Callable[[SourceClient, str, Settings, Freshness], Awaitable[GameDetail]]
FetchSections = Callable[
    [SourceClient, str, Settings, Freshness], Awaitable[GameDetailSections]
]
FetchPlays = Callable[
    [SourceClient, str, Settings, Freshness], Awaitable[list[PlayScore]]
]
FetchStats = Callable[..., Awaitable[PlayerStats]]
FetchRecord = Callable[
    [SourceClient, str, int, Settings], Awaitable[TeamPostseasonRecord]
]
FetchTeamStats = Callable[
    [SourceClient, str, int, Settings], Awaitable[TeamPostseasonStats]
]


class FinalsBuildError(Exception):
    """The playoffs finals feed built from the fetched data is not valid."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class FinalsSources:
    """What the finals build reads. Never reaches a feed."""

    playoffs: PlayoffsFeed
    rosters: Mapping[str, Sequence[RosterEntry | BoxScoreRosterEntry]]
    details: Mapping[str, GameDetail | None]
    sections: Mapping[str, GameDetailSections | None]
    plays: Mapping[str, Sequence[PlayScore] | None]
    player_stats: Mapping[str, PlayerStats | None]
    records: Mapping[str, TeamPostseasonRecord | None]
    team_stats: Mapping[str, TeamPostseasonStats | None]


def finals_series(feed: PlayoffsFeed) -> Series:
    """The Finals series; raise FinalsBuildError when it has no game or a side
    without a team."""
    series = next(s for s in feed.bracket if s.id is SeriesId.FINALS)
    if not series.games:
        raise FinalsBuildError("the Finals has no game")
    if series.top.team is None or series.bottom.team is None:
        raise FinalsBuildError("a Finals side has no team")
    return series


def curve_team(series: Series) -> str:
    """The champion, else the side with more wins, else the top side."""
    top, bottom = series.top.team, series.bottom.team
    assert top is not None and bottom is not None
    if series.winner is not None:
        return series.winner
    top_wins, bottom_wins = series.top.wins or 0, series.bottom.wins or 0
    return str(bottom.code if bottom_wins > top_wins else top.code)


def team_curve(
    sections: GameDetailSections | None, team_is_home: bool
) -> dict[str, Any] | None:
    """The win probability of the team at each point, or none without a curve."""
    if (
        sections is None
        or not sections.win_probability
        or sections.win_probability_periods is None
    ):
        return None
    return {
        "points": [
            {
                "elapsed_seconds": point.elapsed_seconds,
                "win_probability": round(
                    point.home_win_probability
                    if team_is_home
                    else 1 - point.home_win_probability,
                    ROUND_TO,
                ),
            }
            for point in sections.win_probability
        ],
        "periods": sections.win_probability_periods,
    }


def largest_deficit(
    plays: Sequence[PlayScore] | None, team_is_home: bool
) -> dict[str, int] | None:
    """The most points the team trailed by and when it first did, or none."""
    best: dict[str, int] | None = None
    for play in plays or []:
        mine, theirs = (
            (play.home_score, play.away_score)
            if team_is_home
            else (play.away_score, play.home_score)
        )
        behind = theirs - mine
        if behind > 0 and (best is None or behind > best["points"]):
            best = {"points": behind, "elapsed_seconds": play.elapsed_seconds}
    return best


def season_row(stats: PlayerStats | None, label: str) -> StatLine | None:
    """The per game row of the season, or none."""
    if stats is None:
        return None
    return next((row for row in stats.per_game if row.season == label), None)


def _record(wins: int | None, losses: int | None) -> str | None:
    return None if wins is None or losses is None else f"{wins}-{losses}"


def _picture_record(feed: PlayoffsFeed, code: str) -> str | None:
    for table in feed.picture:
        for row in table.rows:
            if row.team.code == code:
                return _record(row.wins, row.losses)
    return None


def road(
    feed: PlayoffsFeed, code: str, record: TeamPostseasonRecord | None
) -> dict[str, Any]:
    """The road to the title of a finalist."""
    finals = next(s for s in feed.bracket if s.id is SeriesId.FINALS)
    side = (
        finals.top
        if finals.top.team and finals.top.team.code == code
        else finals.bottom
    )
    ordered = sorted(
        enumerate(feed.bracket), key=lambda pair: (round_of_series(pair[1].id), pair[0])
    )
    series: list[dict[str, Any]] = []
    for _, found in ordered:
        if found.top.team and found.top.team.code == code:
            mine, other = found.top, found.bottom
        elif found.bottom.team and found.bottom.team.code == code:
            mine, other = found.bottom, found.top
        else:
            continue
        if other.team is None:
            continue
        series.append(
            {
                "round": found.round,
                "opponent": other.team,
                "opponent_seed": other.seed,
                "wins": mine.wins,
                "losses": other.wins,
                "result": None
                if found.winner is None
                else (GameResult.WIN if found.winner == code else GameResult.LOSS),
            }
        )
    return {
        "team": side.team,
        "seed": side.seed,
        "regular_season": _picture_record(feed, code),
        "postseason": None if record is None else record.overall,
        "series": series,
    }


def _bar_value(stat: HeadToHeadStat, stats: TeamPostseasonStats | None) -> float | None:
    raw = None if stats is None else getattr(stats, stat.value)
    if raw is None:
        return None
    return float(raw / 100 if stat in PERCENT_STATS else raw)


def bars(
    stats: Mapping[str, TeamPostseasonStats | None], codes: Sequence[str]
) -> list[dict[str, Any]]:
    """The 8 head to head bars of the two teams."""
    found = []
    for stat in HeadToHeadStat:
        values = [_bar_value(stat, stats.get(code)) for code in codes]
        better: str | None = None
        first, second = values
        if first is not None and second is not None and first != second:
            first_wins = (
                (first < second) if stat in LOWER_IS_BETTER else (first > second)
            )
            better = codes[0] if first_wins else codes[1]
        found.append(
            {
                "stat": stat,
                "values": [
                    {"team_code": code, "value": value}
                    for code, value in zip(codes, values, strict=True)
                ],
                "better": better,
            }
        )
    return found


def averages(
    code: str,
    entries: Sequence[RosterEntry | BoxScoreRosterEntry],
    stats: Mapping[str, PlayerStats | None],
    label: str,
) -> dict[str, Any]:
    """The postseason averages of a roster in jersey order, a player with no
    values last."""
    players: list[dict[str, Any]] = []
    for entry in sorted(entries, key=lambda e: roster_order(e.jersey)):
        row = season_row(stats.get(entry.player_id), label)
        players.append(
            {
                "player_id": entry.player_id,
                "name": player_name(entry),
                "photo_url": entry.headshot_url,
                "points": None if row is None else row.points,
                "rebounds": None if row is None else row.rebounds,
                "assists": None if row is None else row.assists,
                "blocks": None if row is None else row.blocks,
                "field_goal_pct": None if row is None else row.field_goal_pct / 100,
            }
        )
    players.sort(
        key=lambda p: all(
            p[name] is None
            for name in ("points", "rebounds", "assists", "blocks", "field_goal_pct")
        )
    )
    return {"team_code": code, "players": players}


def _mvp_winner(feed: PlayoffsFeed) -> Any:
    for award in feed.awards or []:
        if award.code is AwardCode.FINALS_MVP:
            return award.winners[0]
    return None


def mvp_id(feed: PlayoffsFeed) -> str | None:
    """The player id of the Finals MVP, or none."""
    winner = _mvp_winner(feed)
    return None if winner is None else str(winner.player_id)


def _best_game(
    player_id: str,
    games: Sequence[Any],
    sections: Mapping[str, GameDetailSections | None],
) -> dict[str, Any] | None:
    best: dict[str, Any] | None = None
    for game in games:
        found = sections.get(game.id)
        if found is None or found.box_score is None:
            continue
        for side in (found.box_score.away, found.box_score.home):
            for line in side.players:
                # A line with no points is not a best game (ADR 0055).
                if (
                    line.player_id == player_id
                    and line.points is not None
                    and (best is None or line.points > best["points"])
                ):
                    best = {
                        "game_id": game.id,
                        "number": game.number,
                        "points": line.points,
                    }
    return best


def _mvp(
    feed: PlayoffsFeed,
    games: Sequence[Any],
    sources: FinalsSources,
) -> dict[str, Any] | None:
    winner = _mvp_winner(feed)
    if winner is None:
        return None
    row = season_row(sources.player_stats.get(winner.player_id), feed.season)
    return {
        "player_id": winner.player_id,
        "name": winner.name,
        "photo_url": winner.photo_url,
        "team_code": winner.team_code,
        "games": None if row is None else row.games_played,
        "points": None if row is None else row.points,
        "rebounds": None if row is None else row.rebounds,
        "assists": None if row is None else row.assists,
        "best_game": _best_game(winner.player_id, games, sources.sections),
    }


def build_finals_feed(sources: FinalsSources) -> PlayoffsFinalsFeed:
    """Build the playoffs finals feed; raise FinalsBuildError when it is not
    valid."""
    feed = sources.playoffs
    series = finals_series(feed)
    top, bottom = series.top.team, series.bottom.team
    assert top is not None and bottom is not None
    codes = [str(top.code), str(bottom.code)]
    curve = curve_team(series)
    played = sorted(
        (g for g in series.games if g.status is GameStatus.FINAL),
        key=lambda g: g.number,
    )
    games = [
        {
            "game": game,
            "leaders": None
            if (detail := sources.details.get(game.id)) is None
            else detail.leaders,
            "win_probability": team_curve(
                sources.sections.get(game.id), game.home.code == curve
            ),
            "largest_deficit": largest_deficit(
                sources.plays.get(game.id), game.home.code == curve
            ),
            "highlights": None,
        }
        for game in played
    ]
    try:
        roads = [road(feed, code, sources.records.get(code)) for code in codes]
        return PlayoffsFinalsFeed.model_validate(
            {
                "season": feed.season,
                "status": series.status,
                "champion": series.winner,
                "curve_team": curve,
                "games": games,
                "finals_mvp": _mvp(feed, played, sources),
                "road": roads,
                "head_to_head": {
                    "records": [
                        {"team_code": code, "record": found["postseason"]}
                        for code, found in zip(codes, roads, strict=True)
                    ],
                    "bars": bars(sources.team_stats, codes),
                },
                "averages": [
                    averages(
                        code,
                        sources.rosters.get(code, []),
                        sources.player_stats,
                        feed.season,
                    )
                    for code in codes
                ],
            }
        )
    except TeamBuildError as error:
        raise FinalsBuildError(error.reason) from None
    except ValidationError as error:
        location = ".".join(str(part) for part in error.errors()[0]["loc"])
        raise FinalsBuildError(
            f"invalid feed: {error.error_count()} errors, first at {location}"
        ) from None


class PlayoffsFinalsFeeds:
    def __init__(
        self,
        settings: Settings,
        store: StateStore,
        client: SourceClient,
        cache: FeedCache,
        games: GamesJob,
        stars: StarsJob,
        playoffs: PlayoffsFeeds,
        *,
        fetch_game_detail: FetchDetail = game_detail.fetch_game_detail,
        fetch_game_detail_sections: FetchSections = (
            game_detail.fetch_game_detail_sections
        ),
        fetch_play_scores: FetchPlays = finals_plays.fetch_play_scores,
        fetch_player_stats: FetchStats = player_stats.fetch_player_stats,
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
        self._games = games
        self._stars = stars
        self._playoffs = playoffs
        self._fetch_game_detail = fetch_game_detail
        self._fetch_game_detail_sections = fetch_game_detail_sections
        self._fetch_play_scores = fetch_play_scores
        self._fetch_player_stats = fetch_player_stats
        self._fetch_team_postseason_record = fetch_team_postseason_record
        self._fetch_team_postseason_stats = fetch_team_postseason_stats
        cache.register(self.kind())

    def check(self, feed_id: str) -> IdStatus:
        if feed_id != FEED_ID:
            return IdStatus.UNKNOWN
        stored = self._playoffs.stored()
        if stored is None:
            return IdStatus.NOT_READY
        season = self._stars.current_season()
        if season is not None and stored.season != season_label(season):
            return IdStatus.UNKNOWN
        finals = next(s for s in stored.bracket if s.id is SeriesId.FINALS)
        if not finals.games:
            return IdStatus.UNKNOWN
        return IdStatus.KNOWN

    def depends_on(self, feed_id: str) -> tuple[str, str] | None:
        return (playoffs_feed.KIND, playoffs_feed.FEED_ID)

    def _freshness(self, game_id: str) -> Freshness:
        return self._store.final_time(game_id) or UNPLAYED_FRESH

    async def _guard[T](self, read: Awaitable[T]) -> T | None:
        try:
            return await read
        except SourceError:
            return None

    async def build(self, feed_id: str) -> PlayoffsFinalsFeed:
        return await within_budget(
            ReadBudget(READ_BUDGET, stop_on_rate_limit=False),
            f"playoffs finals: {feed_id}",
            lambda: self._build(feed_id),
        )

    async def _build(self, feed_id: str) -> PlayoffsFinalsFeed:
        season = self._stars.current_season()
        if season is None:
            raise FinalsBuildError("season not known yet")
        stored = self._playoffs.stored()
        if stored is None:
            raise FinalsBuildError("playoffs feed is not stored")
        if stored.season != season_label(season):
            raise FinalsBuildError("playoffs feed is of another season")
        series = finals_series(stored)
        top, bottom = series.top.team, series.bottom.team
        assert top is not None and bottom is not None
        codes = [str(top.code), str(bottom.code)]
        game_ids = [g.id for g in series.games if g.status is GameStatus.FINAL]
        entries = self._stars.roster_entries()
        rosters = {
            code: [
                entry
                for entry in entries.get(code, [])
                if self._stars.player_team(entry.player_id) == code
            ]
            for code in codes
        }
        mvp = mvp_id(stored)
        read_ids: list[str] = []
        for code in codes:
            ordered = sorted(rosters[code], key=lambda e: roster_order(e.jersey))
            if len(ordered) > FINALS_ROSTER_READS:
                logger.warning(
                    "playoffs finals: %d players of %s not read",
                    len(ordered) - FINALS_ROSTER_READS,
                    code,
                )
            read_ids += [entry.player_id for entry in ordered[:FINALS_ROSTER_READS]]
        player_ids = list(dict.fromkeys(read_ids + ([mvp] if mvp is not None else [])))
        client, settings = self._client, self._settings
        details, sections, plays, records, team_stats, stats = await asyncio.gather(
            asyncio.gather(
                *(
                    self._guard(
                        self._fetch_game_detail(
                            client, gid, settings, self._freshness(gid)
                        )
                    )
                    for gid in game_ids
                )
            ),
            asyncio.gather(
                *(
                    self._guard(
                        self._fetch_game_detail_sections(
                            client, gid, settings, self._freshness(gid)
                        )
                    )
                    for gid in game_ids
                )
            ),
            asyncio.gather(
                *(
                    self._guard(
                        self._fetch_play_scores(
                            client, gid, settings, self._freshness(gid)
                        )
                    )
                    for gid in game_ids
                )
            ),
            asyncio.gather(
                *(
                    self._guard(
                        self._fetch_team_postseason_record(
                            client, code, season, settings
                        )
                    )
                    for code in codes
                )
            ),
            asyncio.gather(
                *(
                    self._guard(
                        self._fetch_team_postseason_stats(
                            client, code, season, settings
                        )
                    )
                    for code in codes
                )
            ),
            asyncio.gather(
                *(
                    self._guard(
                        self._fetch_player_stats(client, pid, settings, playoffs=True)
                    )
                    for pid in player_ids
                )
            ),
        )
        return build_finals_feed(
            FinalsSources(
                playoffs=stored,
                rosters=rosters,
                details=dict(zip(game_ids, details, strict=True)),
                sections=dict(zip(game_ids, sections, strict=True)),
                plays=dict(zip(game_ids, plays, strict=True)),
                player_stats=dict(zip(player_ids, stats, strict=True)),
                records=dict(zip(codes, records, strict=True)),
                team_stats=dict(zip(codes, team_stats, strict=True)),
            )
        )

    def final_times(
        self, feed: PlayoffsFinalsFeed, built_at: dt.datetime, now: dt.datetime
    ) -> list[dt.datetime]:
        """The final times of the postseason games that can expire the feed: those
        of the stored playoffs feed and the games of this feed."""
        times: list[dt.datetime] = []
        stored = self._playoffs.stored()
        if stored is not None:
            times += self._playoffs.final_times(stored, built_at, now)
        own = (self._store.final_time(g.game.id) for g in feed.games)
        return times + [time for time in own if time is not None]

    def is_fresh(
        self, feed: PlayoffsFinalsFeed, built_at: dt.datetime, now: dt.datetime
    ) -> bool:
        if feed.status is SeriesStatus.COMPLETE:
            season = self._stars.current_season()
            if season is None or feed.season == season_label(season):
                return True
        parent = self._store.feed_build(playoffs_feed.KIND, playoffs_feed.FEED_ID)
        if (
            parent is not None
            and parent.last_build is not None
            and parent.last_build > built_at
        ):
            return False
        return not feed_expired(built_at, now, self.final_times(feed, built_at, now))

    def serve_with(self, feed_id: str, feed: PlayoffsFinalsFeed) -> PlayoffsFinalsFeed:
        ids = {game.id for game in self._games.loaded_games()}
        highlights = self._store.highlights_for(entry.game.id for entry in feed.games)
        data = feed.model_dump(by_alias=False)
        for entry in data["games"]:
            game_id = entry["game"]["id"]
            entry["game"]["detail_available"] = game_id in ids
            found = highlights.get(game_id)
            entry["highlights"] = (
                None if found is None else [found.model_dump(by_alias=False)]
            )
        return PlayoffsFinalsFeed.model_validate(data)

    def keep(self, feed_id: str) -> bool:
        return feed_id == FEED_ID

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
