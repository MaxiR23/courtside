# api/app/sources/finals_plays.py
#
# Finals view of the game detail (ADR 0033). Reads the same game from the same
# URL with the freshness the caller passes, so it shares one cached response with
# app.sources.game_detail. It maps only the plays' period, clock and home and away
# scores. Its results never reach a core feed, and removing the playoffs section
# removes this module. Provider data never leaves this module.
#
# SEE: docs/api/playoffs.md, docs/adr/0033-playoffs-finals-feed.md,
# api/app/sources/game_detail.py

from pydantic import Field, NonNegativeInt, ValidationError

from app.feeds.games import FeedModel
from app.settings import Settings
from app.sources.game_detail import (
    SOURCE,
    _elapsed_seconds,
    _ProviderModel,
    _SummaryFormat,
    _SummaryPlay,
)
from app.sources.http import Freshness, SourceClient, SourceError, get_json


class _ScoredPlay(_SummaryPlay):
    home_score: int | None = None
    away_score: int | None = None


class _FinalsSummary(_ProviderModel):
    format: _SummaryFormat
    plays: list[_ScoredPlay] = Field(default_factory=list)


class PlayScore(FeedModel):
    """The score after one play, at the game second of the play. Never reaches a
    feed."""

    elapsed_seconds: NonNegativeInt
    home_score: NonNegativeInt
    away_score: NonNegativeInt


async def fetch_play_scores(
    client: SourceClient, game_id: str, settings: Settings, fresh: Freshness
) -> list[PlayScore]:
    """Return the score after each play of one game in game order, or raise
    SourceError. A play without both scores or with a clock that cannot be placed
    is skipped."""
    if settings.game_detail_url is None:
        raise SourceError(SOURCE, "game detail URL is not configured")
    url = settings.game_detail_url.format(game_id=game_id)
    body = await get_json(client, url, source=SOURCE, fresh=fresh)
    try:
        summary = _FinalsSummary.model_validate(body)
    except ValidationError as error:
        location = ".".join(str(part) for part in error.errors()[0]["loc"])
        raise SourceError(
            SOURCE,
            f"invalid payload: {error.error_count()} errors, first at {location}",
        ) from None
    scores: list[PlayScore] = []
    for play in summary.plays:
        if play.home_score is None or play.away_score is None:
            continue
        elapsed = _elapsed_seconds(
            play.period.number, play.clock.display_value, summary.format
        )
        if elapsed is None or play.home_score < 0 or play.away_score < 0:
            continue
        scores.append(
            PlayScore(
                elapsed_seconds=elapsed,
                home_score=play.home_score,
                away_score=play.away_score,
            )
        )
    return sorted(scores, key=lambda score: score.elapsed_seconds)
