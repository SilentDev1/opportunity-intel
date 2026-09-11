# Opportunity Intel — Project Writeup

## The problem

Local B2B vendors (contractors, suppliers, service firms) win work by reaching new and changing
businesses early — a new restaurant fitting out a space, a developer breaking ground, a business
relocating. The signals for all of this are *public*: planning-board agendas, zoning cases, issued
building permits, license filings. But they're scattered across dozens of municipal sites, buried in
PDFs and agenda-center pages, and inconsistent in format. Turning that noise into a list a
salesperson can actually act on — *who*, *where*, *what stage*, *what they'll need* — is the hard part.

Plenty of tools will email you raw permit alerts. That's the easy 20%. The hard 80% is trust: is
this a real, current opportunity, tied to a real business at a real address, and can you explain why?

## The approach: evidence first

The core design decision is that **evidence comes before inference**. The pipeline never asserts an
opportunity it can't trace back to a specific public document:

```
Sources → Raw Documents → Raw Records → Signals → Organizations / Locations
        → Lifecycle stage → Opportunities → Inferred Vendor Needs → Customer Matches
```

Each stage is a separate, inspectable transformation:

1. **Collect** — source adapters fetch official municipal pages and PDFs. Raw documents are stored
   as immutable artifacts so the exact evidence is preserved, not just a parsed summary.
2. **Extract** — deterministic parsing turns documents into raw records, then into typed *signals*
   from independent signal families (so one noisy source can't dominate).
3. **Resolve** — records are de-duplicated and resolved to canonical **organizations** (with alias
   handling) and distinct **physical locations**, with explicit operator vs. developer roles.
4. **Infer** — a rules engine estimates lifecycle stage and produces **opportunities**, each with an
   **explainable vendor-readiness score** — you can see the factors, not just a number.
5. **Match & export** — opportunities are matched to a vendor's stated needs and exported in a
   vendor-ready format, with provenance intact.

## Engineering decisions worth calling out

- **Auditability over magic.** Scoring and signal extraction are rule-based and explainable. For a
  sales tool, "here's why" beats a slightly higher black-box precision — a rep has to defend the lead.
- **Provenance as a first-class citizen.** The schema links signals → records → source documents, so
  every claim is traceable. This also makes the system safe to iterate: you can re-run inference
  without re-fetching, and you can audit regressions.
- **Bounded, official sources only.** Discovery is restricted to official municipal sources rather
  than scraping aggregators — cleaner provenance and fewer legal/ethical gray areas.
- **Honest measurement.** Rather than reporting how many "leads" it can emit, the project validates
  against a **manually reviewed corpus** and reports precision and vendor value. Several sources were
  tested and explicitly recorded as low-value — negative results are kept, not hidden.
- **Operational hygiene.** API-key-gated collection endpoints, Alembic migrations, tests, and CI from
  early on; a Typer CLI + FastAPI/Jinja dashboard for running and reviewing the pipeline.

## Tech

Python 3.11, FastAPI, SQLAlchemy 2, Alembic, PostgreSQL, Typer, httpx, BeautifulSoup, pypdf, Jinja2,
Ruff, MyPy, pytest, GitHub Actions.

## What this demonstrates

- Designing a **data pipeline where correctness and traceability matter more than volume**.
- Turning messy, real-world public data into a structured, explainable product.
- Identity resolution, deterministic rules engines, and evidence-preserving schema design.
- Discipline around **honest validation** — measuring quality against reviewed ground truth and
  recording negative results.

## Status & honesty

This is a **validation-stage engine**, not a finished commercial product. The architecture,
schema, sources, rules, dashboard, and workflows are in place and tested; results are measured on a
bounded reviewed corpus. See the per-phase validation reports in `docs/` for exact, current numbers
before drawing conclusions.
