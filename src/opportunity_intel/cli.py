import asyncio
import json

import typer
from sqlalchemy import select

from .collectors import collect_source
from .db import SessionLocal
from .models import Source
from .processing import process_manchester
from .registry import seed_sources
from .services import validation_summary

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
        typer.echo(json.dumps(validation_summary(db), indent=2, default=str))


@app.command("process")
def process() -> None:
    with SessionLocal() as db:
        typer.echo(json.dumps(process_manchester(db), indent=2))
