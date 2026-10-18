# api/app/jobs/playoffs_feed.py
#
# Playoffs feed builder: a pure function from the season windows, the division
# standings, the team colors, the postseason games of every day read, the rosters
# the stars job keeps, the postseason leaders, the season awards and the
# champion's postseason record to the playoffs feed. The build reads no clock
# and no source: the build date is an input.
#
# The state is complete once a Finals team has four counted wins, else finals
# once any Finals game was read, else playoffs once a round 1 game is live or
# final, else playin on or after the first day of the play-in window,
# else picture. Games are the postseason games of the play-in window and of the
# postseason window, keyed by the season type of the event; a canceled game is
# dropped and a repeated game id keeps one game. A play-in game is placed by its
# note (conference and kind); a postseason game is grouped by round (its
# competition type) and pair of teams. Round 1 is placed by the seeds of the
# pair (1v8, 4v5, 3v6, 2v7, the lower seed on top); the seeds 1 to 6 are the
# standings seeds and the seeds 7 and 8 are the winners of the 7th vs 8th game
# and of the 8th seed game. A later round is placed by the series its teams came
# from, the Finals has the East team on top. A game or team that cannot be placed
# fails the build. Wins, summary, completion and status of a series are counted
# from its final games (the source's winner flag, else the higher score), never
# read from the source's series object; a series with no final game is upcoming
# with null wins and summary (ADR 0060).
# A stage is complete when all its games are final (play-in, 6 games) or all its
# series are complete (8, 4, 2 and 1), in progress when started and not complete,
# next when it is the first stage after the last one complete or in progress, and
# upcoming otherwise. The current round is set only in the playoffs. The picture
# tables are the first ten teams of each conference in seed order; before the
# season starts (the standings are of another season or every team has 0 games)
# the rows carry no record, seed or clinch. The champion is set when complete: the
# Finals result, its dates, the postseason record from the record read and the
# point differential over the champion's final postseason games. Leaders and
# awards name players from the rosters; a player on no roster is left out.
#
# PlayoffsFeeds is the feed kind of the on-demand cache: the only id is "league",
# the feed is stored at feeds/playoffs/league.json only when requested, and it
# answers 503 (not ready) until the stars job knows the season and has fetched
# every roster. It expires 1 hour after a final postseason game that follows the
# build (a game of the feed, or a final game of the games job dated inside the
# postseason dates), while its state is picture also 1 hour after any final game
# of the league that follows the build, at the start of the play-in window when
# the build precedes it, and 7 days after the build (rule G). Once the Finals
# series is complete the feed is kept while its season is the current one, the
# season of the stars job's latest roster. A season type, standings or scoreboard
# day that fails fails the build; leaders, awards, team info and the champion's
# record only null their part. The feed is never deleted.
#
# A past season (ADR 0046) is built from the same builder with two more inputs:
# a season before 2021 has no play-in window, so its play-in block is null, its
# seeds 1 to 8 are the standings seeds and its round 1 labels are all seeds; a
# past postseason where no game has a known competition type gets its rounds
# from derive_series (the k-th series of both teams, 8, 4, 2 and 1 series, the
# Finals the only series across the conferences); a past season whose round 1
# teams have no seed is placed by the round 2 series each one feeds, with null
# side seeds; a past game whose note has no game number takes its position in
# its series; and a past play-in note is read in any letter case.
#
# A past build reads no postseason window: its postseason dates run from the
# start of the play-in window, else from the first game, to the last game read
# (ADR 0058).
#
# SEE: docs/api/playoffs.md, docs/adr/0032-playoffs-feed.md,
# docs/adr/0046-season-playoffs-feeds.md, api/app/jobs/standings_feed.py

import asyncio
import datetime as dt
from collections.abc import Awaitable, Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from app.feeds.game_detail import Conference
from app.feeds.games import GameStatus, PlayInGameKind
from app.feeds.opponent import Side
from app.feeds.playoffs import (
    STAGES,
    AwardCode,
    LeaderCategory,
    PlayoffsFeed,
    PlayoffsState,
    PlayoffStage,
    PlayoffStageStatus,
    SeriesId,
    SeriesLabelKey,
    SeriesStatus,
    round_of_series,
)
from app.jobs.games import GamesJob, final_winner
from app.jobs.on_demand import FeedCache, FeedKind, IdStatus
from app.jobs.standings_feed import (
    conference_games_behind_text,
    conference_order_key,
    leader_of,
    seed_of,
    signed_total,
)
from app.jobs.stars import StarsJob
from app.jobs.team_feed import (
    EASTERN,
    FetchDivisionStandings,
    FetchInfo,
    eastern_date,
    feed_expired,
    player_name,
    season_label,
)
from app.settings import Settings
from app.sources import (
    division_standings,
    postseason_leaders,
    postseason_scoreboard,
    season_awards,
    season_types,
    team_info,
    team_postseason,
)
from app.sources.division_standings import DivisionStandings
from app.sources.game_detail import BoxScoreRosterEntry
from app.sources.http import SourceClient, SourceError
from app.sources.postseason_leaders import PostseasonLeaders
from app.sources.postseason_mark import (
    _PLAY_IN_KINDS_ANY_CASE,
    _PLAY_IN_NOTE_ANY_CASE,
    GAME_NUMBER_NOTE,
    PLAY_IN_KINDS,
    PLAY_IN_NOTE,
    ROUNDS,
)
from app.sources.postseason_scoreboard import PostseasonGame
from app.sources.season_awards import SeasonAwards
from app.sources.season_types import PLAY_IN, POSTSEASON, SeasonWindow
from app.sources.team_info import TeamInfo
from app.sources.team_players import RosterEntry
from app.sources.team_postseason import TeamPostseasonRecord
from app.sources.teams import TEAM_CODES
from app.storage.feeds import read_by_id
from app.storage.state import StateStore

