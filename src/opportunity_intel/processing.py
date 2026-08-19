import re
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import (
    InferredNeed,
    Location,
    Opportunity,
    Organization,
    RawRecord,
    RawSourceDocument,
    ReviewItem,
    Signal,
    Source,
)
from .services import infer_needs, infer_stage, normalize_name, score_opportunity

ITEM = re.compile(
    r"(?ms)^\s*\d+\.\s+((?:SP|CU)\d{4}-\d+)\s+(.*?)(?=^\s*\d+\.\s+(?:SP|CU|S)\d{4}-\d+|^\s*[IVX]+\.|\Z)"
)
ADDRESS = re.compile(r"Property(?:ies)? located (?:at|on)\s+(.+?)\s*\(Tax Map", re.I | re.S)
MEETING_DATE = re.compile(r"(?:Thursday|Wednesday|Tuesday|Monday),\s+(\w+ \d{1,2}, \d{4})")
COMMERCIAL = re.compile(
    r"gaming|facility|fuel|convenience store|restaurant|commercial space|office|storage|retail|"
    r"hotel|industrial|warehouse|food processing|landscape contractor",
    re.I,
)
RESIDENTIAL_ONLY = re.compile(r"dwelling unit|single-family|two-family|existing house", re.I)


def clean(value: str) -> str:
    return " ".join(value.replace(" -", "-").split()).strip(" ,.")


def classify(text: str) -> str:
    for pattern, industry in [
        (r"landscape contractor|office", "professional office"),
        (r"restaurant|convenience store", "restaurant"),
        (r"gaming", "entertainment"),
        (r"fuel|automotive", "automotive"),
        (r"warehouse|storage|industrial", "warehouse/logistics"),
        (r"retail|commercial space", "retail"),
    ]:
        if re.search(pattern, text, re.I):
            return industry
    return "other"


def extract_manchester_projects(text: str) -> list[dict[str, str | date]]:
    meeting = MEETING_DATE.search(text)
    signal_date = (
        datetime.strptime(meeting.group(1), "%B %d, %Y").date() if meeting else date.today()
    )
    projects = []
    for match in ITEM.finditer(text):
        project_id, body = match.group(1), clean(match.group(2))
        address = ADDRESS.search(body)
        if (
            not address
            or not COMMERCIAL.search(body)
            or (RESIDENTIAL_ONLY.search(body) and not re.search(r"commercial space", body, re.I))
        ):
            continue
        reviewed = re.split(r"\(Reviewed", body, maxsplit=1)[0]
        parts = re.split(r"\s+for\s+", reviewed, flags=re.I)
        if len(parts) < 2:
            continue
        applicant = clean(parts[-1])
        if len(applicant) > 180 or " and " in applicant.casefold():
            continue
        projects.append(
            {
                "project_id": project_id,
                "applicant": applicant,
                "address": clean(address.group(1)),
                "description": body,
                "signal_date": signal_date,
                "industry": classify(body),
            }
        )
    return projects


