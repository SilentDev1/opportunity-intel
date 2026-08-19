import csv
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import func, select, tuple_
from sqlalchemy.orm import Session

from .enrichment import independent_signal_families
from .models import (
    BusinessContact,
    InferredNeed,
    Location,
    ManualReview,
    Opportunity,
    OpportunityEnrichment,
    OpportunityOrganizationRole,
    Organization,
    RawRecord,
    RawSourceDocument,
    ReviewItem,
    Signal,
    Source,
    StageHistory,
)
from .services import match_profile, validation_summary

REVIEW_VERDICTS = {
    "actionable",
    "not_actionable",
    "false_positive",
    "duplicate",
    "stale",
    "uncertain",
}

VENDOR_PROFILES: dict[str, dict[str, Any]] = {
    "commercial_cleaning": {
        "service_categories": ["commercial_cleaning", "post_construction_cleaning"],
        "target_industries": [
            "restaurant",
            "medical",
            "dental",
            "retail",
            "childcare",
            "professional_office",
            "fitness",
        ],
    },
    "it_msp": {
        "service_categories": ["it_msp", "networking", "internet"],
        "target_industries": [
            "medical",
            "dental",
            "professional_office",
            "retail",
            "restaurant",
            "hospitality",
            "financial_services",
        ],
    },
    "security_access_control": {
        "service_categories": ["security_cameras", "access_control", "alarm"],
        "target_industries": [
            "retail",
            "restaurant",
            "medical",
            "childcare",
            "professional_office",
            "warehouse_logistics",
            "hospitality",
            "entertainment",
        ],
    },
    "pest_control": {
        "service_categories": ["pest_control"],
        "target_industries": ["restaurant", "hospitality", "childcare", "retail"],
    },
    "commercial_insurance": {
        "service_categories": ["commercial_insurance"],
        "target_industries": [],
    },
    "signage": {"service_categories": ["signage"], "target_industries": []},
    "telecom_internet": {
        "service_categories": ["telecom", "internet", "networking"],
        "target_industries": [],
    },
    "payroll": {"service_categories": ["payroll"], "target_industries": []},
    "waste_management": {
        "service_categories": ["waste_management"],
        "target_industries": ["restaurant", "retail", "warehouse/logistics"],
    },
    "landscaping_snow": {
        "service_categories": ["landscaping", "snow_removal"],
        "target_industries": [],
    },
    "pos_payments": {
        "service_categories": ["pos", "payment_processing"],
        "target_industries": ["restaurant", "retail"],
    },
}

TIMING_BY_STAGE: dict[str, dict[str, str]] = {
    "PLANNING": {
        "commercial_insurance": "contact now",
        "security_access_control": "monitor until buildout",
        "it_msp": "monitor until buildout",
        "commercial_cleaning": "too early; monitor",
        "pest_control": "too early; monitor",
    },
    "BUILDOUT": {
        "commercial_insurance": "contact now",
        "security_access_control": "contact now",
        "it_msp": "contact now",
        "commercial_cleaning": "contact for post-construction work",
        "pest_control": "monitor for pre-opening",
    },
    "PRE_OPENING": {
        "commercial_insurance": "urgent",
        "security_access_control": "urgent",
        "it_msp": "urgent",
        "commercial_cleaning": "contact now",
        "pest_control": "contact now",
    },
    "FINAL_PREP": {key: "urgent; sales window may be closing" for key in VENDOR_PROFILES},
}


def review_opportunity(db: Session, opportunity_id: str, verdict: str, note: str) -> None:
    if verdict not in REVIEW_VERDICTS:
        raise ValueError(f"Invalid verdict: {verdict}")
    opportunity = db.get(Opportunity, opportunity_id)
    if not opportunity:
        raise ValueError("Opportunity not found")
    previous = db.scalar(
        select(ManualReview)
        .where(ManualReview.opportunity_id == opportunity_id)
        .order_by(ManualReview.reviewed_at.desc())
        .limit(1)
    )
    if previous and previous.verdict == verdict and (previous.notes or "") == note:
        return
    db.add(ManualReview(opportunity_id=opportunity_id, verdict=verdict, notes=note))
    opportunity.status = verdict
    for item in db.scalars(
        select(ReviewItem).where(
            ReviewItem.entity_type == "opportunity", ReviewItem.entity_id == opportunity_id
        )
    ):
        item.status = "resolved"
        item.resolution = verdict
        item.notes = note
        item.reviewed_at = datetime.utcnow()
    db.commit()


