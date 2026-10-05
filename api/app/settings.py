import datetime as dt
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal, Self

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

API_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = API_DIR / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_FILE, env_file_encoding="utf-8", hide_input_in_errors=True
    )

    environment: Literal["development", "production"] = "development"
    scoreboard_url: str | None = None
    game_detail_url: str | None = None
    player_photo_url: str | None = None
    # Template with {team}, the provider's team code.
    team_roster_url: str | None = None
    # Template with {team}, the provider's team id from the roster, and {season}.
    team_averages_url: str | None = None
    video_channel_feed_url: str | None = None
    # Template with {video_id}, the channel's video id.
    video_thumbnail_url: str | None = None
    # Template with {video_id}, the channel's video id.
    video_embed_url: str | None = None
    # Template with {query}, the search words, already URL-encoded.
    highlights_search_url: str | None = None
    # US Eastern time of the daily schedule fetch.
    daily_fetch_time: dt.time = dt.time(6, 0)
    data_dir: Path = API_DIR / "data"
    cors_origins: list[str] = []

    @field_validator("data_dir", mode="before")
    @classmethod
    def _reject_empty_data_dir(cls, value: Any) -> Any:
        if isinstance(value, str) and not value.strip():
            raise ValueError("must not be empty")
        return value

    @model_validator(mode="after")
    def _resolve_data_dir(self) -> Self:
        if not self.data_dir.is_absolute():
            self.data_dir = (API_DIR / self.data_dir).resolve()
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
