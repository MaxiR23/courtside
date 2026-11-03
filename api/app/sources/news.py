# api/app/sources/news.py
#
# News adapter: reads the league news list (the whole league or one team, in
# English or Spanish) and the recap article of a game summary, and maps them to
# the contract's notes. A list keeps the headline news, story and recap types
# and drops premium notes. A note keeps a source id, a kind, a trimmed headline
# and description, the published time in UTC, one photo with its size and credit,
# the standard codes of its teams, its players with names and its game id. The
# provider's links are never read, so no link reaches a feed. The provider URLs
# come from Settings; the query is added with with_query, which keeps the URL's
# own query. Provider data never leaves this module.
#
# SEE: docs/api/news.md, docs/adr/0085-news-archive-and-feeds.md, api/app/sources/league_injuries.py

import datetime as dt
import logging
import re
from typing import Any

from pydantic import AwareDatetime, BaseModel, ConfigDict, ValidationError
from pydantic.alias_generators import to_camel

from app.feeds.news import NewsKind, NewsLanguage, NewsNote, NewsPhoto
from app.settings import Settings
from app.sources.http import SourceClient, SourceError, get_json, with_query
from app.sources.teams import team_code_of_id

logger = logging.getLogger(__name__)

SOURCE = "news"
FRESH_FOR = dt.timedelta(minutes=15)
LIST_LIMIT = 50
SPANISH = {"lang": "es", "region": "us"}
KEPT_LIST_TYPES = {"HeadlineNews", "Story", "Recap", "dStory"}
RECAP_TYPES = {"Recap", "BasketballRecap"}
SAFE_ID = re.compile(r"[A-Za-z0-9-]+")
DASH = "—"


class _ProviderModel(BaseModel):
    model_config = ConfigDict(
        extra="ignore", alias_generator=to_camel, validate_by_name=True
    )


class _ProviderImage(_ProviderModel):
    url: str
    width: int | None = None
    height: int | None = None
    type: str | None = None
    credit: str | None = None


class _ProviderCategory(_ProviderModel):
    type: str
    team_id: int | str | None = None
    athlete_id: int | str | None = None
    event_id: int | str | None = None
    description: str | None = None


class _ProviderArticle(_ProviderModel):
    id: int | str
    type: str
    headline: str | None = None
    description: str | None = None
    published: AwareDatetime
    images: list[_ProviderImage] = []
    categories: list[_ProviderCategory] = []
    premium: bool = False


class _ProviderList(_ProviderModel):
    articles: list[Any]


class _ProviderSummary(_ProviderModel):
    # Lenient, like the summary's header: a malformed article is no recap.
    article: Any = None


class _ProviderSummaryArticle(_ProviderModel):
    type: str
    headline: str | None = None
    description: str | None = None
    images: list[_ProviderImage] = []
    premium: bool = False


def _location(error: ValidationError) -> str:
    return ".".join(str(part) for part in error.errors()[0]["loc"])


def _description(text: str | None) -> str | None:
    if text is None:
        return None
    text = text.strip().removeprefix(DASH).strip()
    return text or None


def _photo(images: list[_ProviderImage]) -> NewsPhoto | None:
    sized = [i for i in images if i.url and (i.width or 0) > 0 and (i.height or 0) > 0]
    if not sized:
        return None
    image = next((i for i in sized if i.type == "header"), sized[0])
    try:
        return NewsPhoto.model_validate(
            {
                "url": image.url,
                "width": image.width,
                "height": image.height,
                "credit": (image.credit or "").strip() or None,
            }
        )
    except ValidationError:
        return None


def _teams(categories: list[_ProviderCategory]) -> list[str]:
    codes: list[str] = []
    for category in categories:
        if category.type != "team" or category.team_id is None:
            continue
        try:
            code = team_code_of_id(str(category.team_id), source=SOURCE)
        except SourceError:
            continue
        if code not in codes:
            codes.append(code)
    return codes


def _players(categories: list[_ProviderCategory]) -> list[dict[str, str]]:
    players: dict[str, str] = {}
    for category in categories:
        if category.type != "athlete" or category.athlete_id is None:
            continue
        name = (category.description or "").strip()
        player_id = str(category.athlete_id)
        if name and player_id not in players:
            players[player_id] = name
    return [{"player_id": pid, "name": name} for pid, name in players.items()]


