# api/tests/test_settings.py
#
# Tests for the application settings.
#
# Tested:
# - Defaults to development
# - Reads the environment from an environment variable
# - Rejects a value outside development and production
# - Reads the environment from a .env file
# - Reads its .env file from api/.env
# - Returns the same Settings instance on every call
# - Leaves the scoreboard URL unset by default
# - Reads the scoreboard URL from an environment variable
# - Leaves the game detail URL unset by default
# - Reads the game detail URL from an environment variable
# - Rejects a scoreboard URL without its {date} placeholder
# - Rejects a game detail URL without its {game_id} placeholder
# - Does not count an escaped placeholder
# - Rejects a malformed template without showing it
# - Accepts an empty template as unset
# - Leaves the player photo URL unset by default
# - Reads the player photo URL from an environment variable
# - Leaves the team roster URL unset by default
# - Reads the team roster URL from an environment variable
# - Leaves the team averages URL unset by default
# - Reads the team averages URL from an environment variable
# - Leaves the standings URL unset by default
# - Reads the standings URL from an environment variable
# - Leaves the team schedule URL unset by default
# - Reads the team schedule URL from an environment variable
# - Leaves the league injuries URL unset by default
# - Reads the league injuries URL from an environment variable
# - Leaves the highlights source URL unset by default
# - Reads the highlights source URL from an environment variable
# - Leaves the highlights source key unset by default
# - Reads the highlights source key from exactly HIGHLIGHTS_SOURCE_KEY
# - Never shows the highlights source key when printed
# - Leaves the video embed URL unset by default
# - Reads the video embed URL from an environment variable
# - Leaves the highlights search URL unset by default
# - Reads the highlights search URL from an environment variable
# - Defaults the daily fetch time to six in the morning
# - Reads the daily fetch time from an environment variable
# - Rejects an invalid daily fetch time
# - Validation errors do not include the input value
# - Defaults the data directory to api/data
# - Reads the data directory from an environment variable
# - Resolves a relative data directory against the api folder
# - Rejects an empty data directory
# - Allows no CORS origins by default
# - Reads the CORS origins as a JSON list
# - Ignores a retired setting in a .env file and warns without its value
# - Rejects an unknown key in a .env file that is not retired
#
# What is covered:
# - Happy path, value from the environment, value from a .env file, .env file location, invalid value, shared instance, optional scoreboard URL, optional game detail URL, required URL placeholders (missing, escaped, malformed, empty), optional player photo URL, optional team roster URL, optional team averages URL, optional standings, team schedule and league injuries URLs, optional highlights source URL and key (unset, environment, hidden when printed), video embed URL and highlights search URL, daily fetch time (default, environment, invalid), input hidden from errors, data directory (default, environment, relative, empty), CORS origins (default, JSON list), retired setting (dropped with a warning), unknown key (rejected)
#
# Run with: cd api && .venv/bin/python -m pytest tests/test_settings.py
#
# SEE: api/app/settings.py

import datetime as dt
import logging
import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from pydantic import ValidationError
from pydantic_settings import SettingsConfigDict

from app.settings import Settings, get_settings


class SettingsWithoutEnvFile(Settings):
    model_config = SettingsConfigDict(env_file=None)


@pytest.fixture(autouse=True)
def clear_environment_variable(monkeypatch: pytest.MonkeyPatch) -> None:
    # Settings matches variable names case-insensitively: clear every casing.
    for name in list(os.environ):
        if name.lower() in {
            "environment",
            "scoreboard_url",
            "game_detail_url",
            "player_photo_url",
            "team_roster_url",
            "team_averages_url",
            "player_averages_url",
            "standings_url",
            "team_schedule_url",
            "league_injuries_url",
            "highlights_source_url",
            "highlights_source_key",
            "video_embed_url",
            "highlights_search_url",
            "daily_fetch_time",
            "data_dir",
            "cors_origins",
        }:
            monkeypatch.delenv(name)


@pytest.fixture(autouse=True)
def clear_settings_cache() -> Iterator[None]:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_defaults_to_development_when_no_variable_is_set() -> None:
    assert SettingsWithoutEnvFile().environment == "development"


def test_reads_environment_from_the_environment_variable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ENVIRONMENT", "production")

    assert SettingsWithoutEnvFile().environment == "production"


def test_rejects_an_environment_outside_the_allowed_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ENVIRONMENT", "staging")

    with pytest.raises(ValidationError):
        SettingsWithoutEnvFile()


