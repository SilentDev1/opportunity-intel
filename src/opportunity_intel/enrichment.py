import csv
import hashlib
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import (
    BusinessContact,
    ManualReview,
    Opportunity,
    OpportunityEnrichment,
    OpportunityOrganizationRole,
    Organization,
    RawRecord,
    RawSourceDocument,
    Signal,
    Source,
    StageHistory,
    VendorFeedback,
)
from .services import infer_stage

CONTACT_TYPES = {
    "phone",
    "email",
    "contact_page",
    "website",
    "careers_page",
    "linkedin_business",
    "other",
}
SIGNAL_FAMILIES = {
    "planning_application": "municipal_land_use",
    "zoning_application": "municipal_land_use",
    "sign_permit": "municipal_land_use",
    "building_permit": "permit_buildout",
    "construction_started": "permit_buildout",
    "certificate_of_occupancy": "occupancy",
    "inspection": "occupancy",
    "location_announcement": "official_company",
    "coming_soon_page": "official_company",
    "opening_date_announced": "official_company",
    "opening_confirmed": "official_company",
    "job_posting": "location_hiring",
    "hiring_started": "location_hiring",
    "relocation": "municipal_news",
}
VENDOR_OUTCOMES = {
    "NOT_REVIEWED",
    "REVIEWED_USEFUL",
    "REVIEWED_NOT_USEFUL",
    "CONTACT_ATTEMPTED",
    "CONTACTED",
    "MEETING",
    "QUOTE",
    "CUSTOMER_WON",
    "NO_RESPONSE",
    "BAD_LEAD",
}


def normalize_phone(value: str) -> str:
    digits = re.sub(r"\D", "", value)
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    if len(digits) != 10:
        raise ValueError("Business phone must contain 10 US digits")
    return f"+1{digits}"


def normalize_url(value: str) -> str:
    value = value.strip()
    if not value.startswith(("http://", "https://")):
        value = "https://" + value
    parsed = urlsplit(value)
    if not parsed.hostname or "." not in parsed.hostname:
        raise ValueError("Contact URL must have a valid domain")
    host = parsed.hostname.casefold().removeprefix("www.")
    port = f":{parsed.port}" if parsed.port else ""
    path = parsed.path.rstrip("/") or ""
    return urlunsplit(("https", host + port, path, parsed.query, ""))


def normalize_contact(contact_type: str, value: str) -> str:
    if contact_type not in CONTACT_TYPES:
        raise ValueError(f"Unknown contact type: {contact_type}")
    if contact_type == "phone":
        return normalize_phone(value)
    if contact_type == "email":
        normalized = value.strip().casefold()
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", normalized):
            raise ValueError("Invalid business email")
        return normalized
    if contact_type in {"contact_page", "website", "careers_page", "linkedin_business"}:
        return normalize_url(value)
    return value.strip()


def official_website_match(official: bool, confidence: float, match_reason: str) -> bool:
    reason = match_reason.casefold()
    evidence = (
        "same brand",
        "same address",
        "same city",
        "official location",
        "same operator",
        "same phone",
    )
    return official and confidence >= 0.8 and any(item in reason for item in evidence)


def signal_family(signal: Signal) -> str:
    stored = (signal.structured_data or {}).get("signal_family")
    return str(stored) if stored else SIGNAL_FAMILIES.get(signal.signal_type, signal.signal_type)


def independent_signal_families(signals: list[Signal]) -> set[str]:
    return {signal_family(item) for item in signals}


def contactability_status(contacts: list[BusinessContact]) -> tuple[str, str]:
    active = [item for item in contacts if item.status == "active" and item.is_public]
    strong = [
        item
        for item in active
        if item.is_official
        and item.confidence >= 0.8
        and item.contact_type in {"phone", "email", "contact_page"}
    ]
    inquiry_websites = [
        item
        for item in active
        if item.is_official
        and item.confidence >= 0.8
        and item.contact_type == "website"
        and "inquiry route" in (item.label or "").casefold()
    ]
    if strong or inquiry_websites:
        kinds = sorted({item.contact_type for item in strong + inquiry_websites})
        return "CONTACTABLE", "Verified official public route: " + ", ".join(kinds) + "."
    if any(item.is_official and item.confidence >= 0.8 for item in active):
        return (
            "PARTIALLY_CONTACTABLE",
            "Official business presence verified, but no clear inquiry route.",
        )
    if active:
        return (
            "UNCERTAIN",
            "A public route exists, but official ownership or entity matching is uncertain.",
        )
    return "NOT_CONTACTABLE", "No verified legitimate public business contact route stored."


