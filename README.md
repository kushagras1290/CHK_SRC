# Chakra Page Scraper 

A config-driven, Playwright-based scraper for **authorized** Chakra CRM/page extraction.

This is built for pages that require browser login, JavaScript rendering, and detail-page extraction. It does **not** bypass authentication, CAPTCHA, paywalls, or access controls. Use it only for systems you are authorized to access.

## What This Scrapes

Default output fields are configurable, but the starter config targets common Chakra/CRM lead details:

- lead/customer ID
- customer name
- phone
- email
- status
- owner
- created/updated timestamps
- order/BOT number
- gemstone
- carat/weight
- budget
- comments/remarks
- source URL
- scrape timestamp
- page title
- full page text hash for audit/deduplication

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
python -m playwright install chromium
cp .env.example .env
cp configs/chakra.example.yaml configs/chakra.local.yaml
```

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
python -m playwright install chromium
copy .env.example .env
copy configs\chakra.example.yaml configs\chakra.local.yaml
```

Edit `.env` and `configs/chakra.local.yaml` with the real Chakra URL, allowed host, and selectors.

## Login Once

```bash
chakra-scraper auth
```

This saves the Playwright session to `playwright/.auth/chakra_state.json`. Do not commit it.

## Validate Config

```bash
chakra-scraper validate-config --config configs/chakra.local.yaml
```

## Snapshot for Selector Debugging

```bash
chakra-scraper snapshot --url "https://your-chakra-domain/leads" --out output/list_snapshot
```

## Collect Links

```bash
chakra-scraper collect-links --config configs/chakra.local.yaml --limit 100
```

## Scrape

```bash
chakra-scraper scrape --config configs/chakra.local.yaml --limit 100
```

Outputs:

```text
output/chakra_export.csv
output/chakra_export.jsonl
output/detail_links.txt
output/failures/*.png
output/failures/*.html
```

## Docker

```bash
docker build -t chakra-page-scraper:local .
docker run --rm -v "$PWD:/app" chakra-page-scraper:local validate-config --config configs/chakra.local.yaml
```

## Quality Gates

```bash
ruff check .
ruff format --check .
mypy
pytest
```

## Security Notes

- No credentials are hardcoded.
- Session state is ignored by Git.
- Allowed-host checks block accidental external scraping.
- Logs redact common secret/token/cookie keys.
- Failure snapshots may contain customer data; store and delete them carefully.
- This tool does not bypass login, MFA, CAPTCHA, or authorization.

## Known Limitations

- Real Chakra selectors must be configured from the live DOM or captured snapshots.
- SPA rows without real `href` links may need a custom click-through collector.
- If Chakra changes UI labels/selectors, update `configs/chakra.local.yaml`.
