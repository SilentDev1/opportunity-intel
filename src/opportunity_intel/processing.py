import re
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import (
    InferredNeed,
    LifecycleStage,
    Location,
    Opportunity,
    OpportunityOrganizationRole,
    Organization,
    RawRecord,
    RawSourceDocument,
    ReviewItem,
    Signal,
    Source,
    StageHistory,
)
from .services import infer_needs, infer_stage, normalize_address, normalize_name, score_opportunity

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
    value = re.sub(r"^\d+\.\s*", "", value)
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


COMMERCIAL_USE = re.compile(
    r"restaurant|retail|commercial|office|medical|dental|childcare|daycare|fitness|salon|"
    r"gaming|fuel|convenience store|warehouse|industrial|contractor|bakery|hotel|storage|"
    r"school|education|mixed-use",
    re.I,
)
NON_COMMERCIAL_PROJECT = re.compile(
    r"single.family|two.family|multifamily|multi.family|dwelling units?|residential units?|"
    r"condominiums?|townhomes?|subdivision.{0,80}(?:lots?|dwellings?)|municipal playground|"
    r"elementary school|shoreline trail",
    re.I,
)


def is_commercial_candidate(description: str) -> bool:
    """Reject known non-commercial project uses even when owner/zoning text looks commercial."""
    if NON_COMMERCIAL_PROJECT.search(description) and not re.search(
        r"commercial space|mixed.use.*commercial|retail space", description, re.I
    ):
        return False
    return bool(COMMERCIAL_USE.search(description))


