# api/app/sources/team_players.py
#
# Team players adapter: fetches one team's current roster, with the
# provider's current season, its coach and each player's details, one team's
# per-game season averages (the team leaders, with the previous season as a
# fallback) and one player's per-game season averages, and maps them to
# contract types. The provider URLs come from Settings.
# Provider data never leaves this module. A roster and the team leaders are kept
# for 24 hours; a player's averages are kept as long as the caller's freshness
# allows (rule F of docs/source-rules.md).
#
# SEE: docs/adr/0007-backend-runtime-and-data-pipeline.md, docs/source-rules.md, api/app/sources/game_detail.py

import datetime as dt

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    NonNegativeFloat,
    PositiveInt,
    ValidationError,
)
from pydantic.alias_generators import to_camel

from app.feeds.games import FeedModel, NonEmptyStr, Star
from app.settings import Settings
from app.sources.http import Freshness, SourceClient, SourceError, get_json
from app.sources.teams import TEAM_CODES

SOURCE = "team_players"
ROSTER_FRESH_FOR = dt.timedelta(hours=24)
LEADERS_FRESH_FOR = dt.timedelta(hours=24)
PROVIDER_CODES: dict[str, str] = {
    code: provider for provider, code in TEAM_CODES.items()
}
CATEGORIES = {
    "points": "pointsPerGame",
    "rebounds": "reboundsPerGame",
    "assists": "assistsPerGame",
}
PLAYER_STATS = {
    "points": "avgPoints",
    "rebounds": "avgRebounds",
    "assists": "avgAssists",
}


class _ProviderModel(BaseModel):
    model_config = ConfigDict(
        extra="ignore", alias_generator=to_camel, validate_by_name=True
    )


class _ProviderSeason(_ProviderModel):
    year: int


class _ProviderTeam(_ProviderModel):
    id: str


class _ProviderBirthPlace(_ProviderModel):
    city: str | None = None
    state: str | None = None
    country: str | None = None


class _ProviderNamed(_ProviderModel):
    name: str | None = None


class _ProviderExperience(_ProviderModel):
    years: int


class _ProviderPosition(_ProviderModel):
    name: str | None = None
    abbreviation: str | None = None


class _ProviderHref(_ProviderModel):
    href: str


class _ProviderAthlete(_ProviderModel):
    id: str
    first_name: str
    last_name: str
    short_name: str
    display_name: str | None = None
    jersey: str | None = None
    height: float | None = None
    display_height: str | None = None
    weight: float | None = None
    date_of_birth: AwareDatetime | None = None
    birth_place: _ProviderBirthPlace | None = None
    college: _ProviderNamed | None = None
    experience: _ProviderExperience | None = None
    position: _ProviderPosition | None = None
    headshot: _ProviderHref | None = None


class _ProviderCoach(_ProviderModel):
    first_name: str
    last_name: str
    experience: int | None = None


class _ProviderRoster(_ProviderModel):
    season: _ProviderSeason
    team: _ProviderTeam
    athletes: list[_ProviderAthlete]
    coach: list[_ProviderCoach] = []


class _ProviderAthleteRef(_ProviderModel):
    ref: str = Field(alias="$ref")


class _ProviderLeader(_ProviderModel):
    value: object
    athlete: _ProviderAthleteRef


class _ProviderCategory(_ProviderModel):
    name: str
    leaders: list[_ProviderLeader]


class _ProviderAverages(_ProviderModel):
    categories: list[_ProviderCategory]


class _ProviderStat(_ProviderModel):
    name: str
    value: object


class _ProviderStatCategory(_ProviderModel):
    name: str
    stats: list[_ProviderStat]


class _ProviderSplits(_ProviderModel):
    categories: list[_ProviderStatCategory]


class _ProviderPlayerAverages(_ProviderModel):
    splits: _ProviderSplits


class RosterEntry(FeedModel):
    """One roster player with the details of the provider, in its units: the
    height in inches, the weight in pounds. Never reaches a feed."""

    player_id: NonEmptyStr
    first_name: NonEmptyStr
    last_name: NonEmptyStr
    display_name: NonEmptyStr | None = None
    jersey: NonEmptyStr | None = None
    position_name: NonEmptyStr | None = None
    position_abbreviation: NonEmptyStr | None = None
    height_inches: float | None = None
    display_height: NonEmptyStr | None = None
    weight_lb: float | None = None
    birth_date: dt.date | None = None
    birth_city: NonEmptyStr | None = None
    birth_state: NonEmptyStr | None = None
    birth_country: NonEmptyStr | None = None
    college: NonEmptyStr | None = None
    experience: int | None = None
    headshot_url: NonEmptyStr | None = None