def import_review_csv(db: Session, path: Path) -> int:
    count = 0
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            review_opportunity(db, row["opportunity_id"], row["verdict"], row["note"])
            count += 1
    return count


def latest_reviews(db: Session) -> dict[str, ManualReview]:
    result: dict[str, ManualReview] = {}
    for review in db.scalars(select(ManualReview).order_by(ManualReview.reviewed_at)):
        result[review.opportunity_id] = review
    return result


def detailed_validation_report(db: Session) -> dict[str, Any]:
    report = validation_summary(db)
    reviews = latest_reviews(db)
    verdicts = Counter(review.verdict for review in reviews.values())
    reviewed = sum(verdicts.values())
    report["reviewed_candidates"] = reviewed
    report["manual_reviews"] = dict(verdicts)
    report["review_verdicts"] = dict(verdicts)
    report["manually_verified_actionable"] = verdicts["actionable"]
    report["false_positives"] = verdicts["false_positive"]
    report["actionable_rate"] = (
        round(verdicts["actionable"] / reviewed * 100, 1) if reviewed else None
    )
    report["actionable_conversion_rate"] = report["actionable_rate"]
    report["false_positive_rate"] = (
        round(verdicts["false_positive"] / reviewed * 100, 1) if reviewed else None
    )
    report["duplicate_rate"] = (
        round(verdicts["duplicate"] / reviewed * 100, 1) if reviewed else None
    )
    by_city: dict[str, Counter[str]] = defaultdict(Counter)
    by_industry: dict[str, Counter[str]] = defaultdict(Counter)
    by_source: dict[str, Counter[str]] = defaultdict(Counter)
    for opportunity, org, location in db.execute(
        select(Opportunity, Organization, Location)
        .join(Organization, Opportunity.organization_id == Organization.id)
        .join(Location, Opportunity.location_id == Location.id)
    ):
        verdict = reviews.get(opportunity.id)
        label = verdict.verdict if verdict else "unreviewed"
        by_city[location.city or "unknown"]["candidates"] += 1
        by_city[location.city or "unknown"][label] += 1
        by_industry[org.industry or "unknown"]["candidates"] += 1
        by_industry[org.industry or "unknown"][label] += 1
        source_names = set(
            db.scalars(
                select(Source.name)
                .join(Signal, Signal.source_id == Source.id)
                .where(
                    Signal.organization_id == opportunity.organization_id,
                    Signal.location_id == opportunity.location_id,
                )
            )
        )
        for source_name in source_names:
            by_source[source_name]["opportunities"] += 1
            by_source[source_name][label] += 1
    report["by_city"] = {key: dict(value) for key, value in sorted(by_city.items())}
    report["by_industry"] = {key: dict(value) for key, value in sorted(by_industry.items())}
    report["by_source"] = {key: dict(value) for key, value in sorted(by_source.items())}
    report["multi_signal"] = multi_signal_metrics(db)
    report["independent_signal_families"] = independent_signal_metrics(db)
    report["contactability"] = contactability_metrics(db)
    return report


def vendor_simulation(db: Session, actionable_only: bool = True) -> dict[str, Any]:
    reviews = latest_reviews(db)
    simulations: dict[str, Any] = {}
    for vendor, profile in VENDOR_PROFILES.items():
        scores: list[float] = []
        strong = 0
        for opportunity, org, location in db.execute(
            select(Opportunity, Organization, Location)
            .join(Organization, Opportunity.organization_id == Organization.id)
            .join(Location, Opportunity.location_id == Location.id)
        ):
            if actionable_only and (
                opportunity.id not in reviews or reviews[opportunity.id].verdict != "actionable"
            ):
                continue
            needs = list(
                db.scalars(
                    select(InferredNeed.service_category).where(
                        InferredNeed.opportunity_id == opportunity.id
                    )
                )
            )
            item = {
                "industry": org.industry,
                "city": location.city,
                "stage": opportunity.stage,
                "score": opportunity.score,
                "service_categories": needs,
            }
            result = match_profile(item, {**profile, "cities": [location.city]})
            score = float(result["match_score"])
            if score >= 50:
                scores.append(score)
                strong += score >= 75
        simulations[vendor] = {
            "matches": len(scores),
            "average_match_score": round(sum(scores) / len(scores), 1) if scores else None,
            "strong_matches": strong,
        }
    return simulations


