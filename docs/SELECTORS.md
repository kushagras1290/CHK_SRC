# Selector Guide

Use Playwright/CSS selectors from the live Chakra DOM. Prefer stable attributes first:

1. `data-testid`
2. `aria-label`
3. semantic role/text where stable
4. class names only if stable
5. XPath only when the layout is label/value heavy

## Recommended Flow

```bash
chakra-scraper auth
chakra-scraper snapshot --url "https://your-chakra-domain/leads" --out output/list_snapshot
```

Open `snapshot.html` and inspect rows/detail links.

## List Selectors

```yaml
list_selectors:
  row: "table tbody tr"
  detail_link: "a[href*='/lead']"
  next_button: "button:has-text('Next')"
  wait_for: "table tbody tr"
```

## Detail Selectors

```yaml
detail_selectors:
  wait_for: "body"
  fields:
    customer_name:
      selector: "[data-testid='customer-name']"
    phone:
      regex: "(?:Phone|Mobile)\\s*[:\\-]\\s*(\\+?[0-9][0-9\\s\-]{7,})"
```

## Extraction Priority

For each field, the scraper tries:

1. `selector`
2. `fallback_selectors`
3. `label`
4. `regex`
5. `default`

## Debugging

Run small first:

```bash
chakra-scraper scrape --config configs/chakra.local.yaml --limit 5
```

If fields are empty, inspect `snapshot.html` and tune selectors. If a page fails, check `output/failures/`.
