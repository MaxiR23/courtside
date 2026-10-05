# api/app/routers/feeds.py
#
# Serves the published feeds.
#
# SEE: docs/api/games.md

import hashlib

from fastapi import APIRouter, HTTPException, Request, Response

from app.storage.feeds import read_feed

router = APIRouter()

# Below the 30-second live polling interval of ADR 0007.
CACHE_CONTROL = "public, max-age=10"


def matches(if_none_match: str | None, etag: str) -> bool:
    """Whether an If-None-Match header lists the ETag, weak or not, or is `*`."""
    if if_none_match is None:
        return False
    candidates = [part.strip().removeprefix("W/") for part in if_none_match.split(",")]
    return "*" in candidates or etag in candidates


@router.get("/feeds/games.json")
def read_games_feed(request: Request) -> Response:
    body = read_feed(request.app.state.settings.data_dir, "games")
    if body is None:
        raise HTTPException(status_code=503, detail="games feed is not published yet")
    etag = f'"{hashlib.sha256(body).hexdigest()}"'
    headers = {"Cache-Control": CACHE_CONTROL, "ETag": etag}
    if matches(request.headers.get("if-none-match"), etag):
        return Response(status_code=304, headers=headers)
    return Response(content=body, media_type="application/json", headers=headers)
