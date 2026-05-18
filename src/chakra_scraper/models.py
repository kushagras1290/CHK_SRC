"""Validated config and domain models."""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urljoin, urlparse

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator

from chakra_scraper.errors import ConfigError, SafetyBoundaryError

SelectorType = Literal["css", "text", "label", "regex"]


class FieldRule(BaseModel):
    """How to extract a single field from a detail page."""

    selector: str | None = None
    label: str | None = None
    regex: str | None = None
    attr: str | None = None
    required: bool = False
    fallback_selectors: list[str] = Field(default_factory=list)
    normalize_whitespace: bool = True
    default: str | None = None

    @model_validator(mode="after")
    def validate_rule(self) -> FieldRule:
        if not any([self.selector, self.label, self.regex, self.default is not None]):
            raise ValueError("field rule needs selector, label, regex, or default")
        return self


class ListSelectors(BaseModel):
    """Selectors used on the listing/search result page."""

    container: str | None = None
    row: str
    detail_link: str
    next_button: str | None = None
    next_button_disabled: str | None = None
    empty_state: str | None = None
    wait_for: str | None = None


class DetailSelectors(BaseModel):
    """Selectors used on the detail page."""

    wait_for: str | None = None
    fields: dict[str, FieldRule]
    include_full_text_hash: bool = True
    include_page_title: bool = True

    @field_validator("fields")
    @classmethod
    def validate_field_names(cls, value: dict[str, FieldRule]) -> dict[str, FieldRule]:
        if not value:
            raise ValueError("at least one detail field is required")
        for field_name in value:
            if not field_name.replace("_", "").isalnum():
                raise ValueError(f"invalid field name: {field_name}")
        return value


class ScraperConfig(BaseModel):
    """Full selector/config file."""

    name: str = "chakra"
    list_url: str
    allowed_hosts: list[str] = Field(default_factory=list)
    output_basename: str = "chakra_export"
    max_pages: int = Field(default=10, ge=1, le=5000)
    list_selectors: ListSelectors
    detail_selectors: DetailSelectors
    block_external_links: bool = True

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

    @field_validator("output_basename")
    @classmethod
    def validate_output_basename(cls, value: str) -> str:
        safe = value.strip().replace(" ", "_")
        if not safe or "/" in safe or "\\" in safe or safe.startswith("."):
            raise ValueError("output_basename must be a safe filename stem")
        return safe

    @model_validator(mode="after")
    def derive_allowed_hosts(self) -> ScraperConfig:
        parsed = urlparse(self.list_url)
        if parsed.hostname and not self.allowed_hosts:
            self.allowed_hosts = [parsed.hostname.lower()]
        return self

    @classmethod
    def from_file(cls, path: Path) -> ScraperConfig:
        if not path.exists():
            raise ConfigError(f"Config file does not exist: {path}")
        raw = path.read_text(encoding="utf-8")
        try:
            data = yaml.safe_load(raw)
        except yaml.YAMLError as exc:
            raise ConfigError(f"Invalid YAML config: {path}") from exc
        if not isinstance(data, dict):
            raise ConfigError("Config root must be a mapping/object")
        return cls.model_validate(data)

    def ensure_safe_url(self, url: str) -> str:
        normalized = absolutize_url(self.list_url, url)
        parsed = urlparse(normalized)
        host = (parsed.hostname or "").lower()
        if parsed.scheme not in {"http", "https"}:
            raise SafetyBoundaryError(f"Unsupported URL scheme for {normalized!r}")
        if self.block_external_links and self.allowed_hosts and host not in self.allowed_hosts:
            raise SafetyBoundaryError(
                f"Blocked URL outside allowed hosts: host={host!r}, allowed={self.allowed_hosts!r}"
            )
        return normalized


def absolutize_url(base_url: str, maybe_relative: str) -> str:
    return urljoin(base_url, maybe_relative.strip())


class ScrapedRecord(BaseModel):
    """One extracted record."""

    source_url: str
    scraped_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    data: dict[str, str | None]
    page_title: str | None = None
    full_text_hash: str | None = None

    @classmethod
    def from_parts(
        cls,
        *,
        source_url: str,
        data: dict[str, str | None],
        page_title: str | None,
        page_text: str | None,
    ) -> ScrapedRecord:
        return cls(
            source_url=source_url,
            data=data,
            page_title=page_title,
            full_text_hash=sha256(page_text.encode("utf-8")).hexdigest() if page_text else None,
        )

    def flatten(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "source_url": self.source_url,
            "scraped_at": self.scraped_at,
            "page_title": self.page_title,
            "full_text_hash": self.full_text_hash,
        }
        payload.update(self.data)
        return payload
