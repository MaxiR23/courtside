# api/app/sources/all_star_mark.py
#
# The All-Star mark of a scoreboard game (ADR 0038): its round and whether it is
# the Championship, read from the first note, and the test that tells an All-Star
# game from the season type and the competition type. It is the All-Star
# section's piece of the scoreboard adapter, and removing the section removes it.
# It also holds the note parsing the All-Star feed reads, so both read a note the
# same way. It owns no source URL and never raises: input it cannot read gives no
# mark.
#
# SEE: docs/api/games.md, docs/adr/0038-all-star-marks-in-core-feeds.md

import re

from app.feeds.games import GameAllStar
from app.sources.season_types import REGULAR_SEASON

COMPETITION_TYPE = "ALLSTAR"
CHAMPIONSHIP = "Championship"
NOTE = re.compile(
    r"^NBA All-Star - (?P<round>.+?)"
    r"(?: (?P<suffix>First team to \d+ points wins.*))?$"
)


def parse_note(note: str | None) -> tuple[str | None, str | None]:
    """The round label and the format suffix of a game note, or none of them."""
    found = NOTE.match(note) if note else None
    if found is None:
        return None, None
    return found.group("round"), found.group("suffix")


def is_all_star(season_type: int | None, competition_type: str | None) -> bool:
    """Whether a game is the All-Star game: a regular season game whose
    competition type is ALLSTAR."""
    return season_type == REGULAR_SEASON and competition_type == COMPETITION_TYPE


def all_star_mark(note: str | None) -> GameAllStar | None:
    """The mark of an All-Star game from its note, or None when the note is not
    an All-Star note."""
    label, _ = parse_note(note)
    if label is None:
        return None
    return GameAllStar(round_label=label, championship=label == CHAMPIONSHIP)
