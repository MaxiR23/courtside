# api/app/jobs/cup_team_marks.py
#
# The Cup mark of a team for the team feed (ADR 0066): its group and its Cup
# record. It belongs to the Cup section, builds no feed and reads no source. The
# Cup window of a season runs from the first Cup game (November 1 until the
# stored Cup feed knows it) to December 31 of the season's first calendar year;
# inside it, while the stored Cup feed is not complete, the team feed reads the
# six group tables itself. Otherwise the mark comes from the stored Cup feed,
# and a missing or other-season feed gives none. The core team feed receives it
# as an injected provider and imports no section.
#
# SEE: docs/api/team.md, docs/adr/0035-playoffs-marks-in-core-feeds.md, docs/adr/0066-cut-read-amplification-of-on-demand-builds.md

import datetime as dt

from app.feeds.cup import CupFeed, CupStage
from app.feeds.team import TeamCup
from app.jobs.cup_feed import CupFeeds
from app.jobs.team_feed import season_label


def cup_window_open(season: int, today: dt.date, stored: CupFeed | None) -> bool:
    """Whether today is inside the Cup window of the season (its end year)."""
    start_year = season - 1
    start = (
        stored.first_game_date
        if stored is not None and stored.first_game_date is not None
        else dt.date(start_year, 11, 1)
    )
    return start <= today <= dt.date(start_year, 12, 31)


def team_mark(team: str, cup: CupFeed) -> TeamCup | None:
    """The group and record of the team in the Cup feed, or None without a row."""
    for group in cup.groups:
        for row in group.rows:
            if row.team.code == team:
                return TeamCup(group=group.name, wins=row.wins, losses=row.losses)
    return None


class CupTeamMarks:
    def __init__(self, cup: CupFeeds) -> None:
        self._cup = cup

    def _season_feed(self, season: int) -> CupFeed | None:
        feed = self._cup.stored()
        return (
            feed if feed is not None and feed.season == season_label(season) else None
        )

    def reads_tables(self, season: int, today: dt.date) -> bool:
        feed = self._season_feed(season)
        return cup_window_open(season, today, feed) and (
            feed is None or feed.stage is not CupStage.COMPLETE
        )

    def stored_mark(self, team: str, season: int) -> TeamCup | None:
        feed = self._season_feed(season)
        return None if feed is None else team_mark(team, feed)
