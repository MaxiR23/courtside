# api/app/jobs/team_names.py
#
# Franchise names: the identities (name, city and code) a franchise had from the
# 1993-94 season to the current one, as runs. The pure builder merges the seasons
# it was given: consecutive read seasons with the same name, city and code are
# one run, a skipped season does not split a run, and the run that holds the
# current season is open (its end is null). A provider code becomes its standard
# code, else the source's own code stays (ADR 0025).
#
# TeamNamesFeeds is a stored, non-public feed kind of the on-demand cache (it has
# no route): the id is the lowercase team code, the list is stored at
# feeds/team-names/{code}.json, read once per team and kept for 7 days, and the
# team feeds of the current and of a past season depend on it, so a missing or
# stale list is built first. One season team read per season; a read that fails
# or finds no team object is skipped with a log line that carries the code and the
# season, never a URL. A team exists in a season when its object answers: isActive
# is never read (ADR 0053). A build fails and the stored list is kept (rule H) when
# the current season could not be read (its read failed, or it has no team
# object), since the current run could not be left open; earlier seasons stay
# skippable.
#
# season_identity and season_names answer the name and city a team had in a past
# season, always from the season team object and never from the stored runs;
# season_names also gives that season's code and whether the season's name, city or
# code differs from the current season's (ADR 0054). season_named puts them on a
# league side (ADR 0053); named_sides applies it to every side of a built feed.
#
# SEE: docs/api/team.md, docs/adr/0043-season-feeds-and-franchise-names.md,
# api/app/jobs/team_feed.py

import asyncio
import datetime as dt
import logging
from collections.abc import Awaitable, Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ValidationError

from app.feeds.calendar import FIRST_SEASON
from app.feeds.opponent import Opponent
from app.feeds.team import NameRun, TeamNames
from app.jobs.on_demand import FeedCache, FeedKind, IdStatus
from app.jobs.stars import StarsJob
from app.settings import Settings
from app.sources import season_team
from app.sources.http import SourceClient, SourceError
from app.sources.season_team import SeasonTeam
from app.sources.teams import TEAM_CODES
from app.storage.feeds import read_by_id
from app.storage.state import StateStore

KIND = "team-names"
NAMES_LIFETIME = dt.timedelta(days=7)
TEAM_IDS = frozenset(code.lower() for code in TEAM_CODES.values())

logger = logging.getLogger(__name__)

FetchSeasonTeam = Callable[
    [SourceClient, str, int, Settings], Awaitable[SeasonTeam | None]
]


@dataclass(frozen=True)
class SeasonIdentity:
    """A league team as named in one season (ADR 0053), with that season's code
    and whether it differs from today's name, city or code (ADR 0054)."""

    name: str
    city: str
    code: str
    historical: bool


def season_named[O: Opponent](side: O, names: Mapping[str, SeasonIdentity]) -> O:
    """The side with the name, city, season code and historical flag of its
    season, when it is a league side the names know; any other side as it is."""
    if side.guest or side.code is None or side.code not in names:
        return side
    identity = names[side.code]
    return side.model_copy(
        update={
            "name": identity.name,
            "city": identity.city,
            "season_code": identity.code,
            "historical": identity.historical,
        }
    )


def _sides(value: object) -> Iterable[Opponent]:
    """Every Opponent found in a value: models, nested models and lists."""
    if isinstance(value, Opponent):
        yield value
    elif isinstance(value, BaseModel):
        for name in type(value).model_fields:
            yield from _sides(getattr(value, name))
    elif isinstance(value, list):
        for item in value:
            yield from _sides(item)


def league_codes(model: BaseModel) -> list[str]:
    """The sorted distinct codes of every non-guest side in the model."""
    return sorted({side.code for side in _sides(model) if not side.guest and side.code})


def _renamed(value: Any, names: Mapping[str, SeasonIdentity]) -> Any:
    if isinstance(value, Opponent):
        named = season_named(value, names)
        return named.model_copy(
            update={
                name: _renamed(getattr(named, name), names)
                for name in type(named).model_fields
            }
        )
    if isinstance(value, BaseModel):
        return value.model_copy(
            update={
                name: _renamed(getattr(value, name), names)
                for name in type(value).model_fields
            }
        )
    if isinstance(value, list):
        return [_renamed(item, names) for item in value]
    return value


def named_sides[M: BaseModel](model: M, names: Mapping[str, SeasonIdentity]) -> M:
    """The model with season_named applied to every side in it, validated again."""
    renamed = _renamed(model, names)
    return type(model).model_validate(renamed.model_dump(by_alias=False))


