# api/app/jobs/all_star_feed.py
#
# All-Star feed builder and kind: the data of the All-Star page. The builder is a
# pure function from what the adapters returned to the feed; it reads no clock
# and no source. Seasonal code stays out of the core modules (ADR 0036). The
# edition is the day the discovery job stored: its games are the All-Star games
# of that scoreboard day, in start order, without the canceled ones. The note of
# a game is "NBA All-Star - <round>" with an optional format suffix; the round is
# the label and a game of the round "Championship" is the championship; the only
# game of a single-game edition is the championship whatever its round (ADR 0053).
# Two distinct sides of an edition that share a name, as East and West
# "All-Stars", are drawn with their code and name, "EAST All-Stars" (ADR 0053).
# The state
# is before while no game is live or final (the feed then has the date and the
# venue when known, and no games or teams), after once there is a game and every
# game is final, and live otherwise. A team is a distinct side of the games in
# order of appearance. Wins and losses come from final games only. Once the
# championship is final its winner is the champion and its loser the runner-up,
# and every other team is eliminated, with the round label of its last game; until
# then a team with a final game is so far and the others are yet to play. Who
# advances is never inferred. The format is the parts of the first game that has
# one: the target points and untimed from a note suffix, else the regulation
# periods and minutes of the game summary (ADR 0054). A game has the box score of both teams
# (each player with the jersey, the position and the league team found by id in
# the rosters of the stars job, null when not found), the six team statistics with
# the better side, the leaders of the detail, the Top 5 rows (points, then
# rebounds plus assists) and the attendance and broadcasts. The status text, the
# clock and the period are passed as the scoreboard view returns them. The overtime
# flag is a period beyond the regulation periods. The MVP is the first winner of
# the All-Star MVP award, with one line per final game he has a box row in and the
# day totals. The recap is the previous edition: the Championship result, the
# date, the venue and its MVP, null when it was not discovered, its day could not
# be read or its championship is not final. The previous edition is also carried
# whole, as its after view, with its MVP, from the same reads and only when every
# game of it is final. The edition also carries its counts, its default game and
# its next game, a live game its leading side, a box score its top scorers and a
# team its result rows, so the page counts and compares nothing. A failed detail, summary, extras, team
# info, awards or previous edition read only nulls its part. The MVP of an edition
# in play that comes out null is logged as a warning with the season and the reason
# (the awards read failed, no All-Star MVP award with a winner, or no box row of
# the winner in the final games), each time a build nulls it. The season unknown, a
# failed current scoreboard day and an invalid feed fail the build.
#
# AllStarFeeds is the feed kind of the on-demand cache: the only id is "league",
# the feed is stored at feeds/all-star/league.json only when requested, and it
# answers 503 (not ready) until the stars job knows the season and has fetched
# every roster, and the discovery job has completed a run. It expires (rule G) 30
# seconds after the build while the state is live or the edition's date is today,
# and a request that finds it stale waits for the rebuild; before the edition, when
# the discovery runs after the build; once every game is final it is kept while its
# season is the current one, but only when it was built at least 1 hour after the
# latest time the games were first seen final (before that it expires with the
# live interval). The first build that sees a game final stores that time, and the
# reads of a final game are fresh only when made at or after it. The previous
# edition is finished data: its scoreboard day and game details are read with a
# 24-hour freshness. The inputs of its MVP (awards, sections, extras) are read by
# read_edition_mvp_inputs and its MVP is built by mvp, both shared with the season
# feed; its league teams come from today's rosters as before. A failure of one of
# them other than a 404 keeps the stored previous blocks when they carry an MVP,
# else fails the build, which keeps the stored feed (ADR 0056). Every other part of
# the previous edition is read as before. The stored edition video is added when served as
# editionHighlight, never stored; no game carries a per-game highlight (ADR 0048).
#
# SEE: docs/api/all-star.md, docs/adr/0036-all-star-feed.md,
# docs/adr/0048-highlights-backfill-and-edition-video.md,
# docs/adr/0053-season-level-rules-for-past-seasons.md,
# docs/adr/0056-paced-past-builds-and-one-edition-mvp-path.md,
# api/app/jobs/playoffs_finals_feed.py

import asyncio
import datetime as dt
import logging
import re
from collections import Counter
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from app.feeds.all_star import (
    AllStarFeed,
    AllStarState,
    LeagueTeam,
    PlacementKind,
    Top5Row,
    null_sum,
)
from app.feeds.game_detail import BoxScorePlayer, GameResult, Venue
from app.feeds.games import GameStatus
from app.feeds.opponent import Side
from app.feeds.playoffs import AwardCode
from app.feeds.standings import StandingsColors
from app.jobs.all_star_discovery import AllStarDiscovery
from app.jobs.games import LIVE_INTERVAL, GamesJob
from app.jobs.on_demand import FeedCache, FeedKind, IdStatus
from app.jobs.stars import StarsJob
from app.jobs.team_feed import eastern_date
from app.settings import Settings
from app.sources import (
    all_star_detail,
    all_star_scoreboard,
    game_detail,
    season_awards,
    team_info,
)
from app.sources.all_star_detail import AllStarDetailExtras
from app.sources.all_star_mark import CHAMPIONSHIP, parse_note
from app.sources.all_star_scoreboard import AllStarScoreboardGame, AllStarSide
from app.sources.game_detail import GameDetail, GameDetailSections
from app.sources.http import Freshness, SourceClient, SourceError
from app.sources.scoreboard import FRESH_FOR
from app.sources.season_awards import AwardWinnerRef, SeasonAwards
from app.sources.team_info import TeamInfo, secondary_color
from app.storage.feeds import read_by_id
from app.storage.state import StateStore