KIND = "playoffs"
FEED_ID = "league"
CODES = sorted(set(TEAM_CODES.values()))
SERIES_OF_ROUND = {1: 8, 2: 4, 3: 2, 4: 1}
WINS_TO_WIN = 4
SERIES_OF_SEEDS = {
    frozenset({1, 8}): 1,
    frozenset({4, 5}): 2,
    frozenset({3, 6}): 3,
    frozenset({2, 7}): 4,
}
# The seeds of the top and the bottom side of the round 1 series 1 to 4.
SEEDS_OF_SERIES = {1: (1, 8), 2: (4, 5), 3: (3, 6), 4: (2, 7)}
CONFERENCES = (Conference.EAST, Conference.WEST)
FINALS_ROUND = 4
STANDINGS_SEEDS = 6
STANDINGS_SEEDS_NO_PLAY_IN = 8
MAX_LEADERS = 5
OVERTIME_PERIOD = 5

FetchSeasonType = Callable[[SourceClient, int, int, Settings], Awaitable[SeasonWindow]]
FetchPostseasonGames = Callable[
    [SourceClient, dt.date, Settings], Awaitable[list[PostseasonGame]]
]
FetchLeaders = Callable[[SourceClient, int, Settings], Awaitable[PostseasonLeaders]]
FetchAwards = Callable[[SourceClient, int, Settings], Awaitable[SeasonAwards]]
FetchRecord = Callable[
    [SourceClient, str, int, Settings], Awaitable[TeamPostseasonRecord]
]


class PlayoffsBuildError(Exception):
    """The playoffs feed built from the fetched data is not valid."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class PlayoffsSources:
    """What the playoffs build reads. Never reaches a feed."""

    season: int
    today: dt.date
    play_in: SeasonWindow | None
    # None only on a past build, which reads no postseason window (ADR 0058).
    postseason: SeasonWindow | None
    standings: DivisionStandings
    colors: Mapping[str, TeamInfo | None]
    games: Sequence[PostseasonGame]
    players: Mapping[str, tuple[str, RosterEntry | BoxScoreRosterEntry]]
    leaders: PostseasonLeaders | None
    awards: SeasonAwards | None
    champion_record: TeamPostseasonRecord | None
    past: bool = False


def _feeders() -> dict[SeriesId, tuple[SeriesId, SeriesId]]:
    feeders: dict[SeriesId, tuple[SeriesId, SeriesId]] = {}
    for side in ("east", "west"):
        feeders[SeriesId(f"{side}-r2-1")] = (
            SeriesId(f"{side}-r1-1"),
            SeriesId(f"{side}-r1-2"),
        )
        feeders[SeriesId(f"{side}-r2-2")] = (
            SeriesId(f"{side}-r1-3"),
            SeriesId(f"{side}-r1-4"),
        )
        feeders[SeriesId(f"{side}-r3")] = (
            SeriesId(f"{side}-r2-1"),
            SeriesId(f"{side}-r2-2"),
        )
    feeders[SeriesId.FINALS] = (SeriesId.EAST_R3, SeriesId.WEST_R3)
    return feeders


FEEDERS = _feeders()


def conference_of_series(series_id: SeriesId) -> Conference | None:
    if series_id is SeriesId.FINALS:
        return None
    return Conference(series_id.value.split("-")[0])


def postseason_days(
    play_in: SeasonWindow | None, postseason: SeasonWindow | None
) -> list[dt.date]:
    """The US Eastern dates of both windows, sorted with no repeats; a season
    with no play-in window has the postseason's."""
    days: set[dt.date] = set()
    for window in (play_in, postseason):
        if window is None:
            continue
        day = eastern_date(window.start)
        last = eastern_date(window.end)
        while day <= last:
            days.add(day)
            day += dt.timedelta(days=1)
    return sorted(days)


def reads_days(today: dt.date, play_in: SeasonWindow) -> bool:
    """Whether the build reads the scoreboard days: on or after the first day of
    the play-in window."""
    return today >= eastern_date(play_in.start)


def _undecided(game: PostseasonGame) -> bool:
    """Whether a game neither live nor final has a side that is a guest or has no
    code: a side not decided yet, so the game is not listed."""
    home, away = game.game.home, game.game.away
    return game.game.status not in (GameStatus.LIVE, GameStatus.FINAL) and (
        home.guest or away.guest or home.code is None or away.code is None
    )


def _unique_games(games: Iterable[PostseasonGame]) -> list[PostseasonGame]:
    """The games in start order, with no canceled game, no game with an undecided
    side and one game per id."""
    found: dict[str, PostseasonGame] = {}
    for game in games:
        if (
            game.game.status is GameStatus.CANCELED
            or _undecided(game)
            or game.game.id in found
        ):
            continue
        found[game.game.id] = game
    return sorted(found.values(), key=lambda g: (g.game.start_time, g.game.id))


def _codes(game: PostseasonGame) -> tuple[str, str]:
    """The (home, away) codes of a game; a team outside the league fails."""
    home, away = game.game.home, game.game.away
    if home.guest or away.guest or home.code is None or away.code is None:
        raise PlayoffsBuildError(f"game {game.game.id} has a team outside the league")
    return home.code, away.code


def group_series(
    games: Sequence[PostseasonGame],
) -> dict[tuple[int, frozenset[str]], list[PostseasonGame]]:
    """The postseason games (season type 3) by round and pair of teams, in start
    order; an unknown competition type fails."""
    groups: dict[tuple[int, frozenset[str]], list[PostseasonGame]] = {}
    for game in _unique_games(games):
        if game.season_type != POSTSEASON:
            continue
        round_ = ROUNDS.get(game.competition_type or "")
        if round_ is None:
            raise PlayoffsBuildError(
                f"game {game.game.id} has an unknown competition type"
                f" {game.competition_type!r}"
            )
        home, away = _codes(game)
        groups.setdefault((round_, frozenset({home, away})), []).append(game)
    return groups


def _start_key(games: Sequence[PostseasonGame], pair: frozenset[str]) -> Any:
    return (games[0].game.start_time, sorted(pair))


