# api/app/feeds/team.py
#
# Feed models for the team feed: the single source of truth for its shape.
# The JSON Schema and the TypeScript types are generated from these models.
#
# SEE: docs/api/team.md, docs/design-profiles.md,
# docs/adr/0021-player-and-team-pages.md

import datetime as dt
from enum import StrEnum
from itertools import pairwise
from typing import Annotated, Literal

from pydantic import (
    Field,
    HttpUrl,
    NonNegativeFloat,
    NonNegativeInt,
    PositiveInt,
    StringConstraints,
    model_validator,
)

from app.feeds.game_detail import (
    Conference,
    GameResult,
    InjuryStatus,
    Record,
    Venue,
)
from app.feeds.games import (
    FeedModel,
    NonEmptyStr,
    Percentage,
    TeamCode,
    UtcDatetime,
)
from app.feeds.opponent import Opponent
from app.feeds.player import (
    GameKind,
    GameTag,
    JerseyNumber,
    NextGame,
    SeasonLabel,
)

HexColor = Annotated[str, StringConstraints(pattern=r"^#[0-9A-Fa-f]{6}$")]


class TeamColors(FeedModel):
    primary: HexColor
    secondary: HexColor | None


class Coach(FeedModel):
    name: NonEmptyStr
    seasons: NonNegativeInt | None = None


class SplitRecord(Record):
    win_pct: Percentage


class Streak(FeedModel):
    kind: GameResult
    count: PositiveInt


GroupLetter = Literal["A", "B", "C"]


class CupGroupName(FeedModel):
    """The label of a Cup group: its conference and its letter. The one shape of
    a group label in every feed that names a group."""

    conference: Conference
    letter: GroupLetter


class TeamCup(FeedModel):
    """The Cup mark of a team: its group and its Cup record."""

    group: CupGroupName
    wins: NonNegativeInt
    losses: NonNegativeInt


class PlayoffStatus(StrEnum):
    SEED = "seed"
    PLAYIN = "playin"
    OUT = "out"


SEED_RANGES: dict[PlayoffStatus, range] = {
    PlayoffStatus.SEED: range(1, 7),
    PlayoffStatus.PLAYIN: range(7, 11),
    PlayoffStatus.OUT: range(11, 16),
}


class PlayoffPosition(FeedModel):
    status: PlayoffStatus
    seed: Annotated[int, Field(ge=1, le=15)]

    @model_validator(mode="after")
    def _require_a_seed_of_the_status(self) -> PlayoffPosition:
        if self.seed not in SEED_RANGES[self.status]:
            raise ValueError("playoff seed must match its status")
        return self


class PointsTotal(FeedModel):
    per_game: NonNegativeFloat
    total: NonNegativeInt


class Differential(FeedModel):
    per_game: float
    total: int


class TeamRecord(SplitRecord):
    season: SeasonLabel
    home: SplitRecord | None
    away: SplitRecord | None
    last_ten: SplitRecord
    streak: Streak | None = None
    games_behind: NonNegativeFloat | None = None
    conference_rank: Annotated[int, Field(ge=1, le=15)]
    division_rank: Annotated[int, Field(ge=1, le=8)]
    playoff: PlayoffPosition | None = None
    points_for: PointsTotal | None
    points_against: PointsTotal | None
    differential: Differential | None


class TeamLeader(FeedModel):
    player_id: NonEmptyStr
    name: NonEmptyStr
    number: JerseyNumber | None = None
    # Null on a past season's leader whose box-score position is absent (ADR 0053).
    position: NonEmptyStr | None = None
    photo_url: HttpUrl | None = None
    value: NonNegativeFloat


class TeamLeaders(FeedModel):
    season: SeasonLabel
    points: TeamLeader | None = None
    rebounds: TeamLeader | None = None
    assists: TeamLeader | None = None


