# api/app/jobs/player_identities.py
#
# Player identities: the shared reader of a player's identity (name, position
# and headshot), kept across feeds in the state database. A player is read with
# one athlete object read and kept with its read time; a stored identity younger
# than 30 days is used with no read. Misses are read concurrently, at most eight
# in flight (the wide lane of the read budget). A read that fails is not cached
# and gives None, so the caller shows a dash; a rate limit is raised, so the
# build stops. The past playoffs build and the home build read it. A stored identity
# that is used is touched, and one not touched in 90 days is deleted by the
# games job's daily step (ADR 0063).
#
# SEE: docs/adr/0061-past-playoffs-player-identities-and-finals-mvp-averages.md,
# docs/adr/0058-bounded-past-competition-reads.md,
# docs/adr/0063-bounded-state-and-kept-feeds.md

import asyncio
import datetime as dt
import logging
from collections.abc import Awaitable, Callable, Iterable

from pydantic import ValidationError

from app.settings import Settings
from app.sources import player_draft
from app.sources.http import SourceClient, SourceError, is_rate_limited, wide_reads
from app.sources.player_draft import PlayerAthlete
from app.storage.state import StateStore

logger = logging.getLogger(__name__)

IDENTITY_LIFETIME = dt.timedelta(days=30)
IDENTITY_READS_IN_FLIGHT = 8

type FetchAthlete = Callable[[SourceClient, str, Settings], Awaitable[PlayerAthlete]]


class PlayerIdentities:
    def __init__(
        self,
        settings: Settings,
        store: StateStore,
        client: SourceClient,
        *,
        fetch_player_athlete: FetchAthlete = player_draft.fetch_player_athlete,
    ) -> None:
        self._settings = settings
        self._store = store
        self._client = client
        self._fetch_player_athlete = fetch_player_athlete
        self._semaphore = asyncio.Semaphore(IDENTITY_READS_IN_FLIGHT)

    def _stored(self, player_id: str) -> PlayerAthlete | None:
        entry = self._store.player_identity(player_id)
        if entry is None:
            return None
        if entry.read_at <= self._client.clock() - IDENTITY_LIFETIME:
            return None
        try:
            athlete = PlayerAthlete.model_validate_json(entry.body)
        except ValidationError:
            return None
        self._store.touch_player_identity(player_id, self._client.clock())
        return athlete

    async def _read(self, player_id: str) -> PlayerAthlete | None:
        async with self._semaphore:
            with wide_reads():
                try:
                    athlete = await self._fetch_player_athlete(
                        self._client, player_id, self._settings
                    )
                except SourceError as error:
                    if is_rate_limited(error):
                        raise
                    logger.warning(
                        "player identities: %s not read: %s", player_id, error.reason
                    )
                    return None
        self._store.set_player_identity(
            player_id, athlete.model_dump_json(), self._client.clock()
        )
        return athlete

    async def resolve(
        self, player_ids: Iterable[str]
    ) -> dict[str, PlayerAthlete | None]:
        """The identity of each player id, None for one that could not be read."""
        found: dict[str, PlayerAthlete | None] = {}
        missing: list[str] = []
        for player_id in dict.fromkeys(player_ids):
            stored = self._stored(player_id)
            if stored is None:
                missing.append(player_id)
            else:
                found[player_id] = stored
        read = await asyncio.gather(*(self._read(i) for i in missing))
        found.update(zip(missing, read, strict=True))
        return {player_id: found[player_id] for player_id in dict.fromkeys(player_ids)}