def _upsert_evidence_project(
    db: Session,
    *,
    source: Source,
    record: RawRecord,
    document: RawSourceDocument,
    project_key: str,
    organization_name: str,
    organization_role: str,
    address: str,
    city: str,
    description: str,
    signal_type: str,
    signal_date: date,
    industry: str,
    opportunity_type: str = "major_renovation",
    entity_confidence: float = 0.68,
) -> bool:
    title = f"{project_key} — {source.name}"
    if db.scalar(select(Signal).where(Signal.source_id == source.id, Signal.title == title)):
        return False
    name = clean(organization_name)
    normalized = normalize_name(name)
    org = db.scalar(select(Organization).where(Organization.normalized_name == normalized))
    matched_location: Location | None = None
    if organization_role == "unresolved_project":
        normalized_target = normalize_address(address)
        normalized_first_address = normalize_address(address.split(",", 1)[0])
        address_matches = [
            item
            for item in db.scalars(select(Location).where(Location.city == city))
            if item.address_line_1
            and (
                normalize_address(item.address_line_1) == normalized_target
                or normalize_address(item.address_line_1.split(",", 1)[0])
                == normalized_first_address
            )
        ]
        resolved_matches = [
            item
            for item in address_matches
            if (db.get(Organization, item.organization_id) or Organization()).organization_type
            != "unresolved_project"
        ]
        preferred_matches = resolved_matches or address_matches
        if len(preferred_matches) == 1:
            matched_location = preferred_matches[0]
            org = db.get(Organization, preferred_matches[0].organization_id)
            organization_role = "related_project"
    if not org:
        org = Organization(
            canonical_name=name,
            normalized_name=normalized,
            legal_name=name if organization_role != "unresolved_project" else None,
            organization_type=organization_role,
            industry=industry,
        )
        db.add(org)
        db.flush()
    normalized_address = normalize_address(address)
    location = matched_location or next(
        (
            item
            for item in db.scalars(
                select(Location).where(Location.organization_id == org.id, Location.city == city)
            )
            if item.address_line_1 and normalize_address(item.address_line_1) == normalized_address
        ),
        None,
    )
    if not location:
        location = Location(
            organization_id=org.id,
            address_line_1=clean(address),
            city=city,
            municipality=city,
            state="NH",
            location_status="candidate",
            physical_confidence=0.9,
        )
        db.add(location)
        db.flush()
    if db.scalar(
        select(Signal).where(
            Signal.raw_record_id == record.id,
            Signal.signal_type == signal_type,
            Signal.organization_id == org.id,
            Signal.location_id == location.id,
        )
    ):
        return False
    signal = Signal(
        organization_id=org.id,
        location_id=location.id,
        source_id=source.id,
        raw_record_id=record.id,
        signal_type=signal_type,
        signal_date=signal_date,
        title=title,
        description=description,
        structured_data={
            "external_id": project_key,
            "parser": "phase-0.5-rules-v1",
            "organization_role": organization_role,
        },
        confidence=0.88 if organization_role in {"operator", "tenant"} else 0.72,
        source_url=document.source_url,
        is_verified=False,
    )
    db.add(signal)
    db.flush()
    signals = list(
        db.scalars(
            select(Signal).where(
                Signal.organization_id == org.id, Signal.location_id == location.id
            )
        )
    )
    stage, stage_confidence, reasons = infer_stage(signals)
    latest_signal_date = max(item.signal_date or item.detected_at.date() for item in signals)
    if (
        stage.value not in {"OPEN", "CLOSED", "CANCELLED"}
        and (date.today() - latest_signal_date).days > 180
    ):
        stage = LifecycleStage.STALE
        stage_confidence = 0.9
        reasons = ["no current evidence within 180 days"]
    score, breakdown = score_opportunity(signals, location.physical_confidence, 0.75)
    opportunity = db.scalar(
        select(Opportunity).where(
            Opportunity.organization_id == org.id,
            Opportunity.location_id == location.id,
            Opportunity.opportunity_type == opportunity_type,
        )
    )
    previous_stage = opportunity.stage if opportunity else None
    if not opportunity:
        opportunity = Opportunity(
            organization_id=org.id,
            location_id=location.id,
            opportunity_type=opportunity_type,
            first_detected_at=signal.detected_at,
            summary=f"{name} activity at {location.address_line_1}, {city}",
            why_actionable=(
                "A traceable public source identifies current commercial activity at an exact "
                "location; operating identity and sales timing require review."
            ),
        )
        db.add(opportunity)
        db.flush()
    opportunity.stage = stage.value
    opportunity.stage_confidence = stage_confidence
    opportunity.entity_confidence = max(opportunity.entity_confidence, entity_confidence)
    opportunity.confidence = min(stage_confidence, opportunity.entity_confidence)
    opportunity.stage_reasoning = reasons
    opportunity.stage_updated_at = datetime.utcnow()
    opportunity.last_signal_at = max(item.detected_at for item in signals)
    opportunity.first_actionable_at = opportunity.first_actionable_at or (
        signal.detected_at
        if score >= 60
        and entity_confidence >= 0.65
        and opportunity.stage not in {"STALE", "CANCELLED"}
        else None
    )
    opportunity.score = score
    opportunity.score_breakdown = breakdown
    if previous_stage != opportunity.stage:
        db.add(
            StageHistory(
                opportunity_id=opportunity.id,
                from_stage=previous_stage,
                to_stage=opportunity.stage,
                reason="; ".join(reasons),
                triggering_signal_id=signal.id,
            )
        )
    if not db.scalar(
        select(OpportunityOrganizationRole).where(
            OpportunityOrganizationRole.opportunity_id == opportunity.id,
            OpportunityOrganizationRole.organization_id == org.id,
            OpportunityOrganizationRole.role == organization_role,
        )
    ):
        db.add(
            OpportunityOrganizationRole(
                opportunity_id=opportunity.id,
                organization_id=org.id,
                role=organization_role,
                confidence=entity_confidence,
                evidence=f"Named as {organization_role} in {source.name}",
                source_id=source.id,
            )
        )
    for category, reason in infer_needs(industry, opportunity.stage):
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
                    confidence=0.6,
                    reason=reason,
                )
            )
    if not db.scalar(
        select(ReviewItem).where(
            ReviewItem.entity_type == "opportunity", ReviewItem.entity_id == opportunity.id
        )
    ):
        db.add(
            ReviewItem(
                review_type="candidate_validation",
                entity_type="opportunity",
                entity_id=opportunity.id,
                confidence=opportunity.confidence,
                reason="Real-source candidate requires actionable/not-actionable review.",
            )
        )
    return True


