import pytest
from pydantic import ValidationError

from app.config import get_settings
from app.config import Settings


def test_default_configuration_is_available() -> None:
    get_settings.cache_clear()
    settings = get_settings()

    assert settings.app_name == "Data Engineering Learning Coach"
    assert settings.database_url.startswith("sqlite")
    assert settings.environment == "development"
    assert settings.llm_api_key is None


def test_production_requires_llm_api_key() -> None:
    with pytest.raises(ValidationError, match="LLM_API_KEY"):
        Settings(environment="production", database_url="sqlite:///./data/test.db")


def test_configuration_rejects_invalid_environment() -> None:
    with pytest.raises(ValidationError, match="environment"):
        Settings(environment="local", database_url="sqlite:///./data/test.db")


def test_configuration_rejects_blank_database_url() -> None:
    with pytest.raises(ValidationError, match="DATABASE_URL"):
        Settings(database_url="   ")
