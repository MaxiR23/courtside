# api/app/jobs/cup_titles.py
#
# The Cup title of the current season for the team feed (ADR 0035): the NBA Cup
# title of the team, read from the stored Cup feed of the same season. It belongs
# to the Cup section, builds no feed and reads no source: a missing or invalid
# stored feed gives no title. The core team feed receives it as an injected
# provider and imports no section.
#
# SEE: docs/api/team.md, docs/adr/0035-playoffs-marks-in-core-feeds.md

import datetime as dt

from app.feeds.cup import CupFeed, SlotId
from app.feeds.team import TeamTitle, TitleKind
from app.jobs import cup_feed
from app.jobs.cup_feed import CupFeeds
from app.jobs.team_feed import season_label
from app.storage.state import StateStore


def cup_titles(team: str, season: str, cup: CupFeed | None) -> list[TeamTitle] | None:
    """The Cup title of the team in the season, or None without one."""
    if cup is None or cup.season != season:
        return None
    final = next((slot for slot in cup.bracket if slot.id is SlotId.FINAL), None)
    if (
        cup.champion is None
        or cup.champion.code != team
        or final is None
        or final.game is None
    ):
        return None
    return [
        TeamTitle(
            kind=TitleKind.NBA_CUP_CHAMPIONS,
            year=final.game.date.year,
            conference=None,
        )
    ]


class CupTitles:
    def __init__(self, store: StateStore, cup: CupFeeds) -> None:
        self._store = store
        self._cup = cup

    def titles(self, team: str, season: int) -> list[TeamTitle] | None:
        return cup_titles(team, season_label(season), self._cup.stored())

    def rebuilt_after(self, built_at: dt.datetime) -> bool:
        """True when the stored Cup feed was built after built_at."""
        build = self._store.feed_build(cup_feed.KIND, cup_feed.FEED_ID)
        return (
            build is not None
            and build.last_build is not None
            and build.last_build > built_at
        )