def vendor_readiness(
    opportunity: Opportunity,
    operator_status: str,
    contact_status: str,
    independent_family_count: int,
) -> tuple[float, str, dict[str, float]]:
    breakdown = {
        "actionable": 20.0 if opportunity.status == "actionable" else 0.0,
        "operator": 20.0
        if operator_status == "KNOWN"
        else 5.0
        if operator_status == "UNKNOWN"
        else 0.0,
        "exact_location": 10.0 if opportunity.location_id else 0.0,
        "stage_confidence": round(min(15.0, opportunity.stage_confidence * 15), 1),
        "corroboration": min(15.0, max(0, independent_family_count - 1) * 7.5),
        "contactability": 15.0
        if contact_status == "CONTACTABLE"
        else 8.0
        if contact_status == "PARTIALLY_CONTACTABLE"
        else 2.0
        if contact_status == "UNCERTAIN"
        else 0.0,
        "freshness_timing": 5.0
        if opportunity.stage not in {"OPEN", "CLOSED", "STALE", "CANCELLED"}
        else 0.0,
    }
    score = round(sum(breakdown.values()), 1)
    band = "HIGH" if score >= 75 else "MEDIUM" if score >= 50 else "LOW"
    return score, band, breakdown


def upsert_contact(
    db: Session,
    *,
    organization_id: str,
    location_id: str | None,
    contact_type: str,
    value: str,
    label: str | None,
    is_official: bool,
    is_public: bool,
    source_url: str,
    source_name: str,
    source_type: str,
    confidence: float,
    match_reason: str,
    observed_at: datetime,
) -> tuple[BusinessContact, bool]:
    normalized = normalize_contact(contact_type, value)
    normalized_source = normalize_url(source_url)
    if contact_type in {"website", "contact_page", "careers_page"} and not official_website_match(
        is_official, confidence, match_reason
    ):
        raise ValueError("Website match lacks strong official entity/location evidence")
    existing = db.scalar(
        select(BusinessContact).where(
            BusinessContact.organization_id == organization_id,
            BusinessContact.contact_type == contact_type,
            BusinessContact.value == normalized,
            BusinessContact.source_url == normalized_source,
        )
    )
    if existing:
        existing.last_seen_at = observed_at
        existing.verified_at = observed_at
        existing.confidence = confidence
        existing.status = "active"
        return existing, False
    contact = BusinessContact(
        organization_id=organization_id,
        location_id=location_id,
        contact_type=contact_type,
        value=normalized,
        label=label,
        is_official=is_official,
        is_public=is_public,
        source_url=normalized_source,
        source_name=source_name,
        source_type=source_type,
        confidence=confidence,
        match_reason=match_reason,
        retrieved_at=observed_at,
        verified_at=observed_at,
        first_seen_at=observed_at,
        last_seen_at=observed_at,
    )
    db.add(contact)
    return contact, True


def refresh_enrichment(
    db: Session,
    opportunity: Opportunity,
    operator_status: str | None = None,
    chain_classification: str | None = None,
) -> OpportunityEnrichment:
    enrichment = db.get(OpportunityEnrichment, opportunity.id) or OpportunityEnrichment(
        opportunity_id=opportunity.id
    )
    if operator_status:
        enrichment.operator_status = operator_status
    if chain_classification:
        enrichment.chain_classification = chain_classification
    related_org_ids = {opportunity.organization_id}
    related_org_ids.update(
        db.scalars(
            select(OpportunityOrganizationRole.organization_id).where(
                OpportunityOrganizationRole.opportunity_id == opportunity.id,
                OpportunityOrganizationRole.role.in_(["operator", "tenant", "franchisee"]),
            )
        )
    )
    contacts = list(
        db.scalars(
            select(BusinessContact).where(BusinessContact.organization_id.in_(related_org_ids))
        )
    )
    enrichment.contactability_status, enrichment.contactability_reason = contactability_status(
        contacts
    )
    signals = list(
        db.scalars(
            select(Signal).where(
                Signal.organization_id == opportunity.organization_id,
                Signal.location_id == opportunity.location_id,
            )
        )
    )
    score, band, breakdown = vendor_readiness(
        opportunity,
        enrichment.operator_status,
        enrichment.contactability_status,
        len(independent_signal_families(signals)),
    )
    enrichment.vendor_readiness_score = score
    enrichment.vendor_readiness_band = band
    enrichment.vendor_readiness_breakdown = breakdown
    db.add(enrichment)
    return enrichment


def blind_batch_metrics(db: Session, opportunity_ids: set[str]) -> dict[str, float | int]:
    latest: dict[str, ManualReview] = {}
    for review in db.scalars(
        select(ManualReview)
        .where(ManualReview.opportunity_id.in_(opportunity_ids))
        .order_by(ManualReview.reviewed_at)
    ):
        latest[review.opportunity_id] = review
    counts = Counter(item.verdict for item in latest.values())
    size = len(opportunity_ids)
    return {
        "batch_size": size,
        **{
            key: counts[key]
            for key in ("actionable", "false_positive", "duplicate", "stale", "uncertain")
        },
        "false_positive_rate": round(counts["false_positive"] / size * 100, 1) if size else 0.0,
    }


