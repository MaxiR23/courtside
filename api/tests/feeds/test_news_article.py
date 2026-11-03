# api/tests/feeds/test_news_article.py
#
# Tests for the news article feed model.
#
# Tested:
# - An article with no note and no game is accepted
# - A note with the game it is about is accepted
# - Rejects a game whose id differs from the note's game id, and a game with no note
#
# What is covered:
# - A valid feed is accepted and an invalid one is rejected
#
# Run with: cd api && .venv/bin/python -m pytest tests/feeds/test_news_article.py
#
# SEE: api/app/feeds/news_article.py

from typing import Any

import pytest
from pydantic import ValidationError

from app.feeds.news_article import NewsArticleFeed

Payload = dict[str, Any]


def side(code: str) -> Payload:
    return {"code": code, "name": "Tigers", "city": "Boston"}


def note() -> Payload:
    return {
        "id": "recap-401",
        "language": "en",
        "kind": "recap",
        "headline": "Tigers beat Bears",
        "description": None,
        "published": "2026-11-03T00:00:00Z",
        "photo": None,
        "teams": ["BOS", "NYK"],
        "players": [],
        "gameId": "401",
    }


def game(game_id: str = "401") -> Payload:
    return {
        "id": game_id,
        "away": side("NYK"),
        "home": side("BOS"),
        "score": {"away": 90, "home": 100},
    }


def test_accepts_an_article_with_no_note_and_no_game() -> None:
    feed = NewsArticleFeed.model_validate({"note": None, "game": None})

    assert feed.note is None
    assert feed.game is None


def test_accepts_a_note_with_its_game() -> None:
    feed = NewsArticleFeed.model_validate({"note": note(), "game": game()})

    assert feed.game is not None
    assert feed.game.home.code == "BOS"


def test_accepts_a_game_with_no_score() -> None:
    payload = {"note": note(), "game": game() | {"score": None}}

    assert NewsArticleFeed.model_validate(payload).game is not None


@pytest.mark.parametrize(
    "payload",
    [
        {"note": note(), "game": game("402")},
        {"note": None, "game": game()},
    ],
    ids=["another game", "no note"],
)
def test_rejects_a_game_that_is_not_the_notes(payload: Payload) -> None:
    with pytest.raises(ValidationError):
        NewsArticleFeed.model_validate(payload)
