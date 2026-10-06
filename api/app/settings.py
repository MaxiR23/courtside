import datetime as dt
import logging
import string
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal, Self

from pydantic import SecretStr, ValidationInfo, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

API_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = API_DIR / ".env"

# Placeholder each URL template must contain.
PLACEHOLDERS = {"scoreboard_url": "date", "game_detail_url": "game_id"}

# Names of settings that no longer exist. A stale .env may still carry them,
# so they are dropped with a warning instead of stopping the backend. When a
# setting is removed, add its name here. Any other unknown key still fails.
RETIRED_SETTINGS = {"video_thumbnail_url"}

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_FILE, env_file_encoding="utf-8", hide_input_in_errors=True
    )

    environment: Literal["development", "production"] = "development"
    # Template with {date}, the US Eastern date as YYYYMMDD.
    scoreboard_url: str | None = None
    # Template with {game_id}, the provider's game id.
    game_detail_url: str | None = None
    player_photo_url: str | None = None
    # Template with {team}, the provider's team code.
    team_roster_url: str | None = None
    # Template with {team}, the provider's team id from the roster, and {season}.
    team_averages_url: str | None = None
    # Template with {player_id}, the provider's player id, and {season}.
    player_averages_url: str | None = None
    # Listing of the official channel's uploads, without the key. The adapter
    # adds the page size and the page token.
    highlights_source_url: str | None = None
    # Key of the video source. Never logged or printed.
    highlights_source_key: SecretStr | None = None
    # Template with {video_id}, the channel's video id.
    video_embed_url: str | None = None
    # Template with {query}, the search words, already URL-encoded.
    highlights_search_url: str | None = None
    # US Eastern time of the daily schedule fetch.
    daily_fetch_time: dt.time = dt.time(6, 0)
    data_dir: Path = API_DIR / "data"
    cors_origins: list[str] = []

    @model_validator(mode="before")
    @classmethod
    def _drop_retired_settings(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        kept = {}
        for key, value in data.items():
            if isinstance(key, str) and key.lower() in RETIRED_SETTINGS:
                # Name only: the value is never logged.
                logger.warning(
                    "Ignoring the retired setting %s: delete it from .env.",
                    key.upper(),
                )
            else:
                kept[key] = value
        return kept

    @field_validator("data_dir", mode="before")
    @classmethod
    def _reject_empty_data_dir(cls, value: Any) -> Any:
        if isinstance(value, str) and not value.strip():
            raise ValueError("must not be empty")
        return value

    @field_validator("scoreboard_url", "game_detail_url")
    @classmethod
    def _require_placeholder(
        cls, value: str | None, info: ValidationInfo
    ) -> str | None:
        # An empty value, as listed in .env.example, counts as unset here.
        if not value:
            return value
        placeholder = PLACEHOLDERS.get(info.field_name or "", "")
        fields = {name for _, name, _, _ in string.Formatter().parse(value)}
        if placeholder not in fields:
            raise ValueError(f"must contain the {{{placeholder}}} placeholder")
        return value

    @model_validator(mode="after")
    def _resolve_data_dir(self) -> Self:
        if not self.data_dir.is_absolute():
            self.data_dir = (API_DIR / self.data_dir).resolve()
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
