# api/app/jobs/past_player_ids.py
#
# The player ids known from the stored past feeds (ADR 0043): the roster of a
# stored team feed of a past season and the box score of a stored past game
# detail. A lazy index: each stored file is read once, since a kept feed never
# changes, as PastGameDetailFeeds finds the day of a game. It reads no source.
# A file that does not validate is skipped and read again on the next call.
# Two kinds read it: the current player feed and the player feed of a past
# season. It has its own module so neither of them imports the other.
#
# SEE: docs/api/player.md, docs/adr/0043-season-feeds-and-franchise-names.md,
# api/app/jobs/past_game_detail_feed.py

from pathlib import Path

from pydantic import ValidationError

from app.feeds.game_detail import PastGameDetailFeed
from app.feeds.team import PastTeamFeed
from app.jobs.past_game_detail_feed import KIND as PAST_GAMES_KIND
from app.jobs.season_team_feed import KIND as SEASON_TEAMS_KIND
from app.storage.feeds import published_ids, read_by_id


def _roster_ids(body: bytes) -> set[str]:
    feed = PastTeamFeed.model_validate_json(body)
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
    def __init__(self, data_dir: Path) -> None:
        self._data_dir = data_dir
        self._ids: set[str] = set()
        # (kind, feed id) of the files already read.
        self._scanned: set[tuple[str, str]] = set()

    def known(self, player_id: str) -> bool:
        """Whether a stored past roster or box score has the player."""
        if player_id in self._ids:
            return True
        self._scan()
        return player_id in self._ids

    def _scan(self) -> None:
        for kind, read in (
            (SEASON_TEAMS_KIND, _roster_ids),
            (PAST_GAMES_KIND, _box_score_ids),
        ):
            for feed_id in sorted(published_ids(self._data_dir, kind)):
                if (kind, feed_id) in self._scanned:
                    continue
                body = read_by_id(self._data_dir, kind, feed_id)
                if body is None:
                    continue
                try:
                    self._ids |= read(body)
                except ValidationError:
                    continue
                self._scanned.add((kind, feed_id))
