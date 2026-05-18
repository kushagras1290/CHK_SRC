# Security Notes

## Boundaries

This scraper is only for Chakra pages you are authorized to access. It does not bypass login, MFA, CAPTCHA, rate limits, paywalls, or authorization.

## Secrets

Never commit:

- `.env`
- `playwright/.auth/*`
- exported customer data
- screenshots or HTML snapshots containing CRM data

## Runtime Controls

- Use `allowed_hosts` in config to prevent accidental external scraping.
- Use a dedicated Chakra/service account if available.
- Restrict output directory permissions.
- Apply retention/deletion policy to `output/` and `output/failures/`.

## Data Handling

Failure snapshots can include customer PII. Treat them like production customer data.

## Operational Checks

Before production use:

1. Verify selectors on non-sensitive sample records.
2. Run a small limit first: `--limit 5`.
3. Validate CSV/JSONL output manually.
4. Delete snapshot artifacts after selector debugging.
