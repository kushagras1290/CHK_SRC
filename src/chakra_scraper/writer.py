"""Output writers."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Iterable

from chakra_scraper.models import ScrapedRecord


def write_jsonl(path: Path, records: Iterable[ScrapedRecord]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file_obj:
        for record in records:
            file_obj.write(json.dumps(record.flatten(), ensure_ascii=False, default=str) + "\n")


def write_csv(path: Path, records: list[ScrapedRecord]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [record.flatten() for record in records]
    fieldnames = _fieldnames(rows)
    with path.open("w", encoding="utf-8", newline="") as file_obj:
        writer = csv.DictWriter(file_obj, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _fieldnames(rows: list[dict[str, object]]) -> list[str]:
    priority = ["source_url", "scraped_at", "page_title", "full_text_hash"]
    seen: set[str] = set(priority)
    discovered: list[str] = []
    for row in rows:
        for key in row:
            if key not in seen:
                discovered.append(key)
                seen.add(key)
    return priority + sorted(discovered)
