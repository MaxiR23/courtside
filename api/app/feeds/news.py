# api/app/feeds/news.py
#
# Feed models for the news feeds: the single source of truth for their shape.
# The JSON Schema and the TypeScript types are generated from these models. One
# feed is one page of notes, newest first, of the league, of a team or of a
# player. A note carries no link: nothing leaves the site, and the only URL a
# note holds is its photo's (ADR 0085).
#
# SEE: docs/api/news.md, docs/adr/0085-news-archive-and-feeds.md

from enum import StrEnum
from typing import Annotated

from pydantic import Field, HttpUrl, PositiveInt, StringConstraints, model_validator

from app.feeds.base import FeedModel, NonEmptyStr, TeamCode, UtcDatetime

PAGE_SIZE = 12


class NewsLanguage(StrEnum):
    EN = "en"
    ES = "es"


class NewsKind(StrEnum):
    NEWS = "news"
    RECAP = "recap"


class NewsPhoto(FeedModel):
    url: HttpUrl
    width: PositiveInt
    height: PositiveInt
    credit: NonEmptyStr | None


class NewsPlayer(FeedModel):
    player_id: NonEmptyStr
    name: NonEmptyStr


class NewsNote(FeedModel):
    # Safe as a path and as a cache id.
    id: Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9-]+$")]
    language: NewsLanguage
    kind: NewsKind
    headline: NonEmptyStr
    description: NonEmptyStr | None
    published: UtcDatetime
    photo: NewsPhoto | None
    teams: list[TeamCode]
    players: list[NewsPlayer]
    game_id: NonEmptyStr | None

    @model_validator(mode="after")
    def _require_distinct_tags(self) -> NewsNote:
        if len(set(self.teams)) != len(self.teams):
            raise ValueError("team codes must be distinct")
        ids = [player.player_id for player in self.players]
        if len(set(ids)) != len(ids):
            raise ValueError("player ids must be distinct")
        return self


class NewsFeed(FeedModel):
    page: PositiveInt
    has_more: bool
    notes: Annotated[list[NewsNote], Field(max_length=PAGE_SIZE)]

    @model_validator(mode="after")
    def _require_newest_first(self) -> NewsFeed:
        times = [note.published for note in self.notes]
        if times != sorted(times, reverse=True):
            raise ValueError("notes must be ordered by published, newest first")
        return self
