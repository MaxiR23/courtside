# api/tests/test_log.py
#
# Tests for the logging configuration.
#
# Tested:
# - Configures the app logger at INFO with one handler
# - Does not add a second handler when called twice
# - Passes records from app modules to the handler
#
# What is covered:
# - Happy path, edge case of a repeat call
#
# Run with: cd api && .venv/bin/python -m pytest tests/test_log.py
#
# SEE: api/app/log.py

import logging
from collections.abc import Iterator

import pytest

from app.log import configure_logging


@pytest.fixture(autouse=True)
def reset_app_logger() -> Iterator[None]:
    logger = logging.getLogger("app")
    yield
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
    logger.setLevel(logging.NOTSET)


def test_configures_the_app_logger_at_info_with_one_handler() -> None:
    configure_logging()

    logger = logging.getLogger("app")
    assert logger.level == logging.INFO
    assert len(logger.handlers) == 1


def test_does_not_add_a_second_handler_when_called_twice() -> None:
    configure_logging()
    configure_logging()

    assert len(logging.getLogger("app").handlers) == 1


def test_passes_records_from_app_modules_to_the_handler() -> None:
    configure_logging()
    handler = logging.getLogger("app").handlers[0]
    seen: list[logging.LogRecord] = []

    def capture(record: logging.LogRecord) -> bool:
        seen.append(record)
        return True

    handler.addFilter(capture)

    logging.getLogger("app.storage.feeds").info("hello")

    assert [record.getMessage() for record in seen] == ["hello"]
