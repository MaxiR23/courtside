# api/app/jobs/presence.py
#
# Presence: whether anyone has requested a feed lately (rule B). It is kept in
# memory, so after a restart nobody is present until the first feed request.
# The clock is injected so tests run without real time.
#
# SEE: docs/source-rules.md, docs/adr/0020-source-rules.md

import datetime as dt
from collections.abc import Callable

from app.jobs.scheduler import utc_now

PRESENT_FOR = dt.timedelta(minutes=5)


class Presence:
    def __init__(self, *, clock: Callable[[], dt.datetime] = utc_now) -> None:
        self._clock = clock
        self._last: dt.datetime | None = None

    def seen(self) -> None:
        """Records a feed request now."""
        self._last = self._clock()

    def present(self, now: dt.datetime) -> bool:
        """Whether a feed request was seen less than PRESENT_FOR before now."""
        return self._last is not None and now - self._last < PRESENT_FOR
