# Opportunity Intel

Opportunity Intel turns fragmented public business activity into actionable local B2B sales opportunities. It preserves evidence first, resolves signals to organizations and physical locations, infers lifecycle stage, and produces explainable opportunities and customer matches.

It is **not merely a building-permit notification service**. The core flow is:

```text
Sources → Raw Documents → Raw Records → Signals → Organizations/Locations
        → Lifecycle → Opportunities → Vendor Needs → Customer Matches
```

## Current state

This repository is an early Phase 0 validation engine. It includes the PostgreSQL schema, migrations, source-adapter framework, local artifact storage, three official municipal agenda collectors, rules engines, an internal API/dashboard, review and validation models, tests, and CI. Automated record-to-signal extraction currently covers conservative commercial applications in Manchester agendas. Generated candidates are explicitly queued for review and are not described as verified opportunities.

Current connected discovery pages:

- Nashua Planning Board historical archive (official; pre-February 2025)
- Manchester Planning Board agendas (official)
- Salem Planning Board Agenda Center (official)

See [the source map](docs/nh-source-map.md) for researched sources and precise implementation status.

## Setup

Requirements: Python 3.11+, `uv`, Docker (for local PostgreSQL).

```bash
cp .env.example .env
docker compose up -d db
uv sync --all-extras
uv run alembic upgrade head
uv run opportunity-intel seed-sources
uv run uvicorn opportunity_intel.main:app --reload
```

Open `http://127.0.0.1:8000/` for the internal dashboard and `/api/docs` for API documentation. Set a strong `ADMIN_API_KEY`; collection endpoints return 403 when it is absent or incorrect.

## Collection and validation

```bash
uv run opportunity-intel collect "Manchester Planning Board Agendas" --limit 20
uv run opportunity-intel collect-all --limit 20
uv run opportunity-intel process
uv run opportunity-intel validate
```

These commands are cron-compatible. Collectors use timeouts, a descriptive user agent, bounded retry/backoff, a delay between documents, content hashes, idempotent constraints, local raw artifact retention, and isolated collection runs.

## Development

```bash
make test
make lint
make typecheck
make migrate
```

CI runs Ruff, mypy, PostgreSQL migration upgrade/downgrade/upgrade, and pytest without production secrets.

## API

Read endpoints include `/health`, `/sources`, `/sources/health`, `/organizations`, `/locations`, `/signals`, `/opportunities`, `/validation/summary`, and `/match`. `POST /collect/{source_id}` requires `X-Admin-Key`. Admin endpoints are not usable unless `ADMIN_API_KEY` is configured.

## Known limitations

- Only three source discovery adapters are connected; Nashua's collector is an archive, not its current AMM portal.
- Agenda PDF text extraction is deterministic; applicant/address extraction currently supports only Manchester's observed agenda format.
- No opportunity is marked manually verified yet. Candidate counts must not be presented as actionable conversion.
- No geocoder is included; radius matching needs defensible coordinates before use.
- State registries and license lookups require further terms/API assessment; no browser automation or CAPTCHA circumvention is used.
- The initial migration uses SQLAlchemy metadata to keep the prototype schema concise. Later migrations should use explicit Alembic operations.
- Authentication is an internal shared-key control, not production customer authentication.

## Responsible use

Collect only legitimately public commercial information. Do not bypass authentication, CAPTCHAs, rate limits, or site restrictions. Avoid personal addresses and personal contact data. Every factual opportunity claim must link to its source evidence.