def timing_value(stage: str, signal_types: set[str]) -> tuple[str, str]:
    if stage in {"OPEN", "CLOSED", "STALE", "CANCELLED"}:
        return "LOW", "The useful pre-opening sales window has passed or the project is inactive."
    if stage in {"BUILDOUT", "LOCATION_CONFIRMED"}:
        return "HIGH", "The location is known while vendors can still influence buildout choices."
    if stage in {"PRE_OPENING", "FINAL_PREP"} or "hiring_started" in signal_types:
        return (
            "MEDIUM",
            "The business is approaching opening, so the remaining sales window is short.",
        )
    return "MEDIUM", "Planning evidence is early, but tenant identity or project timing may change."


def freshness(opportunity: Opportunity, today: date | None = None) -> str:
    today = today or date.today()
    if opportunity.stage in {"OPEN", "CANCELLED"}:
        return opportunity.stage
    if opportunity.stage == "STALE":
        return "STALE"
    last = (opportunity.last_signal_at or opportunity.first_detected_at).date()
    age = (today - last).days
    if age <= 14:
        return "NEW"
    if age <= 60:
        return "ACTIVE"
    if age <= 120:
        return "AGING"
    return "STALE"


def multi_signal_metrics(db: Session) -> dict[str, Any]:
    reviews = latest_reviews(db)
    buckets: dict[str, Counter[str]] = defaultdict(Counter)
    for opportunity in db.scalars(select(Opportunity)):
        count = (
            db.scalar(
                select(func.count())
                .select_from(Signal)
                .where(
                    Signal.organization_id == opportunity.organization_id,
                    Signal.location_id == opportunity.location_id,
                )
            )
            or 0
        )
        bucket = "1" if count <= 1 else "2" if count == 2 else "3" if count == 3 else "4+"
        verdict = reviews.get(opportunity.id)
        buckets[bucket]["opportunities"] += 1
        if verdict:
            buckets[bucket]["reviewed"] += 1
            buckets[bucket][verdict.verdict] += 1
    result: dict[str, dict[str, Any]] = {}
    for bucket in ["1", "2", "3", "4+"]:
        values = buckets[bucket]
        result[bucket] = dict(values)
        result[bucket]["actionable_rate"] = (
            round(values["actionable"] / values["reviewed"] * 100, 1)
            if values["reviewed"]
            else None
        )
    return result


def contactability_metrics(db: Session) -> dict[str, Any]:
    reviews = latest_reviews(db)
    actionable = [
        opportunity
        for opportunity in db.scalars(select(Opportunity))
        if reviews.get(opportunity.id) and reviews[opportunity.id].verdict == "actionable"
    ]
    status_values = []
    for item in actionable:
        enrichment = db.get(OpportunityEnrichment, item.id)
        status_values.append(enrichment.contactability_status if enrichment else "NOT_CONTACTABLE")
    statuses = Counter(status_values)
    contactable = statuses["CONTACTABLE"]
    return {
        "actionable": len(actionable),
        "with_legitimate_contact_route": contactable,
        "contactability_rate": round(contactable / len(actionable) * 100, 1)
        if actionable
        else None,
        "statuses": dict(statuses),
    }


