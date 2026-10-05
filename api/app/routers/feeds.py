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


@router.get("/feeds/games.json")
def read_games_feed(request: Request) -> Response:
    body = read_feed(request.app.state.settings.data_dir, "games")
    if body is None:
        raise HTTPException(status_code=503, detail="games feed is not published yet")
    return Response(
        content=body,
        media_type="application/json",
        headers={
            "Cache-Control": CACHE_CONTROL,
            "ETag": f'"{hashlib.sha256(body).hexdigest()}"',
        },
    )
