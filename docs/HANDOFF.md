# Handoff

## Purpose

This repo contains a production-style Playwright scraper for authorized Chakra CRM/page extraction.

## First-Time Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
python -m playwright install chromium
cp .env.example .env
cp configs/chakra.example.yaml configs/chakra.local.yaml
```

## Required Local Edits

1. Update `.env` with Chakra URLs and allowed host.
2. Update `configs/chakra.local.yaml` with real list/detail selectors.
3. Run `chakra-scraper auth` to save local browser state.
4. Run `chakra-scraper validate-config --config configs/chakra.local.yaml`.
5. Test with `chakra-scraper scrape --config configs/chakra.local.yaml --limit 5`.

## Do Not Commit

- `.env`
- `configs/chakra.local.yaml` if it contains sensitive URLs
- `playwright/.auth/*`
- `output/*`

## Operational Run

```bash
chakra-scraper scrape --config configs/chakra.local.yaml --limit 100
```

## Outputs

- CSV: `output/chakra_export.csv`
- JSONL: `output/chakra_export.jsonl`
- collected links: `output/detail_links.txt`
- failures: `output/failures/`

## Troubleshooting

- Missing auth state: run `chakra-scraper auth`.
- Empty CSV fields: selectors are wrong; use snapshot mode.
- Blocked URL: update `allowed_hosts` only if the target host is approved.
- Timeout: increase `CHAKRA_TIMEOUT_MS` or improve `wait_for` selectors.
