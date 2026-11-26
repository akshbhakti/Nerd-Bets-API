# Nerd Bets API gateway — deployment starter v0.1

This is a **capture prototype**, not a production-certified scan, external website, or running service. It does not execute the frozen NFL models, import a real FanDuel snapshot, or construct betting tickets.

## Run locally or on a network-enabled server

```
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
export ODDS_API_KEY='<from secret manager>'
export ADMIN_TOKEN='<long random value>'
export DATA_DIR='./data'
uvicorn app:app --host 127.0.0.1 --port 8000
```

`GET /health` reports configuration (not provider connectivity). To request an actual capture, submit `POST /capture/NFL` or `/capture/NBA` with header `Authorization: Bearer <ADMIN_TOKEN>` over HTTPS. Never expose the token or the odds API key in a browser script or source control. Provider requests use its key as a URL query parameter; the gateway intentionally never logs full provider request URLs.

## Behavior and limitations

* Calls The Odds API v4 `/events`, then per-event `/markets` and `/odds` endpoints using FanDuel as bookmaker.
* Captures only events with future commence times, saves raw quote data, request-count, quota headers, event metadata and SHA-256 into a local JSON plus SQLite audit ledger.
* Differentiates DNS/network failure, authentication, provider access/subscription, rate limiting and general HTTP errors.
* Queries recently observed markets in batches of 10. **A market absent from the event-markets endpoint may still exist**. The model's full-market completeness gate MUST remain blocked until coverage is independently reconciled to a configured approved market inventory and all batches return correctly.
* Does not schedule itself, and SQLite/local disk is not durable on most ephemeral cloud hosts. For production, migrate to managed PostgreSQL and object storage and add managed job queue, alerting, encrypted secrets, TLS, per-user authorization, retries with durable idempotency, and host-level monitoring.
* Does not assume model probabilities, show EV, generate Monte Carlo results or publish wagers.

## Deployment steps

1. Use a network-enabled host; set ODDS_API_KEY and ADMIN_TOKEN as host secrets.
2. Install dependencies and deploy `uvicorn app:app --host 0.0.0.0 --port $PORT` behind HTTPS and private authentication.
3. Test health, capture, quotes, quota, logs and fail-closed paths on a known event. Confirm provider's event-market coverage separately.
4. Migrate persistence to managed DB/object storage before automating game-day scans.
5. Attach approved frozen archives, verified input data and complete market-family checks, then independently regression-test before enabling candidate/ticket certification.

## Testing

```
pytest -q
```

The two included tests are mocked and **do not prove a live API connection**.

## GitHub Actions deployment
Create a private repository and upload this directory (including `.github/workflows/fanduel.yml`). In Settings > Secrets and variables > Actions, create `ODDS_API_KEY` using a valid provider key. Run Actions > FanDuel snapshot > Run workflow and choose NFL or NBA. Download the run artifact containing the original JSON, flattened CSV, and SQLite ledger. A failed run may still contain diagnostic data. No secrets belong in source control. Market discovery is not exhaustive and a captured snapshot is not certified. The runner uses GitHub networking, not the chat sandbox. No scheduled runs or wagers are enabled.