def derive_series(
    games: Sequence[PostseasonGame], conferences: Mapping[str, Conference]
) -> dict[tuple[int, frozenset[str]], list[PostseasonGame]]:
    """The postseason games (season type 3) by round and pair of teams, in start
    order, for a postseason where the games carry no round. A series is round k
    when it is the k-th series of both teams; the Finals is the only series
    across the conferences; the rounds have 8, 4, 2 and 1 series. Anything else
    fails."""
    by_pair: dict[frozenset[str], list[PostseasonGame]] = {}
    for game in _unique_games(games):
        if game.season_type != POSTSEASON:
            continue
        home, away = _codes(game)
        by_pair.setdefault(frozenset({home, away}), []).append(game)
    ordered = sorted(by_pair, key=lambda pair: _start_key(by_pair[pair], pair))
    of_team: dict[str, list[frozenset[str]]] = {}
    for pair in ordered:
        for code in pair:
            of_team.setdefault(code, []).append(pair)
    groups: dict[tuple[int, frozenset[str]], list[PostseasonGame]] = {}
    for pair in ordered:
        first, second = sorted(pair)
        number, other = of_team[first].index(pair) + 1, of_team[second].index(pair) + 1
        if number != other:
            raise PlayoffsBuildError(
                f"series {first} {second} is series {number} of {first}"
                f" and {other} of {second}"
            )
        groups[(number, pair)] = by_pair[pair]
    across = []
    for round_, pair in groups:
        for code in pair:
            if code not in conferences:
                raise PlayoffsBuildError(f"team {code} has no standing")
        if len({conferences[code] for code in pair}) > 1:
            across.append(round_)
    if across != [FINALS_ROUND]:
        raise PlayoffsBuildError(
            "the Finals is not the only series across the conferences"
        )
    counts = [sum(1 for key in groups if key[0] == r) for r in (1, 2, 3, 4)]
    extra = sum(1 for key in groups if key[0] > FINALS_ROUND)
    if counts != list(SERIES_OF_ROUND.values()) or extra:
        raise PlayoffsBuildError(
            f"derived rounds give {'-'.join(str(c) for c in counts)} series,"
            " not 8-4-2-1"
        )
    return groups


def counted_winner(game: PostseasonGame) -> str | None:
    """The code of the team a game counts for: none unless the game is final;
    else the side whose source winner flag is the only true one, else the side
    with more points."""
    if game.game.status is not GameStatus.FINAL:
        return None
    home, away = _codes(game)
    side = game.winner or final_winner(game.game)
    if side is None:
        return None
    return home if side is Side.HOME else away


def series_wins(games: Sequence[PostseasonGame]) -> dict[str, int]:
    """The counted wins of each team over the games."""
    wins: dict[str, int] = {}
    for game in games:
        code = counted_winner(game)
        if code is not None:
            wins[code] = wins.get(code, 0) + 1
    return wins


def finals_winner(games: Sequence[PostseasonGame]) -> str | None:
    """The Finals team with four counted wins; none when no team has them."""
    finals = [
        game
        for game in _unique_games(games)
        if game.season_type == POSTSEASON
        and ROUNDS.get(game.competition_type or "") == 4
    ]
    winners = [
        code for code, wins in series_wins(finals).items() if wins >= WINS_TO_WIN
    ]
    return winners[0] if len(winners) == 1 else None


def _live_or_final(game: PostseasonGame) -> bool:
    return game.game.status in (GameStatus.LIVE, GameStatus.FINAL)


def _winner_and_loser(game: PostseasonGame) -> tuple[str, str] | None:
    side = final_winner(game.game)
    if side is None:
        return None
    home, away = _codes(game)
    return (home, away) if side is Side.HOME else (away, home)


@dataclass(frozen=True)
class _Placed:
    series_id: SeriesId
    top: str
    bottom: str
    games: list[PostseasonGame]


@dataclass(frozen=True)
class _Info:
    status: SeriesStatus
    summary: str | None
    wins: dict[str, int] | None
    winner: str | None