def independent_signal_metrics(db: Session) -> dict[str, Any]:
    reviews = latest_reviews(db)
    buckets: dict[str, Counter[str]] = defaultdict(Counter)
    for opportunity in db.scalars(select(Opportunity)):
        signals = list(
            db.scalars(
                select(Signal).where(
                    Signal.organization_id == opportunity.organization_id,
                    Signal.location_id == opportunity.location_id,
                )
            )
        )
        count = len(independent_signal_families(signals))
        bucket = "1" if count <= 1 else "2" if count == 2 else "3+"
        buckets[bucket]["opportunities"] += 1
        review = reviews.get(opportunity.id)
        if review:
            buckets[bucket]["reviewed"] += 1
            buckets[bucket][review.verdict] += 1
    result: dict[str, Any] = {}
    for bucket in ("1", "2", "3+"):
        values = buckets[bucket]
        result[bucket] = dict(values)
        result[bucket]["actionable_rate"] = (
            round(values["actionable"] / values["reviewed"] * 100, 1)
            if values["reviewed"]
            else None
        )
        result[bucket]["false_positive_rate"] = (
            round(values["false_positive"] / values["reviewed"] * 100, 1)
            if values["reviewed"]
            else None
        )
    return result


def source_value_metrics(db: Session) -> list[dict[str, Any]]:
    """Attribute downstream value to each contributing source without double counting leads."""
    reviews = latest_reviews(db)
    rows: list[dict[str, Any]] = []
    for source in db.scalars(select(Source).order_by(Source.name)):
        record_count = (
            db.scalar(
                select(func.count(RawRecord.id))
                .join(
                    RawSourceDocument,
                    RawRecord.raw_source_document_id == RawSourceDocument.id,
                )
                .where(RawSourceDocument.source_id == source.id)
            )
            or 0
        )
        signals = list(db.scalars(select(Signal).where(Signal.source_id == source.id)))
        keys = {(item.organization_id, item.location_id) for item in signals}
        opportunity_ids = (
            set(
                db.scalars(
                    select(Opportunity.id).where(
                        tuple_(Opportunity.organization_id, Opportunity.location_id).in_(keys)
                    )
                )
            )
            if keys
            else set()
        )
        actionable_ids = {
            item_id
            for item_id in opportunity_ids
            if reviews.get(item_id) and reviews[item_id].verdict == "actionable"
        }
        vendor_ready = sum(
            1
            for item_id in actionable_ids
            if (enrichment := db.get(OpportunityEnrichment, item_id))
            and enrichment.vendor_readiness_tier in {"A", "B"}
        )
        fresh_actionable = sum(
            1
            for item_id in actionable_ids
            if (enrichment := db.get(OpportunityEnrichment, item_id))
            and enrichment.freshness_status == "FRESH"
        )
        contactable = sum(
            1
            for item_id in actionable_ids
            if (enrichment := db.get(OpportunityEnrichment, item_id))
            and enrichment.contactability_status == "CONTACTABLE"
        )
        operator_resolved = sum(
            1
            for item_id in actionable_ids
            if (enrichment := db.get(OpportunityEnrichment, item_id))
            and enrichment.operator_confidence in {"CONFIRMED", "HIGH", "MEDIUM"}
        )
        stage_transitions = (
            db.scalar(
                select(func.count(StageHistory.id)).where(
                    StageHistory.triggering_signal_id.in_([item.id for item in signals])
                )
            )
            if signals
            else 0
        ) or 0
        contacts_discovered = (
            db.scalar(
                select(func.count(BusinessContact.id)).where(
                    BusinessContact.source_name == source.name
                )
            )
            or 0
        )
        corroborations = sum(
            1
            for item_id in opportunity_ids
            if len(
                independent_signal_families(
                    list(
                        db.scalars(
                            select(Signal)
                            .join(
                                Opportunity,
                                (Signal.organization_id == Opportunity.organization_id)
                                & (Signal.location_id == Opportunity.location_id),
                            )
                            .where(Opportunity.id == item_id)
                        )
                    )
                )
            )
            >= 2
        )
        rows.append(
            {
                "source": source.name,
                "records": record_count,
                "signals": len(signals),
                "candidate_opportunities": len(opportunity_ids),
                "actionable_opportunities": len(actionable_ids),
                "fresh_actionable_opportunities": fresh_actionable,
                "operators_resolved": operator_resolved,
                "contactable_opportunities": contactable,
                "contacts_discovered": contacts_discovered,
                "corroborations_added": corroborations,
                "stage_transitions": stage_transitions,
                "vendor_ready_leads": vendor_ready,
                "value_score": vendor_ready * 5
                + operator_resolved * 3
                + len(actionable_ids) * 2
                + contacts_discovered,
            }
        )
    return sorted(rows, key=lambda item: (-item["value_score"], item["source"]))


