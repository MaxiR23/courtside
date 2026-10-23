# api/app/feeds/playoffs.py
#
# Feed models for the playoffs feed: the single source of truth for its shape. The
# JSON Schema and the TypeScript types are generated from these models. The feed
# has the state of the postseason, the five stages with their dates and status,
# the picture tables (seeds 1 to 10 of each conference), the play-in (three games
# per conference, null for a season without one), the bracket of 15 series, the
# champion block when the Finals series is complete, the postseason leaders and
# the season awards. Labels are
# keys and parts, never prose: the page writes the words. Every team is an
# Opponent with its colors. The stage status is this feed's own enum.
#
# SEE: docs/api/playoffs.md, docs/adr/0032-playoffs-feed.md

import datetime as dt
from enum import StrEnum
from itertools import pairwise
from typing import Annotated, Literal

from pydantic import (
    Field,
    HttpUrl,
    NonNegativeInt,
    PositiveInt,
    model_validator,
)

from app.feeds.base import AwardCode
from app.feeds.games import (
    Conference,
    FeedModel,
    GameStatus,
    NonEmptyStr,
    PlayInGameKind,
    Score,
    SideCode,
    TeamCode,
    UtcDatetime,
)
from app.feeds.opponent import Opponent, Side
from app.feeds.player import SeasonLabel
from app.feeds.standings import (
    Clinch,
    GamesBehindText,
    RecordText,
    StandingsColors,
    TotalDifferential,
)

# AwardCode lives in app.feeds.base; the other modules import it from here.
__all__ = ["AwardCode"]

Round = Annotated[int, Field(ge=1, le=4)]


class PlayoffsState(StrEnum):
    PICTURE = "picture"
    PLAYIN = "playin"
    PLAYOFFS = "playoffs"
    FINALS = "finals"
    COMPLETE = "complete"


class PlayoffStage(StrEnum):
    PLAYIN = "playin"
    ROUND_1 = "round_1"
    ROUND_2 = "round_2"
    ROUND_3 = "round_3"
    FINALS = "finals"


STAGES = list(PlayoffStage)


class PlayoffStageStatus(StrEnum):
    COMPLETE = "complete"
    IN_PROGRESS = "in_progress"
    NEXT = "next"
    UPCOMING = "upcoming"


class PlayoffStageEntry(FeedModel):
    stage: PlayoffStage
    status: PlayoffStageStatus
    first_date: dt.date | None
    last_date: dt.date | None

    @model_validator(mode="after")
    def _require_both_dates_or_none(self) -> PlayoffStageEntry:
        if (self.first_date is None) != (self.last_date is None):
            raise ValueError("a stage has both dates or none")
        return self


class DateSpan(FeedModel):
    first_date: dt.date
    last_date: dt.date

    @model_validator(mode="after")
    def _require_first_on_or_before_last(self) -> DateSpan:
        if self.first_date > self.last_date:
            raise ValueError("the first date is on or before the last date")
        return self


class PlayoffTeam(Opponent):
    """A league team of the postseason with its colors."""

    # Keeps the colors of its build, not the identity's (ADR 0068).
    colors: StandingsColors  # type: ignore[assignment]

    @model_validator(mode="after")
    def _require_a_league_team(self) -> PlayoffTeam:
        if self.guest:
            raise ValueError("a playoff team is a league team")
        return self


class PictureLine(StrEnum):
    PLAYOFFS = "playoffs"
    PLAYIN = "playin"


class PictureRow(FeedModel):
    seed: Annotated[int, Field(ge=1, le=15)] | None
    team: PlayoffTeam
    wins: NonNegativeInt | None
    losses: NonNegativeInt | None
    games_behind: GamesBehindText | None
    clinch: Clinch | None
    line: PictureLine | None


PLAYOFFS_LINE_ROW = 6
PLAYIN_LINE_ROW = 10


class PictureTable(FeedModel):
    conference: Conference
    rows: Annotated[list[PictureRow], Field(max_length=10)]

    @model_validator(mode="after")
    def _require_the_lines_after_rows_6_and_10(self) -> PictureTable:
        for number, row in enumerate(self.rows, start=1):
            expected = {
                PLAYOFFS_LINE_ROW: PictureLine.PLAYOFFS,
                PLAYIN_LINE_ROW: PictureLine.PLAYIN,
            }.get(number)
            if row.line != expected:
                raise ValueError("only rows 6 and 10 carry a line")
        return self


