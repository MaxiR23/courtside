# api/app/sources/postseason_mark.py
#
# The postseason mark of a scoreboard game (ADR 0035): its stage, place in the
# bracket and stakes, read from the season type, the competition type, the first
# note and the series wins. It is the playoffs section's piece of the scoreboard
# adapter, and removing the section removes it. It also holds the note and round
# tables the playoffs feed reads, so both read a note the same way. It owns no
# source URL and never raises: input it cannot complete gives no mark.
#
# SEE: docs/api/games.md, docs/adr/0035-playoffs-marks-in-core-feeds.md

import re
from collections.abc import Mapping

from pydantic import ValidationError

from app.feeds.games import (
    Conference,
    GamePostseason,
    GameStatus,
    PlayInGameKind,
    PostseasonStage,
    Score,
    Stakes,
)
from app.sources.season_types import PLAY_IN, POSTSEASON

ROUNDS = {"RD16": 1, "QTR": 2, "SEMI": 3, "FINAL": 4}
PLAY_IN_KINDS = {
    "7th Place vs 8th Place": PlayInGameKind.SEVEN_EIGHT,
    "9th Place vs 10th Place": PlayInGameKind.NINE_TEN,
    "8th Seed Game": PlayInGameKind.EIGHTH_SEED,
}
PLAY_IN_NOTE = re.compile(
    r"^NBA Play-In - (East|West) - "
    r"(7th Place vs 8th Place|9th Place vs 10th Place|8th Seed Game)$"
)
_PLAY_IN_NOTE_ANY_CASE = re.compile(PLAY_IN_NOTE.pattern, re.IGNORECASE)
_PLAY_IN_KINDS_ANY_CASE = {key.casefold(): kind for key, kind in PLAY_IN_KINDS.items()}
GAME_NUMBER_NOTE = re.compile(r" - Game ([1-7])$", re.IGNORECASE)
_SERIES_CONFERENCE = re.compile(r"^(East|West) ", re.IGNORECASE)

WINS_TO_CLINCH = 4
GAME_7 = 7
FINALS_ROUND = 4


def stakes_of(
    number: int,
    wins: Mapping[str, int] | None,
    away: str | None,
    home: str | None,
    status: GameStatus,
    score: Score | None,
) -> Stakes | None:
    """The stakes a series game had at tip-off, or `clinched` once it clinched."""
    if number == GAME_7:
        return Stakes.GAME_7
    if wins is None or away is None or home is None:
        return None
    if away not in wins or home not in wins:
        return None
    entering = {away: wins[away], home: wins[home]}
    if status is GameStatus.FINAL:
        if score is None or score.away == score.home:
            return None
        winner = away if score.away > score.home else home
        if wins[winner] >= WINS_TO_CLINCH:
            return Stakes.CLINCHED
        entering[winner] -= 1
        if entering[winner] < 0:
            return None
    most, fewest = max(entering.values()), min(entering.values())
    if most == WINS_TO_CLINCH - 1 and fewest < WINS_TO_CLINCH - 1:
        return Stakes.CAN_CLINCH
    if most == WINS_TO_CLINCH - 1:
        return Stakes.ELIMINATION
    return None


def postseason_mark(
    *,
    season_type: int | None,
    competition_type: str | None,
    note: str | None,
    summary: str | None,
    wins: Mapping[str, int] | None,
    status: GameStatus,
    away: str | None,
    home: str | None,
    score: Score | None,
) -> GamePostseason | None:
    """The mark of a play-in or playoff game, or None when it cannot be read."""
    try:
        if season_type == PLAY_IN:
            return _play_in_mark(note)
        if season_type == POSTSEASON:
            return _series_mark(
                competition_type, note, summary, wins, status, away, home, score
            )
    except ValidationError:
        return None
    return None


def _play_in_mark(note: str | None) -> GamePostseason | None:
    match = _PLAY_IN_NOTE_ANY_CASE.match(note or "")
    if match is None:
        return None
    kind = _PLAY_IN_KINDS_ANY_CASE[match.group(2).casefold()]
    return GamePostseason(
        stage=PostseasonStage.PLAYIN,
        round=None,
        conference=Conference(match.group(1).lower()),
        number=None,
        summary=None,
        play_in=kind,
        stakes=None if kind is PlayInGameKind.SEVEN_EIGHT else Stakes.ELIMINATION,
    )


def _series_mark(
    competition_type: str | None,
    note: str | None,
    summary: str | None,
    wins: Mapping[str, int] | None,
    status: GameStatus,
    away: str | None,
    home: str | None,
    score: Score | None,
) -> GamePostseason | None:
    round_ = ROUNDS.get(competition_type or "")
    number = GAME_NUMBER_NOTE.search(note or "")
    if round_ is None or number is None:
        return None
    conference: Conference | None = None
    if round_ != FINALS_ROUND:
        side = _SERIES_CONFERENCE.match(note or "")
        if side is None:
            return None
        conference = Conference(side.group(1).lower())
    game = int(number.group(1))
    return GamePostseason(
        stage=PostseasonStage.FINALS
        if round_ == FINALS_ROUND
        else PostseasonStage.PLAYOFFS,
        round=round_,
        conference=conference,
        number=game,
        summary=summary or None,
        play_in=None,
        stakes=stakes_of(game, wins, away, home, status, score),
    )
