"""Environment-backed application configuration."""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

Environment = Literal["development", "staging", "production"]


class Settings(BaseModel):
    """Runtime settings loaded from environment variables."""

    app_name: str = Field(default="Data Engineering Learning Coach")
    environment: Environment = Field(default="development")
    database_url: str = Field(default="sqlite:///./data/learning_coach.db")
    llm_api_key: str | None = Field(default=None)
    gemini_api_key: str | None = Field(default=None)
    gemini_model: str = Field(default="gemini-2.5-flash")
    log_level: str = Field(default="INFO")

    @field_validator("environment", mode="before")
    @classmethod
    def normalize_environment(cls, value: str) -> str:
        """Normalize environment names before validating the allowed values."""
        if not isinstance(value, str):
            raise ValueError("ENVIRONMENT must be a string")
        return value.strip().lower()

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: str) -> str:
        """Require a non-empty SQLAlchemy database URL."""
        value = value.strip()
        if not value or "://" not in value:
            raise ValueError("DATABASE_URL must be a valid SQLAlchemy database URL")
        return value

    @field_validator("llm_api_key", mode="before")
    @classmethod
    def normalize_llm_api_key(cls, value: str | None) -> str | None:
        """Treat an unset or blank API key as absent without inventing a secret."""
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError("LLM_API_KEY must be a string")
        value = value.strip()
        return value or None

    @field_validator("gemini_api_key", mode="before")
    @classmethod
    def normalize_gemini_api_key(cls, value: str | None) -> str | None:
        """Treat an unset or blank Gemini API key as absent."""
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError("GEMINI_API_KEY must be a string")
        value = value.strip()
        return value or None

    @field_validator("gemini_model")
    @classmethod
    def validate_gemini_model(cls, value: str) -> str:
        """Require a non-empty Gemini model name."""
        value = value.strip()
        if not value:
            raise ValueError("GEMINI_MODEL must not be blank")
        return value

    @model_validator(mode="after")
    def validate_production_requirements(self) -> "Settings":
        """Require credentials needed to run the production environment."""
        if self.environment == "production" and not self.llm_api_key:
            raise ValueError("LLM_API_KEY is required when ENVIRONMENT is production")
        return self


@lru_cache
def get_settings() -> Settings:
    """Return a cached settings object for the current process."""
    return Settings(
        app_name=os.getenv("APP_NAME", "Data Engineering Learning Coach"),
        environment=os.getenv("ENVIRONMENT", "development"),
        database_url=os.getenv("DATABASE_URL", "sqlite:///./data/learning_coach.db"),
        llm_api_key=os.getenv("LLM_API_KEY"),
        gemini_api_key=os.getenv("GEMINI_API_KEY"),
        gemini_model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
    )
