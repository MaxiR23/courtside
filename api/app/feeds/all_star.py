# api/app/feeds/all_star.py
#
# Feed models for the All-Star feed: the single source of truth for its shape.
# The JSON Schema and the TypeScript types are generated from these models. The
# feed has the current edition (date, venue, format line, the teams with their
# placement and roster tiles, and the games with their box scores, team
# statistics, leaders and Top 5), the MVP with his game lines and day totals, and
# the recap of the previous edition. The number of teams and rounds changes every
# year: the feed is a list of games with a round label and N teams, never a fixed
# bracket. The previous edition is also carried whole, with its MVP, as its after
# view. The edition also carries its counts, its default game and its next game, a
# live game its leading side, a box score its top scorers and a team its result
# rows, so the page counts and compares nothing. Labels are keys and parts, never prose: the page writes the words. The
# format line is the one text, because the page shows it as sent. Each edition
# and the recap carry the edition video, added when served.
#
# SEE: docs/api/all-star.md, docs/adr/0036-all-star-feed.md,
# docs/adr/0048-highlights-backfill-and-edition-video.md

import datetime as dt
from enum import StrEnum
from itertools import pairwise
from typing import Annotated

from pydantic import (
    Field,
    HttpUrl,
    NonNegativeFloat,
    NonNegativeInt,
    PositiveInt,
    model_validator,
)

from app.feeds.game_detail import BoxScorePlayer, BoxScoreTotals, GameResult, Venue
from app.feeds.games import (
    FeedModel,
    GameStatus,
    Highlight,
    Leaders,
    NonEmptyStr,
    Score,
    TeamCode,
    UtcDatetime,
)
from app.feeds.opponent import Opponent, Side
from app.feeds.standings import StandingsColors

MAX_TOP5 = 5


class AllStarState(StrEnum):
    BEFORE = "before"
    LIVE = "live"
    AFTER = "after"


class PlacementKind(StrEnum):
    CHAMPION = "champion"
    RUNNER_UP = "runner_up"
    ELIMINATED = "eliminated"
    SO_FAR = "so_far"
    YET_TO_PLAY = "yet_to_play"


class Placement(FeedModel):
    kind: PlacementKind
    round_label: NonEmptyStr | None

    @model_validator(mode="after")
    def _require_a_round_label_of_an_eliminated_team(self) -> Placement:
        if (self.round_label is not None) != (self.kind is PlacementKind.ELIMINATED):
            raise ValueError("only an eliminated placement has a round label")
        return self


class LeagueTeam(FeedModel):
    """The league team of a player, by its standard code, with its colors."""

    code: TeamCode
    colors: StandingsColors


class BroadcastKind(StrEnum):
    TV = "tv"
    STREAMING = "streaming"


class Broadcast(FeedModel):
    name: NonEmptyStr
    kind: BroadcastKind


class AllStarBoxPlayer(BoxScorePlayer):
    jersey: NonEmptyStr | None
    position: NonEmptyStr | None
    league_team: LeagueTeam | None
    top_points: bool


class AllStarTeamBox(FeedModel):
    players: list[AllStarBoxPlayer]
    totals: BoxScoreTotals

    @model_validator(mode="after")
    def _require_top_points_on_the_highest_points(self) -> AllStarTeamBox:
        top = max((p.points for p in self.players), default=0)
        if any(p.top_points != (top > 0 and p.points == top) for p in self.players):
            raise ValueError(
                "topPoints marks every player with the team's highest points"
            )
        return self


class AllStarBoxScore(FeedModel):
    away: AllStarTeamBox
    home: AllStarTeamBox


class TeamStatKind(StrEnum):
    FIELD_GOAL_PCT = "field_goal_pct"
    THREE_POINTS_MADE = "three_points_made"
    REBOUNDS = "rebounds"
    ASSISTS = "assists"
    STEALS = "steals"
    BLOCKS = "blocks"


