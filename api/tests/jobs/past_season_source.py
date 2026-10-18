# api/tests/jobs/past_season_source.py
#
# A helper for the tests that count the source reads of a past build (ADR 0058).
# It is not a test module.
#
# ReadRecorder is one respx router on https://example.com/reads/ that answers
# every read with an empty JSON body. It records each request path, the number of
# requests in flight now and at most (and, split by lane, the peak of the narrow
# reads and of the wide reads, the adapters named in `wide`, ADR 0061), and answers a status the test sets for the
# reads of one adapter. count_reads wraps the adapters a kind was given, so that
# every call sends one request through the shared SourceClient (the only place
# that counts a read) before it returns what the kit's fake adapter returns. The
# adapters that read one game share a URL by game id, as the real ones do, so a
# second adapter on a game is a cache hit and not a read (path name "game").
#
# SEE: api/app/sources/http.py, api/tests/jobs/test_past_build_reads.py

import asyncio
import datetime as dt
from collections.abc import Awaitable, Callable
from typing import Any

import httpx
import respx

from app.settings import Settings
from app.sources.http import SourceClient, get_json

BASE = "https://example.com/reads/"
FRESH = dt.timedelta(hours=1)
# The adapters that read the summary of one game: one URL per game id.
GAME_KEYED = frozenset(
    {"game_detail", "game_detail_sections", "play_scores", "game_players"}
)
REAL_SLEEP = asyncio.sleep


class ReadRecorder:
    def __init__(self, wide: frozenset[str] = frozenset({"player_athlete"})) -> None:
        self.paths: list[str] = []
        self.wide = wide
        self.running = 0
        self.peak = 0
        self.running_wide = 0
        self.wide_peak = 0
        self.narrow_peak = 0
        # The adapter name whose reads answer `status`, and that status.
        self.limit_on: str | None = None
        self.status = 429

    def install(self, router: respx.MockRouter) -> None:
        router.get(url__startswith=BASE).mock(side_effect=self._answer)

    async def _answer(self, request: httpx.Request) -> httpx.Response:
        self.paths.append(request.url.path)
        name = request.url.path.removeprefix("/reads/").split("/")[0]
        is_wide = name in self.wide
        self.running += 1
        self.running_wide += is_wide
        self.peak = max(self.peak, self.running)
        self.wide_peak = max(self.wide_peak, self.running_wide)
        self.narrow_peak = max(self.narrow_peak, self.running - self.running_wide)
        try:
            await REAL_SLEEP(0)
        finally:
            self.running -= 1
            self.running_wide -= is_wide
        if self.limit_on is not None and name == self.limit_on:
            return httpx.Response(self.status)
        return httpx.Response(200, json={})

    @property
    def count(self) -> int:
        return len(self.paths)

    def by_adapter(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for path in self.paths:
            name = path.removeprefix("/reads/").split("/")[0]
            counts[name] = counts.get(name, 0) + 1
        return counts

    def reset(self) -> None:
        self.paths.clear()
        self.peak = 0
        self.wide_peak = 0
        self.narrow_peak = 0


def _key(name: str, args: tuple[Any, ...], kwargs: dict[str, Any]) -> str:
    if name in GAME_KEYED:
        return f"game:{args[1]}"
    parts = [repr(a) for a in args[1:] if not isinstance(a, Settings)]
    parts += [f"{k}={v!r}" for k, v in sorted(kwargs.items())]
    return f"{name}:{','.join(parts)}"


def count_reads(kinds: list[object], client: SourceClient) -> None:
    """Wrap every adapter a kind object holds (its `_fetch_*` attributes) so that
    each call first reads one URL through the client."""
    numbers: dict[str, int] = {}

    def wrap(
        name: str, fetch: Callable[..., Awaitable[Any]]
    ) -> Callable[..., Awaitable[Any]]:
        async def counted(*args: Any, **kwargs: Any) -> Any:
            key = _key(name, args, kwargs)
            number = numbers.setdefault(key, len(numbers))
            # The adapters of one game share one URL, so one path name.
            path = "game" if name in GAME_KEYED else name
            await get_json(client, f"{BASE}{path}/{number}", source="test", fresh=FRESH)
            return await fetch(*args, **kwargs)

        return counted

    for kind in kinds:
        for attribute, value in list(vars(kind).items()):
            if attribute.startswith("_fetch_") and callable(value):
                setattr(kind, attribute, wrap(attribute.removeprefix("_fetch_"), value))
