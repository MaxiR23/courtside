# api/app/routers/feeds.py
#
# Serves the published feeds.
#
# SEE: docs/api/games.md, docs/api/game-detail.md

import asyncio
import hashlib

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from app.jobs.game_detail_feed import KIND
from app.jobs.on_demand import FeedCache, FeedUnavailableError, UnknownFeedError
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
    loop = asyncio.get_running_loop()
    started = loop.time()
    budget = feeds.wait
    await request.app.state.games_job.refresh_live(game_id, wait=budget)
    remaining = max(0.0, budget - (loop.time() - started))
    return await serve_on_demand(feeds, KIND, game_id, request, wait=remaining)


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