class PlayoffGame(FeedModel):
    id: NonEmptyStr
    date: dt.date
    start_time: UtcDatetime
    away: Opponent
    home: Opponent
    status: GameStatus
    score: Score | None
    winner: Side | None
    overtime: bool
    venue: NonEmptyStr | None
    broadcast: NonEmptyStr | None
    detail_available: bool

    @model_validator(mode="after")
    def _require_the_result_of_a_final_game(self) -> PlayoffGame:
        final = self.status is GameStatus.FINAL
        if self.winner is not None and not final:
            raise ValueError(f"a {self.status} game has no winner")
        if final and self.score is None:
            raise ValueError("a final game requires score")
        if self.overtime and self.status not in (GameStatus.LIVE, GameStatus.FINAL):
            raise ValueError(f"a {self.status} game has no overtime")
        return self


class SeriesGame(PlayoffGame):
    number: Annotated[int, Field(ge=1, le=7)]
    # Overtimes played: the period minus 4 from the 5th period, 0 in regulation;
    # null before the game, with no period and on a stored feed from before the
    # field.
    overtime_periods: NonNegativeInt | None = None

    @model_validator(mode="after")
    def _require_overtime_periods_of_a_played_game(self) -> SeriesGame:
        if self.overtime_periods is None:
            return self
        if self.status not in (GameStatus.LIVE, GameStatus.FINAL):
            raise ValueError(f"a {self.status} game has no overtime periods")
        if self.overtime != (self.overtime_periods > 0):
            raise ValueError("overtime is set exactly when overtimes were played")
        return self


class PlayInSlotKey(StrEnum):
    PLACE = "place"
    LOSER_OF = "loser_of"
    WINNER_OF = "winner_of"


class PlayInSlotLabel(FeedModel):
    key: PlayInSlotKey
    place: Annotated[int, Field(ge=7, le=10)] | None
    game: PlayInGameKind | None

    @model_validator(mode="after")
    def _require_the_parts_of_the_key(self) -> PlayInSlotLabel:
        if (self.place is not None) != (self.key is PlayInSlotKey.PLACE):
            raise ValueError("place is set exactly for the place key")
        if (self.game is not None) != (self.key is not PlayInSlotKey.PLACE):
            raise ValueError("game is set exactly for loser_of and winner_of")
        return self


class PlayInSlot(FeedModel):
    label: PlayInSlotLabel
    team: PlayoffTeam | None
    currently: PlayoffTeam | None

    @model_validator(mode="after")
    def _require_a_team_or_currently(self) -> PlayInSlot:
        if self.team is not None and self.currently is not None:
            raise ValueError("a slot has a team or a currently team, not both")
        return self


class PlayInOutcome(FeedModel):
    seed: Literal[7, 8] | None
    loser_out: bool


class PlayInGame(FeedModel):
    kind: PlayInGameKind
    top: PlayInSlot
    bottom: PlayInSlot
    game: PlayoffGame | None
    outcome: PlayInOutcome | None

    @model_validator(mode="after")
    def _require_the_outcome_of_a_decided_game(self) -> PlayInGame:
        decided = (
            self.game is not None
            and self.game.status is GameStatus.FINAL
            and self.game.winner is not None
        )
        if (self.outcome is not None) != decided:
            raise ValueError("the outcome is set exactly when the game is decided")
        return self


class PlayIn(FeedModel):
    conference: Conference
    games: Annotated[list[PlayInGame], Field(min_length=3, max_length=3)]

    @model_validator(mode="after")
    def _require_the_order_of_the_games(self) -> PlayIn:
        if [game.kind for game in self.games] != list(PlayInGameKind):
            raise ValueError("play-in games must follow the order of the kinds")
        return self


class SeriesId(StrEnum):
    EAST_R1_1 = "east-r1-1"
    EAST_R1_2 = "east-r1-2"
    EAST_R1_3 = "east-r1-3"
    EAST_R1_4 = "east-r1-4"
    EAST_R2_1 = "east-r2-1"
    EAST_R2_2 = "east-r2-2"
    EAST_R3 = "east-r3"
    FINALS = "finals"
    WEST_R3 = "west-r3"
    WEST_R2_1 = "west-r2-1"
    WEST_R2_2 = "west-r2-2"
    WEST_R1_1 = "west-r1-1"
    WEST_R1_2 = "west-r1-2"
    WEST_R1_3 = "west-r1-3"
    WEST_R1_4 = "west-r1-4"


def round_of_series(series_id: SeriesId) -> int:
    """The round of a series: 1 to 3 by its id, 4 for the Finals."""
    if series_id is SeriesId.FINALS:
        return 4
    return int(series_id.value.split("-")[1][1])


