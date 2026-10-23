# api/app/jobs/cup_feed.py
#
# Cup feed builder: a pure function from the Cup sources (the six groups, their
# tables, the two conference tables and the team schedules) to the Cup feed.
# The draw is the teams of the six groups; with no draw the feed has the stage
# "draw" and empty groups. Games are the schedule games whose note names a Cup
# round, seen from both teams and merged by game id; the championship is the
# only game outside the standings and the semifinals and the championship are
# on a neutral court. A round is final when it has all its games (60, 4, 2, 1)
# and every one is final. The stage is draw with no table rows, group while the
# group round is not final or no quarterfinal is scheduled, then the earliest
# knockout round that is not final, then complete. Seeds are the first three
# rows of each conference table and the wild card is its fourth row; the bracket
# holds the 7 slots with labels and rules as keys, the projected team of an
# unscheduled quarterfinal side with its record, a side's standing (its row in
# its conference table) and the last period of a final game, and the scheduled game that
# replaces it. The build reads no clock and no source. CupFeeds is the feed
# kind of the on-demand cache: the build runs under READ_BUDGET reads (counting reads only) and reads a
# schedule at most 24 hours old, 1 hour for a team playing today (ADR 0066); the
# only id is "league", the feed is stored at
# feeds/cup/league.json only when requested, and it expires 1 hour after a final
# Cup game that follows the build and 7 days after the build (rule G). Once the
# championship is final the feed is kept while its season is the current one,
# the season of the stars job's latest roster. A schedule that fails is skipped
# only when every drawn team still has its 4 group games among the games read.
# The feed is never deleted. read_cup_sources reads the sources of one season;
# the past season kind (season_cup_feed.py) uses it too. In a past season the
# seeds the quarterfinals were drawn by are not known (the tables are those of the
# end of the season), so the two quarterfinals of a conference are placed by start
# time, then id, with a seed label of no seed (ADR 0053). The past Cup feed of the
# season before is built first through the cache under its own budget (the current
# budget is unchanged), and its stored champion is copied as the defending champion,
# null without one; a failure there never fails the feed (ADR 0064).
#
# SEE: docs/api/cup.md, docs/adr/0028-cup-feed.md,
# docs/adr/0072-resolved-team-colors-in-the-playoffs-and-cup-feeds.md,
# api/app/jobs/standings_feed.py

import asyncio
import datetime as dt
import re
from collections.abc import Awaitable, Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol

from pydantic import ValidationError

from app.feeds.cup import (
    GROUP_GAMES,
    GROUP_GAMES_TOTAL,
    ROUNDS,
    BracketSlot,
    CupFeed,
    CupStage,
    CupTag,
    SlotAccent,
    SlotId,
    StageStatus,
)
from app.feeds.game_detail import Conference
from app.feeds.games import CupRound, GameStatus
from app.feeds.opponent import Opponent, Side
from app.jobs.games import GamesJob
from app.jobs.on_demand import FeedCache, FeedKind, IdStatus
from app.jobs.standings_feed import (
    StandingsBuildError,
    division_games_behind,
    signed_per_game,
    signed_total,
)
from app.jobs.stars import StarsJob
from app.jobs.team_feed import (
    TeamBuildError,
    eastern_date,
    feed_expired,
    season_label,
)
from app.jobs.team_feed import streak as parse_streak
from app.jobs.team_identity import pair_colors, resolved_color, team_colors
from app.settings import Settings
from app.sources import cup, team_schedule
from app.sources.cup import GROUP_IDS, CupTable, CupTableRow, cup_round
from app.sources.http import (
    Freshness,
    ReadBudget,
    SourceClient,
    SourceError,
    within_budget,
)
from app.sources.team_schedule import ScheduledGame, SeasonSchedule
from app.sources.teams import TEAM_CODES
from app.storage.feeds import read_by_id
from app.storage.state import StateStore, TeamIdentity

KIND = "cup"
FEED_ID = "league"
CODES = sorted(set(TEAM_CODES.values()))
GAMES_OF_ROUND = {
    CupRound.GROUP: GROUP_GAMES_TOTAL,
    CupRound.QUARTERFINALS: 4,
    CupRound.SEMIFINALS: 2,
    CupRound.CHAMPIONSHIP: 1,
}
GROUP_GAMES_OF_TEAM = 4
STAGE_OF_ROUND = {
    CupRound.QUARTERFINALS: CupStage.QUARTERFINALS,
    CupRound.SEMIFINALS: CupStage.SEMIFINALS,
    CupRound.CHAMPIONSHIP: CupStage.CHAMPIONSHIP,
}
STAGE_INDEX = {
    CupStage.DRAW: -1,
    CupStage.GROUP: 0,
    CupStage.QUARTERFINALS: 1,
    CupStage.SEMIFINALS: 2,
    CupStage.CHAMPIONSHIP: 3,
    CupStage.COMPLETE: 4,
}
_RECORD = re.compile(r"^\d+-\d+$")
CONFERENCES = (Conference.EAST, Conference.WEST)