KIND = "all-star"
FEED_ID = "league"
UNPLAYED_FRESH = dt.timedelta(hours=1)
FINAL_HOLD = dt.timedelta(hours=1)
PREVIOUS_FRESH = dt.timedelta(hours=24)
MAX_TOP5 = 5
NOT_FOUND = 404
logger = logging.getLogger(__name__)
FIRST_TO = re.compile(r"First team to (\d+) points wins")
STAT_ORDER = (
    "field_goal_pct",
    "three_points_made",
    "rebounds",
    "assists",
    "steals",
    "blocks",
)

FetchDay = Callable[
    [SourceClient, dt.date, Settings, Freshness], Awaitable[list[AllStarScoreboardGame]]
]
GameFreshness = Callable[[AllStarScoreboardGame], Freshness]
FetchDetail = Callable[[SourceClient, str, Settings, Freshness], Awaitable[GameDetail]]
FetchSections = Callable[
    [SourceClient, str, Settings, Freshness], Awaitable[GameDetailSections]
]
FetchExtras = Callable[
    [SourceClient, str, Settings, Freshness], Awaitable[AllStarDetailExtras]
]
FetchInfo = Callable[[SourceClient, str, Settings], Awaitable[TeamInfo]]
FetchAwards = Callable[[SourceClient, int, Settings], Awaitable[SeasonAwards]]


@dataclass(frozen=True)
class _Reads:
    """The per game reads of one edition and its season awards."""

    details: dict[str, GameDetail | None]
    sections: dict[str, GameDetailSections | None]
    extras: dict[str, AllStarDetailExtras | None]
    awards: SeasonAwards | None
    awards_error: str | None


@dataclass(frozen=True)
class EditionMvpReads:
    """The inputs of an edition's MVP: the box rows (sections), the jerseys
    (extras) and the season awards (the winner)."""

    sections: dict[str, GameDetailSections | None]
    extras: dict[str, AllStarDetailExtras | None]
    awards: SeasonAwards | None


async def _none_on_404[T](read: Awaitable[T]) -> T | None:
    """The result of a read, or none when the source answers 404; any other
    failure is raised."""
    try:
        return await read
    except SourceError as error:
        if error.status_code == NOT_FOUND:
            return None
        raise


async def read_edition_mvp_inputs(
    client: SourceClient,
    settings: Settings,
    year: int,
    games: Sequence[AllStarScoreboardGame],
    *,
    fetch_game_detail_sections: FetchSections,
    fetch_all_star_extras: FetchExtras,
    fetch_season_awards: FetchAwards,
) -> EditionMvpReads:
    """Read the MVP inputs of a finished edition, shared by the season feed
    and the current feed's previous edition (ADR 0056). A 404 nulls its part;
    any other failure raises SourceError."""
    ids = [g.id for g in edition_games(games)]
    sections, extras, awards = await asyncio.gather(
        asyncio.gather(
            *(
                _none_on_404(
                    fetch_game_detail_sections(client, i, settings, PREVIOUS_FRESH)
                )
                for i in ids
            )
        ),
        asyncio.gather(
            *(
                _none_on_404(fetch_all_star_extras(client, i, settings, PREVIOUS_FRESH))
                for i in ids
            )
        ),
        _none_on_404(fetch_season_awards(client, year, settings)),
    )
    return EditionMvpReads(
        dict(zip(ids, sections, strict=True)),
        dict(zip(ids, extras, strict=True)),
        awards,
    )


