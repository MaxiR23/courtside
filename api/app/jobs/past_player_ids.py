# api/app/jobs/past_player_ids.py
#
# The player ids known from the stored past feeds (ADR 0043): the roster of a
# stored team feed of a past season (none on a feed built from ADR 0059 on) and
# the box score of a stored past game detail. `known_in_season` also knows the
# players the stored past feeds of the sections it is given name (ADR 0059; the
# playoffs and Finals readers come from main.py); only the season player kind
# reads it. A lazy index: each stored file is read once per process, as
# PastGameDetailFeeds finds the day of a game. The ids a file names are kept in
# the state database (past_player_ids, never pruned) and read back with the files
# after a start, so a player stays known when the daily step deletes his feeds
# (ADR 0063). save_stored reads every stored file at once, so the daily cleanup
# keeps the ids of the files it is about to delete. It reads no source.
# A file that does not validate is skipped and read again on the next call.
# Two kinds read it: the current player feed and the player feed of a past
# season. It has its own module so neither of them imports the other.
#
# SEE: docs/api/player.md, docs/adr/0043-season-feeds-and-franchise-names.md,
# api/app/jobs/past_game_detail_feed.py, docs/adr/0063-bounded-state-and-kept-feeds.md

import datetime as dt
from collections.abc import Callable, Sequence
from pathlib import Path

from pydantic import ValidationError

from app.feeds.game_detail import PastGameDetailFeed
from app.feeds.team import PastTeamFeed
from app.jobs.past_game_detail_feed import KIND as PAST_GAMES_KIND
from app.jobs.scheduler import utc_now
from app.jobs.season_team_feed import KIND as SEASON_TEAMS_KIND
from app.storage.feeds import published_ids, read_by_id
from app.storage.state import PastPlayerScope, StateStore


def _roster_ids(body: bytes) -> set[str]:
    feed = PastTeamFeed.model_validate_json(body)
    if feed.roster is None:
        return set()
    return {player.id for player in feed.roster}


def _box_score_ids(body: bytes) -> set[str]:
    feed = PastGameDetailFeed.model_validate_json(body)
    if feed.box_score is None:
        return set()
    return {
        player.player_id
        for side in (feed.box_score.away, feed.box_score.home)
        for player in side.players
    }


class PastPlayerIds:
    def __init__(
        self,
        data_dir: Path,
        store: StateStore,
        *,
        clock: Callable[[], dt.datetime] = utc_now,
        named: Sequence[tuple[str, Callable[[bytes], set[str]]]] = (),
    ) -> None:
        self._data_dir = data_dir
        self._store = store
        self._clock = clock
        # (kind, reader) pairs of the sections that name players in a stored
        # past feed, given by main.py (ADR 0059); the index imports no section.
        self._named_sources = tuple(named)
        self._ids: set[str] = set()
        self._named: set[str] = set()
        # (kind, feed id) of the files already read.
        self._scanned: set[tuple[str, str]] = set()
        # The scopes whose stored ids were read back from the state database.
        self._loaded: set[PastPlayerScope] = set()

    def known(self, player_id: str) -> bool:
        """Whether a stored past roster or box score has the player."""
        if player_id in self._ids:
            return True
        self._scan()
        return player_id in self._ids

    def known_in_season(self, player_id: str) -> bool:
        """Whether the player is known, or a stored past playoffs or Finals feed
        names the player (ADR 0059)."""
        if self.known(player_id):
            return True
        self._scan_named()
        return player_id in self._named

    def save_stored(self) -> None:
        """Reads every stored file and keeps the ids it names in the state
        database; the daily cleanup calls it before it deletes any file."""
        self._scan()
        self._scan_named()

    def _load(self, scope: PastPlayerScope, into: set[str]) -> None:
        """Reads the stored ids of the scope once per process (ADR 0063)."""
        if scope in self._loaded:
            return
        into |= self._store.past_player_ids(scope)
        self._loaded.add(scope)

    def _scan(self) -> None:
        self._load("known", self._ids)
        self._read_all(
            ((SEASON_TEAMS_KIND, _roster_ids), (PAST_GAMES_KIND, _box_score_ids)),
            self._ids,
            "known",
        )

    def _scan_named(self) -> None:
        self._load("in_season", self._named)
        self._read_all(self._named_sources, self._named, "in_season")

    def _read_all(
        self,
        sources: Sequence[tuple[str, Callable[[bytes], set[str]]]],
        into: set[str],
        scope: PastPlayerScope,
    ) -> None:
        for kind, read in sources:
            for feed_id in sorted(published_ids(self._data_dir, kind)):
                if (kind, feed_id) in self._scanned:
                    continue
                body = read_by_id(self._data_dir, kind, feed_id)
                if body is None:
                    continue
                try:
                    found = read(body)
                except ValidationError:
                    continue
                self._store.add_past_player_ids(found, scope, self._clock())
                into |= found
                self._scanned.add((kind, feed_id))
