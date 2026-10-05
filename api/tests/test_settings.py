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
# - Leaves the player photo URL unset by default
# - Reads the player photo URL from an environment variable
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
#
# What is covered:
# - Happy path, value from the environment, value from a .env file, .env file location, invalid value, shared instance, optional scoreboard URL, optional game detail URL, optional player photo URL, daily fetch time (default, environment, invalid), input hidden from errors, data directory (default, environment, relative, empty), CORS origins (default, JSON list)
#
# Run with: cd api && .venv/bin/python -m pytest tests/test_settings.py
#
# SEE: api/app/settings.py

import datetime as dt
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