class AllStarBuildError(Exception):
    """The All-Star feed built from the fetched data is not valid."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class AllStarSources:
    """What the All-Star build reads. Never reaches a feed."""

    year: int
    edition_date: dt.date | None
    games: Sequence[AllStarScoreboardGame]
    details: Mapping[str, GameDetail | None]
    sections: Mapping[str, GameDetailSections | None]
    extras: Mapping[str, AllStarDetailExtras | None]
    colors: Mapping[str, TeamInfo | None]
    player_teams: Mapping[str, str]
    awards: SeasonAwards | None
    previous: AllStarSources | None


def game_format(
    suffix: str | None, extras: AllStarDetailExtras | None
) -> dict[str, Any] | None:
    """The format of a game as parts: the target points and untimed from the note
    suffix, else the regulation periods and minutes, else none."""
    first = FIRST_TO.search(suffix) if suffix else None
    if first is not None:
        return {
            "target_points": int(first.group(1)),
            "untimed": bool(suffix and "Untimed" in suffix),
            "periods": None,
            "minutes": None,
        }
    if extras is None:
        return None
    periods, seconds = extras.regulation_periods, extras.regulation_seconds
    if periods is None or seconds is None:
        return None
    return {
        "target_points": None,
        "untimed": False,
        "periods": periods,
        "minutes": seconds / 60,
    }


def edition_games(
    games: Sequence[AllStarScoreboardGame],
) -> list[AllStarScoreboardGame]:
    """The games of the edition in start order, without the canceled ones and
    repeated ids."""
    seen: set[str] = set()
    kept: list[AllStarScoreboardGame] = []
    for game in sorted(games, key=lambda g: g.start_time):
        if game.status is GameStatus.CANCELED or game.id in seen:
            continue
        seen.add(game.id)
        kept.append(game)
    return kept


def edition_state(games: Sequence[AllStarScoreboardGame]) -> AllStarState:
    """before while no game is live or final, after when every game is final,
    else live. A canceled game is ignored."""
    kept = [g for g in games if g.status is not GameStatus.CANCELED]
    if not any(g.status in (GameStatus.LIVE, GameStatus.FINAL) for g in kept):
        return AllStarState.BEFORE
    if all(g.status is GameStatus.FINAL for g in kept):
        return AllStarState.AFTER
    return AllStarState.LIVE


def winner(game: AllStarScoreboardGame) -> Side | None:
    """The side with the higher final score, or none."""
    if game.status is not GameStatus.FINAL or game.score is None:
        return None
    if game.score.away == game.score.home:
        return None
    return Side.AWAY if game.score.away > game.score.home else Side.HOME


def overtime(game: AllStarScoreboardGame, extras: AllStarDetailExtras | None) -> bool:
    """Whether a live or final game is in a period beyond the regulation ones."""
    if game.status not in (GameStatus.LIVE, GameStatus.FINAL):
        return False
    if game.period is None or extras is None or extras.regulation_periods is None:
        return False
    return game.period > extras.regulation_periods


def team_key(side: AllStarSide) -> str:
    return side.code or side.name or ""


def championship_game(
    games: Sequence[AllStarScoreboardGame],
) -> AllStarScoreboardGame | None:
    """The championship of an edition: its only game when it has exactly one,
    else the first game of the round Championship."""
    ordered = edition_games(games)
    if len(ordered) == 1:
        return ordered[0]
    return next((g for g in ordered if parse_note(g.note)[0] == CHAMPIONSHIP), None)


def _sides(game: AllStarScoreboardGame) -> list[tuple[Side, AllStarSide]]:
    found: list[tuple[Side, AllStarSide]] = []
    if game.away is not None:
        found.append((Side.AWAY, game.away))
    if game.home is not None:
        found.append((Side.HOME, game.home))
    return found


def team_order(games: Sequence[AllStarScoreboardGame]) -> list[AllStarSide]:
    """The distinct sides in order of appearance, away then home."""
    found: dict[str, AllStarSide] = {}
    for game in games:
        for _, side in _sides(game):
            found.setdefault(team_key(side), side)
    return list(found.values())


def side_names(games: Sequence[AllStarScoreboardGame]) -> dict[str, str]:
    """The name drawn for each distinct side that shares its name with another
    distinct side and has a code: its code and its name. Other sides are absent."""
    sides = team_order(games)
    counts = Counter(side.name for side in sides if side.name)
    return {
        team_key(side): f"{side.code} {side.name}"
        for side in sides
        if side.name and side.code and counts[side.name] > 1
    }


def records(games: Sequence[AllStarScoreboardGame]) -> dict[str, tuple[int, int]]:
    """Wins and losses of each team, from final games only."""
    table = {team_key(side): [0, 0] for side in team_order(games)}
    for game in games:
        won = winner(game)
        if won is None or game.away is None or game.home is None:
            continue
        victor, loser = (
            (game.away, game.home) if won is Side.AWAY else (game.home, game.away)
        )
        table[team_key(victor)][0] += 1
        table[team_key(loser)][1] += 1
    return {key: (wins, losses) for key, (wins, losses) in table.items()}


def placements(
    games: Sequence[AllStarScoreboardGame],
) -> dict[str, tuple[PlacementKind, str | None]]:
    """The placement of each team: champion, runner-up and eliminated once the
    championship is final, else so far or yet to play. Never inferred."""
    ordered = edition_games(games)
    teams = [team_key(side) for side in team_order(ordered)]
    candidate = championship_game(ordered)
    final = (
        candidate
        if candidate is not None
        and winner(candidate) is not None
        and candidate.away is not None
        and candidate.home is not None
        else None
    )
    played = {
        team_key(side)
        for g in ordered
        if g.status is GameStatus.FINAL
        for _, side in _sides(g)
    }
    if final is None or final.away is None or final.home is None:
        return {
            key: (
                PlacementKind.SO_FAR if key in played else PlacementKind.YET_TO_PLAY,
                None,
            )
            for key in teams
        }
    won = winner(final)
    victor, loser = (
        (final.away, final.home) if won is Side.AWAY else (final.home, final.away)
    )
    result: dict[str, tuple[PlacementKind, str | None]] = {}
    for key in teams:
        if key == team_key(victor):
            result[key] = (PlacementKind.CHAMPION, None)
        elif key == team_key(loser):
            result[key] = (PlacementKind.RUNNER_UP, None)
        else:
            label = next(
                (
                    found
                    for g in reversed(ordered)
                    if any(team_key(side) == key for _, side in _sides(g))
                    and (found := parse_note(g.note)[0]) is not None
                ),
                None,
            )
            result[key] = (
                (PlacementKind.ELIMINATED, label)
                if label is not None
                else (PlacementKind.SO_FAR, None)
            )
    return result


def edition_counts(games: Sequence[AllStarScoreboardGame]) -> dict[str, int]:
    """The number of games and teams, and of final and live games."""
    return {
        "games": len(games),
        "teams": len(team_order(games)),
        "final": sum(g.status is GameStatus.FINAL for g in games),
        "live": sum(g.status is GameStatus.LIVE for g in games),
    }


def default_game(
    games: Sequence[AllStarScoreboardGame], state: AllStarState
) -> str | None:
    """The game selected by default: the Championship after, the first live game
    while live; if neither exists, the first game not final, then the first game."""
    if not games:
        return None
    if state is AllStarState.AFTER:
        final = championship_game(games)
        if final is not None:
            return final.id
    live = next((g for g in games if g.status is GameStatus.LIVE), None)
    if live is not None:
        return live.id
    unplayed = next((g for g in games if g.status is not GameStatus.FINAL), None)
    if unplayed is not None:
        return unplayed.id
    return games[0].id


def next_game(
    games: Sequence[AllStarScoreboardGame],
    state: AllStarState,
    default_id: str | None,
) -> str | None:
    """While live, the first game neither live nor final other than the default."""
    if state is not AllStarState.LIVE:
        return None
    return next(
        (
            g.id
            for g in games
            if g.status not in (GameStatus.LIVE, GameStatus.FINAL)
            and g.id != default_id
        ),
        None,
    )


def leading(game: AllStarScoreboardGame) -> Side | None:
    """The side with the higher score of a live game, or none."""
    if game.status is not GameStatus.LIVE or game.score is None:
        return None
    if game.score.away == game.score.home:
        return None
    return Side.AWAY if game.score.away > game.score.home else Side.HOME


def top5(rows: Sequence[Top5Row]) -> list[Top5Row]:
    """The first 5 rows by points, then rebounds plus assists, both descending.
    The sort is stable, so ties keep the source order."""
    # A missing value counts as 0 for the order only (ADR 0055).
    ordered = sorted(
        rows,
        key=lambda r: (-(r.points or 0), -((r.rebounds or 0) + (r.assists or 0))),
    )
    return ordered[:MAX_TOP5]


def team_stats(sections: GameDetailSections | None) -> list[dict[str, Any]] | None:
    """The 6 team statistics with the better side, or none without the sections
    or the box score."""
    if sections is None or sections.team_stats is None or sections.box_score is None:
        return None
    away, home = sections.team_stats.away, sections.team_stats.home
    # A missing value leaves the block null (ADR 0052, ADR 0055).
    values = {
        "field_goal_pct": (away.field_goal_pct, home.field_goal_pct),
        "three_points_made": (
            sections.box_score.away.totals.three_points_made,
            sections.box_score.home.totals.three_points_made,
        ),
        "rebounds": (away.rebounds, home.rebounds),
        "assists": (away.assists, home.assists),
        "steals": (away.steals, home.steals),
        "blocks": (away.blocks, home.blocks),
    }
    numbers: dict[str, tuple[float, float]] = {}
    for stat, (away_value, home_value) in values.items():
        if away_value is None or home_value is None:
            return None
        numbers[stat] = (away_value, home_value)
    rows: list[dict[str, Any]] = []
    for stat in STAT_ORDER:
        first, second = numbers[stat]
        better = (
            None if first == second else (Side.AWAY if first > second else Side.HOME)
        )
        rows.append(
            {
                "stat": stat,
                "away": float(first),
                "home": float(second),
                "better": better,
            }
        )
    return rows


def league_team(
    player_id: str,
    player_teams: Mapping[str, str],
    colors: Mapping[str, TeamInfo | None],
) -> LeagueTeam | None:
    """The league team of a player found by id in the rosters, with its colors
    (null on a failed team info read), or none when the player is in no roster."""
    code = player_teams.get(player_id)
    if code is None:
        return None
    info = colors.get(code)
    return LeagueTeam(
        code=code,
        colors=StandingsColors(
            primary=None if info is None else f"#{info.color}",
            secondary=None if info is None else secondary_color(info),
        ),
    )


def _opponent(
    side: AllStarSide | None, renamed: Mapping[str, str]
) -> dict[str, Any] | None:
    if side is None:
        return None
    return {
        "code": side.code,
        "name": renamed.get(team_key(side), side.name),
        "city": side.city,
        "guest": True,
    }


def _venue(
    sources: AllStarSources, games: Sequence[AllStarScoreboardGame]
) -> Venue | None:
    for game in games:
        found = sources.sections.get(game.id)
        if found is not None:
            return found.venue
    first = next((g.venue for g in games if g.venue), None)
    return None if first is None else Venue(name=first)


def _box_rows(
    sources: AllStarSources, game: AllStarScoreboardGame
) -> list[tuple[Side, BoxScorePlayer]]:
    found = sources.sections.get(game.id)
    if found is None or found.box_score is None:
        return []
    box = found.box_score
    return [(Side.AWAY, p) for p in box.away.players] + [
        (Side.HOME, p) for p in box.home.players
    ]


def _box_player(
    sources: AllStarSources,
    game: AllStarScoreboardGame,
    player: BoxScorePlayer,
    top_points: bool,
) -> dict[str, Any]:
    extras = sources.extras.get(game.id)
    return {
        **player.model_dump(by_alias=False),
        "jersey": None if extras is None else extras.jerseys.get(player.player_id),
        "position": None if extras is None else extras.positions.get(player.player_id),
        "league_team": league_team(
            player.player_id, sources.player_teams, sources.colors
        ),
        "top_points": top_points,
    }


def _box_score(
    sources: AllStarSources, game: AllStarScoreboardGame
) -> dict[str, Any] | None:
    found = sources.sections.get(game.id)
    if found is None or found.box_score is None:
        return None
    box = found.box_score
    result: dict[str, Any] = {}
    for side, team in (("away", box.away), ("home", box.home)):
        top = max((p.points or 0 for p in team.players), default=0)
        result[side] = {
            "players": [
                _box_player(sources, game, p, top > 0 and (p.points or 0) == top)
                for p in team.players
            ],
            "totals": team.totals,
        }
    return result


def _top5_rows(sources: AllStarSources, game: AllStarScoreboardGame) -> list[Top5Row]:
    return top5(
        [
            Top5Row(
                player_id=player.player_id,
                name=player.display_name,
                photo_url=player.photo_url,
                side=side,
                league_team=league_team(
                    player.player_id, sources.player_teams, sources.colors
                ),
                points=player.points,
                rebounds=player.rebounds,
                assists=player.assists,
            )
            for side, player in _box_rows(sources, game)
        ]
    )


def _game(
    sources: AllStarSources,
    game: AllStarScoreboardGame,
    next_id: str | None,
    championship_id: str | None,
    renamed: Mapping[str, str],
) -> dict[str, Any]:
    label, _ = parse_note(game.note)
    extras = sources.extras.get(game.id)
    detail = sources.details.get(game.id)
    return {
        "id": game.id,
        "start_time": game.start_time,
        "status": game.status,
        "status_text": game.status_text,
        "clock": game.clock,
        "period": game.period,
        "score": game.score,
        "overtime": overtime(game, extras),
        "winner": winner(game),
        "leading": leading(game),
        "attendance": None if extras is None else extras.attendance,
        "broadcasts": [] if extras is None else extras.broadcasts,
        "round_label": label,
        "championship": game.id == championship_id,
        "is_next": game.id == next_id,
        "away": _opponent(game.away, renamed),
        "home": _opponent(game.home, renamed),
        "to_be_determined": game.away is None or game.home is None,
        "box_score": _box_score(sources, game),
        "team_stats": team_stats(sources.sections.get(game.id)),
        "leaders": None if detail is None else detail.leaders,
        "top5": _top5_rows(sources, game),
        "highlights": None,
    }


def _edition_format(
    sources: AllStarSources, games: Sequence[AllStarScoreboardGame]
) -> dict[str, Any] | None:
    for game in games:
        found = game_format(parse_note(game.note)[1], sources.extras.get(game.id))
        if found is not None:
            return found
    return None


def _results(
    sources: AllStarSources,
    games: Sequence[AllStarScoreboardGame],
    key: str,
    renamed: Mapping[str, str],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for game in games:
        won = winner(game)
        if won is None or game.score is None:
            continue
        for found, mine in _sides(game):
            if team_key(mine) != key:
                continue
            other = game.home if found is Side.AWAY else game.away
            if other is None:
                continue
            ours, theirs = (
                (game.score.away, game.score.home)
                if found is Side.AWAY
                else (game.score.home, game.score.away)
            )
            rows.append(
                {
                    "game_id": game.id,
                    "round_label": parse_note(game.note)[0],
                    "result": GameResult.WIN if won is found else GameResult.LOSS,
                    "team_score": ours,
                    "opponent_score": theirs,
                    "opponent": _opponent(other, renamed),
                    "overtime": overtime(game, sources.extras.get(game.id)),
                }
            )
    return rows


def _teams(
    sources: AllStarSources, games: Sequence[AllStarScoreboardGame]
) -> list[dict[str, Any]]:
    table = records(games)
    placed = placements(games)
    renamed = side_names(games)
    teams: list[dict[str, Any]] = []
    for side in team_order(games):
        key = team_key(side)
        roster: dict[str, dict[str, Any]] = {}
        for game in games:
            for found, mine in _sides(game):
                if team_key(mine) != key:
                    continue
                for box_side, player in _box_rows(sources, game):
                    if box_side is found and player.player_id not in roster:
                        roster[player.player_id] = {
                            "player_id": player.player_id,
                            "name": player.display_name,
                            "photo_url": player.photo_url,
                            "league_team": league_team(
                                player.player_id,
                                sources.player_teams,
                                sources.colors,
                            ),
                        }
        kind, label = placed[key]
        wins, losses = table[key]
        teams.append(
            {
                "team": _opponent(side, renamed),
                "wins": wins,
                "losses": losses,
                "results": _results(sources, games, key, renamed),
                "placement": {"kind": kind, "round_label": label},
                "roster": list(roster.values()),
            }
        )
    return teams


def _mvp_winner(awards: SeasonAwards | None) -> AwardWinnerRef | None:
    return next(
        (
            award.winners[0]
            for award in (awards.awards if awards else [])
            if award.code is AwardCode.ALL_STAR_MVP and award.winners
        ),
        None,
    )


def mvp_null_reason(awards: SeasonAwards | None, error: str | None) -> str:
    """Why an in-play edition's MVP is null."""
    if awards is None:
        return f"awards read failed: {error}"
    if _mvp_winner(awards) is None:
        return "no All-Star MVP award with a winner"
    return "the winner has no box row in the edition's final games"