FetchGroupTeams = Callable[
    [SourceClient, int, Conference, str, Settings], Awaitable[list[str]]
]
FetchGroupTable = Callable[
    [SourceClient, int, Conference, str, Settings], Awaitable[CupTable]
]
FetchConferenceTable = Callable[
    [SourceClient, int, Conference, Settings], Awaitable[CupTable]
]
FetchSeasonSchedule = Callable[..., Awaitable[SeasonSchedule]]
# A team's schedule is fresh for 24 hours, 1 hour for a team with a game today
# (ADR 0066).
SCHEDULE_FRESH = dt.timedelta(hours=24)
# The most source reads one build sends: 6 group teams + 6 group tables + 2
# conference tables + 30 team schedules, as season_cup_feed.READ_BUDGET.
READ_BUDGET = 44


class CupBuildError(Exception):
    """The Cup feed built from the fetched data is not valid."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class PreviousCups(Protocol):
    """The past Cup kind the current Cup feed reads its defending champion from."""

    def previous_cup(self, season: int) -> tuple[str, str] | None:
        """The (kind, id) of the past Cup feed of the season before, or none."""
        ...

    def defending_champion(self, season: int) -> Opponent | None:
        """The champion of the stored past Cup feed of the season before. Reads no source."""
        ...


def with_defending_champion(feed: CupFeed, champion: Opponent | None) -> CupFeed:
    """The feed with the champion of the previous season's Cup."""
    return feed.model_copy(update={"defending_champion": champion})


@dataclass(frozen=True)
class CupSources:
    """What the Cup build reads. Never reaches a feed."""

    season: int
    group_teams: Mapping[tuple[Conference, str], Sequence[str]]
    group_tables: Mapping[tuple[Conference, str], CupTable]
    conference_tables: Mapping[Conference, CupTable]
    schedules: Mapping[str, SeasonSchedule]
    failed_schedules: frozenset[str] = field(default_factory=frozenset)
    # A past season (ADR 0053): its quarterfinals are placed by start time.
    past: bool = False


@dataclass(frozen=True)
class _Game:
    """A Cup game seen from both teams."""

    id: str
    stage: CupRound
    start_time: dt.datetime
    home: str
    away: str
    status: GameStatus
    home_score: int | None
    away_score: int | None
    broadcast: str | None
    venue: str
    city: str | None
    period: int | None

    @property
    def final(self) -> bool:
        return self.status is GameStatus.FINAL

    @property
    def winner(self) -> str | None:
        if not self.final or self.home_score is None or self.away_score is None:
            return None
        if self.home_score == self.away_score:
            return None
        return self.home if self.home_score > self.away_score else self.away

    @property
    def date(self) -> dt.date:
        return eastern_date(self.start_time)


def status_of(game: ScheduledGame) -> GameStatus:
    if game.completed and game.state == "post":
        return GameStatus.FINAL
    if game.state == "in":
        return GameStatus.LIVE
    if game.state == "post":
        return GameStatus.POSTPONED
    return GameStatus.SCHEDULED


def cup_games(schedules: Mapping[str, SeasonSchedule]) -> list[_Game]:
    """The Cup games of the schedules, merged by game id, in start order."""
    merged: dict[str, _Game] = {}
    for code in sorted(schedules):
        for game in schedules[code].games:
            stage = cup_round(game.note)
            if stage is None or game.game_id in merged:
                continue
            other = game.opponent.code
            if other is None or game.opponent.guest:
                raise CupBuildError(
                    f"Cup game {game.game_id} has a team outside the league"
                )
            home, away = (code, other) if game.is_home else (other, code)
            mine, theirs = game.team_score, game.opponent_score
            home_score, away_score = (mine, theirs) if game.is_home else (theirs, mine)
            merged[game.game_id] = _Game(
                id=game.game_id,
                stage=stage,
                start_time=game.start_time,
                home=home,
                away=away,
                status=status_of(game),
                home_score=home_score,
                away_score=away_score,
                broadcast=game.broadcast,
                venue=game.arena,
                city=game.city,
                period=game.period,
            )
    return sorted(merged.values(), key=lambda g: (g.start_time, g.id))