class AllStarTeamStat(FeedModel):
    stat: TeamStatKind
    away: NonNegativeFloat
    home: NonNegativeFloat
    better: Side | None

    @model_validator(mode="after")
    def _require_the_higher_value_as_better(self) -> AllStarTeamStat:
        if self.away == self.home:
            expected = None
        else:
            expected = Side.AWAY if self.away > self.home else Side.HOME
        if self.better != expected:
            raise ValueError("better is the higher value, and null on a tie")
        return self


class Top5Row(FeedModel):
    player_id: NonEmptyStr
    name: NonEmptyStr
    photo_url: HttpUrl | None
    side: Side
    league_team: LeagueTeam | None
    points: NonNegativeInt
    rebounds: NonNegativeInt
    assists: NonNegativeInt


def _top5_key(row: Top5Row) -> tuple[int, int]:
    return (row.points, row.rebounds + row.assists)


class AllStarGame(FeedModel):
    id: NonEmptyStr
    start_time: UtcDatetime
    status: GameStatus
    status_text: NonEmptyStr | None
    clock: NonEmptyStr | None
    period: PositiveInt | None
    score: Score | None
    overtime: bool
    winner: Side | None
    leading: Side | None
    attendance: NonNegativeInt | None
    broadcasts: list[Broadcast]
    round_label: NonEmptyStr | None
    championship: bool
    is_next: bool
    away: Opponent | None
    home: Opponent | None
    to_be_determined: bool
    box_score: AllStarBoxScore | None
    team_stats: list[AllStarTeamStat] | None
    leaders: Leaders | None
    top5: Annotated[list[Top5Row], Field(max_length=MAX_TOP5)]
    highlights: list[Highlight] | None

    @model_validator(mode="after")
    def _require_to_be_determined_exactly_when_a_side_is_missing(self) -> AllStarGame:
        missing = self.away is None or self.home is None
        if self.to_be_determined != missing:
            raise ValueError("toBeDetermined is true exactly when a side is null")
        return self

    @model_validator(mode="after")
    def _require_sides_and_score_of_a_game_in_play(self) -> AllStarGame:
        if self.status in (GameStatus.LIVE, GameStatus.FINAL) and (
            self.to_be_determined or self.score is None
        ):
            raise ValueError("a live or final game has both sides and a score")
        return self

    @model_validator(mode="after")
    def _require_the_winner_of_a_final_game(self) -> AllStarGame:
        expected: Side | None = None
        if (
            self.status is GameStatus.FINAL
            and self.score is not None
            and self.score.away != self.score.home
        ):
            expected = Side.AWAY if self.score.away > self.score.home else Side.HOME
        if self.winner != expected:
            raise ValueError(
                "the winner is the side with the higher score of a final game"
            )
        return self

    @model_validator(mode="after")
    def _require_the_leading_side_of_a_live_game(self) -> AllStarGame:
        expected: Side | None = None
        if (
            self.status is GameStatus.LIVE
            and self.score is not None
            and self.score.away != self.score.home
        ):
            expected = Side.AWAY if self.score.away > self.score.home else Side.HOME
        if self.leading != expected:
            raise ValueError("leading is the side with the higher score of a live game")
        return self

    @model_validator(mode="after")
    def _require_a_next_game_not_in_play(self) -> AllStarGame:
        if self.is_next and self.status in (GameStatus.LIVE, GameStatus.FINAL):
            raise ValueError("a next game is neither live nor final")
        return self

    @model_validator(mode="after")
    def _require_overtime_only_in_play(self) -> AllStarGame:
        if self.overtime and self.status not in (GameStatus.LIVE, GameStatus.FINAL):
            raise ValueError("only a live or final game has overtime")
        return self

    @model_validator(mode="after")
    def _require_the_top5_in_order(self) -> AllStarGame:
        keys = [_top5_key(row) for row in self.top5]
        if any(a < b for a, b in pairwise(keys)):
            raise ValueError("top5 is sorted by points, then rebounds plus assists")
        return self

    @model_validator(mode="after")
    def _require_the_six_stats_in_order(self) -> AllStarGame:
        if self.team_stats is not None and [s.stat for s in self.team_stats] != list(
            TeamStatKind
        ):
            raise ValueError("team stats are the 6 stats in order")
        return self