class _Builder:
    def __init__(self, sources: PlayoffsSources) -> None:
        self.sources = sources
        self.entries = sources.standings.teams
        self.preseason = sources.standings.season != sources.season or all(
            entry.wins == 0 and entry.losses == 0 for entry in self.entries.values()
        )
        unique = _unique_games(sources.games)
        self.play_in_games = [g for g in unique if g.season_type == PLAY_IN]
        self.play_in = self._place_play_in()
        self.outcomes = {
            key: result
            for key, game in self.play_in.items()
            if (result := _winner_and_loser(game)) is not None
        }
        self.seeds = self._seeds()
        self.by_seed = {
            (self.entry(code).conference, seed): code
            for code, seed in self.seeds.items()
            if seed is not None
        }
        self.raw_by_seed = {
            (entry.conference, seed): entry.code
            for entry in self.entries.values()
            if (seed := seed_of(entry)) is not None
        }
        self.placed = self._place_series(sources.games)
        self.info = {sid: self._info(placed) for sid, placed in self.placed.items()}
        self.state = self._state()

    # Teams

    def entry(self, code: str) -> Any:
        found = self.entries.get(code)
        if found is None:
            raise PlayoffsBuildError(f"team {code} has no standing")
        return found

    def team(self, code: str) -> dict[str, Any]:
        entry = self.entry(code)
        info = self.sources.colors.get(code)
        colors = (
            {"primary": f"#{info.color}", "secondary": f"#{info.alternate_color}"}
            if info is not None
            else {"primary": None, "secondary": None}
        )
        return {
            "code": code,
            "name": entry.name,
            "city": entry.location,
            "guest": False,
            "colors": colors,
        }

    # Play-in

    def _place_play_in(self) -> dict[tuple[Conference, PlayInGameKind], PostseasonGame]:
        placed: dict[tuple[Conference, PlayInGameKind], PostseasonGame] = {}
        for game in self.play_in_games:
            if self.sources.past:
                match = _PLAY_IN_NOTE_ANY_CASE.match(game.note or "")
                kinds = _PLAY_IN_KINDS_ANY_CASE
            else:
                match = PLAY_IN_NOTE.match(game.note or "")
                kinds = PLAY_IN_KINDS
            if match is None:
                raise PlayoffsBuildError(
                    f"play-in game {game.game.id} has an unknown note"
                )
            kind_name = (
                match.group(2).casefold() if self.sources.past else match.group(2)
            )
            key = (Conference(match.group(1).lower()), kinds[kind_name])
            if key in placed:
                raise PlayoffsBuildError(
                    f"two play-in games of the kind {key[1].value} in the {key[0].value}"
                )
            _codes(game)
            placed[key] = game
        return placed

    def _seeds(self) -> dict[str, int | None]:
        seeds: dict[str, int | None] = {}
        for code, entry in self.entries.items():
            seed = seed_of(entry)
            limit = (
                STANDINGS_SEEDS
                if self.sources.play_in is not None
                else STANDINGS_SEEDS_NO_PLAY_IN
            )
            seeds[code] = seed if seed is not None and seed <= limit else None
        for (_, kind), (winner, _loser) in self.outcomes.items():
            if kind is PlayInGameKind.SEVEN_EIGHT:
                seeds[winner] = 7
            elif kind is PlayInGameKind.EIGHTH_SEED:
                seeds[winner] = 8
        return seeds

    # Games

    def game(self, game: PostseasonGame) -> dict[str, Any]:
        scoreboard_game = game.game
        home, away = _codes(game)
        live = scoreboard_game.status in (GameStatus.LIVE, GameStatus.FINAL)
        side = final_winner(scoreboard_game)
        score = scoreboard_game.score
        return {
            "id": scoreboard_game.id,
            "date": eastern_date(scoreboard_game.start_time),
            "start_time": scoreboard_game.start_time,
            "away": {
                "code": away,
                "name": scoreboard_game.away.name,
                "city": scoreboard_game.away.city,
                "guest": False,
            },
            "home": {
                "code": home,
                "name": scoreboard_game.home.name,
                "city": scoreboard_game.home.city,
                "guest": False,
            },
            "status": scoreboard_game.status,
            "score": None
            if score is None
            else {"away": score.away, "home": score.home},
            "winner": side,
            "overtime": live
            and game.period is not None
            and game.period >= OVERTIME_PERIOD,
            "venue": scoreboard_game.venue,
            "broadcast": scoreboard_game.broadcast,
            "detail_available": False,
        }

    def game_number(self, game: PostseasonGame, games: Sequence[PostseasonGame]) -> int:
        """The game number of the note, else (a past season) the 1-based position
        of the game in its series; a note without a number fails otherwise."""
        match = GAME_NUMBER_NOTE.search(game.note or "")
        if match is not None:
            return int(match.group(1))
        if not self.sources.past:
            raise PlayoffsBuildError(
                f"game {game.game.id} has a note without a game number"
            )
        return games.index(game) + 1

    def series_game(
        self, game: PostseasonGame, games: Sequence[PostseasonGame]
    ) -> dict[str, Any]:
        return {**self.game(game), "number": self.game_number(game, games)}

    # Series placement

    def _place_series(self, games: Sequence[PostseasonGame]) -> dict[SeriesId, _Placed]:
        if self.sources.past and not any(
            ROUNDS.get(g.competition_type or "")
            for g in _unique_games(games)
            if g.season_type == POSTSEASON
        ):
            groups = derive_series(
                games, {code: e.conference for code, e in self.entries.items()}
            )
        else:
            groups = group_series(games)
        slots = self._seedless_slots(groups)
        placed: dict[SeriesId, _Placed] = {}
        of_team: dict[str, SeriesId] = {}
        for round_ in (1, 2, 3, 4):
            this_round: dict[str, SeriesId] = {}
            ordered = sorted(
                (key for key in groups if key[0] == round_),
                key=lambda key: (
                    groups[key][0].game.start_time,
                    sorted(key[1]),
                ),
            )
            for key in ordered:
                codes = sorted(key[1])
                if slots is not None and round_ == 1:
                    series_id, (top, bottom) = slots[key[1]], codes
                else:
                    series_id, top, bottom = self._slot(round_, codes, of_team)
                if series_id in placed:
                    raise PlayoffsBuildError(
                        f"two series in the slot {series_id.value}"
                    )
                placed[series_id] = _Placed(series_id, top, bottom, groups[key])
                for code in codes:
                    this_round[code] = series_id
            of_team = this_round
        return placed

    def _seedless_slots(
        self, groups: Mapping[tuple[int, frozenset[str]], list[PostseasonGame]]
    ) -> dict[frozenset[str], SeriesId] | None:
        """For a past season where a round 1 team has no seed, the slot of each
        round 1 series from the round 2 series it feeds; none when every round 1
        team has a seed."""
        round_one = [pair for round_, pair in groups if round_ == 1]
        if not self.sources.past or all(
            self.seeds.get(code) is not None for pair in round_one for code in pair
        ):
            return None
        slots: dict[frozenset[str], SeriesId] = {}
        for conference in CONFERENCES:
            second = sorted(
                (
                    key
                    for key in groups
                    if key[0] == 2 and self.entry(min(key[1])).conference is conference
                ),
                key=lambda key: _start_key(groups[key], key[1]),
            )
            if len(second) != 2:
                raise PlayoffsBuildError(
                    f"the {conference.value} has {len(second)} round 2 series, not 2"
                )
            for index, (_, pair) in enumerate(second):
                for offset, code in enumerate(sorted(pair)):
                    feeder = next((p for p in round_one if code in p), None)
                    if feeder is None:
                        raise PlayoffsBuildError(f"team {code} has no round 1 series")
                    if feeder in slots:
                        raise PlayoffsBuildError(
                            f"round 1 series {' '.join(sorted(feeder))} is placed twice"
                        )
                    slots[feeder] = SeriesId(
                        f"{conference.value}-r1-{2 * index + offset + 1}"
                    )
        for pair in round_one:
            if pair not in slots:
                raise PlayoffsBuildError(
                    f"round 1 series {' '.join(sorted(pair))} feeds no round 2 series"
                )
        return slots

    def _slot(
        self, round_: int, codes: list[str], of_team: Mapping[str, SeriesId]
    ) -> tuple[SeriesId, str, str]:
        first, second = codes
        if round_ == 1:
            conference = self.entry(first).conference
            if self.entry(second).conference is not conference:
                raise PlayoffsBuildError(
                    f"round 1 series {first} {second} mixes the conferences"
                )
            seeds = (self.seeds.get(first), self.seeds.get(second))
            number = SERIES_OF_SEEDS.get(frozenset(s for s in seeds if s is not None))
            if None in seeds or number is None:
                raise PlayoffsBuildError(
                    f"round 1 series {first} {second} has seeds outside the bracket"
                )
            top, bottom = (first, second) if seeds[0] < seeds[1] else (second, first)  # type: ignore[operator]
            return SeriesId(f"{conference.value}-r1-{number}"), top, bottom
        feeders = [of_team.get(code) for code in (first, second)]
        for series_id in SeriesId:
            if round_of_series(series_id) != round_:
                continue
            upper, lower = FEEDERS[series_id]
            if set(feeders) == {upper, lower}:
                top, bottom = (
                    (first, second) if feeders[0] == upper else (second, first)
                )
                return series_id, top, bottom
        raise PlayoffsBuildError(
            f"round {round_} series {first} {second} is not fed by its series"
        )

    def _info(self, placed: _Placed) -> _Info:
        wins = series_wins(placed.games)
        top, bottom = wins.get(placed.top, 0), wins.get(placed.bottom, 0)
        if top >= WINS_TO_WIN and bottom >= WINS_TO_WIN:
            raise PlayoffsBuildError(
                f"series {placed.series_id.value} is complete with tied wins"
            )
        if top >= WINS_TO_WIN or bottom >= WINS_TO_WIN:
            winner, loser_wins = (
                (placed.top, bottom) if top > bottom else (placed.bottom, top)
            )
            status = SeriesStatus.COMPLETE
            summary = f"{winner} wins series {WINS_TO_WIN}-{loser_wins}"
        elif any(g.game.status is GameStatus.FINAL for g in placed.games):
            winner = None
            status = SeriesStatus.IN_PROGRESS
            if top == bottom:
                summary = f"Series tied {top}-{top}"
            else:
                leader = placed.top if top > bottom else placed.bottom
                summary = f"{leader} leads series {max(top, bottom)}-{min(top, bottom)}"
        else:
            return _Info(
                status=SeriesStatus.UPCOMING, summary=None, wins=None, winner=None
            )
        return _Info(
            status=status,
            summary=summary,
            wins={placed.top: top, placed.bottom: bottom},
            winner=winner,
        )

    # State

    def _state(self) -> PlayoffsState:
        finals = self.info.get(SeriesId.FINALS)
        if finals is not None and finals.status is SeriesStatus.COMPLETE:
            return PlayoffsState.COMPLETE
        if finals is not None:
            return PlayoffsState.FINALS
        if any(
            _live_or_final(game)
            for series_id, placed in self.placed.items()
            if round_of_series(series_id) == 1
            for game in placed.games
        ):
            return PlayoffsState.PLAYOFFS
        play_in = self.sources.play_in
        if play_in is not None and self.sources.today >= eastern_date(play_in.start):
            return PlayoffsState.PLAYIN
        return PlayoffsState.PICTURE

    # Picture

    def picture(self) -> list[dict[str, Any]]:
        tables = []
        for conference in CONFERENCES:
            members = sorted(
                (e for e in self.entries.values() if e.conference is conference),
                key=conference_order_key,
            )
            leader = leader_of(members) if members else None
            rows = []
            for number, entry in enumerate(members[:10], start=1):
                known = not self.preseason
                rows.append(
                    {
                        "seed": seed_of(entry) if known else None,
                        "team": self.team(entry.code),
                        "wins": entry.wins if known else None,
                        "losses": entry.losses if known else None,
                        "games_behind": (
                            conference_games_behind_text(entry, leader, members)
                            if known and leader is not None
                            else None
                        ),
                        "clinch": entry.clinch if known else None,
                        "line": {6: "playoffs", 10: "playin"}.get(number),
                    }
                )
            tables.append({"conference": conference, "rows": rows})
        return tables

    # Play-in

    def _currently(self, conference: Conference, place: int) -> dict[str, Any] | None:
        if self.state is not PlayoffsState.PICTURE or self.preseason:
            return None
        code = self.raw_by_seed.get((conference, place))
        return None if code is None else self.team(code)

    def _slot_payload(
        self,
        key: str,
        code: str | None,
        currently: dict[str, Any] | None = None,
        place: int | None = None,
        game: PlayInGameKind | None = None,
    ) -> dict[str, Any]:
        return {
            "label": {"key": key, "place": place, "game": game},
            "team": None if code is None else self.team(code),
            "currently": None if code is not None else currently,
        }

    def play_in_feed(self) -> list[dict[str, Any]] | None:
        if self.sources.play_in is None:
            return None
        result = []
        for conference in CONFERENCES:
            games = []
            for kind in PlayInGameKind:
                game = self.play_in.get((conference, kind))
                if kind is PlayInGameKind.EIGHTH_SEED:
                    seven_eight = self.outcomes.get(
                        (conference, PlayInGameKind.SEVEN_EIGHT)
                    )
                    nine_ten = self.outcomes.get((conference, PlayInGameKind.NINE_TEN))
                    top = self._slot_payload(
                        "loser_of",
                        None if seven_eight is None else seven_eight[1],
                        game=PlayInGameKind.SEVEN_EIGHT,
                    )
                    bottom = self._slot_payload(
                        "winner_of",
                        None if nine_ten is None else nine_ten[0],
                        game=PlayInGameKind.NINE_TEN,
                    )
                else:
                    places = (7, 8) if kind is PlayInGameKind.SEVEN_EIGHT else (9, 10)
                    home, away = (None, None) if game is None else _codes(game)
                    top = self._slot_payload(
                        "place",
                        home,
                        self._currently(conference, places[0]),
                        place=places[0],
                    )
                    bottom = self._slot_payload(
                        "place",
                        away,
                        self._currently(conference, places[1]),
                        place=places[1],
                    )
                outcome = None
                if (conference, kind) in self.outcomes:
                    outcome = {
                        PlayInGameKind.SEVEN_EIGHT: {"seed": 7, "loser_out": False},
                        PlayInGameKind.NINE_TEN: {"seed": None, "loser_out": True},
                        PlayInGameKind.EIGHTH_SEED: {"seed": 8, "loser_out": True},
                    }[kind]
                games.append(
                    {
                        "kind": kind,
                        "top": top,
                        "bottom": bottom,
                        "game": None if game is None else self.game(game),
                        "outcome": outcome,
                    }
                )
            result.append({"conference": conference, "games": games})
        return result

    # Bracket

    def _label(self, series_id: SeriesId, side: int) -> dict[str, Any]:
        conference = conference_of_series(series_id)
        label: dict[str, Any] = {
            "key": None,
            "conference": conference,
            "seed": None,
            "series": None,
        }
        round_ = round_of_series(series_id)
        if round_ == 1:
            number = int(series_id.value[-1])
            seed = SEEDS_OF_SERIES[number][side]
            label["key"] = (
                SeriesLabelKey.SEED
                if seed <= STANDINGS_SEEDS or self.sources.play_in is None
                else SeriesLabelKey.PLAYIN_WINNER
            )
            label["seed"] = seed
        elif round_ == 2:
            number = int(series_id.value[-1])
            label["key"] = SeriesLabelKey.ROUND_1_WINNER
            label["series"] = 2 * (number - 1) + side + 1
        elif round_ == 3:
            label["key"] = SeriesLabelKey.ROUND_2_WINNER
            label["series"] = side + 1
        else:
            label["key"] = SeriesLabelKey.ROUND_3_WINNER
            label["conference"] = CONFERENCES[side]
        return label

    def _side(self, series_id: SeriesId, side: int) -> dict[str, Any]:
        label = self._label(series_id, side)
        placed = self.placed.get(series_id)
        team: str | None = None
        currently: dict[str, Any] | None = None
        wins: int | None = None
        if placed is not None:
            team = placed.top if side == 0 else placed.bottom
            info = self.info[series_id]
            wins = None if info.wins is None else info.wins[team]
        elif round_of_series(series_id) == 1:
            conference = conference_of_series(series_id)
            assert conference is not None
            seed = label["seed"]
            if self.state is PlayoffsState.PICTURE:
                code = (
                    None if self.preseason else self.raw_by_seed.get((conference, seed))
                )
                currently = None if code is None else self.team(code)
            elif seed <= 6 and self.preseason:
                team = None
            else:
                team = self.by_seed.get((conference, seed))
        else:
            feeder = self.info.get(FEEDERS[series_id][side])
            if feeder is not None and feeder.status is SeriesStatus.COMPLETE:
                team = feeder.winner
        return {
            "label": label,
            "team": None if team is None else self.team(team),
            "seed": None if team is None else self.seeds.get(team),
            "wins": wins,
            "currently": currently,
        }

    def series(self, series_id: SeriesId) -> dict[str, Any]:
        placed = self.placed.get(series_id)
        info = self.info.get(series_id)
        return {
            "id": series_id,
            "round": round_of_series(series_id),
            "conference": conference_of_series(series_id),
            "top": self._side(series_id, 0),
            "bottom": self._side(series_id, 1),
            "status": SeriesStatus.UPCOMING if info is None else info.status,
            "summary": None if info is None else info.summary,
            "winner": None if info is None else info.winner,
            "games": []
            if placed is None
            else [self.series_game(g, placed.games) for g in placed.games],
        }

    # Stages

    def _round_games(self, round_: int) -> list[PostseasonGame]:
        return [
            game
            for series_id, placed in self.placed.items()
            if round_of_series(series_id) == round_
            for game in placed.games
        ]

    def _stage_games(self, stage: PlayoffStage) -> list[PostseasonGame]:
        if stage is PlayoffStage.PLAYIN:
            return self.play_in_games
        return self._round_games(STAGES.index(stage))

    def _stage_complete(self, stage: PlayoffStage) -> bool:
        if stage is PlayoffStage.PLAYIN:
            return len(self.play_in_games) == 6 and all(
                g.game.status is GameStatus.FINAL for g in self.play_in_games
            )
        round_ = STAGES.index(stage)
        done = [
            sid
            for sid, info in self.info.items()
            if round_of_series(sid) == round_ and info.status is SeriesStatus.COMPLETE
        ]
        return len(done) == SERIES_OF_ROUND[round_]

    def stages(self) -> list[dict[str, Any]]:
        complete = {stage: self._stage_complete(stage) for stage in STAGES}
        started = {
            stage: any(_live_or_final(g) for g in self._stage_games(stage))
            for stage in STAGES
        }
        last = -1
        for index, stage in enumerate(STAGES):
            if complete[stage] or started[stage]:
                last = index
        entries = []
        for index, stage in enumerate(STAGES):
            if complete[stage]:
                status = PlayoffStageStatus.COMPLETE
            elif started[stage]:
                status = PlayoffStageStatus.IN_PROGRESS
            elif index == last + 1:
                status = PlayoffStageStatus.NEXT
            else:
                status = PlayoffStageStatus.UPCOMING
            dates = [eastern_date(g.game.start_time) for g in self._stage_games(stage)]
            entries.append(
                {
                    "stage": stage,
                    "status": status,
                    "first_date": min(dates) if dates else None,
                    "last_date": max(dates) if dates else None,
                }
            )
        return entries

    def current_round(self) -> int | None:
        if self.state is not PlayoffsState.PLAYOFFS:
            return None
        current = 1
        for round_ in (1, 2, 3):
            if any(_live_or_final(g) for g in self._round_games(round_)):
                current = round_
                if self._stage_complete(STAGES[round_]):
                    current = min(round_ + 1, 3)
        return current

    def finals_line(self) -> tuple[int | None, str | None]:
        if self.state not in (PlayoffsState.FINALS, PlayoffsState.COMPLETE):
            return None, None
        finals = self.placed[SeriesId.FINALS]
        played = [g for g in finals.games if _live_or_final(g)]
        if not played:
            return None, None
        last = played[-1]
        number = self.game_number(last, finals.games)
        return number, self.info[SeriesId.FINALS].summary

    # Champion

    def champion(self) -> dict[str, Any] | None:
        if self.state is not PlayoffsState.COMPLETE:
            return None
        finals = self.placed[SeriesId.FINALS]
        info = self.info[SeriesId.FINALS]
        assert info.winner is not None and info.wins is not None
        winner = info.winner
        loser = finals.bottom if winner == finals.top else finals.top
        record = self.sources.champion_record
        dates = [eastern_date(g.game.start_time) for g in finals.games]
        points = 0
        for placed in self.placed.values():
            for game in placed.games:
                score = game.game.score
                if game.game.status is not GameStatus.FINAL or score is None:
                    continue
                home, away = _codes(game)
                if winner == home:
                    points += score.home - score.away
                elif winner == away:
                    points += score.away - score.home
        return {
            "team": self.team(winner),
            "wins": info.wins[winner],
            "losses": info.wins[loser],
            "first_date": min(dates),
            "last_date": max(dates),
            "record": None if record is None else record.overall,
            "home": None if record is None else record.home,
            "road": None if record is None else record.road,
            "point_differential": signed_total(points),
        }

    # Leaders and awards

    def leaders(self) -> list[dict[str, Any]] | None:
        source = self.sources.leaders
        if source is None:
            return None
        groups = []
        for category in LeaderCategory:
            leaders = []
            for rank, entry in enumerate(
                source.categories.get(category, [])[:MAX_LEADERS], start=1
            ):
                found = self.sources.players.get(entry.player_id)
                if found is None:
                    continue
                code, roster = found
                leaders.append(
                    {
                        "rank": rank,
                        "player_id": entry.player_id,
                        "name": player_name(roster),
                        "photo_url": roster.headshot_url,
                        "team_code": code,
                        "value": entry.value,
                    }
                )
            groups.append({"category": category, "leaders": leaders})
        if not any(group["leaders"] for group in groups):
            return None
        return groups

    def awards(self) -> list[dict[str, Any]] | None:
        source = self.sources.awards
        if source is None:
            return None
        order = list(AwardCode)
        awards = []
        for award in source.awards:
            winners = []
            for winner in award.winners:
                found = self.sources.players.get(winner.player_id)
                if found is None:
                    continue
                code, roster = found
                winners.append(
                    {
                        "player_id": winner.player_id,
                        "name": player_name(roster),
                        "photo_url": roster.headshot_url,
                        "team_code": winner.team_code or code,
                    }
                )
            if winners:
                awards.append(
                    {"code": award.code, "team": award.team, "winners": winners}
                )
        if not awards:
            return None
        return sorted(awards, key=lambda a: (order.index(a["code"]), a["team"] or 0))

    # Feed

    def build(self) -> PlayoffsFeed:
        finals_game, finals_summary = self.finals_line()
        sources = self.sources
        first_window = sources.play_in or sources.postseason
        game_dates = [eastern_date(g.game.start_time) for g in sources.games]
        if sources.postseason is not None and first_window is not None:
            first_date = eastern_date(first_window.start)
            last_date = eastern_date(sources.postseason.end)
        else:
            if not game_dates:
                raise PlayoffsBuildError("a build with no window has no game")
            first_date = (
                eastern_date(first_window.start) if first_window else min(game_dates)
            )
            last_date = max(game_dates)
        try:
            return PlayoffsFeed.model_validate(
                {
                    "season": season_label(sources.season),
                    "state": self.state,
                    "postseason_dates": {
                        "first_date": first_date,
                        "last_date": last_date,
                    },
                    "current_round": self.current_round(),
                    "finals_game": finals_game,
                    "finals_summary": finals_summary,
                    "stages": self.stages(),
                    "picture": self.picture(),
                    "play_in": self.play_in_feed(),
                    "bracket": [self.series(series_id) for series_id in SeriesId],
                    "champion": self.champion(),
                    "leaders": self.leaders(),
                    "awards": self.awards(),
                }
            )
        except ValidationError as error:
            location = ".".join(str(part) for part in error.errors()[0]["loc"])
            raise PlayoffsBuildError(
                f"invalid feed: {error.error_count()} errors, first at {location}"
            ) from None


