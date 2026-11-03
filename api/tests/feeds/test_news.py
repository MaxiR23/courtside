# api/tests/feeds/test_news.py
#
# Tests for the news feed models.
#
# Tested:
# - A page of notes is accepted and round-trips to its camelCase payload
# - A note with no description, photo, team, player or game is accepted
# - Rejects notes out of time order and 13 notes
# - Rejects an unsafe note id, a time that is not UTC, a repeated team code, a
#   repeated player id, a photo with no width and an unknown field
#
# What is covered:
# - A valid feed is accepted and an invalid one is rejected
#
# Run with: cd api && .venv/bin/python -m pytest tests/feeds/test_news.py
#
# SEE: api/app/feeds/news.py

import copy
from typing import Any

import pytest
from pydantic import ValidationError

from app.feeds.news import NewsFeed

Payload = dict[str, Any]


def note(index: int) -> Payload:
    return {
        "id": f"note-{index}",
        "language": "en",
        "kind": "news",
        "headline": "Tigers beat Bears",
        "description": "A close one.",
        "published": f"2026-11-0{index}T12:00:00Z",
        "photo": {
            "url": "https://example.com/photo.jpg",
            "width": 1296,
            "height": 729,
            "credit": "Example Press",
        },
        "teams": ["BOS", "NYK"],
        "players": [{"playerId": "1", "name": "Ana Lee"}],
        "gameId": "401",
    }


def page() -> Payload:
    return {"page": 1, "hasMore": False, "notes": [note(3), note(2), note(1)]}


def mutated(change: Any) -> Payload:
    payload = copy.deepcopy(page())
    change(payload)
    return payload


def test_accepts_a_page_of_notes() -> None:
    feed = NewsFeed.model_validate(page())

    assert len(feed.notes) == 3
    assert feed.model_dump(by_alias=True, mode="json")["notes"][0]["gameId"] == "401"


def test_accepts_a_note_with_nothing_optional() -> None:
    payload = mutated(
        lambda p: p["notes"][0].update(
            description=None, photo=None, teams=[], players=[], gameId=None
        )
    )

    assert NewsFeed.model_validate(payload).notes[0].photo is None


def test_accepts_an_empty_page() -> None:
    assert (
        NewsFeed.model_validate({"page": 1, "hasMore": False, "notes": []}).notes == []
    )


def too_many(payload: Payload) -> None:
    payload["notes"] = [note(1)] * 13


def repeat_player(payload: Payload) -> None:
    payload["notes"][0]["players"] = [{"playerId": "1", "name": "A"}] * 2


@pytest.mark.parametrize(
    "payload",
    [
        mutated(lambda p: p["notes"].reverse()),
        mutated(too_many),
        mutated(lambda p: p["notes"][0].update(id="../etc")),
        mutated(lambda p: p["notes"][0].update(published="2026-11-03T12:00:00+02:00")),
        mutated(lambda p: p["notes"][0].update(teams=["BOS", "BOS"])),
        mutated(repeat_player),
        mutated(lambda p: p["notes"][0]["photo"].pop("width")),
        mutated(lambda p: p["notes"][0].update(link="https://example.com/x")),
        mutated(lambda p: p.update(page=0)),
    ],
    ids=[
        "out of order",
        "13 notes",
        "unsafe id",
        "not utc",
        "repeated team",
        "repeated player",
        "photo without width",
        "unknown field",
        "page 0",
    ],
)
def test_rejects_an_invalid_feed(payload: Payload) -> None:
    with pytest.raises(ValidationError):
        NewsFeed.model_validate(payload)
