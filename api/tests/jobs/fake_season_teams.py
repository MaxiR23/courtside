# api/tests/jobs/fake_season_teams.py
#
# A fake season team adapter for the kits that build a feed with a TeamNamesFeeds:
# it answers the season team objects a test sets by (code, season) and nothing
# else, so a side is named by its season only when a test says so (ADR 0054).
#
# SEE: api/app/jobs/team_names.py

from app.settings import Settings
from app.sources.http import SourceClient
from app.sources.season_team import SeasonTeam


def season_team(name: str, city: str, code: str) -> SeasonTeam:
    return SeasonTeam(
        team_id="1",
        abbreviation=code,
        display_name=f"{city} {name}",
        name=name,
        location=city,
    )


class FakeSeasonTeams:
    def __init__(self) -> None:
        self.teams: dict[tuple[str, int], SeasonTeam] = {}
        # The object every code has in a season, when no (code, season) is set.
        self.by_season: dict[int, SeasonTeam] = {}

    async def fetch(
        self, client: SourceClient, code: str, season: int, settings: Settings
    ) -> SeasonTeam | None:
        return self.teams.get((code, season), self.by_season.get(season))


def league_sides(value: object) -> list[dict[str, object]]:
    """Every league side (a dict with the guest and seasonCode keys, not a guest)
    found anywhere in a dumped feed."""
    found: list[dict[str, object]] = []
    if isinstance(value, dict):
        if "seasonCode" in value and "guest" in value and not value["guest"]:
            found.append(value)
        for item in value.values():
            found.extend(league_sides(item))
    elif isinstance(value, list):
        for item in value:
            found.extend(league_sides(item))
    return found
