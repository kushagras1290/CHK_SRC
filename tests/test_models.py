from pathlib import Path

import pytest

from chakra_scraper.errors import SafetyBoundaryError
from chakra_scraper.models import ScraperConfig


CONFIG_YAML = """
name: test
list_url: "https://chakra.example.com/leads"
allowed_hosts: ["chakra.example.com"]
output_basename: "test_export"
max_pages: 2
list_selectors:
  row: "tr"
  detail_link: "a"
detail_selectors:
  fields:
    name:
      label: "Name"
"""


def test_config_loads_and_validates(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text(CONFIG_YAML, encoding="utf-8")

    config = ScraperConfig.from_file(path)

    assert config.name == "test"
    assert config.allowed_hosts == ["chakra.example.com"]
    assert config.list_selectors.row == "tr"


def test_ensure_safe_url_blocks_external_host(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text(CONFIG_YAML, encoding="utf-8")
    config = ScraperConfig.from_file(path)

    with pytest.raises(SafetyBoundaryError):
        config.ensure_safe_url("https://evil.example/steal")


def test_ensure_safe_url_absolutizes_relative_url(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text(CONFIG_YAML, encoding="utf-8")
    config = ScraperConfig.from_file(path)

    assert config.ensure_safe_url("/lead/123") == "https://chakra.example.com/lead/123"