def _group_games_of(games: Iterable[_Game]) -> list[_Game]:
    return [game for game in games if game.stage is CupRound.GROUP]


def covers_the_group_games(
    group_teams: Mapping[tuple[Conference, str], Sequence[str]],
    schedules: Mapping[str, SeasonSchedule],
) -> bool:
    """Whether every drawn team has its 4 group games among the schedules read."""
    games = _group_games_of(cup_games(schedules))
    for teams in group_teams.values():
        for code in teams:
            seen = sum(1 for game in games if code in (game.home, game.away))
            if seen < GROUP_GAMES_OF_TEAM:
                return False
    return True


def group_round_is_decided(
    group_tables: Mapping[tuple[Conference, str], CupTable],
    schedules: Mapping[str, SeasonSchedule],
) -> bool:
    """Whether a knockout game can already be in play: a group row has a won_group
    or wild_card tag, or the group round is final among the schedules read."""
    for table in group_tables.values():
        if any(
            row.clincher in (CupTag.WON_GROUP, CupTag.WILD_CARD) for row in table.rows
        ):
            return True
    return _is_round_final(cup_games(schedules), CupRound.GROUP)


def _is_round_final(games: Sequence[_Game], stage: CupRound) -> bool:
    of_round = [game for game in games if game.stage is stage]
    return len(of_round) == GAMES_OF_ROUND[stage] and all(g.final for g in of_round)


def _record_text(text: str | None) -> str | None:
    return text if text is not None and _RECORD.match(text) else None


def _tag(row: CupTableRow) -> str | None:
    return None if row.clincher is None else row.clincher.value


def _stage_of(
    games: Sequence[_Game], has_rows: bool, final: Mapping[CupRound, bool]
) -> CupStage:
    if not has_rows:
        return CupStage.DRAW
    scheduled_quarterfinals = any(g.stage is CupRound.QUARTERFINALS for g in games)
    if not scheduled_quarterfinals or not final[CupRound.GROUP]:
        return CupStage.GROUP
    for stage in (
        CupRound.QUARTERFINALS,
        CupRound.SEMIFINALS,
        CupRound.CHAMPIONSHIP,
    ):
        if not final[stage]:
            return STAGE_OF_ROUND[stage]
    return CupStage.COMPLETE