class RosterPlayer(FeedModel):
    id: NonEmptyStr
    name: NonEmptyStr
    number: JerseyNumber | None = None
    position: NonEmptyStr | None = None
    height: NonEmptyStr | None = None
    weight: PositiveInt | None = None
    age: NonNegativeInt | None = None
    birth_date: dt.date | None = None
    birthplace: NonEmptyStr | None = None
    college: NonEmptyStr | None = None
    experience: NonNegativeInt | None = None
    photo_url: HttpUrl | None = None
    status: Literal["active"] | InjuryStatus


class TeamInjury(FeedModel):
    player_id: NonEmptyStr
    name: NonEmptyStr
    number: JerseyNumber | None = None
    position: NonEmptyStr | None = None
    status: InjuryStatus
    comment: NonEmptyStr | None = None
    updated_at: UtcDatetime


class ScheduleGame(FeedModel):
    game_id: NonEmptyStr
    start_time: UtcDatetime
    opponent: Opponent
    is_home: bool
    kind: GameKind
    tag: GameTag | None = None
    result: GameResult | None = None
    team_score: NonNegativeInt | None = None
    opponent_score: NonNegativeInt | None = None
    broadcast: NonEmptyStr | None = None
    is_next: bool
    detail_available: bool


class ScheduleGroup(FeedModel):
    key: Annotated[str, StringConstraints(pattern=r"^(\d{4}-\d{2}|playoffs)$")]
    games: Annotated[list[ScheduleGame], Field(min_length=1)]


class Schedule(FeedModel):
    groups: Annotated[list[ScheduleGroup], Field(min_length=1)]
    default_group: NonEmptyStr

    @model_validator(mode="after")
    def _require_an_existing_default_group(self) -> Schedule:
        if self.default_group not in [group.key for group in self.groups]:
            raise ValueError("default group must be the key of a group")
        return self

    @model_validator(mode="after")
    def _require_one_next_game_at_most(self) -> Schedule:
        flagged = sum(game.is_next for group in self.groups for game in group.games)
        if flagged > 1:
            raise ValueError("at most one schedule game is the next game")
        return self


class TitleKind(StrEnum):
    NBA_CHAMPIONS = "nba_champions"
    NBA_CUP_CHAMPIONS = "nba_cup_champions"
    CONFERENCE_CHAMPIONS = "conference_champions"


class TeamTitle(FeedModel):
    """A title the team won in the current season."""

    kind: TitleKind
    year: Annotated[int, Field(ge=1946)] | None
    conference: Conference | None

    @model_validator(mode="after")
    def _require_fields_of_kind(self) -> TeamTitle:
        is_conference = self.kind is TitleKind.CONFERENCE_CHAMPIONS
        if (self.year is None) != is_conference:
            raise ValueError("year is set exactly for a championship title")
        if (self.conference is not None) != is_conference:
            raise ValueError("conference is set exactly for a conference title")
        return self


class NameRun(FeedModel):
    """One identity of the franchise: its name, city and code from one season to
    another. `to` is null on the run that holds the current season."""

    from_: Annotated[int, Field(ge=1994, alias="from")]
    to: int | None
    name: NonEmptyStr
    location: NonEmptyStr
    # A historical code may be any text, as a guest side's (ADR 0025).
    code: NonEmptyStr

    @model_validator(mode="after")
    def _require_to_not_before_from(self) -> NameRun:
        if self.to is not None and self.to < self.from_:
            raise ValueError("a run ends in or after the season it starts")
        return self


class TeamNames(FeedModel):
    """The stored names of one franchise (ADR 0043). The internal kind of the
    names, not a public feed."""

    runs: list[NameRun]
    # The rules version of the stored list (ADR 0053, ADR 0055); null on a list
    # from before the field.
    build_version: PositiveInt | None = None
    # False when the current season could not be read; such a list is fresh for
    # RETRY_AFTER only (ADR 0064).
    complete: bool = True
    # The past seasons whose read failed; the next re-read reads them again
    # (ADR 0065).
    missing: list[int] = Field(default_factory=list)


def _roster_order(number: str | None) -> tuple[bool, int]:
    return (number is None, int(number or 0))