def weekly_cohort(db: Session, period_start: date, period_end: date) -> dict[str, Any]:
    start = datetime.combine(period_start, datetime.min.time())
    end = datetime.combine(period_end + timedelta(days=1), datetime.min.time())
    signals = list(
        db.scalars(select(Signal).where(Signal.detected_at >= start, Signal.detected_at < end))
    )
    opportunities = list(
        db.scalars(
            select(Opportunity).where(
                Opportunity.first_detected_at >= start, Opportunity.first_detected_at < end
            )
        )
    )
    new_keys = {(item.organization_id, item.location_id) for item in opportunities}
    updated_keys = {
        (signal.organization_id, signal.location_id)
        for signal in signals
        if (signal.organization_id, signal.location_id) not in new_keys
    }
    reviews = latest_reviews(db)
    verdicts = Counter(reviews[item.id].verdict for item in opportunities if item.id in reviews)
    return {
        "period": {"start": period_start.isoformat(), "end": period_end.isoformat()},
        "new_signals": len(signals),
        "new_candidate_opportunities": len(opportunities),
        "new_actionable_opportunities": verdicts["actionable"],
        "false_positives": verdicts["false_positive"],
        "duplicates": verdicts["duplicate"],
        "stale_cancelled": verdicts["stale"] + verdicts["cancelled"],
        "existing_opportunities_updated": len(updated_keys),
    }


