# api/app/routers/feeds.py
#
# Serves the published feeds.
#
# SEE: docs/api/games.md, docs/api/game-detail.md, docs/api/player.md, docs/api/team.md,
# docs/api/standings.md, docs/api/search.md, docs/api/cup.md,
# docs/api/cup-matchup.md, docs/api/playoffs.md, docs/api/all-star.md,
# docs/api/calendar.md, docs/api/days.md, docs/api/home.md, docs/adr/0074-home-feed.md,
# docs/api/power-ranking.md, docs/adr/0075-power-ranking-feed.md,
# docs/adr/0041-past-game-detail.md,
# docs/adr/0043-season-feeds-and-franchise-names.md,
# docs/adr/0045-season-competition-feeds.md,
# docs/adr/0046-season-playoffs-feeds.md,
# docs/adr/0047-season-all-star-feed.md

import asyncio
import hashlib

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from app.jobs.all_star_feed import FEED_ID as ALL_STAR_ID
from app.jobs.all_star_feed import KIND as ALL_STAR_KIND
from app.jobs.calendar_feed import KIND as CALENDAR_KIND
from app.jobs.cup_feed import FEED_ID as CUP_ID
from app.jobs.cup_feed import KIND as CUP_KIND
from app.jobs.cup_matchup_feed import KIND as MATCHUP_KIND
from app.jobs.day_feed import KIND as DAY_KIND
from app.jobs.game_detail_feed import KIND
from app.jobs.home_feed import FEED_ID as HOME_ID
from app.jobs.home_feed import KIND as HOME_KIND
from app.jobs.on_demand import (
    FeedCache,
    FeedUnavailableError,
    IdStatus,
    UnknownFeedError,
)
from app.jobs.past_game_detail_feed import KIND as PAST_KIND
from app.jobs.player_feed import KIND as PLAYER_KIND
from app.jobs.playoffs_feed import FEED_ID as PLAYOFFS_ID
from app.jobs.playoffs_feed import KIND as PLAYOFFS_KIND
from app.jobs.playoffs_finals_feed import FEED_ID as FINALS_ID
from app.jobs.playoffs_finals_feed import KIND as FINALS_KIND
from app.jobs.power_ranking_feed import FEED_ID as POWER_RANKING_ID
from app.jobs.power_ranking_feed import KIND as POWER_RANKING_KIND
from app.jobs.search_feed import FEED_ID as SEARCH_ID
from app.jobs.search_feed import KIND as SEARCH_KIND
from app.jobs.season_player_feed import KIND as SEASON_PLAYER_KIND
from app.jobs.season_standings_feed import KIND as SEASON_STANDINGS_KIND
from app.jobs.season_team_feed import KIND as SEASON_TEAM_KIND
from app.jobs.standings_feed import FEED_ID as STANDINGS_ID
from app.jobs.standings_feed import KIND as STANDINGS_KIND
from app.jobs.team_feed import KIND as TEAM_KIND
from app.storage.feeds import read_feed


def record_presence(request: Request) -> None:
    request.app.state.presence.seen()


router = APIRouter(dependencies=[Depends(record_presence)])

# Below the 30-second live refresh of rule C (docs/source-rules.md); rule K keeps it.
CACHE_CONTROL = "public, max-age=10"


def matches(if_none_match: str | None, etag: str) -> bool:
    """Whether an If-None-Match header lists the ETag, weak or not, or is `*`."""
    if if_none_match is None:
        return False
    candidates = [part.strip().removeprefix("W/") for part in if_none_match.split(",")]
    return "*" in candidates or etag in candidates


def _serve(body: bytes, request: Request) -> Response:
    etag = f'"{hashlib.sha256(body).hexdigest()}"'
    headers = {"Cache-Control": CACHE_CONTROL, "ETag": etag}
    if matches(request.headers.get("if-none-match"), etag):
        return Response(status_code=304, headers=headers)
    return Response(content=body, media_type="application/json", headers=headers)


