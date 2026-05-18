"""Playwright browser lifecycle helpers."""

from __future__ import annotations

import logging
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from playwright.sync_api import Browser, BrowserContext, Page, Playwright, sync_playwright

from chakra_scraper.errors import AuthStateMissingError
from chakra_scraper.settings import Settings

logger = logging.getLogger(__name__)


@contextmanager
def browser_context(settings: Settings, *, require_auth_state: bool = True) -> Iterator[BrowserContext]:
    """Create an isolated Chromium context with optional persisted auth state."""

    state_path = settings.state_path
    if require_auth_state and not state_path.exists():
        raise AuthStateMissingError(
            f"Missing auth state: {state_path}. Run `chakra-scraper auth` first."
        )

    with sync_playwright() as playwright:
        browser = _launch_browser(playwright, settings)
        context_kwargs = {
            "viewport": {"width": 1440, "height": 1000},
            "accept_downloads": False,
        }
        if require_auth_state and state_path.exists():
            context_kwargs["storage_state"] = str(state_path)
        context = browser.new_context(**context_kwargs)
        context.set_default_timeout(settings.timeout_ms)
        context.set_default_navigation_timeout(settings.navigation_timeout_ms)
        logger.info("browser_context_started", extra={"headless": settings.headless})
        try:
            yield context
        finally:
            context.close()
            browser.close()
            logger.info("browser_context_closed")


def _launch_browser(playwright: Playwright, settings: Settings) -> Browser:
    return playwright.chromium.launch(headless=settings.headless, slow_mo=settings.slow_mo_ms)


def new_page(context: BrowserContext) -> Page:
    page = context.new_page()
    page.set_extra_http_headers({"DNT": "1"})
    return page


def save_auth_state(context: BrowserContext, state_path: Path) -> None:
    state_path.parent.mkdir(parents=True, exist_ok=True)
    context.storage_state(path=str(state_path))
    logger.info("auth_state_saved", extra={"state_path": str(state_path)})
