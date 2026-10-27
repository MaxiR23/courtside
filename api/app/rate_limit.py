# api/app/rate_limit.py
#
# Per-visitor rate limit on the feed routes. A fixed window of one minute per
# visitor, opened by its first request. It is kept in memory only: nothing is
# stored on disk, and no address is logged or put in a feed. A restart clears
# the windows. The limiter runs in the event loop, so it needs no lock.
#
# SEE: docs/source-rules.md, docs/adr/0080-per-visitor-rate-limit.md

import datetime as dt
import math
from collections import OrderedDict
from collections.abc import Callable

from fastapi import HTTPException, Request

from app.jobs.scheduler import utc_now

WINDOW = dt.timedelta(minutes=1)
# Most visitors tracked at once; past it the oldest window is dropped.
MAX_VISITORS = 10_000


class RateLimiter:
    def __init__(
        self,
        limit: int,
        *,
        clock: Callable[[], dt.datetime] = utc_now,
        max_visitors: int = MAX_VISITORS,
    ) -> None:
        self._limit = limit
        self._clock = clock
        self._max_visitors = max_visitors
        # Window start and request count per visitor, in window-start order.
        self._windows: OrderedDict[str, tuple[dt.datetime, int]] = OrderedDict()

    def __len__(self) -> int:
        return len(self._windows)

    def hit(self, key: str) -> int | None:
        """Counts a request. None when allowed, else the seconds to retry after."""
        if self._limit == 0:
            return None
        now = self._clock()
        while self._windows:
            oldest = next(iter(self._windows.values()))[0]
            if now - oldest < WINDOW:
                break
            self._windows.popitem(last=False)
        window = self._windows.get(key)
        if window is None:
            if len(self._windows) >= self._max_visitors:
                self._windows.popitem(last=False)
            self._windows[key] = (now, 1)
            return None
        start, count = window
        if count >= self._limit:
            return max(1, math.ceil((start + WINDOW - now).total_seconds()))
        self._windows[key] = (start, count + 1)
        return None


def visitor_key(request: Request) -> str:
    """The first address of x-real-ip, else the connection's client address."""
    forwarded = request.headers.get("x-real-ip", "").split(",")[0].strip()
    if forwarded:
        return forwarded
    return request.client.host if request.client else ""


async def limit_rate(request: Request) -> None:
    """Answers 429 with Retry-After when the visitor is over its limit.

    It stays async: a sync dependency would run in a thread and share the dict.
    """
    retry_after = request.app.state.rate_limiter.hit(visitor_key(request))
    if retry_after is not None:
        raise HTTPException(
            status_code=429,
            detail="too many requests",
            headers={"Retry-After": str(retry_after)},
        )
