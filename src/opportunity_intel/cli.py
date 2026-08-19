import asyncio
import json
from pathlib import Path

import typer
from sqlalchemy import select

from .collectors import collect_source
from .db import SessionLocal
from .enrichment import (
    import_enrichment_csv,
    import_evidence_csv,
    import_vendor_feedback_csv,
    refresh_enrichment,
)
from .models import Opportunity, Source
from .processing import process_manchester, process_phase_05
from .registry import seed_sources
from .reporting import (
    detailed_validation_report,
    export_actionable_matrix,
    export_validation_csv,
    export_vendor_ready,
    export_vendor_validation,
    import_review_csv,
    review_opportunity,
    vendor_simulation,
)

app = typer.Typer(no_args_is_help=True)


@app.command("seed-sources")
def seed() -> None:
    with SessionLocal() as db:
        typer.echo(f"Added {seed_sources(db)} sources")


@app.command("collect")
def collect(name: str, limit: int = 20) -> None:
    with SessionLocal() as db:
        source = db.scalar(select(Source).where(Source.name == name))
        if not source:
            raise typer.BadParameter("Unknown source")
        run = asyncio.run(collect_source(db, source, limit))
        typer.echo(
            json.dumps(
                {
                    "run_id": run.id,
                    "status": run.status,
                    "documents": run.documents_discovered,
                    "new": run.documents_new,
                    "records": run.records_parsed,
                    "error": run.error,
                },
                indent=2,
            )
        )


@app.command("collect-all")
def collect_all(limit: int = 20) -> None:
    with SessionLocal() as db:
        for source in db.scalars(select(Source).where(Source.enabled.is_(True))):
            run = asyncio.run(collect_source(db, source, limit))
            typer.echo(f"{source.name}: {run.status}, {run.documents_new} new")


@app.command("validate")
def validate() -> None:
    with SessionLocal() as db:
        typer.echo(json.dumps(detailed_validation_report(db), indent=2, default=str))


@app.command("process")
def process() -> None:
    with SessionLocal() as db:
        results = {"manchester_planning": process_manchester(db), **process_phase_05(db)}
        typer.echo(json.dumps(results, indent=2))


@app.command("review")
def review(opportunity_id: str, verdict: str, note: str = "") -> None:
    with SessionLocal() as db:
        review_opportunity(db, opportunity_id, verdict, note)
        typer.echo(f"Reviewed {opportunity_id}: {verdict}")


@app.command("import-reviews")
def import_reviews(path: Path) -> None:
    with SessionLocal() as db:
        count = import_review_csv(db, path)
        typer.echo(f"Imported {count} review decisions")


@app.command("export-validation")
def export_validation(path: Path = Path("data/exports/validation.csv")) -> None:
    with SessionLocal() as db:
        count = export_validation_csv(db, path)
        typer.echo(f"Exported {count} opportunities to {path}")


@app.command("vendor-simulation")
def simulate_vendors() -> None:
    with SessionLocal() as db:
        typer.echo(json.dumps(vendor_simulation(db), indent=2))


@app.command("export-actionable-matrix")
def export_matrix(path: Path = Path("data/exports/phase05-actionable-matrix.csv")) -> None:
    with SessionLocal() as db:
        count = export_actionable_matrix(db, path)
        typer.echo(f"Exported {count} actionable opportunities to {path}")


@app.command("export-vendor-validation")
def export_vendor(
    vendor_name: str, path: Path = Path("data/exports/vendor-validation.csv")
) -> None:
    with SessionLocal() as db:
        count = export_vendor_validation(db, vendor_name, path)
        typer.echo(f"Exported {count} {vendor_name} matches to {path}")


@app.command("import-enrichment")
def import_enrichment(path: Path) -> None:
    with SessionLocal() as db:
        typer.echo(json.dumps(import_enrichment_csv(db, path), indent=2))


@app.command("import-evidence")
def import_evidence(path: Path) -> None:
    with SessionLocal() as db:
        typer.echo(json.dumps(import_evidence_csv(db, path), indent=2))


@app.command("import-vendor-feedback")
def import_vendor_feedback(path: Path) -> None:
    with SessionLocal() as db:
        typer.echo(f"Imported {import_vendor_feedback_csv(db, path)} vendor responses")


@app.command("refresh-readiness")
def refresh_readiness() -> None:
    with SessionLocal() as db:
        count = 0
        for opportunity in db.scalars(select(Opportunity)):
            refresh_enrichment(db, opportunity)
            count += 1
        db.commit()
        typer.echo(f"Refreshed {count} opportunities")


@app.command("export-vendor-ready")
def export_ready(
    vendor_name: str, path: Path = Path("data/exports/vendor-ready/leads.csv")
) -> None:
    with SessionLocal() as db:
        count = export_vendor_ready(db, vendor_name, path)
        typer.echo(f"Exported {count} vendor-ready {vendor_name} leads to {path}")