class _Builder:
    def __init__(self, sources: CupSources) -> None:
        self.sources = sources
        self.games = cup_games(sources.schedules)
        teams = sources.group_teams
        self.drawn = all(len(teams.get(key, ())) > 0 for key in GROUP_IDS)
        self.group_tables: dict[tuple[Conference, str], CupTable] = {
            key: (
                sources.group_tables.get(key, CupTable(rows=[]))
                if self.drawn
                else CupTable(rows=[])
            )
            for key in GROUP_IDS
        }
        self.conference_tables: dict[Conference, CupTable] = {
            conference: (
                sources.conference_tables.get(conference, CupTable(rows=[]))
                if self.drawn
                else CupTable(rows=[])
            )
            for conference in CONFERENCES
        }
        self.group_of: dict[str, dict[str, Any]] = {}
        if self.drawn:
            for (conference, letter), codes in teams.items():
                for code in codes:
                    self.group_of[code] = {"conference": conference, "letter": letter}
        self.names = self._names()
        self.final = {stage: _is_round_final(self.games, stage) for stage in ROUNDS}

    def _names(self) -> dict[str, dict[str, Any]]:
        names: dict[str, dict[str, Any]] = {}
        for schedule in self.sources.schedules.values():
            for game in schedule.games:
                opponent = game.opponent
                if opponent.code is not None and not opponent.guest:
                    names.setdefault(
                        opponent.code,
                        {"name": opponent.name, "city": opponent.city},
                    )
        return names

    def team(self, code: str) -> dict[str, Any]:
        found = self.names.get(code, {"name": None, "city": None})
        return {
            "code": code,
            "name": found["name"],
            "city": found["city"],
            "guest": False,
        }

    def conference_of(self, code: str) -> Conference:
        group = self.group_of.get(code)
        if group is None:
            raise CupBuildError(f"team {code} is not in the draw")
        conference: Conference = group["conference"]
        return conference

    def standing(self, code: str) -> dict[str, Any] | None:
        """A team's row in its conference table, or None when it has none."""
        for table in self.conference_tables.values():
            for index, row in enumerate(table.rows, start=1):
                if row.code == code:
                    return {
                        "seed": index if index <= 4 else None,
                        "group": self.group_of.get(code),
                        "wins": row.wins,
                        "losses": row.losses,
                    }
        return None

    # Games

    def game(self, game: _Game) -> dict[str, Any]:
        score = (
            None
            if game.home_score is None or game.away_score is None
            else {"away": game.away_score, "home": game.home_score}
        )
        winner = game.winner
        return {
            "id": game.id,
            "stage": game.stage,
            "date": game.date,
            "start_time": game.start_time,
            "away": self.team(game.away),
            "home": self.team(game.home),
            "status": game.status,
            "score": score,
            "winner": (
                None
                if winner is None
                else (Side.HOME if winner == game.home else Side.AWAY)
            ),
            "period": game.period if game.final else None,
            "broadcast": game.broadcast,
            "venue": game.venue,
            "city": game.city,
            "neutral_site": game.stage in (CupRound.SEMIFINALS, CupRound.CHAMPIONSHIP),
            "counts_in_standings": game.stage is not CupRound.CHAMPIONSHIP,
            "detail_available": False,
        }

    def games_list(self) -> dict[str, Any]:
        days: dict[dt.date, list[dict[str, Any]]] = {}
        for game in self.games:
            days.setdefault(game.date, []).append(self.game(game))
        counts = {
            stage.value: sum(1 for g in self.games if g.stage is stage)
            for stage in ROUNDS
        }
        return {
            "days": [{"date": day, "games": days[day]} for day in sorted(days)],
            "counts": {"all": len(self.games), **counts},
        }

    # Groups

    def row(self, row: CupTableRow) -> dict[str, Any]:
        try:
            streak = parse_streak(row.streak) if row.streak else None
            games_behind = division_games_behind(row.games_behind)
        except (TeamBuildError, StandingsBuildError) as error:
            raise CupBuildError(error.reason) from None
        overtime = (
            None
            if row.ot_wins is None or row.ot_losses is None
            else f"{row.ot_wins}-{row.ot_losses}"
        )
        return {
            "position": row.position or None,
            "team": self.team(row.code),
            "wins": row.wins,
            "losses": row.losses,
            "games_behind": games_behind,
            "differential": (
                None if row.differential is None else signed_per_game(row.differential)
            ),
            "total": (
                None
                if row.point_differential is None
                else signed_total(row.point_differential)
            ),
            "streak": streak,
            "points_for": None if row.points_for is None else int(row.points_for),
            "points_against": (
                None if row.points_against is None else int(row.points_against)
            ),
            "home": _record_text(row.home),
            "away": _record_text(row.road),
            "overtime": overtime,
            "tag": _tag(row),
        }

    def groups(self) -> list[dict[str, Any]]:
        group_games = _group_games_of(self.games)
        result = []
        for key in GROUP_IDS:
            conference, letter = key
            codes = list(self.sources.group_teams.get(key, ())) if self.drawn else []
            final = sum(
                1
                for game in group_games
                if game.final and game.home in codes and game.away in codes
            )
            result.append(
                {
                    "name": {"conference": conference, "letter": letter},
                    "teams": [self.team(code) for code in codes],
                    "rows": [self.row(r) for r in self.group_tables[key].rows],
                    "games_final": final,
                    "final": final == GROUP_GAMES,
                }
            )
        return result

    # Wild card and seeds

    def seeds(self, conference: Conference) -> dict[str, CupTableRow]:
        rows = self.conference_tables[conference].rows
        keys = ("1", "2", "3", "wild_card")
        return dict(zip(keys, rows, strict=False))

    def wild_card(self) -> list[dict[str, Any]]:
        tables = []
        for conference in CONFERENCES:
            rows = self.conference_tables[conference].rows[3:]
            tables.append(
                {
                    "conference": conference,
                    "rows": [
                        {
                            "rank": rank,
                            "team": self.team(row.code),
                            "group": self.group_of.get(row.code),
                            "wins": row.wins,
                            "losses": row.losses,
                            "total": (
                                None
                                if row.point_differential is None
                                else signed_total(row.point_differential)
                            ),
                            "points_for": (
                                None if row.points_for is None else int(row.points_for)
                            ),
                            "tag": _tag(row),
                        }
                        for rank, row in enumerate(rows, 1)
                    ],
                }
            )
        return tables

    # Bracket

    def place_games(self) -> dict[SlotId, _Game]:
        placed: dict[SlotId, _Game] = {}
        past_quarterfinals: dict[Conference, list[_Game]] = {}
        for game in self.games:
            if game.stage is CupRound.GROUP:
                continue
            if game.stage is CupRound.CHAMPIONSHIP:
                for code in (game.home, game.away):
                    self.conference_of(code)
                slot = SlotId.FINAL
            else:
                conferences = {
                    self.conference_of(game.home),
                    self.conference_of(game.away),
                }
                if len(conferences) != 1:
                    raise CupBuildError(f"game {game.id} mixes the conferences")
                conference = conferences.pop()
                prefix = conference.value
                if game.stage is CupRound.SEMIFINALS:
                    slot = SlotId(f"{prefix}-sf")
                elif self.sources.past:
                    past_quarterfinals.setdefault(conference, []).append(game)
                    continue
                else:
                    seeds = self.seeds(conference)
                    top = {
                        seeds[key].code for key in ("1", "wild_card") if key in seeds
                    }
                    number = 1 if top & {game.home, game.away} else 2
                    slot = SlotId(f"{prefix}-qf-{number}")
            if slot in placed:
                raise CupBuildError(f"two games in the slot {slot.value}")
            placed[slot] = game
        for conference, quarterfinals in past_quarterfinals.items():
            ordered = sorted(quarterfinals, key=lambda g: (g.start_time, g.id))
            for number, game in enumerate(ordered, start=1):
                slot = SlotId(f"{conference.value}-qf-{min(number, 2)}")
                if slot in placed:
                    raise CupBuildError(f"two games in the slot {slot.value}")
                placed[slot] = game
        return placed

    def bracket(self) -> list[dict[str, Any]]:
        placed = self.place_games()
        slots: dict[SlotId, dict[str, Any]] = {}

        def winner_team(slot: SlotId) -> str | None:
            game = placed.get(slot)
            return None if game is None else game.winner

        def side(
            label: dict[str, Any],
            rule: str,
            known: bool,
            code: str | None,
            projected: dict[str, Any] | None = None,
        ) -> dict[str, Any]:
            return {
                "label": {"seed": None, "quarterfinal": None, **label},
                "rule": rule,
                "known": known,
                "team": None if code is None else self.team(code),
                "projected": projected,
                "standing": None if code is None else self.standing(code),
            }

        def pick(
            game: _Game | None, top_code: str | None
        ) -> tuple[str | None, str | None]:
            """The (top, bottom) codes of a scheduled game."""
            if game is None:
                return None, None
            if top_code in (game.home, game.away):
                other = game.away if top_code == game.home else game.home
                return top_code, other
            return game.home, game.away

        group_final = self.final[CupRound.GROUP]

        def quarterfinal(conference: Conference, number: int) -> dict[str, Any]:
            slot = SlotId(f"{conference.value}-qf-{number}")
            seeds = self.seeds(conference)
            keys = ("1", "wild_card") if number == 1 else ("2", "3")
            labels: list[dict[str, Any]] = (
                [
                    {"key": "seed", "conference": conference, "seed": None},
                    {"key": "seed", "conference": conference, "seed": None},
                ]
                if self.sources.past
                else [
                    {"key": "seed", "conference": conference, "seed": 1},
                    {"key": "wild_card", "conference": conference},
                ]
                if number == 1
                else [
                    {"key": "seed", "conference": conference, "seed": 2},
                    {"key": "seed", "conference": conference, "seed": 3},
                ]
            )
            rules = (
                ("best_group_winner", "best_non_winner")
                if number == 1
                else ("second_best_group_winner", "third_best_group_winner")
            )
            game = placed.get(slot)
            top_row = seeds.get(keys[0])
            codes = pick(
                game,
                None if top_row is None or self.sources.past else top_row.code,
            )
            sides = []
            for index in range(2):
                row = seeds.get(keys[index])
                if game is not None:
                    code, projected = codes[index], None
                    known = self.sources.past or (group_final and row is not None)
                elif row is None:
                    code, projected, known = None, None, False
                elif group_final:
                    code, projected, known = row.code, None, True
                else:
                    code, known = None, False
                    projected = {
                        "team": self.team(row.code),
                        "wins": row.wins,
                        "losses": row.losses,
                    }
                sides.append(side(labels[index], rules[index], known, code, projected))
            return {
                "id": slot,
                "round": CupRound.QUARTERFINALS,
                "conference": conference,
                "top": sides[0],
                "bottom": sides[1],
                "game": None if game is None else self.game(game),
            }

        def semifinal(conference: Conference) -> dict[str, Any]:
            slot = SlotId(f"{conference.value}-sf")
            feeders = [SlotId(f"{conference.value}-qf-{n}") for n in (1, 2)]
            winners = [winner_team(feeder) for feeder in feeders]
            game = placed.get(slot)
            codes = pick(game, winners[0])
            sides = []
            for index in range(2):
                code = codes[index] if game is not None else winners[index]
                sides.append(
                    side(
                        {
                            "key": "quarterfinal_winner",
                            "conference": conference,
                            "quarterfinal": index + 1,
                        },
                        "quarterfinal_winner",
                        winners[index] is not None,
                        code,
                    )
                )
            return {
                "id": slot,
                "round": CupRound.SEMIFINALS,
                "conference": conference,
                "top": sides[0],
                "bottom": sides[1],
                "game": None if game is None else self.game(game),
            }

        def final() -> dict[str, Any]:
            feeders = [SlotId.EAST_SF, SlotId.WEST_SF]
            winners = [winner_team(feeder) for feeder in feeders]
            game = placed.get(SlotId.FINAL)
            if game is None:
                codes: tuple[str | None, str | None] = (None, None)
            else:
                east = next(
                    (
                        code
                        for code in (game.home, game.away)
                        if self.conference_of(code) is Conference.EAST
                    ),
                    None,
                )
                codes = pick(game, east)
            sides = []
            for index, conference in enumerate(CONFERENCES):
                code = codes[index] if game is not None else winners[index]
                sides.append(
                    side(
                        {"key": "semifinal_winner", "conference": conference},
                        "semifinal_winner",
                        winners[index] is not None,
                        code,
                    )
                )
            return {
                "id": SlotId.FINAL,
                "round": CupRound.CHAMPIONSHIP,
                "conference": None,
                "top": sides[0],
                "bottom": sides[1],
                "game": None if game is None else self.game(game),
            }

        for conference in CONFERENCES:
            slots[SlotId(f"{conference.value}-qf-1")] = quarterfinal(conference, 1)
            slots[SlotId(f"{conference.value}-qf-2")] = quarterfinal(conference, 2)
        for conference in CONFERENCES:
            slots[SlotId(f"{conference.value}-sf")] = semifinal(conference)
        slots[SlotId.FINAL] = final()
        return [slots[slot_id] for slot_id in SlotId]

    # Stages

    def stages(self, stage: CupStage) -> list[dict[str, Any]]:
        current = STAGE_INDEX[stage]
        entries = []
        for index, round_ in enumerate(ROUNDS):
            dates = [game.date for game in self.games if game.stage is round_]
            if index < current:
                status = StageStatus.COMPLETE
            elif index == current:
                status = StageStatus.IN_PROGRESS
            elif index == current + 1:
                status = StageStatus.NEXT
            else:
                status = StageStatus.UPCOMING
            entries.append(
                {
                    "stage": round_,
                    "status": status,
                    "first_date": min(dates) if dates else None,
                    "last_date": max(dates) if dates else None,
                }
            )
        return entries

    def build(self) -> CupFeed:
        has_rows = any(t.rows for t in self.group_tables.values()) or any(
            t.rows for t in self.conference_tables.values()
        )
        stage = _stage_of(self.games, has_rows, self.final)
        groups = self.groups()
        group_games = _group_games_of(self.games)
        champion: dict[str, Any] | None = None
        if stage is CupStage.COMPLETE:
            winner = next(
                (g.winner for g in self.games if g.stage is CupRound.CHAMPIONSHIP),
                None,
            )
            champion = None if winner is None else self.team(winner)
        try:
            return CupFeed.model_validate(
                {
                    "season": season_label(self.sources.season),
                    "drawn": self.drawn,
                    "stage": stage,
                    "first_game_date": (
                        min(game.date for game in group_games) if group_games else None
                    ),
                    "group_games_played": sum(g["games_final"] for g in groups),
                    "group_games_total": GROUP_GAMES_TOTAL,
                    "champion": champion,
                    "stages": self.stages(stage),
                    "groups": groups,
                    "wild_card": self.wild_card(),
                    "bracket": self.bracket(),
                    "games": self.games_list(),
                }
            )
        except ValidationError as error:
            location = ".".join(str(part) for part in error.errors()[0]["loc"])
            raise CupBuildError(
                f"invalid feed: {error.error_count()} errors, first at {location}"
            ) from None


