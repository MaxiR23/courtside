# api/app/storage/feeds.py
#
# Feed publication: validate, write atomically, keep the last valid file.
# It also holds the per-game feeds, one file per game under feeds/games.
#
# SEE: docs/adr/0007-backend-runtime-and-data-pipeline.md,
# docs/adr/0019-game-detail-route-and-feed.md

import logging
import os
import re
import tempfile
from pathlib import Path

from pydantic import BaseModel, ValidationError

from app.feeds.game_detail import GameDetailFeed
from app.feeds.schema import FEEDS

logger = logging.getLogger(__name__)

FEED_DIR = "feeds"
GAME_DETAIL_DIR = "games"
GAME_ID = re.compile(r"^[A-Za-z0-9-]+$")


def _feed_path(data_dir: Path, name: str) -> Path:
    return data_dir / FEED_DIR / f"{name}.json"


def _game_detail_dir(data_dir: Path) -> Path:
    return data_dir / FEED_DIR / GAME_DETAIL_DIR


def _publish(model: type[BaseModel], path: Path, label: str, feed: BaseModel) -> bool:
    try:
        validated = model.model_validate(feed.model_dump(mode="json"))
    except ValidationError as error:
        location = ".".join(str(part) for part in error.errors()[0]["loc"])
        logger.error(
            "feed %s not published: invalid feed: %d errors, first at %s",
            label,
            error.error_count(),
            location,
        )
        return False

    temporary: str | None = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            dir=path.parent, prefix=f".{path.stem}.", suffix=".tmp", delete=False
        ) as handle:
            temporary = handle.name
            handle.write(validated.model_dump_json().encode("utf-8"))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except OSError as error:
        if temporary is not None and os.path.exists(temporary):
            os.remove(temporary)
        logger.error("feed %s not published: %s", label, error.strerror or error)
        return False
    return True


def publish_feed(data_dir: Path, name: str, feed: BaseModel) -> bool:
    return _publish(FEEDS[name], _feed_path(data_dir, name), name, feed)


def publish_game_detail(data_dir: Path, feed: GameDetailFeed) -> bool:
    if not GAME_ID.match(feed.id):
        logger.error("feed game-detail %s not published: invalid game id", feed.id)
        return False
    return _publish(
        FEEDS["game-detail"],
        _game_detail_dir(data_dir) / f"{feed.id}.json",
        f"game-detail {feed.id}",
        feed,
    )


def read_feed(data_dir: Path, name: str) -> bytes | None:
    try:
        return _feed_path(data_dir, name).read_bytes()
    except FileNotFoundError:
        return None


def read_game_detail(data_dir: Path, game_id: str) -> bytes | None:
    if not GAME_ID.match(game_id):
        return None
    try:
        return (_game_detail_dir(data_dir) / f"{game_id}.json").read_bytes()
    except FileNotFoundError:
        return None


def published_game_details(data_dir: Path) -> set[str]:
    directory = _game_detail_dir(data_dir)
    if not directory.is_dir():
        return set()
    return {path.stem for path in directory.glob("*.json") if GAME_ID.match(path.stem)}


def delete_game_detail(data_dir: Path, game_id: str) -> None:
    if not GAME_ID.match(game_id):
        return
    try:
        (_game_detail_dir(data_dir) / f"{game_id}.json").unlink(missing_ok=True)
    except OSError as error:
        logger.error(
            "feed game-detail %s not deleted: %s", game_id, error.strerror or error
        )
