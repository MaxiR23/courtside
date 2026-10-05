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
#
# What is covered:
# - Happy path, value from the environment, value from a .env file, .env file location, invalid value, shared instance
#
# Run with: cd api && .venv/bin/python -m pytest tests/test_settings.py
#
# SEE: api/app/settings.py

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
        if name.lower() == "environment":
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