def build_cup_feed(sources: CupSources) -> CupFeed:
    """Build the Cup feed; raise CupBuildError when it is not valid."""
    return _Builder(sources).build()


async def read_cup_sources(
    client: SourceClient,
    settings: Settings,
    season: int,
    *,
    fetch_group_teams: FetchGroupTeams,
    fetch_group_table: FetchGroupTable,
    fetch_conference_table: FetchConferenceTable,
    fetch_season_schedule: FetchSeasonSchedule,
    schedule_fresh: Callable[[str], Freshness] | None = None,
) -> CupSources:
    """Read the Cup sources of one season (its end year), or raise SourceError.
    A failed schedule is skipped only when every drawn team still has its 4
    group games and the group round is not decided."""
    keys = list(GROUP_IDS)
    teams, tables, conferences = await asyncio.gather(
        asyncio.gather(
            *(
                fetch_group_teams(client, season, conference, letter, settings)
                for conference, letter in keys
            )
        ),
        asyncio.gather(
            *(
                fetch_group_table(client, season, conference, letter, settings)
                for conference, letter in keys
            )
        ),
        asyncio.gather(
            *(
                fetch_conference_table(client, season, conference, settings)
                for conference in CONFERENCES
            )
        ),
    )
    results = await asyncio.gather(
        *(
            fetch_season_schedule(client, code, season, settings, playoffs=False)
            if schedule_fresh is None
            else fetch_season_schedule(
                client,
                code,
                season,
                settings,
                playoffs=False,
                fresh=schedule_fresh(code),
            )
            for code in CODES
        ),
        return_exceptions=True,
    )
    schedules: dict[str, SeasonSchedule] = {}
    failures: list[tuple[str, SourceError]] = []
    for code, result in zip(CODES, results, strict=True):
        if isinstance(result, SourceError):
            failures.append((code, result))
        elif isinstance(result, BaseException):
            raise result
        else:
            schedules[code] = result
    group_teams = dict(zip(keys, teams, strict=True))
    group_tables = dict(zip(keys, tables, strict=True))
    if failures and (
        not covers_the_group_games(
            {key: codes for key, codes in group_teams.items()}, schedules
        )
        or group_round_is_decided(group_tables, schedules)
    ):
        raise failures[0][1]
    return CupSources(
        season=season,
        group_teams=group_teams,
        group_tables=group_tables,
        conference_tables=dict(zip(CONFERENCES, conferences, strict=True)),
        schedules=schedules,
        failed_schedules=frozenset(code for code, _ in failures),
    )