def process_manchester(db: Session) -> dict[str, int]:
    source = db.scalar(select(Source).where(Source.name == "Manchester Planning Board Agendas"))
    if not source:
        return {"projects": 0, "signals": 0, "opportunities": 0}
    rows = db.execute(
        select(RawRecord, RawSourceDocument)
        .join(RawSourceDocument)
        .where(RawSourceDocument.source_id == source.id)
    ).all()
    found: dict[str, tuple[dict[str, str | date], RawRecord, RawSourceDocument]] = {}
    for record, document in rows:
        for project in extract_manchester_projects(record.extracted_text or ""):
            found[str(project["project_id"])] = (project, record, document)
    created_signals = created_opportunities = 0
    for project_id, (project, record, document) in found.items():
        signal_title = f"{project_id} — Manchester Planning Board commercial application"
        if db.scalar(
            select(Signal).where(Signal.source_id == source.id, Signal.title == signal_title)
        ):
            continue
        name = str(project["applicant"])
        normalized = normalize_name(name)
        org = db.scalar(select(Organization).where(Organization.normalized_name == normalized))
        if not org:
            org = Organization(
                canonical_name=name,
                normalized_name=normalized,
                legal_name=name,
                industry=str(project["industry"]),
            )
            db.add(org)
            db.flush()
        address = str(project["address"])
        location = db.scalar(
            select(Location).where(
                Location.organization_id == org.id,
                Location.city == "Manchester",
                Location.address_line_1 == address,
            )
        )
        if not location:
            location = Location(
                organization_id=org.id,
                address_line_1=address,
                city="Manchester",
                municipality="Manchester",
                physical_confidence=0.9,
                location_status="candidate",
            )
            db.add(location)
            db.flush()
        existing_for_record = db.scalar(
            select(Signal).where(
                Signal.raw_record_id == record.id,
                Signal.signal_type == "planning_application",
                Signal.organization_id == org.id,
                Signal.location_id == location.id,
            )
        )
        if existing_for_record:
            continue
        signal = Signal(
            organization_id=org.id,
            location_id=location.id,
            source_id=source.id,
            raw_record_id=record.id,
            signal_type="planning_application",
            signal_date=project["signal_date"],
            title=signal_title,
            description=str(project["description"]),
            structured_data={"external_id": project_id, "parser": "manchester-commercial-v1"},
            confidence=0.85,
            source_url=document.source_url,
            is_verified=False,
        )
        db.add(signal)
        db.flush()
        created_signals += 1
        signals = list(
            db.scalars(
                select(Signal).where(
                    Signal.organization_id == org.id, Signal.location_id == location.id
                )
            )
        )
        stage, stage_confidence, reasons = infer_stage(signals)
        score, breakdown = score_opportunity(signals, location.physical_confidence, 0.8)
        opportunity = db.scalar(
            select(Opportunity).where(
                Opportunity.organization_id == org.id,
                Opportunity.location_id == location.id,
                Opportunity.opportunity_type == "major_renovation",
            )
        )
        if not opportunity:
            opportunity = Opportunity(
                organization_id=org.id,
                location_id=location.id,
                opportunity_type="major_renovation",
                first_detected_at=signal.detected_at,
                summary=f"{name} commercial planning activity at {address}, Manchester",
                why_actionable=(
                    "An official Planning Board filing identifies a commercial project and exact "
                    "physical address; operating status and vendor timing require review."
                ),
            )
            db.add(opportunity)
            db.flush()
            created_opportunities += 1
        opportunity.stage = stage.value
        opportunity.stage_confidence = stage_confidence
        opportunity.entity_confidence = 0.82
        opportunity.confidence = min(stage_confidence, 0.82)
        opportunity.stage_reasoning = reasons
        opportunity.stage_updated_at = datetime.utcnow()
        opportunity.last_signal_at = max(s.detected_at for s in signals)
        opportunity.score = score
        opportunity.score_breakdown = breakdown
        for category, reason in infer_needs(org.industry, opportunity.stage):
            if not db.scalar(
                select(InferredNeed).where(
                    InferredNeed.opportunity_id == opportunity.id,
                    InferredNeed.service_category == category,
                )
            ):
                db.add(
                    InferredNeed(
                        opportunity_id=opportunity.id,
                        service_category=category,
                        confidence=0.65,
                        reason=reason,
                    )
                )
    opportunity_ids = list(
        db.scalars(
            select(Opportunity.id)
            .join(Signal, Signal.organization_id == Opportunity.organization_id)
            .where(Signal.source_id == source.id)
            .distinct()
        )
    )
    for opportunity_id in opportunity_ids:
        if not db.scalar(
            select(ReviewItem).where(
                ReviewItem.entity_type == "opportunity",
                ReviewItem.entity_id == opportunity_id,
                ReviewItem.review_type == "uncertain_opportunity_status",
            )
        ):
            db.add(
                ReviewItem(
                    review_type="uncertain_opportunity_status",
                    entity_type="opportunity",
                    entity_id=opportunity_id,
                    confidence=0.67,
                    reason=(
                        "Official commercial planning evidence requires manual confirmation of "
                        "current status, operating brand, and vendor timing."
                    ),
                )
            )
    db.commit()
    return {
        "projects": len(found),
        "signals": created_signals,
        "opportunities": created_opportunities,
    }