class SeriesLabelKey(StrEnum):
    SEED = "seed"
    PLAYIN_WINNER = "playin_winner"
    ROUND_1_WINNER = "round_1_winner"
    ROUND_2_WINNER = "round_2_winner"
    ROUND_3_WINNER = "round_3_winner"


class SeriesLabel(FeedModel):
    key: SeriesLabelKey
    conference: Conference
    seed: Annotated[int, Field(ge=1, le=8)] | None
    series: Annotated[int, Field(ge=1, le=4)] | None

    @model_validator(mode="after")
    def _require_the_parts_of_the_key(self) -> SeriesLabel:
        with_seed = self.key in (SeriesLabelKey.SEED, SeriesLabelKey.PLAYIN_WINNER)
        with_series = self.key in (
            SeriesLabelKey.ROUND_1_WINNER,
            SeriesLabelKey.ROUND_2_WINNER,
        )
        if (self.seed is not None) != with_seed:
            raise ValueError("seed is set exactly for seed and playin_winner")
        if (self.series is not None) != with_series:
            raise ValueError(
                "series is set exactly for round_1_winner and round_2_winner"
            )
        return self


class SeriesSide(FeedModel):
    label: SeriesLabel
    team: PlayoffTeam | None
    seed: Annotated[int, Field(ge=1, le=15)] | None
    wins: Annotated[int, Field(ge=0, le=4)] | None
    currently: PlayoffTeam | None

    @model_validator(mode="after")
    def _require_a_team_or_currently(self) -> SeriesSide:
        if self.team is not None and self.currently is not None:
            raise ValueError("a side has a team or a currently team, not both")
        return self

    @model_validator(mode="after")
    def _require_a_team_for_wins_and_seed(self) -> SeriesSide:
        if self.team is None and (self.wins is not None or self.seed is not None):
            raise ValueError("a side has wins and a seed only with a team")
        return self


class SeriesStatus(StrEnum):
    UPCOMING = "upcoming"
    IN_PROGRESS = "in_progress"
    COMPLETE = "complete"


class Series(FeedModel):
    id: SeriesId
    round: Round
    conference: Conference | None
    top: SeriesSide
    bottom: SeriesSide
    status: SeriesStatus
    summary: NonEmptyStr | None
    winner: TeamCode | None
    games: Annotated[list[SeriesGame], Field(max_length=7)]

    @model_validator(mode="after")
    def _require_no_conference_for_the_finals(self) -> Series:
        if (self.conference is None) != (self.id is SeriesId.FINALS):
            raise ValueError("only the finals has no conference")
        return self

    @model_validator(mode="after")
    def _require_the_round_of_the_id(self) -> Series:
        if self.round != round_of_series(self.id):
            raise ValueError("the round must match the series id")
        return self

    @model_validator(mode="after")
    def _require_the_winner_of_a_complete_series(self) -> Series:
        complete = self.status is SeriesStatus.COMPLETE
        if (self.winner is not None) != complete:
            raise ValueError("the winner is set exactly when the series is complete")
        if self.winner is not None:
            codes = {side.team.code for side in (self.top, self.bottom) if side.team}
            if self.winner not in codes:
                raise ValueError("the winner must be one of the sides")
        return self

    @model_validator(mode="after")
    def _require_the_wins_of_a_complete_series(self) -> Series:
        if self.status is SeriesStatus.COMPLETE and (
            self.top.wins is None or self.bottom.wins is None
        ):
            raise ValueError("a complete series has the wins of both sides")
        return self

    @model_validator(mode="after")
    def _require_the_games_in_start_order(self) -> Series:
        times = [game.start_time for game in self.games]
        if times != sorted(times):
            raise ValueError("games must be in start order")
        return self


class Champion(FeedModel):
    team: PlayoffTeam
    wins: Literal[4]
    losses: Annotated[int, Field(ge=0, le=3)]
    first_date: dt.date
    last_date: dt.date
    record: RecordText | None
    home: RecordText | None
    road: RecordText | None
    point_differential: TotalDifferential


class LeaderCategory(StrEnum):
    POINTS = "points"
    REBOUNDS = "rebounds"
    ASSISTS = "assists"
    STEALS = "steals"
    BLOCKS = "blocks"
    FIELD_GOAL_PCT = "field_goal_pct"
    THREES_MADE = "threes_made"
    DOUBLE_DOUBLES = "double_doubles"
    MINUTES = "minutes"


