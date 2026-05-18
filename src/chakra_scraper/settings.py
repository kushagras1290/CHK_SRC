"""Environment-backed runtime settings."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings loaded from env vars and optional .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="CHAKRA_",
        extra="ignore",
        case_sensitive=False,
    )

    login_url: str = ""
    default_list_url: str = ""
    allowed_hosts: list[str] = Field(default_factory=list)
    state_path: Path = Path("playwright/.auth/chakra_state.json")
    output_dir: Path = Path("output")
    headless: bool = True
    slow_mo_ms: Annotated[int, Field(ge=0, le=3000)] = 0
    timeout_ms: Annotated[int, Field(ge=5000, le=120000)] = 30_000
    navigation_timeout_ms: Annotated[int, Field(ge=5000, le=180000)] = 45_000
    min_delay_ms: Annotated[int, Field(ge=0, le=60000)] = 700
    max_delay_ms: Annotated[int, Field(ge=0, le=60000)] = 1800
    max_retries: Annotated[int, Field(ge=0, le=5)] = 2
    log_level: str = "INFO"

    @field_validator("allowed_hosts", mode="before")
    @classmethod
    def parse_allowed_hosts(cls, value: object) -> list[str]:
        if value is None or value == "":
            return []
        if isinstance(value, str):
            return [host.strip().lower() for host in value.split(",") if host.strip()]
        if isinstance(value, list):
            return [str(host).strip().lower() for host in value if str(host).strip()]
        raise TypeError("allowed_hosts must be a comma-separated string or list")

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, value: str) -> str:
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        normalized = value.upper()
        if normalized not in allowed:
            raise ValueError(f"log_level must be one of {sorted(allowed)}")
        return normalized

    @field_validator("max_delay_ms")
    @classmethod
    def validate_delay_range(cls, value: int, info: object) -> int:
        data = getattr(info, "data", {})
        min_delay = data.get("min_delay_ms", 0)
        if value < min_delay:
            raise ValueError("max_delay_ms must be >= min_delay_ms")
        return value
