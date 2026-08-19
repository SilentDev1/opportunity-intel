import asyncio
import json
from pathlib import Path

import typer
from sqlalchemy import select

from .collectors import collect_source
from .db import SessionLocal
from .enrichment import (
    freeze_blind_batch,
    import_enrichment_csv,
    import_evidence_csv,
    import_vendor_feedback_csv,
    import_vendor_outcomes_csv,
    record_blind_reviews,
    refresh_enrichment,
)
from .models import Opportunity, Source
from .phase09 import export_cleaning_packet, refresh_phase09_metrics, weekly_cleaning_flow
from .phase10 import export_current_cleaning_test, write_vendor_validation_report
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


@app.command("import-vendor-outcomes")
def import_vendor_outcomes(path: Path) -> None:
    with SessionLocal() as db:
        typer.echo(f"Imported {import_vendor_outcomes_csv(db, path)} vendor outcome events")


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


@app.command("freeze-blind-batch")
def freeze_batch(name: str, source_scope: str, opportunity_ids: str) -> None:
    with SessionLocal() as db:
        batch = freeze_blind_batch(
            db,
            name,
            source_scope,
            {item.strip() for item in opportunity_ids.split(",") if item.strip()},
        )
        typer.echo(f"Frozen blind batch {batch.name}: {batch.id}")


@app.command("record-blind-reviews")
def record_batch_reviews(name: str) -> None:
    with SessionLocal() as db:
        typer.echo(json.dumps(record_blind_reviews(db, name), indent=2))


@app.command("refresh-phase09")
def refresh_phase09(period_start: str = "2026-08-17", period_end: str = "2026-08-23") -> None:
    from datetime import date

    with SessionLocal() as db:
        counts = refresh_phase09_metrics(
            db, date.fromisoformat(period_start), date.fromisoformat(period_end)
        )
        flow = weekly_cleaning_flow(
            db, date.fromisoformat(period_start), date.fromisoformat(period_end)
        )
        typer.echo(json.dumps({"classified": dict(counts), "weekly_flow": flow}, indent=2))


@app.command("export-cleaning-packet")
def export_cleaning(
    path: Path = Path("data/exports/vendor-ready/cleaning/statewide.csv"),
    territory: str = "statewide",
    fresh_only: bool = False,
) -> None:
    if territory not in {"statewide", "southern_nh"}:
        raise typer.BadParameter("Territory must be statewide or southern_nh")
    with SessionLocal() as db:
        count = export_cleaning_packet(db, path, territory, fresh_only)
        typer.echo(f"Exported {count} cleaning leads to {path}")


@app.command("export-current-cleaning-test")
def export_current_cleaning(
    path: Path = Path("data/exports/vendor-test/cleaning-current.csv"), limit: int = 10
) -> None:
    with SessionLocal() as db:
        count = export_current_cleaning_test(db, path, limit)
        typer.echo(f"Exported {count} current cleaning leads to {path}")


@app.command("write-vendor-validation-report")
def write_vendor_report(
    path: Path = Path("docs/vendor-validation-results.md"),
    vendor_profile: str = "commercial_cleaning",
) -> None:
    with SessionLocal() as db:
        write_vendor_validation_report(db, path, vendor_profile)
        typer.echo(f"Wrote vendor validation report to {path}")