class RosterCoach(FeedModel):
    """A team's coach. Never reaches a feed."""

    first_name: NonEmptyStr
    last_name: NonEmptyStr
    experience: int | None = None


class Roster(FeedModel):
    """A team's current roster and the season the provider says is current."""

    season: PositiveInt
    team_id: NonEmptyStr
    players: list[Star] = Field(min_length=1)
    entries: list[RosterEntry] = Field(default_factory=list)
    coach: RosterCoach | None = None


class PlayerAverages(FeedModel):
    """One player's per-game averages for a season. Never reaches the feed."""

    player_id: NonEmptyStr
    points: NonNegativeFloat
    rebounds: NonNegativeFloat
    assists: NonNegativeFloat


class SeasonLeaders(FeedModel):
    """The players' per-game averages of the season the leaders were read for."""

    season: PositiveInt
    players: list[PlayerAverages]


def _location(error: ValidationError) -> str:
    return ".".join(str(part) for part in error.errors()[0]["loc"])


def _invalid_payload(error: ValidationError) -> SourceError:
    return SourceError(
        SOURCE,
        f"invalid payload: {error.error_count()} errors, first at {_location(error)}",
    )


def _provider_code(team_code: str) -> str:
    try:
        return PROVIDER_CODES[team_code]
    except KeyError:
        raise SourceError(SOURCE, f"unknown team code {team_code!r}") from None


def _entry(athlete: _ProviderAthlete) -> dict[str, object]:
    place = athlete.birth_place
    return {
        "player_id": athlete.id,
        "first_name": athlete.first_name,
        "last_name": athlete.last_name,
        "display_name": athlete.display_name,
        "jersey": athlete.jersey,
        "position_name": athlete.position.name if athlete.position else None,
        "position_abbreviation": (
            athlete.position.abbreviation if athlete.position else None
        ),
        "height_inches": athlete.height,
        "display_height": athlete.display_height,
        "weight_lb": athlete.weight,
        "birth_date": (
            athlete.date_of_birth.astimezone(dt.UTC).date()
            if athlete.date_of_birth
            else None
        ),
        "birth_city": place.city if place else None,
        "birth_state": place.state if place else None,
        "birth_country": place.country if place else None,
        "college": athlete.college.name if athlete.college else None,
        "experience": athlete.experience.years if athlete.experience else None,
        "headshot_url": athlete.headshot.href if athlete.headshot else None,
    }


def _coach(coaches: list[_ProviderCoach]) -> dict[str, object] | None:
    if not coaches:
        return None
    first = coaches[0]
    return {
        "first_name": first.first_name,
        "last_name": first.last_name,
        "experience": first.experience,
    }


async def fetch_roster(
    client: SourceClient, team_code: str, settings: Settings
) -> Roster:
    """Return the current roster of one team, or raise SourceError."""
    if settings.team_roster_url is None:
        raise SourceError(SOURCE, "team roster URL is not configured")
    if settings.player_photo_url is None:
        raise SourceError(SOURCE, "player photo URL is not configured")
    provider_code = _provider_code(team_code)
    url = settings.team_roster_url.format(team=provider_code)
    body = await get_json(client, url, source=SOURCE, fresh=ROSTER_FRESH_FOR)
    try:
        provider = _ProviderRoster.model_validate(body)
    except ValidationError as error:
        raise _invalid_payload(error) from None
    try:
        return Roster.model_validate(
            {
                "season": provider.season.year,
                "team_id": provider.team.id,
                "players": [
                    {
                        "player_id": athlete.id,
                        "first_name": athlete.first_name,
                        "last_name": athlete.last_name,
                        "short_name": athlete.short_name,
                        "team_code": team_code,
                        "photo_url": settings.player_photo_url.format(
                            player_id=athlete.id
                        ),
                    }
                    for athlete in provider.athletes
                ],
                "entries": [_entry(athlete) for athlete in provider.athletes],
                "coach": _coach(provider.coach),
            }
        )
    except ValidationError as error:
        first = error.errors()[0]
        raise SourceError(
            SOURCE,
            f"team {team_code} is invalid: {first['type']} at {_location(error)}",
        ) from None