def _source_rows(
    db: Session, name: str
) -> tuple[Source | None, list[tuple[RawRecord, RawSourceDocument]]]:
    source = db.scalar(select(Source).where(Source.name == name))
    if not source:
        return None, []
    rows = [
        (record, document)
        for record, document in db.execute(
            select(RawRecord, RawSourceDocument)
            .join(RawSourceDocument)
            .where(RawSourceDocument.source_id == source.id)
        )
    ]
    return source, rows


def process_bedford(db: Session) -> int:
    source, rows = _source_rows(db, "Bedford Planning Board Agenda Center")
    if not source:
        return 0
    found: dict[str, tuple[str, str, str, date, RawRecord, RawSourceDocument]] = {}
    pattern = re.compile(
        r"(?s)([A-Z0-9][A-Za-z0-9 &'.,-]{2,100}?)\s*\(([^)]*(?:Owner|Applicant)[^)]*)\)\s*"
        r"[–-]\s*Request for (?:approval of )?(.+?)(?=\s+\d+\.\s+|\s+IV\.|\s+V\.|\Z)"
    )
    for record, document in rows:
        text = " ".join((record.extracted_text or "").split())
        agenda_date = date.today()
        date_match = re.search(r"PLANNING BOARD\s+(\w+ \d{1,2}, 2026)", text)
        if date_match:
            agenda_date = datetime.strptime(date_match.group(1), "%B %d, %Y").date()
        for match in pattern.finditer(text):
            name, roles, description = clean(match.group(1)), match.group(2), clean(match.group(3))
            address_match = re.search(r"\bat\s+(.+?),\s+Lots?\b", description, re.I)
            if not address_match or not COMMERCIAL_USE.search(description):
                continue
            key = f"bedford:{normalize_name(name)}:{normalize_address(address_match.group(1))}"
            role = "applicant" if "Applicant" in roles else "property_owner"
            found[key] = (name, role, description, agenda_date, record, document)
    created = 0
    for key, (name, role, description, signal_date, record, document) in found.items():
        address = re.search(r"\bat\s+(.+?),\s+Lots?\b", description, re.I)
        assert address
        created += _upsert_evidence_project(
            db,
            source=source,
            record=record,
            document=document,
            project_key=key,
            organization_name=name,
            organization_role=role,
            address=address.group(1),
            city="Bedford",
            description=description,
            signal_type="planning_application",
            signal_date=signal_date,
            industry=classify(description),
        )
    db.commit()
    return created


def process_portsmouth(db: Session) -> int:
    source, rows = _source_rows(db, "Portsmouth Planning Board Materials")
    if not source:
        return 0
    found: dict[str, tuple[str, str, str, date, RawRecord, RawSourceDocument]] = {}
    pattern = re.compile(
        r"(?is)request of\s+([^()]{2,120})\s*\((Owner[^)]*)\)"
        r"(?:,?\s*and\s+[^()]{2,120}\s*\(Applicant[^)]*\))?,\s*"
        r"for property located at\s+(.+?)\s+"
        r"requesting\s+(.+?)(?=\s+The Board|\s+Motion:|\s+[IVX]+\.|\Z)"
    )
    for record, document in rows:
        text = " ".join((record.extracted_text or "").split())
        date_match = re.search(
            r"(January|February|March|April|May|June|July|August)\s+\d{1,2},\s+2026", text
        )
        signal_date = (
            datetime.strptime(date_match.group(0), "%B %d, %Y").date()
            if date_match
            else date.today()
        )
        for match in pattern.finditer(text):
            name, address = clean(match.group(1)), clean(match.group(3))
            description = clean(match.group(4))
            if not is_commercial_candidate(description):
                continue
            key = f"portsmouth:{normalize_address(address)}"
            found[key] = (name, address, description, signal_date, record, document)
    created = 0
    for key, (name, address, description, signal_date, record, document) in found.items():
        withdrawn = bool(re.search(r"withdrawn|denied", description, re.I))
        created += _upsert_evidence_project(
            db,
            source=source,
            record=record,
            document=document,
            project_key=key,
            organization_name=name,
            organization_role="property_owner",
            address=address,
            city="Portsmouth",
            description=description,
            signal_type="project_withdrawn" if withdrawn else "planning_application",
            signal_date=signal_date,
            industry=classify(description),
        )
    db.commit()
    return created


