# api/app/jobs/playoffs_titles.py
#
# The playoffs titles of the current season for the team feed (ADR 0035): the NBA
# title and the conference title of the team, read from the stored playoffs feed
# of the same season. It belongs to the playoffs section, builds no feed and
# reads no source: a missing or invalid stored feed gives no title. The core team
# feed receives it as an injected provider and imports no section.
#
# SEE: docs/api/team.md, docs/adr/0035-playoffs-marks-in-core-feeds.md

import datetime as dt

from app.feeds.playoffs import PlayoffsFeed, SeriesId, SeriesStatus
from app.feeds.team import TeamTitle, TitleKind
from app.jobs import playoffs_feed
from app.jobs.playoffs_feed import PlayoffsFeeds
from app.jobs.team_feed import season_label
from app.storage.state import StateStore

CONFERENCE_SERIES = (SeriesId.EAST_R3, SeriesId.WEST_R3)


def playoffs_titles(
    team: str, season: str, playoffs: PlayoffsFeed | None
) -> list[TeamTitle] | None:
    """The NBA and conference titles of the team in the season, in kind order, or None."""
    if playoffs is None or playoffs.season != season:
        return None
    titles: list[TeamTitle] = []
    champion = playoffs.champion
    if champion is not None and champion.team.code == team:
        titles.append(
            TeamTitle(
                kind=TitleKind.NBA_CHAMPIONS,
                year=champion.last_date.year,
                conference=None,
            )
        )
    for series in playoffs.bracket:
        if (
            series.id in CONFERENCE_SERIES
            and series.status is SeriesStatus.COMPLETE
            and series.winner == team
            and series.conference is not None
        ):
            titles.append(
                TeamTitle(
                    kind=TitleKind.CONFERENCE_CHAMPIONS,
                    year=None,
                    conference=series.conference,
                )
            )
    return titles or None


class PlayoffsTitles:
    def __init__(self, store: StateStore, playoffs: PlayoffsFeeds) -> None:
        self._store = store
        self._playoffs = playoffs

    def titles(self, team: str, season: int) -> list[TeamTitle] | None:
        return playoffs_titles(team, season_label(season), self._playoffs.stored())

    def rebuilt_after(self, built_at: dt.datetime) -> bool:
        """True when the stored playoffs feed was built after built_at."""
        build = self._store.feed_build(playoffs_feed.KIND, playoffs_feed.FEED_ID)
        return (
            build is not None
            and build.last_build is not None
            and build.last_build > built_at
        )
