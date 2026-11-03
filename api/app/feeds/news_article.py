# api/app/feeds/news_article.py
#
# Feed models for the news article feed: the single source of truth for its shape.
# The JSON Schema and the TypeScript types are generated from these models. One
# feed is one note, or none, with the site's own game (sides and score) when the
# site holds the game the note is about. It serves the article path and the game
# recap path. The logo and colors of a side are added when served (ADR 0068); they
# are null in the stored file (ADR 0085).
#
# SEE: docs/api/news.md, docs/adr/0085-news-archive-and-feeds.md

from pydantic import model_validator

from app.feeds.base import FeedModel, NonEmptyStr
from app.feeds.games import Score
from app.feeds.news import NewsNote
from app.feeds.opponent import Opponent


class NewsGame(FeedModel):
    id: NonEmptyStr
    away: Opponent
    home: Opponent
    score: Score | None


class NewsArticleFeed(FeedModel):
    note: NewsNote | None
    game: NewsGame | None

    @model_validator(mode="after")
    def _require_the_game_of_the_note(self) -> NewsArticleFeed:
        if self.game is not None and (
            self.note is None or self.note.game_id != self.game.id
        ):
            raise ValueError("a game requires a note about that game")
        return self