class TeamNamesBuildError(Exception):
    """The current season of the team could not be read, so no names were built."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def build_name_runs(
    seasons: Sequence[tuple[int, SeasonTeam]], current_season: int
) -> list[NameRun]:
    """The runs of the seasons given, oldest first. `to` is null on the run that
    holds the current season."""
    runs: list[dict[str, object]] = []
    for season, found in sorted(seasons, key=lambda item: item[0]):
        code = TEAM_CODES.get(found.abbreviation, found.abbreviation)
        identity = (found.name, found.location, code)
        if runs and (runs[-1]["name"], runs[-1]["location"], runs[-1]["code"]) == (
            identity
        ):
            runs[-1]["to"] = season
            continue
        runs.append(
            {
                "from": season,
                "to": season,
                "name": found.name,
                "location": found.location,
                "code": code,
            }
        )
    for run in runs:
        if run["to"] == current_season:
            run["to"] = None
    return [NameRun.model_validate(run) for run in runs]


class TeamNamesFeeds:
    def __init__(
        self,
        settings: Settings,
        store: StateStore,
        client: SourceClient,
        cache: FeedCache,
        stars: StarsJob,
        *,
        fetch_season_team: FetchSeasonTeam = season_team.fetch_season_team,
    ) -> None:
        self._settings = settings
        self._store = store
        self._client = client
        self._stars = stars
        self._fetch_season_team = fetch_season_team
        cache.register(self.kind())

    def check(self, code: str) -> IdStatus:
        if code not in TEAM_IDS:
            return IdStatus.UNKNOWN
        if self._stars.current_season() is None:
            return IdStatus.NOT_READY
        return IdStatus.KNOWN

    async def _read(self, code: str, season: int) -> tuple[int, SeasonTeam] | None:
        try:
            found = await self._fetch_season_team(
                self._client, code.upper(), season, self._settings
            )
        except SourceError as error:
            logger.warning(
                "team names: %s season %d skipped: %s", code, season, error.reason
            )
            return None
        if found is None:
            logger.warning("team names: %s season %d skipped: no team", code, season)
            return None
        return season, found

    async def build(self, code: str) -> TeamNames:
        current = self._stars.current_season()
        if current is None:
            raise TeamNamesBuildError("current season is not known")
        read = await asyncio.gather(
            *(self._read(code, season) for season in range(FIRST_SEASON, current + 1))
        )
        found = [item for item in read if item is not None]
        if not any(season == current for season, _ in found):
            raise TeamNamesBuildError(
                f"current season of team {code} could not be read"
            )
        try:
            return TeamNames(runs=build_name_runs(found, current))
        except ValidationError as error:
            location = ".".join(str(part) for part in error.errors()[0]["loc"])
            raise TeamNamesBuildError(
                f"invalid names: {error.error_count()} errors, first at {location}"
            ) from None

    async def season_identity(self, code: str, season: int) -> tuple[str, str] | None:
        """The (name, city) a team had in a season, always from that season's team
        object (the source cache serves a repeat read), never from a stored
        franchise-names list. None when the season has no such team; a SourceError
        propagates."""
        found = await self._fetch_season_team(
            self._client, code.upper(), season, self._settings
        )
        return None if found is None else (found.name, found.location)

    async def season_names(
        self, codes: Iterable[str], season: int
    ) -> dict[str, SeasonIdentity]:
        """The identity of each distinct code in a season, without the codes that
        have no team that season. `historical` compares the season's name, city and
        code with the current season's; it is False when the current season has no
        object for the franchise."""
        distinct = sorted(set(codes))
        current = self._stars.current_season()

        async def read(code: str) -> SeasonIdentity | None:
            found = await self._fetch_season_team(
                self._client, code.upper(), season, self._settings
            )
            if found is None:
                return None
            shown = TEAM_CODES.get(found.abbreviation, found.abbreviation)
            historical = False
            if current is not None and current != season:
                today = await self._fetch_season_team(
                    self._client, code.upper(), current, self._settings
                )
                if today is not None:
                    historical = (found.name, found.location, shown) != (
                        today.name,
                        today.location,
                        TEAM_CODES.get(today.abbreviation, today.abbreviation),
                    )
            return SeasonIdentity(found.name, found.location, shown, historical)

        found = await asyncio.gather(*(read(code) for code in distinct))
        return {
            code: identity
            for code, identity in zip(distinct, found, strict=True)
            if identity is not None
        }

    async def name_sides[M: BaseModel](self, feed: M, season: int) -> M:
        """The feed with every league side named by its season (ADR 0054)."""
        return named_sides(feed, await self.season_names(league_codes(feed), season))

    def stored(self, code: str) -> list[NameRun] | None:
        body = read_by_id(self._settings.data_dir, KIND, code.lower())
        if body is None:
            return None
        try:
            return TeamNames.model_validate_json(body).runs
        except ValidationError:
            return None

    def is_fresh(
        self, feed: TeamNames, built_at: dt.datetime, now: dt.datetime
    ) -> bool:
        return now - built_at < NAMES_LIFETIME

    def keep(self, code: str) -> bool:
        return code in TEAM_IDS

    def kind(self) -> FeedKind[TeamNames]:
        return FeedKind(
            KIND,
            TeamNames,
            check=self.check,
            build=self.build,
            is_fresh=self.is_fresh,
            keep=self.keep,
        )