def export_validation_csv(db: Session, path: Path) -> int:
    reviews = latest_reviews(db)
    fields = [
        "organization",
        "brand",
        "operating_brand",
        "operator_status",
        "operator_confidence",
        "city",
        "address",
        "industry",
        "stage",
        "opportunity_type",
        "score",
        "vendor_readiness_score",
        "vendor_readiness_tier",
        "independent_signal_count",
        "contactability_status",
        "contact_utility_class",
        "contact_utility_score",
        "freshness_status",
        "source_event_at",
        "source_published_at",
        "first_observed_live_at",
        "first_actionable_live_at",
        "last_meaningful_signal_at",
        "cleaning_relevance_score",
        "cleaning_lead_tier",
        "official_website",
        "business_phone",
        "business_email",
        "contact_page",
        "timing_value",
        "stage_confidence",
        "signal_count",
        "first_detected_at",
        "first_actionable_at",
        "first_operator_identified_at",
        "first_contactable_at",
        "last_signal_at",
        "estimated_open_window",
        "review_status",
        "review_note",
        "source_count",
        "vendor_needs",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = 0
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for opportunity, org, location in db.execute(
            select(Opportunity, Organization, Location)
            .join(Organization, Opportunity.organization_id == Organization.id)
            .join(Location, Opportunity.location_id == Location.id)
        ):
            signals = list(
                db.scalars(
                    select(Signal).where(
                        Signal.organization_id == opportunity.organization_id,
                        Signal.location_id == opportunity.location_id,
                    )
                )
            )
            needs = list(
                db.scalars(
                    select(InferredNeed.service_category).where(
                        InferredNeed.opportunity_id == opportunity.id
                    )
                )
            )
            review = reviews.get(opportunity.id)
            enrichment = db.get(OpportunityEnrichment, opportunity.id)
            role_org_ids = list(
                db.scalars(
                    select(OpportunityOrganizationRole.organization_id).where(
                        OpportunityOrganizationRole.opportunity_id == opportunity.id,
                        OpportunityOrganizationRole.role.in_(["operator", "tenant", "franchisee"]),
                    )
                )
            )
            contacts = list(
                db.scalars(
                    select(BusinessContact).where(
                        BusinessContact.organization_id.in_(role_org_ids or [org.id]),
                        BusinessContact.status == "active",
                    )
                )
            )
            operator_org = db.get(Organization, role_org_ids[0]) if role_org_ids else org
            assert operator_org is not None
            by_type: dict[str, str] = {}
            for contact in contacts:
                by_type.setdefault(contact.contact_type, contact.value)
            timing, _ = timing_value(opportunity.stage, {signal.signal_type for signal in signals})
            writer.writerow(
                {
                    "organization": org.legal_name or org.canonical_name,
                    "brand": org.dba_name or org.canonical_name,
                    "operating_brand": operator_org.dba_name or operator_org.canonical_name,
                    "operator_status": enrichment.operator_status if enrichment else "UNKNOWN",
                    "operator_confidence": enrichment.operator_confidence
                    if enrichment
                    else "UNKNOWN",
                    "city": location.city,
                    "address": location.address_line_1,
                    "industry": org.industry,
                    "stage": opportunity.stage,
                    "opportunity_type": opportunity.opportunity_type,
                    "score": opportunity.score,
                    "vendor_readiness_score": enrichment.vendor_readiness_score
                    if enrichment
                    else 0,
                    "vendor_readiness_tier": enrichment.vendor_readiness_tier
                    if enrichment
                    else "NOT_READY",
                    "independent_signal_count": len(independent_signal_families(signals)),
                    "contactability_status": enrichment.contactability_status
                    if enrichment
                    else "NOT_CONTACTABLE",
                    "contact_utility_class": enrichment.contact_utility_class
                    if enrichment
                    else "UNKNOWN",
                    "contact_utility_score": enrichment.contact_utility_score if enrichment else 0,
                    "freshness_status": enrichment.freshness_status if enrichment else "HISTORICAL",
                    "source_event_at": enrichment.source_event_at if enrichment else None,
                    "source_published_at": enrichment.source_published_at if enrichment else None,
                    "first_observed_live_at": enrichment.first_observed_live_at
                    if enrichment
                    else None,
                    "first_actionable_live_at": enrichment.first_actionable_live_at
                    if enrichment
                    else None,
                    "last_meaningful_signal_at": enrichment.last_meaningful_signal_at
                    if enrichment
                    else None,
                    "cleaning_relevance_score": enrichment.cleaning_relevance_score
                    if enrichment
                    else 0,
                    "cleaning_lead_tier": enrichment.cleaning_lead_tier
                    if enrichment
                    else "NOT_RELEVANT",
                    "official_website": by_type.get("website", ""),
                    "business_phone": by_type.get("phone", ""),
                    "business_email": by_type.get("email", ""),
                    "contact_page": by_type.get("contact_page", ""),
                    "timing_value": timing,
                    "stage_confidence": opportunity.stage_confidence,
                    "signal_count": len(signals),
                    "first_detected_at": opportunity.first_detected_at,
                    "first_actionable_at": opportunity.first_actionable_at,
                    "first_operator_identified_at": enrichment.first_operator_identified_at
                    if enrichment
                    else None,
                    "first_contactable_at": enrichment.first_contactable_at if enrichment else None,
                    "last_signal_at": opportunity.last_signal_at,
                    "estimated_open_window": " to ".join(
                        str(value)
                        for value in [
                            opportunity.estimated_open_start,
                            opportunity.estimated_open_end,
                        ]
                        if value
                    ),
                    "review_status": review.verdict if review else "unreviewed",
                    "review_note": review.notes if review else "",
                    "source_count": len({signal.source_id for signal in signals}),
                    "vendor_needs": ";".join(sorted(needs)),
                }
            )
            rows += 1
    return rows


def export_actionable_matrix(db: Session, path: Path) -> int:
    reviews = latest_reviews(db)
    vendor_names = list(VENDOR_PROFILES)
    fields = [
        "organization",
        "city",
        "address",
        "industry",
        "stage",
        "score",
        "stage_confidence",
        "signal_count",
        "source_types",
        "timing_value",
        "timing_reason",
        "contact_route",
        *vendor_names,
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = 0
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for opportunity, org, location in db.execute(
            select(Opportunity, Organization, Location)
            .join(Organization, Opportunity.organization_id == Organization.id)
            .join(Location, Opportunity.location_id == Location.id)
        ):
            if not reviews.get(opportunity.id) or reviews[opportunity.id].verdict != "actionable":
                continue
            signals = list(
                db.scalars(
                    select(Signal).where(
                        Signal.organization_id == opportunity.organization_id,
                        Signal.location_id == opportunity.location_id,
                    )
                )
            )
            needs = list(
                db.scalars(
                    select(InferredNeed.service_category).where(
                        InferredNeed.opportunity_id == opportunity.id
                    )
                )
            )
            source_types = set(
                db.scalars(
                    select(Source.source_type).where(Source.id.in_([s.source_id for s in signals]))
                )
            )
            value, reason = timing_value(
                opportunity.stage, {signal.signal_type for signal in signals}
            )
            item = {
                "industry": org.industry,
                "city": location.city,
                "stage": opportunity.stage,
                "score": opportunity.score,
                "service_categories": needs,
            }
            row: dict[str, Any] = {
                "organization": org.dba_name or org.canonical_name,
                "city": location.city,
                "address": location.address_line_1,
                "industry": org.industry,
                "stage": opportunity.stage,
                "score": opportunity.score,
                "stage_confidence": opportunity.stage_confidence,
                "signal_count": len(signals),
                "source_types": ";".join(sorted(source_types)),
                "timing_value": value,
                "timing_reason": reason,
                "contact_route": org.website or org.phone or org.email or "",
            }
            for name, profile in VENDOR_PROFILES.items():
                row[name] = match_profile(item, {**profile, "cities": [location.city]})[
                    "match_score"
                ]
            writer.writerow(row)
            rows += 1
    return rows


def export_vendor_validation(db: Session, vendor_name: str, path: Path) -> int:
    if vendor_name not in VENDOR_PROFILES:
        raise ValueError(f"Unknown vendor profile: {vendor_name}")
    reviews = latest_reviews(db)
    profile = VENDOR_PROFILES[vendor_name]
    fields = [
        "business",
        "city",
        "industry",
        "stage",
        "why_it_matches",
        "why_now",
        "evidence_summary",
        "estimated_opening_window",
        "official_public_contact_route",
        "source_provenance",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = 0
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for opportunity, org, location in db.execute(
            select(Opportunity, Organization, Location)
            .join(Organization, Opportunity.organization_id == Organization.id)
            .join(Location, Opportunity.location_id == Location.id)
        ):
            review = reviews.get(opportunity.id)
            if not review or review.verdict != "actionable":
                continue
            signals = list(
                db.scalars(
                    select(Signal).where(
                        Signal.organization_id == opportunity.organization_id,
                        Signal.location_id == opportunity.location_id,
                    )
                )
            )
            needs = list(
                db.scalars(
                    select(InferredNeed.service_category).where(
                        InferredNeed.opportunity_id == opportunity.id
                    )
                )
            )
            match = match_profile(
                {
                    "industry": org.industry,
                    "city": location.city,
                    "stage": opportunity.stage,
                    "score": opportunity.score,
                    "service_categories": needs,
                },
                {**profile, "cities": [location.city]},
            )
            if float(match["match_score"]) < 50:
                continue
            _, why_now = timing_value(opportunity.stage, {signal.signal_type for signal in signals})
            writer.writerow(
                {
                    "business": org.dba_name or org.canonical_name,
                    "city": location.city,
                    "industry": org.industry,
                    "stage": opportunity.stage,
                    "why_it_matches": "; ".join(match["why_it_matches"]),
                    "why_now": why_now,
                    "evidence_summary": review.notes,
                    "estimated_opening_window": " to ".join(
                        str(value)
                        for value in [
                            opportunity.estimated_open_start,
                            opportunity.estimated_open_end,
                        ]
                        if value
                    ),
                    "official_public_contact_route": org.website or org.phone or org.email or "",
                    "source_provenance": "; ".join(
                        sorted({signal.source_url for signal in signals})
                    ),
                }
            )
            rows += 1
    return rows


def export_vendor_ready(db: Session, vendor_name: str, path: Path) -> int:
    if vendor_name not in VENDOR_PROFILES:
        raise ValueError(f"Unknown vendor profile: {vendor_name}")
    reviews = latest_reviews(db)
    fields = [
        "business",
        "legal_entity",
        "operator_status",
        "city",
        "address",
        "industry",
        "stage",
        "opportunity_score",
        "vendor_readiness_score",
        "vendor_readiness_band",
        "vendor_readiness_tier",
        "independent_signal_count",
        "contactability_status",
        "official_website",
        "business_phone",
        "business_email",
        "contact_page",
        "why_now",
        "relevant_services",
        "source_links",
        "last_updated",
        "what_is_happening",
        "current_stage",
        "why_you_are_seeing_this_now",
        "why_it_may_be_relevant",
        "verified_contact_route",
        "evidence",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = 0
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for opportunity, org, location, enrichment in db.execute(
            select(Opportunity, Organization, Location, OpportunityEnrichment)
            .join(Organization, Opportunity.organization_id == Organization.id)
            .join(Location, Opportunity.location_id == Location.id)
            .join(OpportunityEnrichment, OpportunityEnrichment.opportunity_id == Opportunity.id)
        ):
            review = reviews.get(opportunity.id)
            if (
                not review
                or review.verdict != "actionable"
                or enrichment.vendor_readiness_tier not in {"A", "B"}
            ):
                continue
            needs = list(
                db.scalars(
                    select(InferredNeed.service_category).where(
                        InferredNeed.opportunity_id == opportunity.id
                    )
                )
            )
            match = match_profile(
                {
                    "industry": org.industry,
                    "city": location.city,
                    "stage": opportunity.stage,
                    "score": opportunity.score,
                    "service_categories": needs,
                },
                {**VENDOR_PROFILES[vendor_name], "cities": [location.city]},
            )
            if float(match["match_score"]) < 50:
                continue
            signals = list(
                db.scalars(
                    select(Signal).where(
                        Signal.organization_id == opportunity.organization_id,
                        Signal.location_id == opportunity.location_id,
                    )
                )
            )
            role_org_ids = list(
                db.scalars(
                    select(OpportunityOrganizationRole.organization_id).where(
                        OpportunityOrganizationRole.opportunity_id == opportunity.id,
                        OpportunityOrganizationRole.role.in_(["operator", "tenant", "franchisee"]),
                    )
                )
            )
            contact_org_ids = role_org_ids or [org.id]
            contacts = list(
                db.scalars(
                    select(BusinessContact).where(
                        BusinessContact.organization_id.in_(contact_org_ids),
                        BusinessContact.status == "active",
                    )
                )
            )
            by_type: dict[str, str] = {}
            for contact in contacts:
                by_type.setdefault(contact.contact_type, contact.value)
            operator = db.get(Organization, role_org_ids[0]) if role_org_ids else org
            assert operator is not None
            _, why_now = timing_value(opportunity.stage, {item.signal_type for item in signals})
            writer.writerow(
                {
                    "business": operator.dba_name or operator.canonical_name,
                    "legal_entity": operator.legal_name or operator.canonical_name,
                    "operator_status": enrichment.operator_status,
                    "city": location.city,
                    "address": location.address_line_1,
                    "industry": org.industry,
                    "stage": opportunity.stage,
                    "opportunity_score": opportunity.score,
                    "vendor_readiness_score": enrichment.vendor_readiness_score,
                    "vendor_readiness_band": enrichment.vendor_readiness_band,
                    "vendor_readiness_tier": enrichment.vendor_readiness_tier,
                    "independent_signal_count": len(independent_signal_families(signals)),
                    "contactability_status": enrichment.contactability_status,
                    "official_website": by_type.get("website", ""),
                    "business_phone": by_type.get("phone", ""),
                    "business_email": by_type.get("email", ""),
                    "contact_page": by_type.get("contact_page", ""),
                    "why_now": why_now,
                    "relevant_services": ";".join(sorted(needs)),
                    "source_links": ";".join(
                        sorted(
                            {item.source_url for item in signals}
                            | {item.source_url for item in contacts}
                        )
                    ),
                    "last_updated": enrichment.updated_at,
                    "what_is_happening": opportunity.summary,
                    "current_stage": opportunity.stage,
                    "why_you_are_seeing_this_now": why_now,
                    "why_it_may_be_relevant": "; ".join(match["why_it_matches"]),
                    "verified_contact_route": next(
                        (
                            by_type[key]
                            for key in ("phone", "email", "contact_page", "website")
                            if by_type.get(key)
                        ),
                        "",
                    ),
                    "evidence": review.notes,
                }
            )
            rows += 1
    return rows