@router.get("/feeds/games.json")
async def read_games_feed(request: Request) -> Response:
    await request.app.state.games_job.refresh_live()
    body = read_feed(request.app.state.settings.data_dir, "games")
    if body is None:
        raise HTTPException(status_code=503, detail="games feed is not published yet")
    return _serve(body, request)


@router.get("/feeds/games/{game_id}.json")
async def read_game_detail_feed(game_id: str, request: Request) -> Response:
    feeds: FeedCache = request.app.state.feed_cache
    # A final game of a stored day feed that the games job has not loaded is a
    # past game (ADR 0041); every other id keeps the games path.
    if (
        request.app.state.games_job.loaded_game(game_id) is None
        and feeds.status(PAST_KIND, game_id) is IdStatus.KNOWN
    ):
        return await serve_on_demand(feeds, PAST_KIND, game_id, request)
    loop = asyncio.get_running_loop()
    started = loop.time()
    budget = feeds.wait
    await request.app.state.games_job.refresh_live(game_id, wait=budget)
    remaining = max(0.0, budget - (loop.time() - started))
    return await serve_on_demand(feeds, KIND, game_id, request, wait=remaining)


@router.get("/feeds/teams/{code}.json")
async def read_team_feed(code: str, request: Request) -> Response:
    return await serve_on_demand(request.app.state.feed_cache, TEAM_KIND, code, request)


@router.get("/feeds/standings.json")
async def read_standings_feed(request: Request) -> Response:
    return await serve_on_demand(
        request.app.state.feed_cache, STANDINGS_KIND, STANDINGS_ID, request
    )


@router.get("/feeds/home.json")
async def read_home_feed(request: Request) -> Response:
    return await serve_on_demand(
        request.app.state.feed_cache, HOME_KIND, HOME_ID, request
    )


@router.get("/feeds/power-ranking.json")
async def read_power_ranking_feed(request: Request) -> Response:
    return await serve_on_demand(
        request.app.state.feed_cache, POWER_RANKING_KIND, POWER_RANKING_ID, request
    )


@router.get("/feeds/search.json")
async def read_search_feed(request: Request) -> Response:
    return await serve_on_demand(
        request.app.state.feed_cache, SEARCH_KIND, SEARCH_ID, request
    )


@router.get("/feeds/cup.json")
async def read_cup_feed(request: Request) -> Response:
    return await serve_on_demand(
        request.app.state.feed_cache, CUP_KIND, CUP_ID, request
    )


@router.get("/feeds/playoffs.json")
async def read_playoffs_feed(request: Request) -> Response:
    return await serve_on_demand(
        request.app.state.feed_cache, PLAYOFFS_KIND, PLAYOFFS_ID, request
    )


@router.get("/feeds/playoffs/finals.json")
async def read_playoffs_finals_feed(request: Request) -> Response:
    return await _serve_current_finals(request)


async def _serve_current_finals(request: Request) -> Response:
    feeds: FeedCache = request.app.state.feed_cache
    loop = asyncio.get_running_loop()
    started = loop.time()
    budget = feeds.wait
    try:
        await feeds.serve(PLAYOFFS_KIND, PLAYOFFS_ID, wait=budget)
    except FeedUnavailableError:
        raise HTTPException(
            status_code=503, detail="feed is not available yet"
        ) from None
    remaining = max(0.0, budget - (loop.time() - started))
    return await serve_on_demand(feeds, FINALS_KIND, FINALS_ID, request, wait=remaining)


@router.get("/feeds/all-star.json")
async def read_all_star_feed(request: Request) -> Response:
    return await serve_on_demand(
        request.app.state.feed_cache, ALL_STAR_KIND, ALL_STAR_ID, request
    )


@router.get("/feeds/cup/matchups/{slot_id}.json")
async def read_cup_matchup_feed(slot_id: str, request: Request) -> Response:
    return await serve_on_demand(
        request.app.state.feed_cache, MATCHUP_KIND, slot_id, request
    )


