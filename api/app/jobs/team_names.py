# api/app/jobs/team_names.py
#
# Franchise names: the identities (name, city and code) a franchise had from the
# 1993-94 season to the current one, as runs. The pure builder merges the seasons
# it was given: consecutive read seasons with the same name, city and code are
# one run, a skipped season does not split a run, and the run that holds the
# current season is open (its end is null). A provider code becomes its standard
# code, else the source's own code stays (ADR 0025). The code of a historical
# identity (that season's name or city differs from today's) is the season team
# object's abbreviation as the source sends it, never mapped to a standard code;
# an identity whose name and city equal today's keeps the mapped standard code
# (ADR 0055).
#
# TeamNamesFeeds is a stored, non-public feed kind of the on-demand cache (it has
# no route): the id is the lowercase team code, the list is stored at
# feeds/team-names/{code}.json, read once per team and kept for 7 days or until
# SEASON_BUILD_VERSION changes (a list of another or no version is stale, ADR 0055),
# and the team feeds of the current and of a past season depend on it, so a
# missing or stale list is built first. One season team read per season; a read that fails
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
# league side (ADR 0053); named_sides applies it to every side of a built feed. It
# also sets the season code of the plain-code fields of a past feed (a playoff
# leader, an award winner, the Finals MVP, a finalist record, a roster average and a
# player's team), from their team_code or code (ADR 0055).
#
# payload_names answers the same identity from the names the payloads of the
# build itself give the teams (SeasonTeamName), with no read: the name and city
# are the payload's, "today" is the open run of the stored franchise-names list
# (no run: the code is the standard one and the identity is not historical).
# identities_of reads the identities a named feed already carries on its sides.
# The past playoffs, Finals and Cup builds use them (ADR 0058).
#
# with_career_codes sets, on every season row of a player feed, the code each of
# its teams had in that season, from the stored runs of the franchises: the run
# that holds the row's end year gives the code, and an entry is null when no run
# holds it (a season before 1994, or a franchise with no stored list). Both player
# kinds apply it when they serve, so a rebuilt names list reaches the next served
# feed with no player rebuild. career_runs reads the stored lists and starts, in
# the background, the build of a list that is missing or outdated; it never waits
# (ADR 0055).
#
# SEE: docs/api/team.md, docs/adr/0043-season-feeds-and-franchise-names.md,
# docs/adr/0055-past-season-reading-rules-and-versioned-stored-data.md,
# api/app/jobs/team_feed.py

import asyncio
import datetime as dt
import logging
from collections.abc import Awaitable, Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ValidationError

from app.feeds.calendar import FIRST_SEASON
from app.feeds.games import Team
from app.feeds.opponent import Opponent
from app.feeds.player import PlayerFeed, SeasonRow, SeasonSplit
from app.feeds.playoffs import AwardWinner, PlayoffLeader
from app.feeds.playoffs_finals import FinalistRecord, FinalsMvp, RosterAverages
from app.feeds.team import NameRun, TeamNames
from app.jobs.on_demand import (
    FeedCache,
    FeedKind,
    IdStatus,
    is_current_build,
    with_build_version,
)
from app.jobs.stars import StarsJob
from app.settings import Settings
from app.sources import season_team
from app.sources.http import SourceClient, SourceError
from app.sources.season_team import SeasonTeam
from app.sources.teams import TEAM_CODES, SeasonTeamName
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


# The models with a plain team code and a season_code beside it (ADR 0055).
_CODED = (
    PlayoffLeader,
    AwardWinner,
    FinalsMvp,
    FinalistRecord,
    RosterAverages,
    Team,
)


def _plain_code(model: BaseModel) -> str | None:
    """The team code of a coded model: its team_code, else its code."""
    code = getattr(model, "team_code", None) or getattr(model, "code", None)
    return None if code is None else str(code)


def run_code(runs: Sequence[NameRun], end_year: int) -> str | None:
    """The code of the run that holds the season (by its end year), or none."""
    for run in runs:
        if run.from_ <= end_year and (run.to is None or end_year <= run.to):
            return run.code
    return None


def career_team_codes(feed: PlayerFeed) -> list[str]:
    """The sorted distinct team codes of the season rows of a player feed."""
    return sorted(
        {
            code
            for split in (feed.seasons.regular, feed.seasons.playoffs)
            for rows in (split.per_game, split.totals)
            for row in rows
            for code in row.teams
        }
    )


def with_career_codes[F: PlayerFeed](
    feed: F, runs: Mapping[str, Sequence[NameRun]]
) -> F:
    """The feed with the season code of each team of every season row, from the
    runs of the franchises; validated again."""

    def coded(rows: list[SeasonRow]) -> list[SeasonRow]:
        return [
            row.model_copy(
                update={
                    "season_codes": [
                        run_code(runs.get(code, ()), int(row.season[:4]) + 1)
                        for code in row.teams
                    ]
                }
            )
            for row in rows
        ]

    def split(value: SeasonSplit) -> SeasonSplit:
        return value.model_copy(
            update={"per_game": coded(value.per_game), "totals": coded(value.totals)}
        )

    seasons = feed.seasons.model_copy(
        update={
            "regular": split(feed.seasons.regular),
            "playoffs": split(feed.seasons.playoffs),
        }
    )
    updated = feed.model_copy(update={"seasons": seasons})
    return type(feed).model_validate(updated.model_dump(by_alias=False))


