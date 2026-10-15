# api/app/jobs/cup_backfill_games.py
#
# The final games of the stored Cup feeds for the highlights backfill (ADR 0048):
# the current Cup feed and every stored season Cup feed. It belongs to the Cup
# section, builds no feed and reads no source: a missing or invalid stored feed
# gives no game. A game with a side without a name cannot be matched by title and
# is skipped. The core backfill receives it as an injected provider and imports
# no section.
#
# SEE: docs/adr/0048-highlights-backfill-and-edition-video.md,
# docs/adr/0035-playoffs-marks-in-core-feeds.md

from pathlib import Path

from pydantic import ValidationError

from app.feeds.cup import CupFeed
from app.feeds.games import GameStatus
from app.jobs import cup_feed, season_cup_feed
from app.jobs.highlights_backfill import GameTarget
from app.storage.feeds import published_ids, read_by_id


def _bodies(data_dir: Path) -> list[bytes]:
    bodies = [read_by_id(data_dir, cup_feed.KIND, cup_feed.FEED_ID)]
    for feed_id in sorted(published_ids(data_dir, season_cup_feed.KIND)):
        bodies.append(read_by_id(data_dir, season_cup_feed.KIND, feed_id))
    return [body for body in bodies if body is not None]


def cup_backfill_games(data_dir: Path) -> list[GameTarget]:
    """The final games of the stored Cup feeds, in the order read."""
    found: list[GameTarget] = []
    for body in _bodies(data_dir):
        try:
            feed = CupFeed.model_validate_json(body)
        except ValidationError:
            continue
        for day in feed.games.days:
            for game in day.games:
                if (
                    game.status is GameStatus.FINAL
                    and game.away.name is not None
                    and game.home.name is not None
                ):
                    found.append(
                        GameTarget(
                            game.id, game.away.name, game.home.name, game.start_time
                        )
                    )
    return found