class PlayoffLeader(FeedModel):
    rank: PositiveInt
    player_id: NonEmptyStr
    name: NonEmptyStr
    photo_url: HttpUrl | None
    team_code: TeamCode
    # The team's abbreviation in this past season, from that season's team object
    # (ADR 0055). Null on a current feed.
    season_code: SideCode | None = None
    value: NonEmptyStr


class LeaderGroup(FeedModel):
    category: LeaderCategory
    leaders: Annotated[list[PlayoffLeader], Field(max_length=5)]

    @model_validator(mode="after")
    def _require_increasing_ranks(self) -> LeaderGroup:
        ranks = [leader.rank for leader in self.leaders]
        if any(a >= b for a, b in pairwise(ranks)):
            raise ValueError("ranks must strictly increase")
        return self


# The highest team number of each award that has teams.
TEAM_NUMBERS: dict[AwardCode, int] = {
    AwardCode.ALL_NBA: 3,
    AwardCode.ALL_ROOKIE: 2,
    AwardCode.ALL_DEFENSIVE: 2,
}


class AwardWinner(FeedModel):
    player_id: NonEmptyStr
    name: NonEmptyStr
    photo_url: HttpUrl | None
    team_code: TeamCode | None
    # The team's abbreviation in this past season, from that season's team object
    # (ADR 0055). Null on a current feed.
    season_code: SideCode | None = None


class Award(FeedModel):
    code: AwardCode
    team: Annotated[int, Field(ge=1, le=3)] | None
    winners: Annotated[list[AwardWinner], Field(min_length=1)]

    @model_validator(mode="after")
    def _require_the_team_number_of_a_team_award(self) -> Award:
        highest = TEAM_NUMBERS.get(self.code)
        if highest is None:
            if self.team is not None:
                raise ValueError("only a team award has a team number")
        elif self.team is None or self.team > highest:
            raise ValueError(f"a {self.code} award has a team from 1 to {highest}")
        return self


class PlayoffsFeed(FeedModel):
    season: SeasonLabel
    state: PlayoffsState
    postseason_dates: DateSpan
    current_round: Annotated[int, Field(ge=1, le=3)] | None
    finals_game: Annotated[int, Field(ge=1, le=7)] | None
    finals_summary: NonEmptyStr | None
    stages: Annotated[list[PlayoffStageEntry], Field(min_length=5, max_length=5)]
    picture: Annotated[list[PictureTable], Field(min_length=2, max_length=2)]
    play_in: Annotated[list[PlayIn], Field(min_length=2, max_length=2)] | None
    bracket: Annotated[list[Series], Field(min_length=15, max_length=15)]
    champion: Champion | None
    leaders: Annotated[list[LeaderGroup], Field(min_length=9, max_length=9)] | None
    awards: list[Award] | None
    # The rules version of a kept season feed (ADR 0053); null on a current feed
    # and on a stored feed from before the field.
    build_version: PositiveInt | None = None

    @model_validator(mode="after")
    def _require_the_champion_when_complete(self) -> PlayoffsFeed:
        if (self.champion is not None) != (self.state is PlayoffsState.COMPLETE):
            raise ValueError(
                "the champion is set exactly when the postseason is complete"
            )
        return self

    @model_validator(mode="after")
    def _require_the_round_in_the_playoffs(self) -> PlayoffsFeed:
        if (self.current_round is not None) != (self.state is PlayoffsState.PLAYOFFS):
            raise ValueError("the current round is set exactly in the playoffs")
        return self

    @model_validator(mode="after")
    def _require_the_finals_line_in_the_finals(self) -> PlayoffsFeed:
        in_finals = self.state in (PlayoffsState.FINALS, PlayoffsState.COMPLETE)
        if not in_finals and (
            self.finals_game is not None or self.finals_summary is not None
        ):
            raise ValueError("the finals game and summary need the finals")
        return self

    @model_validator(mode="after")
    def _require_the_order_of_the_lists(self) -> PlayoffsFeed:
        if [entry.stage for entry in self.stages] != STAGES:
            raise ValueError("stages must follow the order of the stages")
        east_west = [Conference.EAST, Conference.WEST]
        if [table.conference for table in self.picture] != east_west:
            raise ValueError("picture tables must be east then west")
        if (
            self.play_in is not None
            and [play_in.conference for play_in in self.play_in] != east_west
        ):
            raise ValueError("play-in must be east then west")
        if [series.id for series in self.bracket] != list(SeriesId):
            raise ValueError("bracket series must follow the order of the series ids")
        if self.leaders is not None and [
            group.category for group in self.leaders
        ] != list(LeaderCategory):
            raise ValueError("leaders must follow the order of the categories")
        return self