def process_salem(db: Session) -> int:
    source, rows = _source_rows(db, "Salem Planning Board Agenda Center")
    if not source:
        return 0
    pattern = re.compile(
        r"\d+\.\s+([A-Z][A-Za-z0-9&' .,-]{2,80}?)\s+Site Plan\s*[–-]\s*"
        r"(?:Public Hearing )?for\s+"
        r"(.+?)\s+at\s+([^,]+),\s+Map\s+\d+",
        re.I,
    )
    found: dict[str, tuple[str, str, str, RawRecord, RawSourceDocument]] = {}
    for record, document in rows:
        text = " ".join((record.extracted_text or "").split())
        for match in pattern.finditer(text):
            raw_name = clean(match.group(1))
            name = re.sub(r"^.*(?:NEW|OLD) BUSINESS\s+\d+\.\s*", "", raw_name, flags=re.I)
            description, address = (
                clean(match.group(2)),
                clean(match.group(3)),
            )
            if not is_commercial_candidate(description) and name.casefold() != "wonder":
                continue
            key = f"salem:{normalize_name(name)}:{normalize_address(address)}"
            found[key] = (name, address, description, record, document)
    created = 0
    for key, (name, address, description, record, document) in found.items():
        role = "operator" if name.casefold() == "wonder" else "applicant"
        created += _upsert_evidence_project(
            db,
            source=source,
            record=record,
            document=document,
            project_key=key,
            organization_name=name,
            organization_role=role,
            address=address,
            city="Salem",
            description=description,
            signal_type="sign_permit"
            if "sign" in description.casefold()
            else "planning_application",
            signal_date=date.today(),
            industry="restaurant" if name.casefold() == "wonder" else classify(description),
            opportunity_type="new_location" if name.casefold() == "wonder" else "major_renovation",
            entity_confidence=0.9 if name.casefold() == "wonder" else 0.68,
        )
    db.commit()
    return created


def process_dover(db: Session) -> int:
    source, rows = _source_rows(db, "Dover Down to Business")
    if not source:
        return 0
    found: dict[str, tuple[str, str, str, str, date, RawRecord, RawSourceDocument]] = {}
    patterns = [
        (
            re.compile(
                r"relocation of ([A-Z][^.!?]{2,80}?) to its new home at ([0-9][^,.]{2,80})", re.I
            ),
            "relocation",
            "relocating",
        ),
        (
            re.compile(r"soft opening of ([A-Z][^.!?]{2,80}?) at ([0-9][^,.]{2,80})", re.I),
            "opening_confirmed",
            "operator",
        ),
    ]
    for record, document in rows:
        text = " ".join((record.extracted_text or "").split())
        published = re.search(
            r"(January|February|March|April|May|June|July|August) \d{1,2}, 2026", text
        )
        signal_date = (
            datetime.strptime(published.group(0), "%B %d, %Y").date() if published else date.today()
        )
        for pattern, signal_type, _role in patterns:
            for match in pattern.finditer(text):
                name, address = clean(match.group(1)), clean(match.group(2))
                key = f"dover:{normalize_name(name)}:{normalize_address(address)}:{signal_type}"
                found[key] = (
                    name,
                    address,
                    clean(match.group(0)),
                    signal_type,
                    signal_date,
                    record,
                    document,
                )
    created = 0
    for key, (
        name,
        address,
        description,
        signal_type,
        signal_date,
        record,
        document,
    ) in found.items():
        created += _upsert_evidence_project(
            db,
            source=source,
            record=record,
            document=document,
            project_key=key,
            organization_name=name,
            organization_role="operator",
            address=address,
            city="Dover",
            description=description,
            signal_type=signal_type,
            signal_date=signal_date,
            industry=classify(description),
            opportunity_type="relocation" if signal_type == "relocation" else "new_business",
            entity_confidence=0.9,
        )
    db.commit()
    return created