def import_enrichment_csv(db: Session, path: Path) -> dict[str, int]:
    counts: Counter[str] = Counter()
    observed_at = datetime.utcnow()
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            opportunity = db.get(Opportunity, row["opportunity_id"])
            if not opportunity:
                raise ValueError(f"Unknown opportunity: {row['opportunity_id']}")
            target_org = db.get(Organization, opportunity.organization_id)
            operator_name = row.get("operator_name", "").strip()
            if (
                operator_name
                and target_org
                and operator_name.casefold() != target_org.canonical_name.casefold()
            ):
                operator = db.scalar(
                    select(Organization).where(
                        Organization.normalized_name == operator_name.casefold()
                    )
                )
                if not operator:
                    operator = Organization(
                        canonical_name=operator_name,
                        normalized_name=operator_name.casefold(),
                        legal_name=row.get("operator_legal_name") or None,
                        dba_name=row.get("operating_brand") or None,
                        industry=target_org.industry,
                    )
                    db.add(operator)
                    db.flush()
                    counts["organizations"] += 1
                role = db.scalar(
                    select(OpportunityOrganizationRole).where(
                        OpportunityOrganizationRole.opportunity_id == opportunity.id,
                        OpportunityOrganizationRole.organization_id == operator.id,
                        OpportunityOrganizationRole.role == "operator",
                    )
                )
                if not role:
                    db.add(
                        OpportunityOrganizationRole(
                            opportunity_id=opportunity.id,
                            organization_id=operator.id,
                            role="operator",
                            confidence=float(row.get("operator_confidence") or 0.9),
                            evidence=row.get("operator_evidence") or "Official enrichment evidence",
                        )
                    )
                    counts["roles"] += 1
                target_org = operator
            for suffix in range(1, 6):
                contact_type = row.get(f"contact_type_{suffix}", "").strip()
                if not contact_type or not target_org:
                    continue
                _, created = upsert_contact(
                    db,
                    organization_id=target_org.id,
                    location_id=opportunity.location_id,
                    contact_type=contact_type,
                    value=row[f"contact_value_{suffix}"],
                    label=row.get(f"contact_label_{suffix}") or None,
                    is_official=True,
                    is_public=True,
                    source_url=row[f"contact_source_url_{suffix}"],
                    source_name=row.get(f"contact_source_name_{suffix}")
                    or "Official business source",
                    source_type=row.get(f"contact_source_type_{suffix}") or "official_company",
                    confidence=float(row.get(f"contact_confidence_{suffix}") or 0.9),
                    match_reason=row.get(f"contact_match_reason_{suffix}")
                    or "same brand shown on official source",
                    observed_at=observed_at,
                )
                counts["contacts"] += int(created)
            refresh_enrichment(
                db,
                opportunity,
                row.get("operator_status") or None,
                row.get("chain_classification") or None,
            )
            counts["opportunities"] += 1
    db.commit()
    return dict(counts)