def _season_code(found: SeasonTeam, today: SeasonTeam | None) -> str:
    """The code of a team's season identity (ADR 0055): the source's own
    abbreviation when the name or city differs from today's, else the standard
    code. Without today's object the standard code."""
    mapped = TEAM_CODES.get(found.abbreviation, found.abbreviation)
    if today is None or (found.name, found.location) == (today.name, today.location):
        return mapped
    return found.abbreviation


def payload_names(
    identities: Mapping[str, SeasonTeamName],
    runs: Mapping[str, Sequence[NameRun]],
) -> dict[str, SeasonIdentity]:
    """The identity of each team a payload names, with no read (ADR 0058). It
    applies the rule of `_season_code` and `season_names`, taking "today" from
    the open run of the stored franchise-names list."""
    names: dict[str, SeasonIdentity] = {}
    for code, found in identities.items():
        today = next((run for run in runs.get(code, ()) if run.to is None), None)
        mapped = TEAM_CODES.get(found.abbreviation, found.abbreviation)
        if today is None or (found.name, found.location) == (
            today.name,
            today.location,
        ):
            shown = mapped
        else:
            shown = found.abbreviation
        historical = today is not None and (found.name, found.location, shown) != (
            today.name,
            today.location,
            today.code,
        )
        names[code] = SeasonIdentity(found.name, found.location, shown, historical)
    return names


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


def _coded(value: object) -> Iterable[str]:
    """Every code of a coded model found in a value: models, nested models and
    lists."""
    if isinstance(value, _CODED):
        code = _plain_code(value)
        if code is not None:
            yield code
    elif isinstance(value, BaseModel):
        for name in type(value).model_fields:
            yield from _coded(getattr(value, name))
    elif isinstance(value, list):
        for item in value:
            yield from _coded(item)


def league_codes(model: BaseModel) -> list[str]:
    """The sorted distinct codes of every non-guest side in the model and of every
    coded model."""
    sides = {side.code for side in _sides(model) if not side.guest and side.code}
    return sorted(sides | set(_coded(model)))


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
        update = {
            name: _renamed(getattr(value, name), names)
            for name in type(value).model_fields
        }
        if isinstance(value, _CODED):
            code = _plain_code(value)
            if code is not None and code in names:
                update["season_code"] = names[code].code
        return value.model_copy(update=update)
    if isinstance(value, list):
        return [_renamed(item, names) for item in value]
    return value


def named_sides[M: BaseModel](model: M, names: Mapping[str, SeasonIdentity]) -> M:
    """The model with season_named applied to every side in it, validated again."""
    renamed = _renamed(model, names)
    return type(model).model_validate(renamed.model_dump(by_alias=False))


def identities_of(model: BaseModel) -> dict[str, SeasonIdentity]:
    """The identity each league side of a named feed carries, by code: the first
    side of a code wins. A side with no season code is left out."""
    found: dict[str, SeasonIdentity] = {}
    for side in _sides(model):
        if (
            side.guest
            or side.code is None
            or side.season_code is None
            or side.name is None
            or side.city is None
        ):
            continue
        found.setdefault(
            side.code,
            SeasonIdentity(side.name, side.city, side.season_code, side.historical),
        )
    return found


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
    today = next((found for season, found in seasons if season == current_season), None)
    for season, found in sorted(seasons, key=lambda item: item[0]):
        code = _season_code(found, today)
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
        self._cache = cache
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
            return with_build_version(TeamNames(runs=build_name_runs(found, current)))
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
            today: SeasonTeam | None = None
            if current is not None and current != season:
                today = await self._fetch_season_team(
                    self._client, code.upper(), current, self._settings
                )
            shown = _season_code(found, today)
            historical = False
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

    def _stored_names(self, code: str) -> TeamNames | None:
        body = read_by_id(self._settings.data_dir, KIND, code.lower())
        if body is None:
            return None
        try:
            return TeamNames.model_validate_json(body)
        except ValidationError:
            return None

    def stored(self, code: str) -> list[NameRun] | None:
        names = self._stored_names(code)
        return None if names is None else names.runs

    def outdated(self, code: str) -> bool:
        """Whether a list is stored and is not of the current build (ADR 0055)."""
        names = self._stored_names(code)
        return names is not None and not is_current_build(names)

    def career_runs(self, codes: Iterable[str]) -> dict[str, list[NameRun]]:
        """The stored runs of each distinct code that has a list, an outdated one
        included. The build of a list that is missing or outdated starts in the
        background, unless one is in flight or failed within the retry window; this
        never waits and reads no source."""
        found: dict[str, list[NameRun]] = {}
        for code in sorted(set(codes)):
            runs = self.stored(code)
            if runs is not None:
                found[code] = runs
            if runs is None or self.outdated(code):
                self._cache.warm(KIND, code.lower())
        return found

    def is_fresh(
        self, feed: TeamNames, built_at: dt.datetime, now: dt.datetime
    ) -> bool:
        return is_current_build(feed) and now - built_at < NAMES_LIFETIME

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