def build_playoffs_feed(sources: PlayoffsSources) -> PlayoffsFeed:
    """Build the playoffs feed; raise PlayoffsBuildError when it is not valid."""
    return _Builder(sources).build()


class PlayoffsFeeds:
    def __init__(
        self,
        settings: Settings,
        store: StateStore,
        client: SourceClient,
        cache: FeedCache,
        games: GamesJob,
        stars: StarsJob,
        *,
        fetch_season_type: FetchSeasonType = season_types.fetch_season_type,
        fetch_postseason_games: FetchPostseasonGames = (
            postseason_scoreboard.fetch_postseason_games
        ),
        fetch_division_standings: FetchDivisionStandings = (
            division_standings.fetch_division_standings
        ),
        fetch_team_info: FetchInfo = team_info.fetch_team_info,
        fetch_postseason_leaders: FetchLeaders = (
            postseason_leaders.fetch_postseason_leaders
        ),
        fetch_season_awards: FetchAwards = season_awards.fetch_season_awards,
        fetch_team_postseason_record: FetchRecord = (
            team_postseason.fetch_team_postseason_record
        ),
    ) -> None:
        self._settings = settings
        self._store = store
        self._client = client
        self._games = games
        self._stars = stars
        self._fetch_season_type = fetch_season_type
        self._fetch_postseason_games = fetch_postseason_games
        self._fetch_division_standings = fetch_division_standings
        self._fetch_team_info = fetch_team_info
        self._fetch_postseason_leaders = fetch_postseason_leaders
        self._fetch_season_awards = fetch_season_awards
        self._fetch_team_postseason_record = fetch_team_postseason_record
        cache.register(self.kind())

    def check(self, feed_id: str) -> IdStatus:
        if feed_id != FEED_ID:
            return IdStatus.UNKNOWN
        if (
            self._stars.current_season() is None or not self._stars.rosters_ready()
        ) and read_by_id(self._settings.data_dir, KIND, FEED_ID) is None:
            return IdStatus.NOT_READY
        return IdStatus.KNOWN

    def stored(self) -> PlayoffsFeed | None:
        """The stored playoffs feed, or none when missing or invalid."""
        body = read_by_id(self._settings.data_dir, KIND, FEED_ID)
        if body is None:
            return None
        try:
            return PlayoffsFeed.model_validate_json(body)
        except ValidationError:
            return None

    async def _info(self, code: str) -> TeamInfo | None:
        try:
            return await self._fetch_team_info(self._client, code, self._settings)
        except SourceError:
            return None

    async def _leaders(self, season: int) -> PostseasonLeaders | None:
        try:
            return await self._fetch_postseason_leaders(
                self._client, season, self._settings
            )
        except SourceError:
            return None

    async def _awards(self, season: int) -> SeasonAwards | None:
        try:
            return await self._fetch_season_awards(self._client, season, self._settings)
        except SourceError:
            return None

    async def _record(self, code: str, season: int) -> TeamPostseasonRecord | None:
        try:
            return await self._fetch_team_postseason_record(
                self._client, code, season, self._settings
            )
        except SourceError:
            return None

    async def build(self, feed_id: str) -> PlayoffsFeed:
        season = self._stars.current_season()
        if season is None:
            raise PlayoffsBuildError("season not known yet")
        client, settings = self._client, self._settings
        today = eastern_date(client.clock())
        play_in, postseason, standings, infos, leaders, awards = await asyncio.gather(
            self._fetch_season_type(client, season, PLAY_IN, settings),
            self._fetch_season_type(client, season, POSTSEASON, settings),
            self._fetch_division_standings(client, settings),
            asyncio.gather(*(self._info(code) for code in CODES)),
            self._leaders(season),
            self._awards(season),
        )
        games: list[PostseasonGame] = []
        if reads_days(today, play_in):
            days = await asyncio.gather(
                *(
                    self._fetch_postseason_games(client, day, settings)
                    for day in postseason_days(play_in, postseason)
                )
            )
            games = [game for day in days for game in day]
        winner = finals_winner(games)
        record = None if winner is None else await self._record(winner, season)
        players = {
            entry.player_id: (code, entry)
            for code, entries in self._stars.roster_entries().items()
            for entry in entries
            if self._stars.player_team(entry.player_id) == code
        }
        return build_playoffs_feed(
            PlayoffsSources(
                season=season,
                today=today,
                play_in=play_in,
                postseason=postseason,
                standings=standings,
                colors=dict(zip(CODES, infos, strict=True)),
                games=games,
                players=players,
                leaders=leaders,
                awards=awards,
                champion_record=record,
            )
        )

    def league_final_times(self) -> list[dt.datetime]:
        """The final times of every game of the league."""
        ids = sorted(game.id for game in self._games.final_games())
        times = (self._store.final_time(game_id) for game_id in ids)
        return [time for time in times if time is not None]

    def final_times(
        self, feed: PlayoffsFeed, built_at: dt.datetime, now: dt.datetime
    ) -> list[dt.datetime]:
        """The final times of the postseason games that can expire a feed built at
        built_at: the final games of the games job dated inside the postseason
        dates, and every game of the feed."""
        first, last = feed.postseason_dates.first_date, feed.postseason_dates.last_date
        ids = {
            game.id
            for game in self._games.final_games()
            if first <= eastern_date(game.start_time) <= last
        }
        for play_in in feed.play_in or []:
            ids |= {g.game.id for g in play_in.games if g.game is not None}
        for series in feed.bracket:
            ids |= {g.id for g in series.games}
        times = (self._store.final_time(game_id) for game_id in sorted(ids))
        return [time for time in times if time is not None]

    def is_fresh(
        self, feed: PlayoffsFeed, built_at: dt.datetime, now: dt.datetime
    ) -> bool:
        if feed.state is PlayoffsState.COMPLETE:
            season = self._stars.current_season()
            if season is None or feed.season == season_label(season):
                return True
        start = dt.datetime.combine(
            feed.postseason_dates.first_date, dt.time(0), EASTERN
        )
        if built_at < start <= now:
            return False
        if feed.state is PlayoffsState.PICTURE and feed_expired(
            built_at, now, self.league_final_times()
        ):
            return False
        return not feed_expired(built_at, now, self.final_times(feed, built_at, now))

    def serve_with(self, feed_id: str, feed: PlayoffsFeed) -> PlayoffsFeed:
        ids = {game.id for game in self._games.loaded_games()}
        data = feed.model_dump(by_alias=False)
        for play_in in data["play_in"] or []:
            for entry in play_in["games"]:
                if entry["game"] is not None:
                    entry["game"]["detail_available"] = entry["game"]["id"] in ids
        for series in data["bracket"]:
            for game in series["games"]:
                game["detail_available"] = game["id"] in ids
        return PlayoffsFeed.model_validate(data)

    def keep(self, feed_id: str) -> bool:
        return feed_id == FEED_ID

    def kind(self) -> FeedKind[PlayoffsFeed]:
        return FeedKind(
            KIND,
            PlayoffsFeed,
            check=self.check,
            build=self.build,
            is_fresh=self.is_fresh,
            keep=self.keep,
            serve_with=self.serve_with,
        )