def slot_accent(
    slot: BracketSlot, identities: Mapping[str, TeamIdentity]
) -> SlotAccent:
    """The resolved color of each side of a bracket slot. The smaller seed goes first
    in the pair rule; with equal or missing seeds, the home side of the game does;
    with no game, the top side does (ADR 0072)."""
    top = team_colors(slot.top.team, identities)
    bottom = team_colors(slot.bottom.team, identities)
    top_standing, bottom_standing = slot.top.standing, slot.bottom.standing
    top_seed = None if top_standing is None else top_standing.seed
    bottom_seed = None if bottom_standing is None else bottom_standing.seed
    if top_seed is not None and bottom_seed is not None and top_seed != bottom_seed:
        bottom_first = bottom_seed < top_seed
    elif slot.game is not None and slot.bottom.team is not None:
        bottom_first = slot.bottom.team.code != slot.game.away.code
    else:
        bottom_first = False
    if bottom_first:
        bottom_color, top_color = pair_colors(bottom, top)
    else:
        top_color, bottom_color = pair_colors(top, bottom)
    return SlotAccent(top=top_color, bottom=bottom_color)


def with_accents(feed: CupFeed, identities: Mapping[str, TeamIdentity]) -> CupFeed:
    """The feed with the resolved team colors of its bracket slots and champions,
    added when it is served (ADR 0072)."""
    return feed.model_copy(
        update={
            "bracket": [
                slot.model_copy(update={"accent": slot_accent(slot, identities)})
                for slot in feed.bracket
            ],
            "champion_accent": resolved_color(team_colors(feed.champion, identities)),
            "defending_champion_accent": resolved_color(
                team_colors(feed.defending_champion, identities)
            ),
        }
    )


