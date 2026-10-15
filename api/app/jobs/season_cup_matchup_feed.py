# api/app/jobs/season_cup_matchup_feed.py
#
# Cup matchup feed of a past season (ADR 0045): the Cup matchup feed's shape for
# one bracket slot of a past season. The builder is a pure function from the slot
# of the stored season Cup feed and the two teams' season schedules to the feed;
# it reads no clock and no source. A side's team is as the Cup matchup feed picks
# it and its path is built as that feed builds it. The injuries and the roster
# are empty lists: rosters, depth charts and injuries are current season only, so
# none is read.
#
# SeasonCupMatchupFeeds is the feed kind of the on-demand cache: the id is
# {season}-{slot} (the season's end year and one of the 7 slot ids), the feed is
# stored at feeds/season-cup-matchups/{id}.json only when requested and the
# season Cup feed is built first when it is missing. The current season is
# resolved before the cache (target) to the current Cup matchup feed. A failed
# schedule read fails the build. A feed is built once and kept (rule G): it is
# never refreshed and never deleted.
#
# SEE: docs/api/cup-matchup.md, docs/adr/0045-season-competition-feeds.md,
# api/app/jobs/cup_matchup_feed.py

import asyncio
import datetime as dt
import re
from collections.abc import Mapping
from typing import Any

from pydantic import ValidationError

from app.feeds.cup import BracketSlot
from app.feeds.cup_matchup import CupMatchupFeed
from app.jobs import cup_matchup_feed, season_cup_feed
from app.jobs.cup_matchup_feed import (
    SLOT_IDS,
    FetchSeasonSchedule,
    MatchupBuildError,
    _code_of,
    _path,
    side_team,
)
from app.jobs.on_demand import FeedCache, FeedKind, IdStatus
from app.jobs.season_cup_feed import SeasonCupFeeds, past_cup_season_status
from app.jobs.stars import StarsJob
from app.jobs.team_feed import season_label
from app.settings import Settings
from app.sources import team_schedule
from app.sources.http import SourceClient
from app.sources.team_schedule import SeasonSchedule
from app.storage.state import StateStore

KIND = "season-cup-matchups"
_ID = re.compile(r"^([0-9]{4})-(.+)$")


def build_past_matchup_feed(
    season: str, slot: BracketSlot, schedules: Mapping[str, SeasonSchedule]
) -> CupMatchupFeed:
    """Build the matchup feed of one slot of a past season; raise
    MatchupBuildError when it is not valid."""
    sides: dict[str, dict[str, Any]] = {}
    for name, side in (("top", slot.top), ("bottom", slot.bottom)):
        team, projected = side_team(side)
        sides[name] = {
            "label": side.label,
            "rule": side.rule,
            "known": side.known,
            "projected": projected,
            "team": team,
            "details": None
            if team is None
            else {
                "path": _path(schedules[_code_of(team)]),
                "injuries": [],
                "roster": [],
            },
        }
    try:
        return CupMatchupFeed.model_validate(
            {
                "season": season,
                "id": slot.id,
                "round": slot.round,
                "conference": slot.conference,
                "game": slot.game,
                **sides,
            }
        )
    except ValidationError as error:
        location = ".".join(str(part) for part in error.errors()[0]["loc"])
        raise MatchupBuildError(
            f"invalid feed: {error.error_count()} errors, first at {location}"
        ) from None


class SeasonCupMatchupFeeds:
    def __init__(
        self,
        settings: Settings,
        store: StateStore,
        client: SourceClient,
        cache: FeedCache,
        stars: StarsJob,
        cups: SeasonCupFeeds,
        *,
        fetch_season_schedule: FetchSeasonSchedule = (
            team_schedule.fetch_season_schedule
        ),
    ) -> None:
        self._settings = settings
        self._store = store
        self._client = client
        self._stars = stars
        self._cups = cups
        self._fetch_season_schedule = fetch_season_schedule
        cache.register(self.kind())

    def check(self, feed_id: str) -> IdStatus:
        match = _ID.fullmatch(feed_id)
        if match is None or match[2] not in SLOT_IDS:
            return IdStatus.UNKNOWN
        return past_cup_season_status(match[1], self._stars.current_season())

    def target(self, season: str, slot_id: str) -> tuple[str, str]:
        """The (kind, id) a route season and slot map to: the current season is
        the current Cup matchup feed."""
        current = self._stars.current_season()
        if current is not None and season == str(current):
            return cup_matchup_feed.KIND, slot_id
        return KIND, f"{season}-{slot_id}"

    def depends_on(self, feed_id: str) -> tuple[str, str] | None:
        match = _ID.fullmatch(feed_id)
        return None if match is None else (season_cup_feed.KIND, match[1])

    async def build(self, feed_id: str) -> CupMatchupFeed:
        match = _ID.fullmatch(feed_id)
        if match is None:
            raise MatchupBuildError(f"{feed_id} is not a season and a slot")
        season, slot_id = match[1], match[2]
        cup = self._cups.stored(season)
        if cup is None:
            raise MatchupBuildError("season Cup feed is not stored")
        if cup.season != season_label(int(season)):
            raise MatchupBuildError("Cup feed is of another season")
        slot = next((s for s in cup.bracket if s.id.value == slot_id), None)
        if slot is None:
            raise MatchupBuildError(f"slot {slot_id} is not in the Cup feed")
        teams = [team for team, _ in (side_team(slot.top), side_team(slot.bottom))]
        codes = sorted({_code_of(team) for team in teams if team is not None})
        client, settings = self._client, self._settings
        found = await asyncio.gather(
            *(
                self._fetch_season_schedule(
                    client,
                    code,
                    int(season),
                    settings,
                    playoffs=False,
                    by_id_first=True,
                )
                for code in codes
            )
        )
        schedules = dict(zip(codes, found, strict=True))
        return build_past_matchup_feed(cup.season, slot, schedules)

    def is_fresh(
        self, feed: CupMatchupFeed, built_at: dt.datetime, now: dt.datetime
    ) -> bool:
        return True

    def keep(self, feed_id: str) -> bool:
        return True

    def kind(self) -> FeedKind[CupMatchupFeed]:
        return FeedKind(
            KIND,
            CupMatchupFeed,
            check=self.check,
            build=self.build,
            is_fresh=self.is_fresh,
            keep=self.keep,
            depends_on=self.depends_on,
        )
