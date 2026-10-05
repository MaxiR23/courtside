# api/app/log.py
#
# Logging configuration, applied once at startup.
#
# SEE: docs/adr/0007-backend-runtime-and-data-pipeline.md

import logging

LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


def configure_logging() -> None:
    """Configure the app logger, parent of every logger in app/. Idempotent."""
    logger = logging.getLogger("app")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(LOG_FORMAT))
        logger.addHandler(handler)