class CupFeeds:
    def __init__(
        self,
        settings: Settings,
        store: StateStore,
        client: SourceClient,
        cache: FeedCache,
        games: GamesJob,
        stars: StarsJob,
        *,
        fetch_group_teams: FetchGroupTeams = cup.fetch_group_teams,
        fetch_group_table: FetchGroupTable = cup.fetch_group_table,
        fetch_conference_table: FetchConferenceTable = cup.fetch_conference_table,
        fetch_season_schedule: FetchSeasonSchedule = team_schedule.fetch_season_schedule,
        previous: PreviousCups | None = None,
    ) -> None:
        self._settings = settings
        self._store = store
        self._client = client
        self._previous = previous
        self._games = games
        self._stars = stars
        self._fetch_group_teams = fetch_group_teams
        self._fetch_group_table = fetch_group_table
        self._fetch_conference_table = fetch_conference_table
        self._fetch_season_schedule = fetch_season_schedule
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

    def stored(self) -> CupFeed | None:
        """The stored Cup feed, or none when missing or invalid."""
        body = read_by_id(self._settings.data_dir, KIND, FEED_ID)
        if body is None:
            return None
        try:
            return CupFeed.model_validate_json(body)
        except ValidationError:
            return None

    async def build(self, feed_id: str) -> CupFeed:
        season = self._stars.current_season()
        if season is None:
            raise CupBuildError("season not known yet")
        return await within_budget(
            ReadBudget(READ_BUDGET, stop_on_rate_limit=False),
            f"cup: {feed_id}",
            lambda: self._build(season),
        )

    def _schedule_fresh(self) -> Callable[[str], Freshness]:
        """A team with a game today in the games job's shown games keeps the
        schedule freshness of 1 hour; before the job's first run every team does."""
        shown = self._games.shown_games()
        if shown is None:
            return lambda code: team_schedule.FRESH_FOR
        today = eastern_date(self._client.clock())
        playing = {
            team.code
            for game in shown
            if eastern_date(game.start_time) == today
            for team in (game.home, game.away)
        }
        return lambda code: (
            team_schedule.FRESH_FOR if code in playing else SCHEDULE_FRESH
        )

    def depends_on(self, feed_id: str) -> tuple[str, str] | None:
        season = self._stars.current_season()
        if self._previous is None or season is None:
            return None
        return self._previous.previous_cup(season)

    async def _build(self, season: int) -> CupFeed:
        return with_defending_champion(
            build_cup_feed(
                await read_cup_sources(
                    self._client,
                    self._settings,
                    season,
                    fetch_group_teams=self._fetch_group_teams,
                    fetch_group_table=self._fetch_group_table,
                    fetch_conference_table=self._fetch_conference_table,
                    fetch_season_schedule=self._fetch_season_schedule,
                    schedule_fresh=self._schedule_fresh(),
                )
            ),
            None
            if self._previous is None
            else self._previous.defending_champion(season),
        )

    def final_times(
        self, feed: CupFeed, built_at: dt.datetime, now: dt.datetime
    ) -> list[dt.datetime]:
        """The final times of the Cup games that can expire a feed built at built_at."""
        ids = {game.id for game in self._games.final_games() if game.cup is not None}
        ids |= {game.id for day in feed.games.days for game in day.games}
        times = (self._store.final_time(game_id) for game_id in sorted(ids))
        return [time for time in times if time is not None]

    def is_fresh(self, feed: CupFeed, built_at: dt.datetime, now: dt.datetime) -> bool:
        if feed.stage is CupStage.COMPLETE:
            season = self._stars.current_season()
            if season is None or feed.season == season_label(season):
                return True
        return not feed_expired(built_at, now, self.final_times(feed, built_at, now))

    def serve_with(self, feed_id: str, feed: CupFeed) -> CupFeed:
        ids = {game.id for game in self._games.loaded_games()}
        data = feed.model_dump(by_alias=False)
        for day in data["games"]["days"]:
            for game in day["games"]:
                game["detail_available"] = game["id"] in ids
        for slot in data["bracket"]:
            if slot["game"] is not None:
                slot["game"]["detail_available"] = slot["game"]["id"] in ids
        return with_accents(CupFeed.model_validate(data), self._stars.team_identities())

    def keep(self, feed_id: str) -> bool:
        return feed_id == FEED_ID

    def kind(self) -> FeedKind[CupFeed]:
        return FeedKind(
            KIND,
            CupFeed,
            check=self.check,
            build=self.build,
            is_fresh=self.is_fresh,
            keep=self.keep,
            serve_with=self.serve_with,
            depends_on=self.depends_on,
        )