def mvp(
    sources: AllStarSources, games: Sequence[AllStarScoreboardGame]
) -> dict[str, Any] | None:
    """The All-Star MVP with one line per final game he has a box row in and the
    day totals, or none without the award or a box row of his."""
    winner_ref = _mvp_winner(sources.awards)
    if winner_ref is None:
        return None
    renamed = side_names(games)
    lines: list[dict[str, Any]] = []
    first: tuple[AllStarScoreboardGame, BoxScorePlayer] | None = None
    for game in games:
        won = winner(game)
        if won is None or game.score is None or game.away is None or game.home is None:
            continue
        row = next(
            (
                (side, player)
                for side, player in _box_rows(sources, game)
                if player.player_id == winner_ref.player_id
            ),
            None,
        )
        if row is None:
            continue
        side, player = row
        if first is None:
            first = (game, player)
        mine, theirs = (
            (game.score.away, game.score.home)
            if side is Side.AWAY
            else (game.score.home, game.score.away)
        )
        lines.append(
            {
                "game_id": game.id,
                "round_label": parse_note(game.note)[0],
                "result": GameResult.WIN if won is side else GameResult.LOSS,
                "team_score": mine,
                "opponent_score": theirs,
                "opponent": _opponent(
                    game.home if side is Side.AWAY else game.away, renamed
                ),
                "points": player.points,
                "rebounds": player.rebounds,
                "assists": player.assists,
            }
        )
    if first is None:
        return None
    game, player = first
    extras = sources.extras.get(game.id)
    return {
        "player_id": player.player_id,
        "name": player.display_name,
        "photo_url": player.photo_url,
        "jersey": None if extras is None else extras.jerseys.get(player.player_id),
        "league_team": league_team(
            player.player_id, sources.player_teams, sources.colors
        ),
        "lines": lines,
        "totals": {
            "games": len(lines),
            "points": null_sum([line["points"] for line in lines]),
            "rebounds": null_sum([line["rebounds"] for line in lines]),
            "assists": null_sum([line["assists"] for line in lines]),
        },
    }


