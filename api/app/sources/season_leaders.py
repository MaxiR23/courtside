# api/app/sources/season_leaders.py
#
# Season leaders adapter: fetches the regular-season leaders of a season from the
# provider and maps the four per-game categories (points, rebounds, assists and
# blocks) to the athlete ids and the display values, in the provider's order. Any
# other category is ignored and a category with no leaders is absent. An athlete
# is read from the provider athlete id in its link, never by following the link.
# A leader's team code comes from its team link, null when the link is absent or
# is not a league team. The provider URL comes from Settings, and its own query
# selects the regular season. Provider data never leaves this module.
#
# SEE: docs/api/home.md, docs/adr/0074-home-feed.md,
# api/app/sources/postseason_leaders.py

import datetime as dt

from app.feeds.games import FeedModel
from app.feeds.playoffs import LeaderCategory
from app.settings import Settings
from app.sources.http import SourceClient, SourceError, get_json
from app.sources.postseason_leaders import LeaderEntry, parse_leaders

SOURCE = "season_leaders"
FRESH_FOR = dt.timedelta(hours=1)
# The provider's category names: per-game only, no percentages.
CATEGORIES: dict[str, LeaderCategory] = {
    "pointsPerGame": LeaderCategory.POINTS,
    "reboundsPerGame": LeaderCategory.REBOUNDS,
    "assistsPerGame": LeaderCategory.ASSISTS,
    "blocksPerGame": LeaderCategory.BLOCKS,
}


class SeasonLeaders(FeedModel):
    """The regular-season leaders of each category in the provider's order. A
    category with no leaders is absent. Never reaches a feed."""

    categories: dict[LeaderCategory, list[LeaderEntry]]


async def fetch_season_leaders(
    client: SourceClient, season: int, settings: Settings
) -> SeasonLeaders:
    """Return the regular-season leaders of a season, or raise SourceError."""
    if not settings.season_leaders_url:
        raise SourceError(SOURCE, "season leaders URL is not configured")
    url = settings.season_leaders_url.format(season=season)
    body = await get_json(client, url, source=SOURCE, fresh=FRESH_FOR)
    return SeasonLeaders.model_validate(
        {"categories": parse_leaders(body, source=SOURCE, names=CATEGORIES)}
    )