class RosterTile(FeedModel):
    player_id: NonEmptyStr
    name: NonEmptyStr
    photo_url: HttpUrl | None
    league_team: LeagueTeam | None


class AllStarTeamResult(FeedModel):
    game_id: NonEmptyStr
    round_label: NonEmptyStr | None
    result: GameResult
    team_score: NonNegativeInt
    opponent_score: NonNegativeInt
    opponent: Opponent
    overtime: bool

    @model_validator(mode="after")
    def _require_the_result_of_the_scores(self) -> AllStarTeamResult:
        if self.team_score == self.opponent_score:
            raise ValueError("a result has a winner")
        won = self.team_score > self.opponent_score
        if (self.result is GameResult.WIN) != won:
            raise ValueError("the result is a win exactly when the team scored more")
        return self


class AllStarTeam(FeedModel):
    team: Opponent
    wins: NonNegativeInt
    losses: NonNegativeInt
    results: list[AllStarTeamResult]
    placement: Placement
    roster: list[RosterTile]

    @model_validator(mode="after")
    def _require_a_record_of_the_results(self) -> AllStarTeam:
        wins = sum(r.result is GameResult.WIN for r in self.results)
        if (self.wins, self.losses) != (wins, len(self.results) - wins):
            raise ValueError("wins and losses are the numbers of win and loss results")
        return self


class AllStarCounts(FeedModel):
    games: NonNegativeInt
    teams: NonNegativeInt
    final: NonNegativeInt
    live: NonNegativeInt

    @model_validator(mode="after")
    def _require_final_and_live_within_the_games(self) -> AllStarCounts:
        if self.final + self.live > self.games:
            raise ValueError("final and live games are within the games")
        return self


class AllStarEdition(FeedModel):
    date: dt.date | None
    venue: Venue | None
    format_line: NonEmptyStr | None
    teams: list[AllStarTeam]
    games: list[AllStarGame]
    counts: AllStarCounts
    default_game_id: NonEmptyStr | None
    edition_highlight: Highlight | None = None

    @model_validator(mode="after")
    def _require_at_most_one_champion_and_runner_up(self) -> AllStarEdition:
        for kind in (PlacementKind.CHAMPION, PlacementKind.RUNNER_UP):
            if sum(team.placement.kind is kind for team in self.teams) > 1:
                raise ValueError(f"at most one team is the {kind}")
        return self

    @model_validator(mode="after")
    def _require_the_counts_of_the_lists(self) -> AllStarEdition:
        counts = self.counts
        final = sum(g.status is GameStatus.FINAL for g in self.games)
        live = sum(g.status is GameStatus.LIVE for g in self.games)
        if (counts.games, counts.teams, counts.final, counts.live) != (
            len(self.games),
            len(self.teams),
            final,
            live,
        ):
            raise ValueError("counts are the sizes of the lists and the game statuses")
        return self

    @model_validator(mode="after")
    def _require_a_default_game_of_the_list(self) -> AllStarEdition:
        ids = [g.id for g in self.games]
        if self.default_game_id is None:
            if ids:
                raise ValueError("a default game is required when there are games")
        elif self.default_game_id not in ids:
            raise ValueError("the default game must be the id of a game")
        return self

    @model_validator(mode="after")
    def _require_one_next_game_at_most(self) -> AllStarEdition:
        if sum(g.is_next for g in self.games) > 1:
            raise ValueError("at most one game is the next game")
        return self