def _recap(previous: AllStarSources | None) -> dict[str, Any] | None:
    if previous is None or previous.edition_date is None:
        return None
    games = edition_games(previous.games)
    final = championship_game(games)
    won = None if final is None else winner(final)
    if (
        final is None
        or won is None
        or final.score is None
        or final.away is None
        or final.home is None
    ):
        return None
    venue = _venue(previous, games)
    renamed = side_names(games)
    return {
        "year": previous.year,
        "date": previous.edition_date,
        "venue": venue,
        "championship": {
            "game_id": final.id,
            "away": _opponent(final.away, renamed),
            "home": _opponent(final.home, renamed),
            "score": final.score,
            "winner": won,
            "overtime": overtime(final, previous.extras.get(final.id)),
        },
        "mvp": mvp(previous, games),
    }


def _edition(
    sources: AllStarSources,
    games: Sequence[AllStarScoreboardGame],
    state: AllStarState,
) -> dict[str, Any]:
    before = state is AllStarState.BEFORE
    shown = [] if before else list(games)
    default_id = default_game(shown, state)
    next_id = next_game(shown, state, default_id)
    champion = championship_game(games)
    championship_id = None if champion is None else champion.id
    renamed = side_names(games)
    return {
        "date": sources.edition_date,
        "venue": _venue(sources, games),
        "format": None if before else _edition_format(sources, games),
        "teams": [] if before else _teams(sources, games),
        "games": [_game(sources, g, next_id, championship_id, renamed) for g in shown],
        "counts": edition_counts(shown),
        "default_game_id": default_id,
    }


