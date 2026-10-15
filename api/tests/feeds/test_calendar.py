# api/tests/feeds/test_calendar.py
#
# Tests for the calendar feed model.
#
# Tested:
# - A valid calendar is accepted and serialized with camelCase keys
# - Rejects unsorted days, a repeated day, empty days, a season before 1994, a
#   bad season label, a firstDay or lastDay that is not the first or last day
#   and an unknown field
# - Accepts an empty windowDays
# - Seasons run newest first down to 1994 and hold the feed's season; an empty
#   list, ascending seasons, a gap, a list not ending at 1994 and a list without
#   the feed's season are rejected
#
# What is covered:
# - A valid feed is accepted and an invalid one is rejected
#
# Run with: cd api && .venv/bin/python -m pytest tests/feeds/test_calendar.py
#
# SEE: api/app/feeds/calendar.py

from typing import Any

import pytest
from pydantic import ValidationError

from app.feeds.calendar import CalendarFeed

Payload = dict[str, Any]


def seasons(first: int = 2027, last: int = 1994) -> list[Payload]:
    return [
        {"season": year, "seasonLabel": f"{year - 1}-{str(year)[2:]}"}
        for year in range(first, last - 1, -1)
    ]


def feed(**overrides: object) -> Payload:
    payload: Payload = {
        "generatedAt": "2026-01-15T12:00:00Z",
        "season": 1999,
        "seasonLabel": "1998-99",
        "firstDay": "1999-02-05",
        "lastDay": "1999-02-07",
        "days": ["1999-02-05", "1999-02-06", "1999-02-07"],
        "windowDays": ["1999-02-06"],
        "seasons": seasons(),
    }
    payload.update(overrides)
    return payload


def test_accepts_a_valid_calendar_and_serializes_camel_case() -> None:
    calendar = CalendarFeed.model_validate(feed())

    assert calendar.season == 1999
    assert set(calendar.model_dump(mode="json", by_alias=True)) == set(feed())


def test_serializes_the_seasons_newest_first() -> None:
    body = CalendarFeed.model_validate(feed()).model_dump(mode="json", by_alias=True)

    assert body["seasons"][0] == {"season": 2027, "seasonLabel": "2026-27"}
    assert body["seasons"][-1]["season"] == 1994


def test_accepts_an_empty_window() -> None:
    assert CalendarFeed.model_validate(feed(windowDays=[])).window_days == []


@pytest.mark.parametrize(
    "overrides",
    [
        {"days": ["1999-02-06", "1999-02-05", "1999-02-07"]},
        {"days": ["1999-02-05", "1999-02-05", "1999-02-07"]},
        {"days": [], "firstDay": "1999-02-05", "lastDay": "1999-02-07"},
        {"season": 1993, "seasonLabel": "1992-93"},
        {"seasonLabel": "1998/99"},
        {"firstDay": "1999-02-06"},
        {"lastDay": "1999-02-06"},
        {"extra": 1},
        {"seasons": []},
        {"seasons": list(reversed(seasons()))},
        {"seasons": seasons(2027, 2000) + seasons(1999, 1994)[1:]},
        {"seasons": seasons(2027, 1995)},
        {"seasons": seasons(1998, 1994)},
    ],
)
def test_rejects_an_invalid_calendar(overrides: Payload) -> None:
    with pytest.raises(ValidationError):
        CalendarFeed.model_validate(feed(**overrides))
