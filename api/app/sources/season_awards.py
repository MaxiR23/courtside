# api/app/sources/season_awards.py
#
# Season awards adapter: reads the season's paged index of award links from the
# provider, then each linked award document, and maps each award it knows to its code, its team number (the
# All-NBA, All-Rookie and All-Defensive teams) and the winners in the provider's
# order. The name of an award is matched ignoring case against a fixed table. An
# award with no winners is skipped before the lookup, which covers the awards
# the app does not show (the coach and the executive of the year); an unknown
# name with winners is skipped and logged by name. A player and a team are read
# from the provider ids in their links, never by following the link; only the
# award links of the index are followed, one after the other, with the shared
# cache and the 1-hour freshness. A winner with no team link, or with a team link that is not a league team (the All-Star MVP's All-Star side), has a null team. The provider URL comes from Settings.
# Provider data never leaves this module.
#
# SEE: docs/api/playoffs.md, docs/adr/0032-playoffs-feed.md,
# api/app/sources/depth_chart.py

import datetime as dt
import logging

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from pydantic.alias_generators import to_camel

from app.feeds.games import FeedModel, NonEmptyStr, TeamCode
from app.feeds.playoffs import AwardCode
from app.settings import Settings
from app.sources.http import SourceClient, SourceError, get_json
from app.sources.teams import TEAM_IDS, team_code_of_id

SOURCE = "season_awards"
FRESH_FOR = dt.timedelta(hours=1)
# The provider's award names, compared in lower case, with the code of the award
# and its team number.
AWARDS: dict[str, tuple[AwardCode, int | None]] = {
    "mvp": (AwardCode.MVP, None),
    "defensive player of the year": (AwardCode.DPOY, None),
    "rookie of the year": (AwardCode.ROY, None),
    "sixth man of the year": (AwardCode.SIXTH_MAN, None),
    "most improved player": (AwardCode.MIP, None),
    "clutch player of the year": (AwardCode.CPOY, None),
    "finals mvp": (AwardCode.FINALS_MVP, None),
    "eastern conference finals mvp": (AwardCode.EAST_FINALS_MVP, None),
    "western conference finals mvp": (AwardCode.WEST_FINALS_MVP, None),
    "all-star mvp": (AwardCode.ALL_STAR_MVP, None),
    "nba cup mvp": (AwardCode.CUP_MVP, None),
    "nba cup all-tournament team": (AwardCode.CUP_ALL_TOURNAMENT, None),
    "all-nba 1st team": (AwardCode.ALL_NBA, 1),
    "all-nba 2nd team": (AwardCode.ALL_NBA, 2),
    "all-nba 3rd team": (AwardCode.ALL_NBA, 3),
    "all-rookie 1st team": (AwardCode.ALL_ROOKIE, 1),
    "all-rookie 2nd team": (AwardCode.ALL_ROOKIE, 2),
    "all-defensive 1st team": (AwardCode.ALL_DEFENSIVE, 1),
    "all-defensive 2nd team": (AwardCode.ALL_DEFENSIVE, 2),
    "twyman-stokes teammate of the year": (AwardCode.TWYMAN_STOKES, None),
}

logger = logging.getLogger(__name__)


class _ProviderModel(BaseModel):
    model_config = ConfigDict(
        extra="ignore", alias_generator=to_camel, validate_by_name=True
    )


class _ProviderRef(_ProviderModel):
    ref: str = Field(alias="$ref")


class _ProviderWinner(_ProviderModel):
    athlete: _ProviderRef
    team: _ProviderRef | None = None


class _ProviderAward(_ProviderModel):
    name: str
    winners: list[_ProviderWinner] = []


class _ProviderIndex(_ProviderModel):
    items: list[_ProviderRef]


class AwardWinnerRef(FeedModel):
    """A winner of an award. Never reaches a feed."""

    player_id: NonEmptyStr
    team_code: TeamCode | None


class SeasonAward(FeedModel):
    """An award with winners. Never reaches a feed."""

    code: AwardCode
    team: int | None
    winners: list[AwardWinnerRef]


class SeasonAwards(FeedModel):
    """The known awards with winners, in the provider's order. Never reaches a
    feed."""

    awards: list[SeasonAward]


def _location(error: ValidationError) -> str:
    return ".".join(str(part) for part in error.errors()[0]["loc"])


def _id_after(ref: str, segment: str, what: str) -> str:
    parts = httpx.URL(ref).path.rstrip("/").split("/")
    if segment not in parts[:-1]:
        raise SourceError(SOURCE, f"{what} link has no {what} id")
    return parts[parts.index(segment) + 1]


def _winner(winner: _ProviderWinner) -> dict[str, str | None]:
    player_id = _id_after(winner.athlete.ref, "athletes", "athlete")
    team_id = (
        None if winner.team is None else _id_after(winner.team.ref, "teams", "team")
    )
    return {
        "player_id": player_id,
        "team_code": (
            team_code_of_id(team_id, source=SOURCE)
            if team_id is not None and team_id in TEAM_IDS
            else None
        ),
    }


async def _read_award(client: SourceClient, ref: str) -> _ProviderAward:
    body = await get_json(client, ref, source=SOURCE, fresh=FRESH_FOR)
    try:
        return _ProviderAward.model_validate(body)
    except ValidationError as error:
        raise SourceError(
            SOURCE,
            f"invalid award payload: {error.error_count()} errors, first at {_location(error)}",
        ) from None


async def fetch_season_awards(
    client: SourceClient, season: int, settings: Settings
) -> SeasonAwards:
    """Return the known awards of a season with winners, or raise SourceError."""
    if not settings.season_awards_url:
        raise SourceError(SOURCE, "season awards URL is not configured")
    url = settings.season_awards_url.format(season=season)
    body = await get_json(client, url, source=SOURCE, fresh=FRESH_FOR)
    try:
        provider = _ProviderIndex.model_validate(body)
    except ValidationError as error:
        raise SourceError(
            SOURCE,
            f"invalid payload: {error.error_count()} errors, first at {_location(error)}",
        ) from None
    documents = []
    for item in provider.items:
        documents.append(await _read_award(client, item.ref))
    awards = []
    for award in documents:
        if not award.winners:
            continue
        known = AWARDS.get(award.name.casefold())
        if known is None:
            logger.warning("season awards: unknown award %r", award.name)
            continue
        code, team = known
        awards.append(
            {
                "code": code,
                "team": team,
                "winners": [_winner(winner) for winner in award.winners],
            }
        )
    try:
        return SeasonAwards.model_validate({"awards": awards})
    except ValidationError as error:
        raise SourceError(
            SOURCE,
            f"invalid payload: {error.error_count()} errors, first at {_location(error)}",
        ) from None
