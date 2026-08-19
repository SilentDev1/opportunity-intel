import hmac
from datetime import datetime
from typing import Annotated, Any

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from .collectors import collect_source
from .config import get_settings
from .db import get_db
from .models import (
    CollectionRun,
    InferredNeed,
    Location,
    Opportunity,
    Organization,
    OrganizationAlias,
    ReviewItem,
    Signal,
    Source,
)
from .services import match_profile, validation_summary

app = FastAPI(title="Opportunity Intel", version="0.1.0", docs_url="/api/docs")
templates = Jinja2Templates(directory="src/opportunity_intel/templates")
DB = Annotated[Session, Depends(get_db)]


class MatchProfile(BaseModel):
    business_name: str = Field(max_length=200)
    service_categories: list[str]
    target_industries: list[str]
    cities: list[str]
    radius_miles: float = Field(ge=0, le=500)


class ReviewDecision(BaseModel):
    resolution: str = Field(
        pattern="^(true_positive|false_positive|uncertain|duplicate|not_actionable)$"
    )
    notes: str | None = Field(default=None, max_length=2000)


def admin(x_admin_key: Annotated[str | None, Header()] = None) -> None:
    expected = get_settings().admin_api_key
    if not expected or not x_admin_key or not hmac.compare_digest(expected, x_admin_key):
        raise HTTPException(403, "Admin API key required")


def serialize(obj: Any) -> dict[str, Any]:
    return {column.name: getattr(obj, column.name) for column in obj.__table__.columns}


@app.get("/health")
def health(db: DB) -> dict[str, str]:
    db.execute(select(1))
    return {"status": "ok", "time": datetime.utcnow().isoformat()}


@app.get("/sources")
def sources(db: DB) -> list[dict[str, Any]]:
    return [serialize(x) for x in db.scalars(select(Source).order_by(Source.name))]


@app.get("/sources/health")
def source_health(db: DB) -> list[dict[str, Any]]:
    return [
        {
            "source": s.name,
            "enabled": s.enabled,
            "last_attempt": s.last_attempt_at,
            "last_success": s.last_success_at,
            "failure_count": s.failure_count,
            "error": s.last_error,
            "collector_version": s.collector_version,
        }
        for s in db.scalars(select(Source).order_by(Source.name))
    ]


@app.get("/organizations")
def organizations(db: DB, limit: int = Query(100, le=500)) -> list[dict[str, Any]]:
    return [serialize(x) for x in db.scalars(select(Organization).limit(limit))]


@app.get("/organizations/{entity_id}")
def organization(entity_id: str, db: DB) -> dict[str, Any]:
    obj = db.get(Organization, entity_id)
    if not obj:
        raise HTTPException(404, "Organization not found")
    result = serialize(obj)
    result["aliases"] = [
        serialize(a)
        for a in db.scalars(
            select(OrganizationAlias).where(OrganizationAlias.organization_id == entity_id)
        )
    ]
    return result


@app.get("/locations")
def locations(db: DB, city: str | None = None) -> list[dict[str, Any]]:
    query = select(Location)
    if city:
        query = query.where(Location.city == city)
    return [serialize(x) for x in db.scalars(query.limit(500))]


@app.get("/signals")
def signals(db: DB, limit: int = Query(100, le=500)) -> list[dict[str, Any]]:
    return [
        serialize(x)
        for x in db.scalars(select(Signal).order_by(desc(Signal.detected_at)).limit(limit))
    ]


@app.get("/opportunities")
def opportunities(
    db: DB,
    city: str | None = None,
    industry: str | None = None,
    stage: str | None = None,
    min_score: float = 0,
    limit: int = Query(100, le=500),
) -> list[dict[str, Any]]:
    query = (
        select(Opportunity, Organization, Location)
        .join(Organization)
        .outerjoin(Location)
        .where(Opportunity.score >= min_score)
    )
    if city:
        query = query.where(Location.city == city)
    if industry:
        query = query.where(Organization.industry == industry)
    if stage:
        query = query.where(Opportunity.stage == stage)
    return [
        {
            **serialize(o),
            "organization": org.canonical_name,
            "industry": org.industry,
            "city": loc.city if loc else None,
        }
        for o, org, loc in db.execute(query.order_by(desc(Opportunity.score)).limit(limit))
    ]


