# api/app/jobs/playoffs_backfill_games.py
#
# The final games of the stored playoffs feeds for the highlights backfill (ADR
# 0048): the current playoffs feed and every stored season playoffs feed, the
# series games and the play-in games. The Finals feeds are not read: their games
# are those of the Finals series of the bracket. It belongs to the playoffs
# section, builds no feed and reads no source: a missing or invalid stored feed
# gives no game. A game with a side without a name cannot be matched by title and
# is skipped. The core backfill receives it as an injected provider and imports
# no section.
#
# SEE: docs/adr/0048-highlights-backfill-and-edition-video.md,
# docs/adr/0035-playoffs-marks-in-core-feeds.md

from pathlib import Path

from pydantic import ValidationError

from app.feeds.games import GameStatus
from app.feeds.playoffs import PlayoffGame, PlayoffsFeed
from app.jobs import playoffs_feed, season_playoffs_feed
from app.jobs.highlights_backfill import GameTarget
from app.storage.feeds import published_ids, read_by_id


def _bodies(data_dir: Path) -> list[bytes]:
    bodies = [read_by_id(data_dir, playoffs_feed.KIND, playoffs_feed.FEED_ID)]
    for feed_id in sorted(published_ids(data_dir, season_playoffs_feed.KIND)):
        bodies.append(read_by_id(data_dir, season_playoffs_feed.KIND, feed_id))
    return [body for body in bodies if body is not None]


def _games(feed: PlayoffsFeed) -> list[PlayoffGame]:
    games: list[PlayoffGame] = [g for series in feed.bracket for g in series.games]
    for play_in in feed.play_in or []:
        games += [g.game for g in play_in.games if g.game is not None]
    return games


def playoffs_backfill_games(data_dir: Path) -> list[GameTarget]:
    """The final games of the stored playoffs feeds, once each."""
    found: dict[str, GameTarget] = {}
    for body in _bodies(data_dir):
        try:
            feed = PlayoffsFeed.model_validate_json(body)
        except ValidationError:
            continue
        for game in _games(feed):
            if (
                game.status is GameStatus.FINAL
                and game.away.name is not None
                and game.home.name is not None
                and game.id not in found
            ):
                found[game.id] = GameTarget(
                    game.id, game.away.name, game.home.name, game.start_time
                )
    return list(found.values())