def process_manchester_zoning(db: Session) -> int:
    source, rows = _source_rows(db, "Manchester Zoning Board Agendas")
    if not source:
        return 0
    item_pattern = re.compile(
        r"(?ms)^\s*\d+[.)]\s+(ZBA\d{4}-\d+),\s+(.+?)\s*\n"
        r"[^\n]*Zoning District[^\n]*\n(.+?)(?=^\s*\d+[.)]\s+ZBA\d{4}-\d+|^\s*[IVX]+\.|\Z)"
    )
    found: dict[str, tuple[str, str, date, RawRecord, RawSourceDocument]] = {}
    for record, document in rows:
        text = record.extracted_text or ""
        date_match = re.search(
            r"(?:Thursday|Wednesday|Tuesday|Monday),\s+(\w+ \d{1,2}, 2026)", text
        )
        signal_date = (
            datetime.strptime(date_match.group(1), "%B %d, %Y").date()
            if date_match
            else date.today()
        )
        for match in item_pattern.finditer(text):
            project_id, address, description = (
                match.group(1),
                clean(match.group(2)),
                clean(match.group(3)),
            )
            if not COMMERCIAL_USE.search(description):
                continue
            if re.search(
                r"existing (?:beauty salon|retail|office)", description, re.I
            ) and not re.search(
                r"expand|new|establish|change the use|construct", description, re.I
            ):
                continue
            found[project_id] = (address, description, signal_date, record, document)
    created = 0
    for project_id, (address, description, signal_date, record, document) in found.items():
        signal_type = "sign_permit" if "sign" in description.casefold() else "zoning_application"
        created += _upsert_evidence_project(
            db,
            source=source,
            record=record,
            document=document,
            project_key=project_id,
            organization_name=f"Unresolved commercial project — {address}",
            organization_role="unresolved_project",
            address=address,
            city="Manchester",
            description=description,
            signal_type=signal_type,
            signal_date=signal_date,
            industry=classify(description),
            entity_confidence=0.4,
        )
    db.commit()
    return created


def process_nashua(db: Session) -> int:
    source, rows = _source_rows(db, "Nashua Planning Board Archive")
    if not source:
        return 0
    pattern = re.compile(
        r"(?s)(A\d{2}-\d+)\s+(.{2,140}?)\s*\(([^)]*(?:Owner|Applicant)[^)]*)\)"
        r"[,.]?\s*(?:requesting|requests|Proposed)\s+(.+?)Property is located at\s+"
        r"(.+?)\.\s*Sheet"
    )
    found: dict[str, tuple[str, str, str, str, date, RawRecord, RawSourceDocument]] = {}
    for record, document in rows:
        text = " ".join((record.extracted_text or "").split())
        date_match = re.search(
            r"(?:meeting|Hearing)\s+(January|February|March|April|May|June)\s+"
            r"(\d{1,2}),\s+(2025)",
            text,
            re.I,
        )
        signal_date = (
            datetime.strptime(" ".join(date_match.groups()), "%B %d %Y").date()
            if date_match
            else date(2025, 1, 1)
        )
        for match in pattern.finditer(text):
            project_id, name, roles, description, address = (
                match.group(1),
                clean(match.group(2)),
                match.group(3),
                clean(match.group(4)),
                clean(match.group(5)),
            )
            if not COMMERCIAL_USE.search(description):
                continue
            role = "applicant" if "Applicant" in roles else "property_owner"
            found[project_id] = (
                name,
                role,
                address,
                description,
                signal_date,
                record,
                document,
            )
    created = 0
    for project_id, (
        name,
        role,
        address,
        description,
        signal_date,
        record,
        document,
    ) in found.items():
        created += _upsert_evidence_project(
            db,
            source=source,
            record=record,
            document=document,
            project_key=project_id,
            organization_name=name,
            organization_role=role,
            address=address,
            city="Nashua",
            description=description,
            signal_type="planning_application",
            signal_date=signal_date,
            industry=classify(description),
            entity_confidence=0.65,
        )
    db.commit()
    return created


