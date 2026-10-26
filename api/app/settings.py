import datetime as dt
import logging
import string
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal, Self

from pydantic import (
    PositiveInt,
    SecretStr,
    ValidationInfo,
    field_validator,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict

API_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = API_DIR / ".env"

# Placeholder each URL template must contain.
PLACEHOLDERS = {"scoreboard_url": "date", "game_detail_url": "game_id"}

# Placeholders each of these URL templates must contain, and no other.
EXACT_PLACEHOLDERS: dict[str, frozenset[str]] = {
    "player_bio_url": frozenset({"player_id"}),
    "player_draft_url": frozenset({"player_id"}),
    "player_overview_url": frozenset({"player_id"}),
    "player_gamelog_url": frozenset({"player_id"}),
    "player_stats_url": frozenset({"player_id"}),
    "team_info_url": frozenset({"team"}),
    "division_standings_url": frozenset(),
    "cup_group_url": frozenset({"season", "group"}),
    "cup_group_standings_url": frozenset({"season", "group"}),
    "depth_chart_url": frozenset({"season", "team_id"}),
    "season_team_url": frozenset({"season", "team_id"}),
    "season_roster_url": frozenset({"season", "team_id"}),
    "season_type_url": frozenset({"season", "type"}),
    "postseason_leaders_url": frozenset({"season"}),
    "season_leaders_url": frozenset({"season"}),
    "team_postseason_record_url": frozenset({"season", "team_id"}),
    "team_postseason_stats_url": frozenset({"season", "team_id"}),
    "season_awards_url": frozenset({"season"}),
}

# Names of settings that no longer exist. A stale .env may still carry them,
# so they are dropped with a warning instead of stopping the backend. When a
# setting is removed, add its name here. Any other unknown key still fails.
RETIRED_SETTINGS = {"video_thumbnail_url", "highlights_backfill_pages"}

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
    # Standings of both conferences.
    standings_url: str | None = None
    # Template with {team}, the provider's team code. The adapter adds the
    # season and the season type to its query.
    team_schedule_url: str | None = None
    # Injuries of every team in the league.
    league_injuries_url: str | None = None
    # Template with {player_id}, the provider's player id: bio with the season summary.
    player_bio_url: str | None = None
    # Template with {player_id}: the player's draft.
    player_draft_url: str | None = None
    # Template with {player_id}: the player's overview with the awards.
    player_overview_url: str | None = None
    # Template with {player_id}: the player's game log of the current season.
    player_gamelog_url: str | None = None
    # Template with {player_id}: the player's season stats. The adapter adds the
    # playoffs season type to its query.
    player_stats_url: str | None = None
    # Template with {team}, the provider's team code: colors, arena and images.
    team_info_url: str | None = None
    # Standings by division, requested as is: its query must select the regular
    # season. When the response is not of the regular season, the adapter adds
    # the season to its query.
    division_standings_url: str | None = None
    # Template with {season}, the end year of the season, and {group}, the
    # provider's group id: the teams collection of one Cup group.
    cup_group_url: str | None = None
    # Template with {season} and {group}: the Cup table (the standings item
    # named "inseason") of one Cup group or Cup conference.
    cup_group_standings_url: str | None = None
    # Template with {season}, the end year of the season, and {team_id}, the
    # provider's team id: the current depth chart of one team.
    depth_chart_url: str | None = None
    # Template with {season}, the end year of the season, and {team_id}, the
    # provider's team id: the team object of one season, with its abbreviation,
    # display name, name, location and active state.
    season_team_url: str | None = None
    # Template with {season} and {team_id}: the roster collection of one team in
    # one season.
    season_roster_url: str | None = None
    # Template with {season}, the end year of the season, and {type}, the season
    # type (2 regular season, 5 play-in, 3 postseason): the start and end of that
    # season type.
    season_type_url: str | None = None
    # Template with {season}: the postseason leaders by category.
    postseason_leaders_url: str | None = None
    # Template with {season}, the end year of the season: the regular-season
    # leaders by category. The template's own query selects the regular season.
    season_leaders_url: str | None = None
    # Template with {season} and {team_id}, the provider's team id: the
    # postseason record of one team (overall, home and road).
    team_postseason_record_url: str | None = None
    # Template with {season} and {team_id}: the postseason statistics of one team.
    team_postseason_stats_url: str | None = None
    # Template with {season}: the awards of the season with their winners.
    season_awards_url: str | None = None
    # Listing of the official channel's uploads, without the key. The adapter
    # adds the page size and the page token.
    highlights_source_url: str | None = None
    # Key of the video source. Never logged or printed.
    highlights_source_key: SecretStr | None = None
    # Template with {video_id}, the channel's video id.
    video_embed_url: str | None = None
    # Template with {query}, the search words, already URL-encoded.
    highlights_search_url: str | None = None
    # The channel-scoped search endpoint of the same video API, without the key.
    # The adapter adds the query and the result count. Unset: no search runs.
    highlights_search_api_url: str | None = None
    # Searches the on-demand highlights search sends per US Eastern day.
    highlights_search_daily_cap: PositiveInt = 80
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

    @field_validator(*EXACT_PLACEHOLDERS)
    @classmethod
    def _require_exact_placeholders(
        cls, value: str | None, info: ValidationInfo
    ) -> str | None:
        # An empty value, as listed in .env.example, counts as unset here.
        if not value:
            return value
        expected = EXACT_PLACEHOLDERS[info.field_name or ""]
        found = {name for _, name, _, _ in string.Formatter().parse(value) if name}
        if found != expected:
            if not expected:
                raise ValueError("must contain no placeholder")
            names = ", ".join(f"{{{name}}}" for name in sorted(expected))
            raise ValueError(f"must contain only the {names} placeholder")
        return value

    @model_validator(mode="after")
    def _resolve_data_dir(self) -> Self:
        if not self.data_dir.is_absolute():
            self.data_dir = (API_DIR / self.data_dir).resolve()
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