def test_reads_environment_from_a_dotenv_file(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("ENVIRONMENT=production\n", encoding="utf-8")

    class SettingsWithTemporaryEnvFile(Settings):
        model_config = SettingsConfigDict(env_file=env_file)

    assert SettingsWithTemporaryEnvFile().environment == "production"


def test_reads_its_dotenv_file_from_the_api_folder() -> None:
    api_dir = Path(__file__).resolve().parent.parent

    assert Settings.model_config.get("env_file") == api_dir / ".env"


def test_get_settings_returns_the_same_instance_on_every_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.settings.Settings", SettingsWithoutEnvFile)

    assert get_settings() is get_settings()


def test_scoreboard_url_is_unset_when_no_variable_is_set() -> None:
    assert SettingsWithoutEnvFile().scoreboard_url is None


def test_reads_the_scoreboard_url_from_the_environment_variable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SCOREBOARD_URL", "https://example.com/scoreboard/{date}")

    assert (
        SettingsWithoutEnvFile().scoreboard_url
        == "https://example.com/scoreboard/{date}"
    )


def test_game_detail_url_is_unset_when_no_variable_is_set() -> None:
    assert SettingsWithoutEnvFile().game_detail_url is None


def test_reads_the_game_detail_url_from_the_environment_variable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GAME_DETAIL_URL", "https://example.com/games/{game_id}")

    assert (
        SettingsWithoutEnvFile().game_detail_url
        == "https://example.com/games/{game_id}"
    )


def test_rejects_a_scoreboard_url_without_its_date_placeholder(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SCOREBOARD_URL", "https://example.com/hidden/scoreboard")

    with pytest.raises(ValidationError) as raised:
        SettingsWithoutEnvFile()

    assert "{date}" in str(raised.value)
    assert "example.com/hidden" not in str(raised.value)


def test_rejects_a_game_detail_url_without_its_game_id_placeholder(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GAME_DETAIL_URL", "https://example.com/hidden/game")

    with pytest.raises(ValidationError) as raised:
        SettingsWithoutEnvFile()

    assert "{game_id}" in str(raised.value)
    assert "example.com/hidden" not in str(raised.value)


def test_does_not_count_an_escaped_placeholder(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SCOREBOARD_URL", "https://example.com/hidden/{{date}}")

    with pytest.raises(ValidationError) as raised:
        SettingsWithoutEnvFile()

    assert "example.com/hidden" not in str(raised.value)


def test_rejects_a_malformed_template_without_showing_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SCOREBOARD_URL", "https://example.com/hidden/{date")

    with pytest.raises(ValidationError) as raised:
        SettingsWithoutEnvFile()

    assert "example.com/hidden" not in str(raised.value)


def test_accepts_an_empty_template_as_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SCOREBOARD_URL", "")
    monkeypatch.setenv("GAME_DETAIL_URL", "")

    settings = SettingsWithoutEnvFile()

    assert settings.scoreboard_url == ""
    assert settings.game_detail_url == ""


def test_player_photo_url_is_unset_when_no_variable_is_set() -> None:
    assert SettingsWithoutEnvFile().player_photo_url is None


def test_reads_the_player_photo_url_from_the_environment_variable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "PLAYER_PHOTO_URL", "https://example.com/players/{player_id}.png"
    )

    assert (
        SettingsWithoutEnvFile().player_photo_url
        == "https://example.com/players/{player_id}.png"
    )


def test_team_roster_url_is_unset_when_no_variable_is_set() -> None:
    assert SettingsWithoutEnvFile().team_roster_url is None


def test_reads_the_team_roster_url_from_the_environment_variable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TEAM_ROSTER_URL", "https://example.com/teams/{team}/roster")

    assert (
        SettingsWithoutEnvFile().team_roster_url
        == "https://example.com/teams/{team}/roster"
    )


def test_team_averages_url_is_unset_when_no_variable_is_set() -> None:
    assert SettingsWithoutEnvFile().team_averages_url is None


def test_reads_the_team_averages_url_from_the_environment_variable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "TEAM_AVERAGES_URL", "https://example.com/{season}/teams/{team}/leaders"
    )

    assert (
        SettingsWithoutEnvFile().team_averages_url
        == "https://example.com/{season}/teams/{team}/leaders"
    )


def test_player_averages_url_is_unset_when_no_variable_is_set() -> None:
    assert SettingsWithoutEnvFile().player_averages_url is None


def test_reads_the_player_averages_url_from_the_environment_variable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "PLAYER_AVERAGES_URL",
        "https://example.com/{season}/athletes/{player_id}/statistics",
    )

    assert (
        SettingsWithoutEnvFile().player_averages_url
        == "https://example.com/{season}/athletes/{player_id}/statistics"
    )


def test_standings_url_is_unset_when_no_variable_is_set() -> None:
    assert SettingsWithoutEnvFile().standings_url is None


def test_reads_the_standings_url_from_the_environment_variable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("STANDINGS_URL", "https://example.com/standings")

    assert SettingsWithoutEnvFile().standings_url == "https://example.com/standings"


def test_team_schedule_url_is_unset_when_no_variable_is_set() -> None:
    assert SettingsWithoutEnvFile().team_schedule_url is None


def test_reads_the_team_schedule_url_from_the_environment_variable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TEAM_SCHEDULE_URL", "https://example.com/teams/{team}/schedule")

    assert (
        SettingsWithoutEnvFile().team_schedule_url
        == "https://example.com/teams/{team}/schedule"
    )


def test_league_injuries_url_is_unset_when_no_variable_is_set() -> None:
    assert SettingsWithoutEnvFile().league_injuries_url is None


def test_reads_the_league_injuries_url_from_the_environment_variable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LEAGUE_INJURIES_URL", "https://example.com/injuries")

    assert (
        SettingsWithoutEnvFile().league_injuries_url == "https://example.com/injuries"
    )


def test_highlights_source_url_is_unset_when_no_variable_is_set() -> None:
    assert SettingsWithoutEnvFile().highlights_source_url is None


def test_reads_the_highlights_source_url_from_the_environment_variable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HIGHLIGHTS_SOURCE_URL", "https://example.com/uploads")

    assert (
        SettingsWithoutEnvFile().highlights_source_url == "https://example.com/uploads"
    )


def test_highlights_source_key_is_unset_when_no_variable_is_set() -> None:
    assert SettingsWithoutEnvFile().highlights_source_key is None


def test_reads_the_highlights_source_key_from_exactly_highlights_source_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HIGHLIGHTS_SOURCE_KEY", "test-key-value")

    key = SettingsWithoutEnvFile().highlights_source_key

    assert key is not None
    assert key.get_secret_value() == "test-key-value"


def test_never_shows_the_highlights_source_key_when_printed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HIGHLIGHTS_SOURCE_KEY", "test-key-value")
    settings = SettingsWithoutEnvFile()

    assert "test-key-value" not in repr(settings)
    assert "test-key-value" not in str(settings)
    assert "test-key-value" not in settings.model_dump_json()


def test_video_embed_url_is_unset_when_no_variable_is_set() -> None:
    assert SettingsWithoutEnvFile().video_embed_url is None


def test_reads_the_video_embed_url_from_the_environment_variable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("VIDEO_EMBED_URL", "https://example.com/e/{video_id}")

    assert (
        SettingsWithoutEnvFile().video_embed_url == "https://example.com/e/{video_id}"
    )


def test_highlights_search_url_is_unset_when_no_variable_is_set() -> None:
    assert SettingsWithoutEnvFile().highlights_search_url is None


def test_reads_the_highlights_search_url_from_the_environment_variable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HIGHLIGHTS_SEARCH_URL", "https://example.com/s?q={query}")

    assert (
        SettingsWithoutEnvFile().highlights_search_url
        == "https://example.com/s?q={query}"
    )


def test_defaults_the_daily_fetch_time_to_six_in_the_morning() -> None:
    assert SettingsWithoutEnvFile().daily_fetch_time == dt.time(6, 0)


def test_reads_the_daily_fetch_time_from_an_environment_variable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DAILY_FETCH_TIME", "07:30")

    assert SettingsWithoutEnvFile().daily_fetch_time == dt.time(7, 30)


def test_rejects_an_invalid_daily_fetch_time(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DAILY_FETCH_TIME", "25:00")

    with pytest.raises(ValidationError):
        SettingsWithoutEnvFile()


def test_validation_errors_do_not_include_the_input_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ENVIRONMENT", "https://example.com/hidden")

    with pytest.raises(ValidationError) as raised:
        SettingsWithoutEnvFile()

    assert "example.com/hidden" not in str(raised.value)


def test_data_dir_defaults_to_the_data_folder_in_api() -> None:
    api_dir = Path(__file__).resolve().parent.parent

    assert SettingsWithoutEnvFile().data_dir == api_dir / "data"


def test_reads_the_data_dir_from_the_environment_variable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))

    assert SettingsWithoutEnvFile().data_dir == tmp_path