def process_salem_permits(db: Session) -> int:
    source, rows = _source_rows(db, "Salem Issued Building Permits (Historical)")
    if not source:
        return 0
    created = 0
    high_value = re.compile(
        r"CHANGE OF OCCUPANT|TENANT FIT|NEW CONSTRUCTION--COMMERCIAL|RESTAURANT FIT|"
        r"CERTIFICATE OF OCCUPANCY|NEW (?:RESTAURANT|RETAIL|OFFICE)",
        re.I,
    )
    permit_type = re.compile(
        r"ALTERATION--COMMERCIAL|CHANGE OF OCCUPANT--\s*COMMERCIAL|"
        r"NEW OCCUPANT--NO CONSTRUCTION|NEW CONSTRUCTION--COMMERCIAL|"
        r"CERTIFICATE OF OCCUPANCY|TEMPORARY EVENT",
        re.I,
    )
    for record, document in rows:
        description = clean(record.extracted_text or "")
        if not high_value.search(description) or "TEMPORARY EVENT" in description.upper():
            continue
        address = re.sub(
            r"^(\d+)([A-Z])", r"\1 \2", str(record.raw_payload.get("address") or "").strip()
        )
        issued = str(record.raw_payload.get("issued_date") or "")
        if not address or not issued:
            continue
        body = re.sub(r"^B-\d{2}-\d+\s+\d{1,2}/\d{1,2}/\d{4}\s+", "", description)
        before_type = permit_type.split(body, maxsplit=1)[0]
        candidate_name = (
            clean(before_type[len(address) :]) if before_type.startswith(address) else ""
        )
        if "-" in candidate_name and re.search(r"\d", candidate_name.split("-", 1)[0]):
            candidate_name = clean(candidate_name.split("-", 1)[1])
        candidate_name = re.sub(r"^#[A-Z0-9-]+\s+", "", candidate_name).strip()
        generic_name = not candidate_name or bool(
            re.search(r"^(UNIT|SUITE|BUILDING|LOT)\b", candidate_name, re.I)
        )
        name = f"Unresolved commercial permit — {address}" if generic_name else candidate_name
        role = "unresolved_project" if generic_name else "operator"
        signal_type = (
            "certificate_of_occupancy"
            if "CERTIFICATE OF OCCUPANCY" in description.upper()
            else "building_permit"
        )
        created += _upsert_evidence_project(
            db,
            source=source,
            record=record,
            document=document,
            project_key=record.external_id,
            organization_name=name,
            organization_role=role,
            address=address,
            city="Salem",
            description=description,
            signal_type=signal_type,
            signal_date=datetime.strptime(issued, "%m/%d/%Y").date(),
            industry=classify(description),
            opportunity_type="new_location",
            entity_confidence=0.85 if role == "operator" else 0.45,
        )
    db.commit()
    return created


def process_phase_05(db: Session) -> dict[str, int]:
    results = {
        "nashua": process_nashua(db),
        "manchester_zoning": process_manchester_zoning(db),
        "bedford": process_bedford(db),
        "portsmouth": process_portsmouth(db),
        "salem": process_salem(db),
        "dover": process_dover(db),
        "salem_permits": process_salem_permits(db),
    }
    return results