def previous_edition(previous: AllStarSources | None) -> dict[str, Any] | None:
    """The previous edition as its after view with its MVP, or none when there is
    no recap or a game of it is not final."""
    if previous is None or _recap(previous) is None:
        return None
    games = edition_games(previous.games)
    if edition_state(games) is not AllStarState.AFTER:
        return None
    return {
        **_edition(previous, games, AllStarState.AFTER),
        "mvp": mvp(previous, games),
    }


def build_all_star_feed(sources: AllStarSources) -> AllStarFeed:
    """Build the All-Star feed; raise AllStarBuildError when it is not valid."""
    games = edition_games(sources.games)
    state = edition_state(games)
    before = state is AllStarState.BEFORE
    try:
        return AllStarFeed.model_validate(
            {
                "year": sources.year,
                "state": state,
                "edition": _edition(sources, games, state),
                "mvp": None if before else mvp(sources, games),
                "previous": _recap(sources.previous),
                "previous_edition": previous_edition(sources.previous),
            }
        )
    except ValidationError as error:
        location = ".".join(str(part) for part in error.errors()[0]["loc"])
        raise AllStarBuildError(
            f"invalid feed: {error.error_count()} errors, first at {location}"
        ) from None


def with_edition_highlights(feed: AllStarFeed, store: StateStore) -> AllStarFeed:
    """The feed with the stored edition video on the edition, and on the recap
    and the previous edition when there are. Stores nothing."""
    data = feed.model_dump(by_alias=False)
    data["edition"]["edition_highlight"] = store.all_star_edition_highlight(feed.year)
    if feed.previous is not None:
        found = store.all_star_edition_highlight(feed.previous.year)
        data["previous"]["edition_highlight"] = found
        if data["previous_edition"] is not None:
            data["previous_edition"]["edition_highlight"] = found
    return AllStarFeed.model_validate(data)