def _athlete_id(team_id: str, ref: str) -> str:
    athlete_id = ref.split("?")[0].rstrip("/").rsplit("/", 1)[-1]
    if not athlete_id:
        raise SourceError(SOURCE, f"team {team_id} has an athlete link without an id")
    return athlete_id


def _number(owner_id: str, value: object, kind: str = "team") -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise SourceError(SOURCE, f"{kind} {owner_id} has a stat that is not a number")
    return float(value)


async def fetch_season_averages(
    client: SourceClient, team_id: str, season: int, settings: Settings
) -> list[PlayerAverages]:
    """Return the per-game averages of a team's players for a season.

    The team is the provider's team id from the roster. The list is empty when
    the provider has no statistics for that team and season.
    """
    if settings.team_averages_url is None:
        raise SourceError(SOURCE, "team averages URL is not configured")
    url = settings.team_averages_url.format(team=team_id, season=season)
    try:
        body = await get_json(client, url, source=SOURCE, fresh=LEADERS_FRESH_FOR)
    except SourceError as error:
        if error.status_code == 404:
            return []
        raise
    try:
        provider = _ProviderAverages.model_validate(body)
    except ValidationError as error:
        raise _invalid_payload(error) from None

    values: dict[str, dict[str, float]] = {}
    for category in provider.categories:
        for field, name in CATEGORIES.items():
            if category.name != name:
                continue
            for leader in category.leaders:
                athlete_id = _athlete_id(team_id, leader.athlete.ref)
                values.setdefault(athlete_id, {})[field] = _number(
                    team_id, leader.value
                )
    try:
        return [
            PlayerAverages.model_validate(
                {
                    "player_id": athlete_id,
                    "points": stats.get("points", 0.0),
                    "rebounds": stats.get("rebounds", 0.0),
                    "assists": stats.get("assists", 0.0),
                }
            )
            for athlete_id, stats in values.items()
        ]
    except ValidationError as error:
        first = error.errors()[0]
        raise SourceError(
            SOURCE,
            f"team {team_id} is invalid: {first['type']} at {_location(error)}",
        ) from None


async def fetch_team_leaders(
    client: SourceClient, roster: Roster, settings: Settings
) -> SeasonLeaders:
    """Return the players' averages of the roster's season, or of the previous
    one when the provider has none, with the season used.

    The current season with no players when neither has statistics."""
    for season in (roster.season, roster.season - 1):
        players = await fetch_season_averages(client, roster.team_id, season, settings)
        if players:
            return SeasonLeaders(season=season, players=players)
    return SeasonLeaders(season=roster.season, players=[])


async def fetch_player_averages(
    client: SourceClient,
    player_id: str,
    season: int,
    settings: Settings,
    fresh: Freshness,
) -> PlayerAverages | None:
    """Return one player's per-game averages for a season.

    None when the provider has no statistics for that player and season. `fresh`
    is the freshness the caller needs: the stars job passes the final time of the
    team's latest final game.
    """
    if settings.player_averages_url is None:
        raise SourceError(SOURCE, "player averages URL is not configured")
    url = settings.player_averages_url.format(player_id=player_id, season=season)
    try:
        body = await get_json(client, url, source=SOURCE, fresh=fresh)
    except SourceError as error:
        if error.status_code == 404:
            return None
        raise
    try:
        provider = _ProviderPlayerAverages.model_validate(body)
    except ValidationError as error:
        raise _invalid_payload(error) from None

    values: dict[str, float] = {}
    for category in provider.splits.categories:
        for stat in category.stats:
            for field, name in PLAYER_STATS.items():
                if stat.name == name:
                    values[field] = _number(player_id, stat.value, "player")
    try:
        return PlayerAverages.model_validate(
            {
                "player_id": player_id,
                "points": values.get("points", 0.0),
                "rebounds": values.get("rebounds", 0.0),
                "assists": values.get("assists", 0.0),
            }
        )
    except ValidationError as error:
        first = error.errors()[0]
        raise SourceError(
            SOURCE,
            f"player {player_id} is invalid: {first['type']} at {_location(error)}",
        ) from None
