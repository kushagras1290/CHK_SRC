"""Extraction engine for Chakra-like dynamic pages."""

from __future__ import annotations

import logging
import random
import re
import time
from pathlib import Path
from typing import Iterable

from playwright.sync_api import Locator, Page, TimeoutError as PlaywrightTimeoutError

from chakra_scraper.errors import ExtractionError, SafetyBoundaryError
from chakra_scraper.models import FieldRule, ScrapedRecord, ScraperConfig
from chakra_scraper.settings import Settings

logger = logging.getLogger(__name__)

_WHITESPACE_RE = re.compile(r"\s+")


class ChakraExtractor:
    """Config-driven extractor for listing pages and detail pages."""

    def __init__(self, config: ScraperConfig, settings: Settings) -> None:
        self.config = config
        self.settings = settings

    def collect_detail_links(self, page: Page, *, limit: int | None) -> list[str]:
        """Collect detail links from paginated list pages."""

        links: list[str] = []
        seen: set[str] = set()
        page.goto(self.config.list_url, wait_until="domcontentloaded")
        if self.config.list_selectors.wait_for:
            page.locator(self.config.list_selectors.wait_for).first.wait_for(state="visible")

        for page_number in range(1, self.config.max_pages + 1):
            logger.info("list_page_extract_started", extra={"page_number": page_number})
            self._sleep_between_actions()
            if self._is_empty_state(page):
                logger.info("list_empty_state_detected", extra={"page_number": page_number})
                break

            row_locator = page.locator(self.config.list_selectors.row)
            row_count = row_locator.count()
            logger.info(
                "list_rows_detected",
                extra={"page_number": page_number, "row_count": row_count},
            )

            for row_index in range(row_count):
                row = row_locator.nth(row_index)
                link = self._extract_link_from_row(row)
                if not link:
                    continue
                try:
                    safe_url = self.config.ensure_safe_url(link)
                except SafetyBoundaryError as exc:
                    logger.warning("detail_link_blocked", extra={"url": link, "error": str(exc)})
                    continue
                if safe_url not in seen:
                    seen.add(safe_url)
                    links.append(safe_url)
                if limit is not None and len(links) >= limit:
                    logger.info("detail_link_limit_reached", extra={"limit": limit})
                    return links

            if not self._goto_next_page(page):
                break

        return links

    def scrape_detail_pages(self, page: Page, urls: Iterable[str]) -> list[ScrapedRecord]:
        """Scrape each detail page with retries and failure snapshots."""

        records: list[ScrapedRecord] = []
        for index, url in enumerate(urls, start=1):
            logger.info("detail_scrape_started", extra={"index": index, "url": url})
            try:
                record = self._scrape_one_with_retries(page, url)
            except ExtractionError as exc:
                logger.error("detail_scrape_failed", extra={"url": url, "error": str(exc)})
                continue
            records.append(record)
            logger.info("detail_scrape_completed", extra={"index": index, "url": url})
        return records

    def _scrape_one_with_retries(self, page: Page, url: str) -> ScrapedRecord:
        last_error: Exception | None = None
        for attempt in range(self.settings.max_retries + 1):
            try:
                self._sleep_between_actions()
                return self._scrape_one(page, url)
            except Exception as exc:  # noqa: BLE001 - converted to domain error after retry budget
                last_error = exc
                logger.warning(
                    "detail_scrape_attempt_failed",
                    extra={"url": url, "attempt": attempt + 1, "error": str(exc)},
                )
                self._capture_failure_snapshot(page, url=url, attempt=attempt + 1)
                self._backoff(attempt)
        raise ExtractionError(f"Failed scraping {url}: {last_error}") from last_error

    def _scrape_one(self, page: Page, url: str) -> ScrapedRecord:
        page.goto(url, wait_until="domcontentloaded")
        wait_for = self.config.detail_selectors.wait_for
        if wait_for:
            page.locator(wait_for).first.wait_for(state="visible")

        data: dict[str, str | None] = {}
        missing_required: list[str] = []
        for field_name, rule in self.config.detail_selectors.fields.items():
            value = self.extract_field(page, rule)
            if value is None and rule.required:
                missing_required.append(field_name)
            data[field_name] = value

        if missing_required:
            raise ExtractionError(f"Missing required fields: {', '.join(missing_required)}")

        title = page.title() if self.config.detail_selectors.include_page_title else None
        page_text = page.locator("body").inner_text(timeout=self.settings.timeout_ms)
        return ScrapedRecord.from_parts(
            source_url=url,
            data=data,
            page_title=title,
            page_text=page_text if self.config.detail_selectors.include_full_text_hash else None,
        )

    def extract_field(self, page: Page, rule: FieldRule) -> str | None:
        """Extract a field using selector, label, regex, or default fallback."""

        candidates: list[str] = []
        if rule.selector:
            candidates.append(rule.selector)
        candidates.extend(rule.fallback_selectors)

        for selector in candidates:
            value = self._extract_by_selector(page, selector, attr=rule.attr)
            if value:
                return self._normalize(value, rule.normalize_whitespace)

        if rule.label:
            value = self._extract_by_label(page, rule.label)
            if value:
                return self._normalize(value, rule.normalize_whitespace)

        if rule.regex:
            body = page.locator("body").inner_text(timeout=self.settings.timeout_ms)
            match = re.search(rule.regex, body, flags=re.IGNORECASE | re.MULTILINE)
            if match:
                group = match.group(1) if match.groups() else match.group(0)
                return self._normalize(group, rule.normalize_whitespace)

        return rule.default

    def _extract_by_selector(self, page: Page, selector: str, *, attr: str | None) -> str | None:
        locator = page.locator(selector).first
        try:
            if locator.count() == 0:
                return None
            if attr:
                return locator.get_attribute(attr)
            return locator.inner_text(timeout=self.settings.timeout_ms)
        except PlaywrightTimeoutError:
            return None

    def _extract_by_label(self, page: Page, label: str) -> str | None:
        escaped_label = re.escape(label.strip())
        candidates = [
            f"xpath=//*[normalize-space()='{label}']/following::*[normalize-space()][1]",
            f"xpath=//td[normalize-space()='{label}']/following-sibling::td[1]",
            f"xpath=//*[matches(normalize-space(), '^{escaped_label}$', 'i')]/following::*[normalize-space()][1]",
        ]
        for selector in candidates:
            try:
                locator = page.locator(selector).first
                if locator.count() == 0:
                    continue
                value = locator.inner_text(timeout=self.settings.timeout_ms)
                if value and value.strip().lower() != label.strip().lower():
                    return value
            except Exception:  # noqa: BLE001 - XPath engines vary; fallback continues
                continue
        return self._extract_label_from_text(page, label)

    def _extract_label_from_text(self, page: Page, label: str) -> str | None:
        body = page.locator("body").inner_text(timeout=self.settings.timeout_ms)
        pattern = re.compile(rf"{re.escape(label)}\s*[:\-]\s*(.+)", flags=re.IGNORECASE)
        match = pattern.search(body)
        if not match:
            return None
        return match.group(1).splitlines()[0]

    def _extract_link_from_row(self, row: Locator) -> str | None:
        link = row.locator(self.config.list_selectors.detail_link).first
        try:
            if link.count() == 0:
                return None
            href = link.get_attribute("href")
            if href:
                return href
            logger.warning("detail_link_missing_href", extra={"text": link.inner_text(timeout=3000)})
            return None
        except PlaywrightTimeoutError:
            return None

    def _goto_next_page(self, page: Page) -> bool:
        selector = self.config.list_selectors.next_button
        if not selector:
            return False
        next_button = page.locator(selector).first
        if next_button.count() == 0:
            return False
        disabled_selector = self.config.list_selectors.next_button_disabled
        if disabled_selector and page.locator(disabled_selector).count() > 0:
            return False
        try:
            next_button.click()
            if self.config.list_selectors.wait_for:
                page.locator(self.config.list_selectors.wait_for).first.wait_for(state="visible")
            return True
        except PlaywrightTimeoutError:
            return False

    def _is_empty_state(self, page: Page) -> bool:
        selector = self.config.list_selectors.empty_state
        return bool(selector and page.locator(selector).count() > 0)

    def _capture_failure_snapshot(self, page: Page, *, url: str, attempt: int) -> None:
        output_dir = self.settings.output_dir / "failures"
        output_dir.mkdir(parents=True, exist_ok=True)
        safe_name = re.sub(r"[^a-zA-Z0-9_.-]+", "_", url)[:120]
        base = output_dir / f"failure_attempt_{attempt}_{safe_name}"
        try:
            page.screenshot(path=str(base.with_suffix(".png")), full_page=True)
            base.with_suffix(".html").write_text(page.content(), encoding="utf-8")
        except Exception as exc:  # noqa: BLE001 - snapshot failure must not hide root cause
            logger.warning("failure_snapshot_failed", extra={"error": str(exc)})

    def _sleep_between_actions(self) -> None:
        min_ms = self.settings.min_delay_ms
        max_ms = self.settings.max_delay_ms
        if max_ms <= 0:
            return
        time.sleep(random.randint(min_ms, max_ms) / 1000)  # noqa: S311 - not security-sensitive

    def _backoff(self, attempt: int) -> None:
        time.sleep(min(2**attempt, 8))

    @staticmethod
    def _normalize(value: str | None, enabled: bool) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return _WHITESPACE_RE.sub(" ", stripped) if enabled else stripped


def write_debug_links(path: Path, links: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(links), encoding="utf-8")


def read_links_file(path: Path) -> list[str]:
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