class MvpLine(FeedModel):
    game_id: NonEmptyStr
    round_label: NonEmptyStr | None
    result: GameResult
    team_score: NonNegativeInt
    opponent_score: NonNegativeInt
    opponent: Opponent
    points: NonNegativeInt
    rebounds: NonNegativeInt
    assists: NonNegativeInt


class MvpTotals(FeedModel):
    games: PositiveInt
    points: NonNegativeInt
    rebounds: NonNegativeInt
    assists: NonNegativeInt


class AllStarMvp(FeedModel):
    player_id: NonEmptyStr
    name: NonEmptyStr
    photo_url: HttpUrl | None
    jersey: NonEmptyStr | None
    league_team: LeagueTeam | None
    lines: Annotated[list[MvpLine], Field(min_length=1)]
    totals: MvpTotals

    @model_validator(mode="after")
    def _require_totals_that_are_the_sums_of_the_lines(self) -> AllStarMvp:
        totals = self.totals
        sums = (
            len(self.lines),
            sum(line.points for line in self.lines),
            sum(line.rebounds for line in self.lines),
            sum(line.assists for line in self.lines),
        )
        if (totals.games, totals.points, totals.rebounds, totals.assists) != sums:
            raise ValueError("totals are the sums of the lines")
        return self


class AllStarResult(FeedModel):
    game_id: NonEmptyStr
    away: Opponent
    home: Opponent
    score: Score
    winner: Side
    overtime: bool

    @model_validator(mode="after")
    def _require_the_winner_to_be_the_higher_score(self) -> AllStarResult:
        if self.score.away == self.score.home:
            raise ValueError("a result has a winner")
        expected = Side.AWAY if self.score.away > self.score.home else Side.HOME
        if self.winner != expected:
            raise ValueError("the winner is the side with the higher score")
        return self


class AllStarRecap(FeedModel):
    year: PositiveInt
    date: dt.date
    venue: Venue | None
    championship: AllStarResult
    mvp: AllStarMvp | None
    edition_highlight: Highlight | None = None


class AllStarPreviousEdition(AllStarEdition):
    """The previous edition drawn as its after view: the edition and its MVP."""

    mvp: AllStarMvp | None

    @model_validator(mode="after")
    def _require_a_finished_edition(self) -> AllStarPreviousEdition:
        if self.date is None or not self.games:
            raise ValueError("a previous edition has a date and games")
        if any(g.status is not GameStatus.FINAL for g in self.games):
            raise ValueError("every game of a previous edition is final")
        return self


class AllStarFeed(FeedModel):
    year: PositiveInt
    state: AllStarState
    edition: AllStarEdition
    mvp: AllStarMvp | None
    previous: AllStarRecap | None
    previous_edition: AllStarPreviousEdition | None
    # The rules version of a kept season feed (ADR 0053); null on a current feed
    # and on a stored feed from before the field.
    build_version: PositiveInt | None = None

    @model_validator(mode="after")
    def _require_the_recap_of_a_previous_edition(self) -> AllStarFeed:
        edition = self.previous_edition
        if edition is not None and (
            self.previous is None or edition.date != self.previous.date
        ):
            raise ValueError("a previous edition has the recap with the same date")
        return self

    @model_validator(mode="after")
    def _require_the_games_of_the_state(self) -> AllStarFeed:
        games = self.edition.games
        in_play = [g for g in games if g.status in (GameStatus.LIVE, GameStatus.FINAL)]
        every_final = bool(games) and all(g.status is GameStatus.FINAL for g in games)
        if self.state is AllStarState.BEFORE:
            if games or self.edition.teams:
                raise ValueError("a before feed has no games and no teams")
            if self.mvp is not None:
                raise ValueError("a before feed has no MVP")
        elif self.state is AllStarState.AFTER:
            if not every_final:
                raise ValueError("an after feed has games and every game is final")
        elif not in_play or every_final:
            raise ValueError(
                "a live feed has a live or final game and not every game is final"
            )
        return self