def import_evidence_csv(db: Session, path: Path) -> dict[str, int]:
    """Import manually verified evidence snapshots without pretending to crawl whole sites."""
    counts: Counter[str] = Counter()
    observed_at = datetime.utcnow()
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            opportunity = db.get(Opportunity, row["opportunity_id"])
            if not opportunity:
                raise ValueError(f"Unknown opportunity: {row['opportunity_id']}")
            source = db.scalar(select(Source).where(Source.name == row["source_name"]))
            if not source:
                source = Source(
                    name=row["source_name"],
                    source_type=row["source_type"],
                    jurisdiction=row.get("jurisdiction") or "New Hampshire",
                    base_url=normalize_url(row["source_url"]),
                    authority_level=int(row.get("authority_level") or 4),
                    is_official=row.get("is_official", "true").casefold() == "true",
                    collector_name="targeted_enrichment",
                    collector_version="1",
                    enabled=False,
                    schedule="manual",
                )
                db.add(source)
                db.flush()
                counts["sources"] += 1
            snapshot = row["title"] + "\n" + row["description"]
            content_hash = hashlib.sha256(snapshot.encode()).hexdigest()
            document = db.scalar(
                select(RawSourceDocument).where(
                    RawSourceDocument.source_id == source.id,
                    RawSourceDocument.content_hash == content_hash,
                )
            )
            if not document:
                document = RawSourceDocument(
                    source_id=source.id,
                    source_url=normalize_url(row["source_url"]),
                    retrieved_at=observed_at,
                    published_at=datetime.fromisoformat(row["signal_date"])
                    if row.get("signal_date")
                    else None,
                    content_type="text/plain",
                    http_status=200,
                    content_hash=content_hash,
                    storage_path=f"targeted-enrichment/{content_hash}.txt",
                    title=row["title"],
                    document_metadata={
                        "evidence_snapshot": snapshot,
                        "collection_mode": "manual_verified",
                    },
                    processing_status="processed",
                    extraction_quality=1.0,
                )
                db.add(document)
                db.flush()
                counts["documents"] += 1
            external_id = f"{opportunity.id}:{row['signal_type']}:{row['signal_family']}"
            record = db.scalar(
                select(RawRecord).where(
                    RawRecord.raw_source_document_id == document.id,
                    RawRecord.external_id == external_id,
                )
            )
            if not record:
                record = RawRecord(
                    raw_source_document_id=document.id,
                    record_type="targeted_enrichment",
                    external_id=external_id,
                    raw_payload=dict(row),
                    extracted_text=snapshot,
                )
                db.add(record)
                db.flush()
                counts["records"] += 1
            existing = db.scalar(
                select(Signal).where(
                    Signal.raw_record_id == record.id,
                    Signal.signal_type == row["signal_type"],
                    Signal.organization_id == opportunity.organization_id,
                    Signal.location_id == opportunity.location_id,
                )
            )
            if not existing:
                existing = Signal(
                    organization_id=opportunity.organization_id,
                    location_id=opportunity.location_id,
                    source_id=source.id,
                    raw_record_id=record.id,
                    signal_type=row["signal_type"],
                    signal_date=datetime.fromisoformat(row["signal_date"]).date()
                    if row.get("signal_date")
                    else None,
                    title=row["title"],
                    description=row["description"],
                    structured_data={
                        "signal_family": row["signal_family"],
                        "targeted_enrichment": True,
                    },
                    confidence=float(row.get("confidence") or 0.9),
                    source_url=normalize_url(row["source_url"]),
                    is_verified=True,
                )
                db.add(existing)
                db.flush()
                counts["signals"] += 1
            signals = list(
                db.scalars(
                    select(Signal).where(
                        Signal.organization_id == opportunity.organization_id,
                        Signal.location_id == opportunity.location_id,
                    )
                )
            )
            prior_stage = opportunity.stage
            stage, stage_confidence, reasoning = infer_stage(signals)
            if (
                stage.value != prior_stage
                and row.get("allow_stage_change", "false").casefold() == "true"
            ):
                opportunity.stage = stage.value
                opportunity.stage_confidence = stage_confidence
                opportunity.stage_reasoning = reasoning
                opportunity.stage_updated_at = observed_at
                db.add(
                    StageHistory(
                        opportunity_id=opportunity.id,
                        from_stage=prior_stage,
                        to_stage=stage.value,
                        reason="Targeted corroborating evidence: " + row["title"],
                        triggering_signal_id=existing.id,
                    )
                )
                counts["stage_changes"] += 1
            refresh_enrichment(db, opportunity)
    db.commit()
    return dict(counts)


def import_vendor_feedback_csv(db: Session, path: Path) -> int:
    count = 0
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if not row.get("opportunity_id"):
                continue
            if not db.get(Opportunity, row["opportunity_id"]):
                raise ValueError(f"Unknown opportunity: {row['opportunity_id']}")
            outcome = row.get("outcome_status") or "NOT_REVIEWED"
            if outcome not in VENDOR_OUTCOMES:
                raise ValueError(f"Unknown vendor outcome: {outcome}")

            def optional_bool(raw_value: str) -> bool | None:
                value = raw_value.strip().casefold()
                return None if not value else value in {"true", "yes", "1"}

            rating = int(row["rating"]) if row.get("rating") else None
            if rating is not None and not 1 <= rating <= 5:
                raise ValueError("Vendor rating must be 1 through 5")
            db.add(
                VendorFeedback(
                    vendor_profile=row["vendor_profile"],
                    opportunity_id=row["opportunity_id"],
                    already_knew=optional_bool(row.get("already_knew", "")),
                    would_contact=optional_bool(row.get("would_contact", "")),
                    timing_useful=optional_bool(row.get("timing_useful", "")),
                    lead_relevant=optional_bool(row.get("lead_relevant", "")),
                    contact_info_sufficient=optional_bool(row.get("contact_info_sufficient", "")),
                    rating=rating,
                    comment=row.get("comment") or None,
                    outcome_status=outcome,
                    created_at=datetime.fromisoformat(row["created_at"])
                    if row.get("created_at")
                    else datetime.utcnow(),
                )
            )
            count += 1
    db.commit()
    return count
