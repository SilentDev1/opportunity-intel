# Opportunity Intel

**Evidence-first local B2B opportunity intelligence.** Opportunity Intel turns fragmented,
public municipal activity — planning-board agendas, zoning cases, issued building permits — into
explainable, vendor-ready sales opportunities. It preserves the underlying evidence first, resolves
each signal to a real organization and physical location, infers where that business is in its
lifecycle, and only then produces opportunities and customer matches you can trace back to a source
document.

It is deliberately **not** "another building-permit alert feed." The value is the chain from a raw
public record to a defensible, explainable opportunity:

```text
Sources → Raw Documents → Raw Records → Signals → Organizations / Locations
        → Lifecycle stage → Opportunities → Inferred Vendor Needs → Customer Matches
```

## Why it's built this way

- **Provenance before inference.** Every signal links back to the exact source document and record
  it came from — results are auditable, not black-box.
- **Deterministic extraction, explainable scoring.** Signal families and vendor-readiness scores are
  rule-based and inspectable — each opportunity can show *why* it scored as it did.
- **Identity resolution.** Raw records are de-duplicated and resolved to canonical organizations
  (with aliases) and distinct physical locations, with explicit operator/developer roles.
- **Honest validation.** The pipeline is measured against a manually reviewed corpus; the repo
  reports precision/value rather than vanity counts.

## Architecture

```text
src/opportunity_intel/
  collectors.py     Source adapters — fetch official municipal pages/PDFs
  storage.py        Local artifact storage for raw source documents (evidence)
  processing.py     Raw records → signals → organizations/locations → opportunities
  enrichment.py     Targeted official-source contact/role enrichment
  services.py       Vendor-need inference, customer matching, validation summaries
  reporting.py      Blind batch reports + vendor-ready CSV exports
  models.py         SQLAlchemy schema (sources, documents, signals, orgs, opportunities…)
  main.py / cli.py  FastAPI internal dashboard/API + Typer CLI
  registry.py       Declarative source registry
migrations/         Alembic schema migrations
docs/               Source maps, per-phase validation reports, methodology
tests/              Unit + workflow tests
```

**Stack:** Python 3.11 · FastAPI · SQLAlchemy 2 · Alembic · PostgreSQL · Typer CLI · httpx ·
BeautifulSoup · pypdf · Jinja2 · Ruff · MyPy · pytest · GitHub Actions CI.

## Sources

Discovery is bounded to **official municipal sources** (New Hampshire), currently including
Nashua / Manchester / Salem / Bedford / Portsmouth / Dover planning & zoning materials and Salem
issued building permits. See [`docs/nh-source-map.md`](docs/nh-source-map.md) for the researched
source map and precise per-source implementation status.

## Run it locally

Requirements: Python 3.11+, [`uv`](https://docs.astral.sh/uv/), Docker (local PostgreSQL).

```bash
cp .env.example .env            # set a strong ADMIN_API_KEY
docker compose up -d db
uv sync --all-extras
uv run alembic upgrade head
uv run opportunity-intel seed-sources
uv run uvicorn opportunity_intel.main:app --reload
```

Open `http://127.0.0.1:8000/` for the internal dashboard and `/api/docs` for API docs. Collection
endpoints return `403` without the correct `ADMIN_API_KEY`.

Typical pipeline:

```bash
uv run opportunity-intel collect-all --limit 20   # fetch + store raw evidence
uv run opportunity-intel process                  # signals → orgs/locations → opportunities
uv run opportunity-intel validate                 # measure quality vs reviewed corpus
```

## Status

Validation-stage engine. It ships the PostgreSQL schema + migrations, the source-adapter framework,
several official municipal sources, the rules engines, the internal API/dashboard, review/validation
workflows, CSV export, tests, and CI. Results are reported against a **bounded, manually reviewed
corpus** — read the validation reports in `docs/` before interpreting numbers. A deeper design
narrative is in [`docs/PROJECT_WRITEUP.md`](docs/PROJECT_WRITEUP.md).

## License

See [`LICENSE`](LICENSE) — all rights reserved; published for portfolio review only.