@router.get("/feeds/players/{player_id}.json")
async def read_player_feed(player_id: str, request: Request) -> Response:
    feeds: FeedCache = request.app.state.feed_cache
    loop = asyncio.get_running_loop()
    started = loop.time()
    budget = feeds.wait
    await request.app.state.player_feeds.refresh_live(player_id, wait=budget)
    remaining = max(0.0, budget - (loop.time() - started))
    return await serve_on_demand(feeds, PLAYER_KIND, player_id, request, wait=remaining)


async def serve_on_demand(
    feeds: FeedCache,
    kind: str,
    feed_id: str,
    request: Request,
    *,
    wait: float | None = None,
) -> Response:
    try:
        body = await feeds.serve(kind, feed_id, wait=wait)
    except UnknownFeedError:
        raise HTTPException(status_code=404, detail="feed not found") from None
    except FeedUnavailableError:
        raise HTTPException(
            status_code=503, detail="feed is not available yet"
        ) from None
    return _serve(body, request)


@router.get("/feeds/seasons/{season}/calendar.json")
async def read_calendar_feed(season: str, request: Request) -> Response:
    feed_id = request.app.state.calendar_feeds.feed_id(season)
    if feed_id is None:
        raise HTTPException(status_code=503, detail="feed is not available yet")
    return await serve_on_demand(
        request.app.state.feed_cache, CALENDAR_KIND, feed_id, request
    )


@router.get("/feeds/seasons/{season}/standings.json")
async def read_season_standings_feed(season: str, request: Request) -> Response:
    return await serve_on_demand(
        request.app.state.feed_cache, SEASON_STANDINGS_KIND, season, request
    )


@router.get("/feeds/seasons/{season}/teams/{code}.json")
async def read_season_team_feed(season: str, code: str, request: Request) -> Response:
    return await serve_on_demand(
        request.app.state.feed_cache, SEASON_TEAM_KIND, f"{season}-{code}", request
    )


@router.get("/feeds/seasons/{season}/players/{player_id}.json")
async def read_season_player_feed(
    season: str, player_id: str, request: Request
) -> Response:
    return await serve_on_demand(
        request.app.state.feed_cache,
        SEASON_PLAYER_KIND,
        f"{season}-{player_id}",
        request,
    )


@router.get("/feeds/seasons/{season}/cup.json")
async def read_season_cup_feed(season: str, request: Request) -> Response:
    kind, feed_id = request.app.state.season_cup_feeds.target(season)
    return await serve_on_demand(request.app.state.feed_cache, kind, feed_id, request)


@router.get("/feeds/seasons/{season}/cup/matchups/{slot_id}.json")
async def read_season_cup_matchup_feed(
    season: str, slot_id: str, request: Request
) -> Response:
    kind, feed_id = request.app.state.season_cup_matchup_feeds.target(season, slot_id)
    return await serve_on_demand(request.app.state.feed_cache, kind, feed_id, request)


@router.get("/feeds/seasons/{season}/playoffs.json")
async def read_season_playoffs_feed(season: str, request: Request) -> Response:
    kind, feed_id = request.app.state.season_playoffs_feeds.target(season)
    return await serve_on_demand(request.app.state.feed_cache, kind, feed_id, request)


@router.get("/feeds/seasons/{season}/playoffs/finals.json")
async def read_season_playoffs_finals_feed(season: str, request: Request) -> Response:
    kind, feed_id = request.app.state.season_playoffs_finals_feeds.target(season)
    if kind == FINALS_KIND:
        return await _serve_current_finals(request)
    return await serve_on_demand(request.app.state.feed_cache, kind, feed_id, request)


@router.get("/feeds/seasons/{season}/all-star.json")
async def read_season_all_star_feed(season: str, request: Request) -> Response:
    kind, feed_id = request.app.state.season_all_star_feeds.target(season)
    return await serve_on_demand(request.app.state.feed_cache, kind, feed_id, request)


@router.get("/feeds/days/{day}.json")
async def read_day_feed(day: str, request: Request) -> Response:
    return await serve_on_demand(request.app.state.feed_cache, DAY_KIND, day, request)
