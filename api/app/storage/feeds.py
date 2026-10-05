# api/app/storage/feeds.py
#
# Feed publication: validate, write atomically, keep the last valid file.
#
# SEE: docs/adr/0007-backend-runtime-and-data-pipeline.md

import logging
import os
import tempfile
from pathlib import Path

from pydantic import BaseModel, ValidationError

from app.feeds.schema import FEEDS

logger = logging.getLogger(__name__)

FEED_DIR = "feeds"


def _feed_path(data_dir: Path, name: str) -> Path:
    return data_dir / FEED_DIR / f"{name}.json"


def publish_feed(data_dir: Path, name: str, feed: BaseModel) -> bool:
    try:
        validated = FEEDS[name].model_validate(feed.model_dump(mode="json"))
    except ValidationError as error:
        location = ".".join(str(part) for part in error.errors()[0]["loc"])
        logger.error(
            "feed %s not published: invalid feed: %d errors, first at %s",
            name,
            error.error_count(),
            location,
        )
        return False

    path = _feed_path(data_dir, name)
    temporary: str | None = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            dir=path.parent, prefix=f".{name}.", suffix=".tmp", delete=False
        ) as handle:
            temporary = handle.name
            handle.write(validated.model_dump_json().encode("utf-8"))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except OSError as error:
        if temporary is not None and os.path.exists(temporary):
            os.remove(temporary)
        logger.error("feed %s not published: %s", name, error.strerror or error)
        return False
    return True


def read_feed(data_dir: Path, name: str) -> bytes | None:
    try:
        return _feed_path(data_dir, name).read_bytes()
    except FileNotFoundError:
        return None
