# api/tests/test_settings.py
#
# Tests for the application settings.
#
# Tested:
# - Defaults to development
# - Reads the environment from an environment variable
# - Rejects a value outside development and production
# - Returns the same Settings instance on every call
#
# What is covered:
# - Happy path, value from the environment, invalid value, shared instance
#
# Run with: cd api && .venv/bin/python -m pytest tests/test_settings.py
#
# SEE: api/app/settings.py

from collections.abc import Iterator

import pytest
from pydantic import ValidationError
from pydantic_settings import SettingsConfigDict

from app.settings import Settings, get_settings


class SettingsWithoutEnvFile(Settings):
    model_config = SettingsConfigDict(env_file=None)


@pytest.fixture(autouse=True)
def clear_settings_cache() -> Iterator[None]:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_defaults_to_development_when_no_variable_is_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ENVIRONMENT", raising=False)

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


def test_get_settings_returns_the_same_instance_on_every_call() -> None:
    assert get_settings() is get_settings()