@app.get("/opportunities/{entity_id}")
def opportunity(entity_id: str, db: DB) -> dict[str, Any]:
    obj = db.get(Opportunity, entity_id)
    if not obj:
        raise HTTPException(404, "Opportunity not found")
    result = serialize(obj)
    result["organization"] = serialize(db.get(Organization, obj.organization_id))
    result["location"] = serialize(db.get(Location, obj.location_id)) if obj.location_id else None
    result["signals"] = [
        serialize(s)
        for s in db.scalars(
            select(Signal)
            .where(Signal.organization_id == obj.organization_id)
            .order_by(Signal.signal_date)
        )
    ]
    result["needs"] = [
        serialize(n)
        for n in db.scalars(select(InferredNeed).where(InferredNeed.opportunity_id == obj.id))
    ]
    return result


@app.get("/validation/summary")
def validation(db: DB) -> dict[str, Any]:
    return validation_summary(db)


@app.post("/collect/{source_id}", dependencies=[Depends(admin)])
async def collect(source_id: str, db: DB) -> dict[str, Any]:
    source = db.get(Source, source_id)
    if not source or not source.enabled:
        raise HTTPException(404, "Enabled source not found")
    return serialize(await collect_source(db, source))


@app.post("/match")
def match(profile: MatchProfile, db: DB) -> list[dict[str, Any]]:
    results = []
    for opp, org, loc in db.execute(
        select(Opportunity, Organization, Location)
        .join(Organization)
        .outerjoin(Location)
        .where(Opportunity.status != "suppressed")
    ):
        needs = list(
            db.scalars(
                select(InferredNeed.service_category).where(InferredNeed.opportunity_id == opp.id)
            )
        )
        item = {
            "id": opp.id,
            "score": opp.score,
            "stage": opp.stage,
            "industry": org.industry,
            "city": loc.city if loc else None,
            "service_categories": needs,
        }
        results.append({**item, **match_profile(item, profile.model_dump())})
    return sorted(results, key=lambda x: x["match_score"], reverse=True)


@app.post("/review/{item_id}", dependencies=[Depends(admin)])
def resolve_review(item_id: str, decision: ReviewDecision, db: DB) -> dict[str, Any]:
    item = db.get(ReviewItem, item_id)
    if not item:
        raise HTTPException(404, "Review item not found")
    item.status = "resolved"
    item.resolution = decision.resolution
    item.notes = decision.notes
    item.reviewed_at = datetime.utcnow()
    db.commit()
    return serialize(item)


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request, db: DB) -> HTMLResponse:
    metrics = validation_summary(db)
    recent = list(
        db.execute(
            select(Opportunity, Organization, Location)
            .join(Organization)
            .outerjoin(Location)
            .order_by(desc(Opportunity.score))
            .limit(30)
        )
    )
    return templates.TemplateResponse(
        request, "overview.html", {"metrics": metrics, "rows": recent}
    )


@app.get("/dashboard/opportunities/{entity_id}", response_class=HTMLResponse)
def detail(entity_id: str, request: Request, db: DB) -> HTMLResponse:
    obj = db.get(Opportunity, entity_id)
    if not obj:
        raise HTTPException(404)
    org = db.get(Organization, obj.organization_id)
    loc = db.get(Location, obj.location_id) if obj.location_id else None
    timeline = list(
        db.scalars(
            select(Signal)
            .where(Signal.organization_id == obj.organization_id)
            .order_by(desc(Signal.signal_date))
        )
    )
    needs = list(db.scalars(select(InferredNeed).where(InferredNeed.opportunity_id == obj.id)))
    return templates.TemplateResponse(
        request,
        "detail.html",
        {"opportunity": obj, "org": org, "location": loc, "timeline": timeline, "needs": needs},
    )


@app.get("/dashboard/sources", response_class=HTMLResponse)
def dashboard_sources(request: Request, db: DB) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "sources.html",
        {
            "sources": list(db.scalars(select(Source).order_by(Source.name))),
            "runs": list(
                db.scalars(select(CollectionRun).order_by(desc(CollectionRun.started_at)).limit(30))
            ),
        },
    )


@app.get("/dashboard/review", response_class=HTMLResponse)
def review(request: Request, db: DB) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "review.html",
        {"items": list(db.scalars(select(ReviewItem).order_by(ReviewItem.created_at)))},
    )