class AllStarFeeds:
    def __init__(
        self,
        settings: Settings,
        store: StateStore,
        client: SourceClient,
        cache: FeedCache,
        games: GamesJob,
        stars: StarsJob,
        discovery: AllStarDiscovery,
        *,
        fetch_all_star_games: FetchDay = all_star_scoreboard.fetch_all_star_games,
        fetch_game_detail: FetchDetail = game_detail.fetch_game_detail,
        fetch_game_detail_sections: FetchSections = (
            game_detail.fetch_game_detail_sections
        ),
        fetch_all_star_extras: FetchExtras = all_star_detail.fetch_all_star_extras,
        fetch_team_info: FetchInfo = team_info.fetch_team_info,
        fetch_season_awards: FetchAwards = season_awards.fetch_season_awards,
    ) -> None:
        self._settings = settings
        self._store = store
        self._client = client
        self._games = games
        self._stars = stars
        self._discovery = discovery
        self._fetch_all_star_games = fetch_all_star_games
        self._fetch_game_detail = fetch_game_detail
        self._fetch_game_detail_sections = fetch_game_detail_sections
        self._fetch_all_star_extras = fetch_all_star_extras
        self._fetch_team_info = fetch_team_info
        self._fetch_season_awards = fetch_season_awards
        cache.register(self.kind())

    def check(self, feed_id: str) -> IdStatus:
        if feed_id != FEED_ID:
            return IdStatus.UNKNOWN
        if (
            self._stars.current_season() is None
            or not self._stars.rosters_ready()
            or not self._discovery.ready()
        ) and read_by_id(self._settings.data_dir, KIND, FEED_ID) is None:
            return IdStatus.NOT_READY
        return IdStatus.KNOWN

    def stored(self) -> AllStarFeed | None:
        """The stored All-Star feed, or none when missing or invalid."""
        body = read_by_id(self._settings.data_dir, KIND, FEED_ID)
        if body is None:
            return None
        try:
            return AllStarFeed.model_validate_json(body)
        except ValidationError:
            return None

    def _freshness(self, game: AllStarScoreboardGame) -> Freshness:
        if game.status is GameStatus.LIVE:
            return LIVE_INTERVAL
        if game.status is GameStatus.FINAL:
            return self._store.all_star_final_time(game.id) or LIVE_INTERVAL
        return UNPLAYED_FRESH

    def _record_finals(self, games: Sequence[AllStarScoreboardGame]) -> None:
        """Store now as the first-seen-final time of each final game without one."""
        now = self._client.clock()
        for game in games:
            if (
                game.status is GameStatus.FINAL
                and self._store.all_star_final_time(game.id) is None
            ):
                self._store.record_all_star_final(game.id, now)

    async def _guard[T](self, read: Awaitable[T]) -> T | None:
        try:
            return await read
        except SourceError:
            return None

    async def _reads(
        self, games: Sequence[AllStarScoreboardGame], fresh: GameFreshness
    ) -> tuple[
        dict[str, GameDetail | None],
        dict[str, GameDetailSections | None],
        dict[str, AllStarDetailExtras | None],
    ]:
        client, settings = self._client, self._settings
        ids = [g.id for g in games]
        details, sections, extras = await asyncio.gather(
            asyncio.gather(
                *(
                    self._guard(
                        self._fetch_game_detail(client, g.id, settings, fresh(g))
                    )
                    for g in games
                )
            ),
            asyncio.gather(
                *(
                    self._guard(
                        self._fetch_game_detail_sections(
                            client, g.id, settings, fresh(g)
                        )
                    )
                    for g in games
                )
            ),
            asyncio.gather(
                *(
                    self._guard(
                        self._fetch_all_star_extras(client, g.id, settings, fresh(g))
                    )
                    for g in games
                )
            ),
        )
        return (
            dict(zip(ids, details, strict=True)),
            dict(zip(ids, sections, strict=True)),
            dict(zip(ids, extras, strict=True)),
        )

    async def _awards(
        self, season: int, in_play: bool
    ) -> tuple[SeasonAwards | None, str | None]:
        if not in_play:
            return None, None
        try:
            awards = await self._fetch_season_awards(
                self._client, season, self._settings
            )
        except SourceError as error:
            return None, error.reason
        return awards, None

    async def _day_of(
        self, season: int, fresh: Freshness
    ) -> tuple[dt.date, list[AllStarScoreboardGame]] | None:
        """The stored day of a season with its games, or none when the season is
        not discovered or its day cannot be read."""
        record = self._discovery.edition(season)
        if record is None:
            return None
        games = await self._guard(
            self._fetch_all_star_games(
                self._client, record.game_date, self._settings, fresh
            )
        )
        return None if games is None else (record.game_date, games)

    async def _read_edition(
        self,
        season: int,
        games: Sequence[AllStarScoreboardGame],
        fresh: GameFreshness,
    ) -> _Reads:
        kept = edition_games(games)
        in_play = edition_state(kept) is not AllStarState.BEFORE
        reads, awards = await asyncio.gather(
            self._reads(kept, fresh), self._awards(season, in_play)
        )
        return _Reads(reads[0], reads[1], reads[2], awards[0], awards[1])

    async def _read_previous(
        self, season: int, games: Sequence[AllStarScoreboardGame]
    ) -> tuple[_Reads | None, SourceError | None]:
        """The reads of the previous edition. Its MVP inputs go through
        read_edition_mvp_inputs: a failure other than a 404 is returned as the
        error and no reads (ADR 0056). The rest is read as the current one."""
        kept = edition_games(games)
        if edition_state(kept) is AllStarState.BEFORE:
            return await self._read_edition(
                season, games, lambda _: PREVIOUS_FRESH
            ), None
        client, settings = self._client, self._settings

        async def inputs() -> EditionMvpReads | SourceError:
            try:
                return await read_edition_mvp_inputs(
                    client,
                    settings,
                    season,
                    games,
                    fetch_game_detail_sections=self._fetch_game_detail_sections,
                    fetch_all_star_extras=self._fetch_all_star_extras,
                    fetch_season_awards=self._fetch_season_awards,
                )
            except SourceError as error:
                return error

        found, details = await asyncio.gather(
            inputs(),
            asyncio.gather(
                *(
                    self._guard(
                        self._fetch_game_detail(client, g.id, settings, PREVIOUS_FRESH)
                    )
                    for g in kept
                )
            ),
        )
        if isinstance(found, SourceError):
            return None, found
        return (
            _Reads(
                dict(zip((g.id for g in kept), details, strict=True)),
                found.sections,
                found.extras,
                found.awards,
                None,
            ),
            None,
        )

    async def build(self, feed_id: str) -> AllStarFeed:
        season = self._stars.current_season()
        if season is None:
            raise AllStarBuildError("season not known yet")
        client, settings = self._client, self._settings
        record = self._discovery.edition(season)
        games: list[AllStarScoreboardGame] = []
        if record is not None:
            games = await self._fetch_all_star_games(
                client, record.game_date, settings, FRESH_FOR
            )
            self._record_finals(games)
        earlier_day = await self._day_of(season - 1, PREVIOUS_FRESH)
        earlier_games = [] if earlier_day is None else earlier_day[1]
        current, (earlier, earlier_error) = await asyncio.gather(
            self._read_edition(season, games, self._freshness),
            self._read_previous(season - 1, earlier_games),
        )
        kept_previous: AllStarFeed | None = None
        if earlier_error is not None:
            kept_previous = self._stored_previous(season)
            if kept_previous is None:
                raise earlier_error
            logger.warning(
                "all-star: previous edition of season %d kept from the stored feed: %s",
                season - 1,
                earlier_error.reason,
            )
        player_teams: dict[str, str] = {}
        for reads in (current, earlier):
            if reads is None:
                continue
            for found in reads.sections.values():
                if found is None or found.box_score is None:
                    continue
                for team in (found.box_score.away, found.box_score.home):
                    for player in team.players:
                        code = self._stars.player_team(player.player_id)
                        if code is not None:
                            player_teams[player.player_id] = code
        codes = sorted(set(player_teams.values()))
        infos = await asyncio.gather(
            *(
                self._guard(self._fetch_team_info(client, code, settings))
                for code in codes
            )
        )
        colors = dict(zip(codes, infos, strict=True))
        previous = (
            None
            if earlier_day is None or earlier is None
            else AllStarSources(
                year=season - 1,
                edition_date=earlier_day[0],
                games=earlier_games,
                details=earlier.details,
                sections=earlier.sections,
                extras=earlier.extras,
                colors=colors,
                player_teams=player_teams,
                awards=earlier.awards,
                previous=None,
            )
        )
        feed = build_all_star_feed(
            AllStarSources(
                year=season,
                edition_date=None if record is None else record.game_date,
                games=games,
                details=current.details,
                sections=current.sections,
                extras=current.extras,
                colors=colors,
                player_teams=player_teams,
                awards=current.awards,
                previous=previous,
            )
        )
        if feed.state is not AllStarState.BEFORE and feed.mvp is None:
            self._log_null_mvp(season, current)
        if kept_previous is not None:
            return feed.model_copy(
                update={
                    "previous": kept_previous.previous,
                    "previous_edition": kept_previous.previous_edition,
                }
            )
        if (
            feed.previous is not None
            and feed.previous.mvp is None
            and earlier is not None
        ):
            self._log_null_mvp(season - 1, earlier, "not found")
        return feed

    def _stored_previous(self, season: int) -> AllStarFeed | None:
        """The stored feed when its previous blocks are those of the season
        before and carry an MVP, else none."""
        stored = self.stored()
        if (
            stored is not None
            and stored.previous is not None
            and stored.previous.year == season - 1
            and stored.previous.mvp is not None
        ):
            return stored
        return None

    def _log_null_mvp(self, year: int, reads: _Reads, error: str | None = None) -> None:
        logger.warning(
            "all-star: MVP of season %d is null: %s",
            year,
            mvp_null_reason(reads.awards, error or reads.awards_error),
        )

    def _held(self, feed: AllStarFeed, built_at: dt.datetime) -> bool:
        """Whether the build is at least 1 hour after the latest time the games of
        the edition were first seen final."""
        seen = [self._store.all_star_final_time(g.id) for g in feed.edition.games]
        times = [t for t in seen if t is not None]
        if len(times) != len(seen):
            return False
        return built_at >= max(times) + FINAL_HOLD

    def is_fresh(
        self, feed: AllStarFeed, built_at: dt.datetime, now: dt.datetime
    ) -> bool:
        season = self._stars.current_season()
        if feed.state is AllStarState.AFTER and (season is None or season == feed.year):
            return self._held(feed, built_at) or now - built_at < LIVE_INTERVAL
        if season is not None and season != feed.year:
            return False
        if feed.state is AllStarState.LIVE or feed.edition.date == eastern_date(now):
            return now - built_at < LIVE_INTERVAL
        last_run = self._discovery.last_run()
        return last_run is None or last_run <= built_at

    def wait_when_stale(self, feed_id: str) -> bool:
        stored = self.stored()
        if stored is None:
            return False
        return stored.state is AllStarState.LIVE or (
            stored.edition.date == eastern_date(self._client.clock())
        )

    def serve_with(self, feed_id: str, feed: AllStarFeed) -> AllStarFeed:
        return with_edition_highlights(feed, self._store)

    def keep(self, feed_id: str) -> bool:
        return feed_id == FEED_ID

    def kind(self) -> FeedKind[AllStarFeed]:
        return FeedKind(
            KIND,
            AllStarFeed,
            check=self.check,
            build=self.build,
            is_fresh=self.is_fresh,
            keep=self.keep,
            serve_with=self.serve_with,
            wait_when_stale=self.wait_when_stale,
        )