def test_resolves_a_relative_data_dir_against_the_api_folder(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api_dir = Path(__file__).resolve().parent.parent
    monkeypatch.setenv("DATA_DIR", "state")

    assert SettingsWithoutEnvFile().data_dir == api_dir / "state"


def test_rejects_an_empty_data_dir(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATA_DIR", "")

    with pytest.raises(ValidationError):
        SettingsWithoutEnvFile()


def test_cors_origins_are_empty_when_no_variable_is_set() -> None:
    assert SettingsWithoutEnvFile().cors_origins == []


def test_reads_the_cors_origins_as_a_json_list(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CORS_ORIGINS", '["https://a.example","https://b.example"]')

    assert SettingsWithoutEnvFile().cors_origins == [
        "https://a.example",
        "https://b.example",
    ]


def test_ignores_a_retired_setting_in_a_dotenv_file_and_warns_without_its_value(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "VIDEO_THUMBNAIL_URL=https://example.com/hidden\n", encoding="utf-8"
    )

    class SettingsWithTemporaryEnvFile(Settings):
        model_config = SettingsConfigDict(env_file=env_file)

    with caplog.at_level(logging.WARNING, logger="app.settings"):
        settings = SettingsWithTemporaryEnvFile()

    assert not hasattr(settings, "video_thumbnail_url")
    assert len(caplog.records) == 1
    assert "VIDEO_THUMBNAIL_URL" in caplog.text
    assert "example.com/hidden" not in caplog.text


def test_rejects_an_unknown_key_in_a_dotenv_file_that_is_not_retired(
    tmp_path: Path,
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("NOT_A_SETTING=value\n", encoding="utf-8")

    class SettingsWithTemporaryEnvFile(Settings):
        model_config = SettingsConfigDict(env_file=env_file)

    with pytest.raises(ValidationError) as raised:
        SettingsWithTemporaryEnvFile()

    assert raised.value.errors()[0]["type"] == "extra_forbidden"