class TeamFeed(FeedModel):
    code: TeamCode
    city: NonEmptyStr
    name: NonEmptyStr
    conference: Conference
    division: NonEmptyStr
    colors: TeamColors | None
    arena: Venue | None
    coach: Coach | None = None
    season: SeasonLabel
    record: TeamRecord
    leaders: TeamLeaders | None
    roster: list[RosterPlayer] | None
    injuries: list[TeamInjury] | None
    next_game: NextGame | None = None
    schedule: Schedule | None = None
    cup: TeamCup | None = None
    titles: Annotated[list[TeamTitle], Field(min_length=1, max_length=3)] | None = None
    # The franchise names, oldest first. The default reads a stored feed from
    # before the field.
    names: list[NameRun] = Field(default_factory=list)
    # The rules version of a kept season feed (ADR 0053); null on a current feed
    # and on a stored feed from before the field.
    build_version: PositiveInt | None = None
    # The abbreviation the team had in the season on show and whether that season's
    # name, city or abbreviation differs from today's (ADR 0054). Null and false on
    # a current feed and on a stored feed from before the fields.
    season_code: NonEmptyStr | None = None
    historical: bool = False

    @model_validator(mode="after")
    def _require_a_season_code_of_a_historical_team(self) -> TeamFeed:
        if self.historical and self.season_code is None:
            raise ValueError("a historical team has a season code")
        return self

    @model_validator(mode="after")
    def _require_the_blocks_of_the_current_season(self) -> TeamFeed:
        if (
            self.injuries is None
            or self.colors is None
            or self.leaders is None
            or self.roster is None
        ):
            raise ValueError(
                "the current season has injuries, colors, leaders and a roster"
            )
        return self

    @model_validator(mode="after")
    def _require_names_oldest_first(self) -> TeamFeed:
        for run, later in pairwise(self.names):
            if later.from_ <= run.from_:
                raise ValueError("names must be listed oldest first")
            if run.to is None or later.from_ <= run.to:
                raise ValueError(
                    "only the last name run may be open, and runs do not overlap"
                )
        return self

    @model_validator(mode="after")
    def _require_roster_by_number(self) -> TeamFeed:
        keys = [_roster_order(player.number) for player in self.roster or []]
        if any(later < earlier for earlier, later in pairwise(keys)):
            raise ValueError("roster must be ordered by number, unnumbered last")
        return self

    @model_validator(mode="after")
    def _require_unique_titles_in_kind_order(self) -> TeamFeed:
        if self.titles is None:
            return self
        order = list(TitleKind)
        positions = [order.index(title.kind) for title in self.titles]
        if any(later <= earlier for earlier, later in pairwise(positions)):
            raise ValueError("titles must be unique and in kind order")
        return self

    @model_validator(mode="after")
    def _require_the_next_game_of_the_schedule(self) -> TeamFeed:
        if self.schedule is None:
            return self
        flagged = [
            game.game_id
            for group in self.schedule.groups
            for game in group.games
            if game.is_next
        ]
        expected = [] if self.next_game is None else [self.next_game.game_id]
        if flagged != expected:
            raise ValueError("the schedule next game must be the next game")
        return self


# The team feed of a past season (ADR 0043): the team feed's shape, but no block
# that describes today. The record and schedule are the season's; the roster and
# leaders are null (ADR 0059) or, on a feed stored before, the season's.
class PastTeamFeed(TeamFeed):
    @model_validator(mode="after")
    def _require_the_blocks_of_the_current_season(self) -> PastTeamFeed:
        # Same name as TeamFeed's validator: it replaces that rule.
        blocks = (
            ("arena", self.arena),
            ("coach", self.coach),
            ("injuries", self.injuries),
            ("nextGame", self.next_game),
            ("cup", self.cup),
            ("titles", self.titles),
        )
        for name, block in blocks:
            if block is not None:
                raise ValueError(f"a past season has no {name}")
        return self