def _game_id(categories: list[_ProviderCategory]) -> str | None:
    for category in categories:
        if category.type == "event" and category.event_id is not None:
            return str(category.event_id)
    return None


def _note(article: _ProviderArticle, language: NewsLanguage) -> NewsNote | None:
    note_id = str(article.id)
    headline = (article.headline or "").strip()
    if SAFE_ID.fullmatch(note_id) is None or not headline:
        logger.warning("Skipping a news note %s: unusable id or headline.", note_id)
        return None
    try:
        return NewsNote.model_validate(
            {
                "id": note_id,
                "language": language,
                "kind": NewsKind.RECAP
                if article.type in RECAP_TYPES
                else NewsKind.NEWS,
                "headline": headline,
                "description": _description(article.description),
                "published": article.published.astimezone(dt.UTC),
                "photo": _photo(article.images),
                "teams": _teams(article.categories),
                "players": _players(article.categories),
                "game_id": _game_id(article.categories),
            }
        )
    except ValidationError as error:
        logger.warning(
            "Skipping a news note %s: %d errors, first at %s.",
            note_id,
            error.error_count(),
            _location(error),
        )
        return None


async def fetch_news_list(
    client: SourceClient,
    settings: Settings,
    language: NewsLanguage,
    team: str | None = None,
) -> list[NewsNote]:
    """Return the kept notes of the league list, or of one team's, or raise SourceError."""
    if settings.news_url is None:
        raise SourceError(SOURCE, "news URL is not configured")
    query: dict[str, str | int] = {"limit": LIST_LIMIT}
    if team:
        query["team"] = team.lower()
    if language is NewsLanguage.ES:
        query |= SPANISH
    body = await get_json(
        client, with_query(settings.news_url, query), source=SOURCE, fresh=FRESH_FOR
    )
    try:
        envelope = _ProviderList.model_validate(body)
    except ValidationError as error:
        raise SourceError(
            SOURCE,
            f"invalid payload: {error.error_count()} errors, first at {_location(error)}",
        ) from None
    notes: list[NewsNote] = []
    for raw in envelope.articles:
        try:
            article = _ProviderArticle.model_validate(raw)
        except ValidationError as error:
            known = raw.get("id") if isinstance(raw, dict) else None
            logger.warning(
                "Skipping a news note %s: %d errors, first at %s.",
                known,
                error.error_count(),
                _location(error),
            )
            continue
        if article.type not in KEPT_LIST_TYPES or article.premium:
            continue
        note = _note(article, language)
        if note is not None:
            notes.append(note)
    return notes


async def fetch_game_recap(
    client: SourceClient,
    settings: Settings,
    game_id: str,
    language: NewsLanguage,
    *,
    published: dt.datetime,
    teams: list[str],
) -> NewsNote | None:
    """Return the recap article of a game summary, or None when it has none.

    The summary names no id, time or tags for the article: the id is
    `recap-{game_id}`, and the time and teams are the site's own game's."""
    if settings.game_detail_url is None:
        raise SourceError(SOURCE, "game detail URL is not configured")
    url = settings.game_detail_url.format(game_id=game_id)
    if language is NewsLanguage.ES:
        url = with_query(url, SPANISH)
    body = await get_json(client, url, source=SOURCE, fresh=FRESH_FOR)
    try:
        summary = _ProviderSummary.model_validate(body)
    except ValidationError as error:
        raise SourceError(
            SOURCE,
            f"invalid payload: {error.error_count()} errors, first at {_location(error)}",
        ) from None
    if summary.article is None:
        return None
    try:
        article = _ProviderSummaryArticle.model_validate(summary.article)
    except ValidationError:
        return None
    if article.type not in RECAP_TYPES or article.premium:
        return None
    headline = (article.headline or "").strip()
    if not headline:
        return None
    try:
        return NewsNote.model_validate(
            {
                "id": f"recap-{game_id}",
                "language": language,
                "kind": NewsKind.RECAP,
                "headline": headline,
                "description": _description(article.description),
                "published": published.astimezone(dt.UTC),
                "photo": _photo(article.images),
                "teams": teams,
                "players": [],
                "game_id": game_id,
            }
        )
    except ValidationError as error:
        logger.warning(
            "Skipping the recap of game %s: %d errors, first at %s.",
            game_id,
            error.error_count(),
            _location(error),
        )
        return None
