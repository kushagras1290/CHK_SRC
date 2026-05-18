"""CLI entrypoint for Chakra scraper."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from pydantic import ValidationError

from chakra_scraper.browser import browser_context, new_page, save_auth_state
from chakra_scraper.errors import ChakraScraperError
from chakra_scraper.extractor import ChakraExtractor, read_links_file, write_debug_links
from chakra_scraper.logging_config import configure_logging
from chakra_scraper.models import ScraperConfig
from chakra_scraper.settings import Settings
from chakra_scraper.writer import write_csv, write_jsonl

logger = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="chakra-scraper",
        description="Authorized Chakra CRM/page scraper using Playwright.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    auth = subparsers.add_parser("auth", help="Open a browser and save manual login storage state.")
    auth.add_argument("--login-url", default=None, help="Override CHAKRA_LOGIN_URL.")
    auth.add_argument("--headless", action="store_true", help="Run auth browser headless. Usually false.")

    validate = subparsers.add_parser("validate-config", help="Validate selector YAML config.")
    validate.add_argument("--config", type=Path, required=True)

    collect = subparsers.add_parser("collect-links", help="Collect detail URLs from listing pages only.")
    collect.add_argument("--config", type=Path, required=True)
    collect.add_argument("--limit", type=int, default=None)
    collect.add_argument("--links-out", type=Path, default=Path("output/detail_links.txt"))

    scrape = subparsers.add_parser("scrape", help="Collect links and scrape detail pages.")
    scrape.add_argument("--config", type=Path, required=True)
    scrape.add_argument("--limit", type=int, default=None)
    scrape.add_argument("--links-file", type=Path, default=None, help="Reuse a collected links file.")
    scrape.add_argument("--csv", action="store_true", default=True, help="Write CSV output.")
    scrape.add_argument("--jsonl", action="store_true", default=True, help="Write JSONL output.")

    snapshot = subparsers.add_parser("snapshot", help="Save screenshot and HTML for selector building.")
    snapshot.add_argument("--url", required=True)
    snapshot.add_argument("--out", type=Path, default=Path("output/snapshot"))

    return parser


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        settings = Settings()
        configure_logging(settings.log_level)
        return dispatch(args, settings)
    except (ValidationError, ChakraScraperError) as exc:
        configure_logging("INFO")
        logger.error("command_failed", extra={"error": str(exc)})
        return 2
    except KeyboardInterrupt:
        logger.warning("interrupted_by_user")
        return 130


def dispatch(args: argparse.Namespace, settings: Settings) -> int:
    match args.command:
        case "auth":
            return run_auth(args, settings)
        case "validate-config":
            return run_validate_config(args)
        case "collect-links":
            return run_collect_links(args, settings)
        case "scrape":
            return run_scrape(args, settings)
        case "snapshot":
            return run_snapshot(args, settings)
        case _:
            raise ChakraScraperError(f"Unsupported command: {args.command}")


def run_auth(args: argparse.Namespace, settings: Settings) -> int:
    login_url = args.login_url or settings.login_url
    if not login_url:
        raise ChakraScraperError("CHAKRA_LOGIN_URL or --login-url is required")

    auth_settings = settings.model_copy(update={"headless": args.headless})
    with browser_context(auth_settings, require_auth_state=False) as context:
        page = new_page(context)
        page.goto(login_url, wait_until="domcontentloaded")
        print(
            "\nComplete Chakra/Google login in the opened browser, then return here and press Enter.\n"
            "Do not share the generated storage-state file.\n",
            file=sys.stderr,
        )
        input("Press Enter after login is complete: ")
        save_auth_state(context, settings.state_path)
    return 0


def run_validate_config(args: argparse.Namespace) -> int:
    config = ScraperConfig.from_file(args.config)
    logger.info("config_valid", extra={"name": config.name, "list_url": config.list_url})
    print(f"Valid config: {args.config}")
    return 0


def run_collect_links(args: argparse.Namespace, settings: Settings) -> int:
    config = ScraperConfig.from_file(args.config)
    extractor = ChakraExtractor(config, settings)
    with browser_context(settings, require_auth_state=True) as context:
        page = new_page(context)
        links = extractor.collect_detail_links(page, limit=args.limit)
    write_debug_links(args.links_out, links)
    logger.info("links_written", extra={"count": len(links), "path": str(args.links_out)})
    print(f"Collected {len(links)} links -> {args.links_out}")
    return 0


def run_scrape(args: argparse.Namespace, settings: Settings) -> int:
    config = ScraperConfig.from_file(args.config)
    extractor = ChakraExtractor(config, settings)
    settings.output_dir.mkdir(parents=True, exist_ok=True)

    with browser_context(settings, require_auth_state=True) as context:
        page = new_page(context)
        if args.links_file:
            links = [config.ensure_safe_url(url) for url in read_links_file(args.links_file)]
        else:
            links = extractor.collect_detail_links(page, limit=args.limit)
        write_debug_links(settings.output_dir / "detail_links.txt", links)
        records = extractor.scrape_detail_pages(page, links)

    csv_path = settings.output_dir / f"{config.output_basename}.csv"
    jsonl_path = settings.output_dir / f"{config.output_basename}.jsonl"
    if args.csv:
        write_csv(csv_path, records)
    if args.jsonl:
        write_jsonl(jsonl_path, records)
    logger.info(
        "scrape_completed",
        extra={"links": len(links), "records": len(records), "csv": str(csv_path), "jsonl": str(jsonl_path)},
    )
    print(f"Scraped {len(records)}/{len(links)} records")
    print(f"CSV:   {csv_path}")
    print(f"JSONL: {jsonl_path}")
    return 0


def run_snapshot(args: argparse.Namespace, settings: Settings) -> int:
    out_dir = args.out
    out_dir.mkdir(parents=True, exist_ok=True)
    with browser_context(settings, require_auth_state=True) as context:
        page = new_page(context)
        try:
            page.goto(args.url, wait_until="domcontentloaded")
            page.screenshot(path=str(out_dir / "snapshot.png"), full_page=True)
            (out_dir / "snapshot.html").write_text(page.content(), encoding="utf-8")
            (out_dir / "snapshot.txt").write_text(page.locator("body").inner_text(), encoding="utf-8")
        except PlaywrightTimeoutError as exc:
            raise ChakraScraperError(f"Snapshot timed out for {args.url}") from exc
    print(f"Snapshot written to {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
