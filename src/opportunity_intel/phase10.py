import csv
from collections import Counter
from datetime import date
from pathlib import Path

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from .models import (
    BlindValidationBatch,
    BlindValidationResult,
    BusinessContact,
    Location,
    Opportunity,
    OpportunityEnrichment,
    OpportunityOrganizationRole,
    Organization,
    RawSourceDocument,
    Signal,
    Source,
    VendorFeedback,
    VendorLeadOutcome,
)
from .phase09 import HISTORICAL_SOURCE_PATTERN, SOUTHERN_NH, _date_from_url

MEANINGFUL_UPDATE_TYPES = {
    "operator_identified",
    "buildout_started",
    "contact_available",
    "hiring_started",
    "occupancy_activity",
    "opening_date_announced",
    "stage_transition",
}


def vendor_validation_metrics(db: Session, vendor_profile: str) -> dict[str, object]:
    rows = list(
        db.scalars(select(VendorFeedback).where(VendorFeedback.vendor_profile == vendor_profile))
    )
    if not rows:
        return {
            "status": "No external vendor feedback has been received yet.",
            "vendors": 0,
            "leads_reviewed": 0,
        }

    def pct(values: list[bool]) -> float | None:
        return round(sum(values) / len(values) * 100, 1) if values else None

    vendor_names = {row.vendor_name or row.vendor_profile for row in rows}
    unknown = [not row.already_knew for row in rows if row.already_knew is not None]
    contact_yes = [
        (row.would_contact_response == "YES")
        if row.would_contact_response
        else bool(row.would_contact)
        for row in rows
        if row.would_contact_response or row.would_contact is not None
    ]
    contact_yes_maybe = [
        row.would_contact_response in {"YES", "MAYBE"}
        if row.would_contact_response
        else bool(row.would_contact)
        for row in rows
        if row.would_contact_response or row.would_contact is not None
    ]
    timing_good = [
        row.timing_response == "GOOD" if row.timing_response else bool(row.timing_useful)
        for row in rows
        if row.timing_response or row.timing_useful is not None
    ]
    sufficient = [
        row.contact_sufficiency_response == "YES"
        if row.contact_sufficiency_response
        else bool(row.contact_info_sufficient)
        for row in rows
        if row.contact_sufficiency_response or row.contact_info_sufficient is not None
    ]
    ratings = [row.rating for row in rows if row.rating is not None]
    vendor_feed: dict[str, bool] = {}
    for row in rows:
        if row.wants_weekly_feed is not None:
            vendor_feed[row.vendor_name or row.vendor_profile] = row.wants_weekly_feed
    willingness = {
        price: pct(
            [
                bool(getattr(row, f"willing_to_pay_{price}"))
                for row in rows
                if getattr(row, f"willing_to_pay_{price}") is not None
            ]
        )
        for price in (49, 79, 99, 149)
    }
    return {
        "status": "feedback_received",
        "vendors": len(vendor_names),
        "leads_reviewed": len(
            {(row.vendor_name or row.vendor_profile, row.opportunity_id) for row in rows}
        ),
        "previously_unknown_pct": pct(unknown),
        "would_contact_yes_pct": pct(contact_yes),
        "would_contact_yes_maybe_pct": pct(contact_yes_maybe),
        "timing_good_pct": pct(timing_good),
        "contact_sufficient_pct": pct(sufficient),
        "average_rating": round(sum(ratings) / len(ratings), 2) if ratings else None,
        "wants_weekly_feed_pct": pct(list(vendor_feed.values())),
        "willingness_to_pay_pct": willingness,
    }


def write_vendor_validation_report(
    db: Session, path: Path, vendor_profile: str = "commercial_cleaning"
) -> None:
    metrics = vendor_validation_metrics(db, vendor_profile)
    lines = ["# Vendor validation results", "", "Generated from stored vendor feedback.", ""]
    if metrics["vendors"] == 0:
        lines.extend(["No external vendor feedback has been received yet.", ""])
    else:
        labels = {
            "vendors": "Vendors reviewed",
            "leads_reviewed": "Leads reviewed",
            "previously_unknown_pct": "Previously unknown",
            "would_contact_yes_pct": "Would contact — YES",
            "would_contact_yes_maybe_pct": "Would contact — YES/MAYBE",
            "timing_good_pct": "Timing GOOD",
            "contact_sufficient_pct": "Contact sufficient",
            "average_rating": "Average rating",
            "wants_weekly_feed_pct": "Want weekly feed",
        }
        lines.extend(["| Metric | Result |", "|---|---:|"])
        for key, label in labels.items():
            value = metrics.get(key)
            suffix = "%" if key.endswith("_pct") and value is not None else ""
            lines.append(f"| {label} | {value}{suffix} |")
        willingness = metrics["willingness_to_pay_pct"]
        if isinstance(willingness, dict):
            for price, value in willingness.items():
                lines.append(f"| Willing to pay ${price}/month | {value}% |")
        lines.append("")
    lines.extend(
        [
            "Percentages are omitted when no applicable responses exist. Survey evidence is not "
            "treated as a lead outcome.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def outcome_metrics(db: Session) -> dict[str, object]:
    rows = list(db.scalars(select(VendorLeadOutcome)))
    counts = Counter(row.outcome_status for row in rows)
    return {
        "events": len(rows),
        "vendors": len({row.vendor_name for row in rows}),
        "leads": len({(row.vendor_name, row.opportunity_id) for row in rows}),
        "outcomes": dict(sorted(counts.items())),
    }


def customer_facing_precision(db: Session, batch_name: str | None = None) -> dict[str, object]:
    query = (
        select(BlindValidationResult, OpportunityEnrichment)
        .join(
            OpportunityEnrichment,
            OpportunityEnrichment.opportunity_id == BlindValidationResult.opportunity_id,
        )
        .where(OpportunityEnrichment.cleaning_lead_tier.in_(["CLEANING_A", "CLEANING_B"]))
    )
    if batch_name:
        query = query.join(
            BlindValidationBatch, BlindValidationBatch.id == BlindValidationResult.batch_id
        ).where(BlindValidationBatch.name == batch_name)
    rows = list(db.execute(query))
    reviewed = [(result, enrichment) for result, enrichment in rows if result.manual_verdict]
    usable = sum(result.manual_verdict == "actionable" for result, _ in reviewed)
    false = len(reviewed) - usable
    return {
        "blind_ab_count": len(reviewed),
        "true_usable_ab": usable,
        "false_ab": false,
        "precision_pct": round(usable / len(reviewed) * 100, 1) if reviewed else None,
    }


def classify_currentness(
    latest_record_date: date | None, today: date, historical: bool = False
) -> str:
    if historical or latest_record_date is None:
        return "HISTORICAL"
    age = (today - latest_record_date).days
    if age <= 2:
        return "DAILY"
    if age <= 10:
        return "WEEKLY"
    if age <= 40:
        return "MONTHLY"
    if age <= 120:
        return "IRREGULAR"
    return "HISTORICAL"


def source_currentness_metrics(db: Session, today: date) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    for source in db.scalars(select(Source).order_by(Source.name)):
        documents = list(
            db.scalars(select(RawSourceDocument).where(RawSourceDocument.source_id == source.id))
        )
        record_dates = [
            value
            for document in documents
            if (
                value := (
                    _date_from_url(document.source_url)
                    or (document.published_at.date() if document.published_at else None)
                )
            )
        ]
        latest = max(record_dates, default=None)
        fresh_yield = db.scalar(
            select(func.count(func.distinct(Opportunity.id)))
            .select_from(Signal)
            .join(
                Opportunity,
                (Opportunity.organization_id == Signal.organization_id)
                & (Opportunity.location_id == Signal.location_id),
            )
            .join(OpportunityEnrichment, OpportunityEnrichment.opportunity_id == Opportunity.id)
            .where(
                Signal.source_id == source.id,
                OpportunityEnrichment.freshness_status == "FRESH",
            )
        )
        result.append(
            {
                "source": source.name,
                "documents": len(documents),
                "latest_record_date": latest.isoformat() if latest else None,
                "collector_cadence": "manual/live collection",
                "currentness": classify_currentness(
                    latest, today, bool(HISTORICAL_SOURCE_PATTERN.search(source.name))
                ),
                "fresh_opportunity_yield": fresh_yield or 0,
            }
        )
    return result


def meaningful_update(kind: str, *, duplicate_evidence: bool = False) -> bool:
    return not duplicate_evidence and kind in MEANINGFUL_UPDATE_TYPES


def live_geographic_flow(db: Session) -> dict[str, int]:
    rows = list(
        db.execute(
            select(OpportunityEnrichment, Location)
            .join(Opportunity, Opportunity.id == OpportunityEnrichment.opportunity_id)
            .join(Location, Location.id == Opportunity.location_id)
            .where(
                Opportunity.status == "actionable",
                OpportunityEnrichment.freshness_status == "FRESH",
                OpportunityEnrichment.cleaning_lead_tier.in_(["CLEANING_A", "CLEANING_B"]),
            )
        )
    )
    return {
        "statewide_fresh_cleaning_ab": len(rows),
        "southern_nh_fresh_cleaning_ab": sum(location.city in SOUTHERN_NH for _, location in rows),
    }


def evaluate_customer_mvp_gate(
    *,
    current_strong_leads: int,
    vendors: int,
    contact_intent_pct: float | None,
    weekly_feed_interest_pct: float | None,
    precision_pct: float | None,
    completed_live_weeks: int,
) -> dict[str, object]:
    checks = {
        "ten_current_strong_leads": current_strong_leads >= 10,
        "three_vendor_testers": vendors >= 3,
        "positive_contact_intent": (contact_intent_pct or 0) >= 50,
        "weekly_feed_interest": (weekly_feed_interest_pct or 0) >= 50,
        "customer_precision": (precision_pct or 0) >= 85,
        "credible_live_flow": completed_live_weeks >= 4,
    }
    return {"passed": all(checks.values()), "checks": checks}


def customer_mvp_gate(db: Session, completed_live_weeks: int = 0) -> dict[str, object]:
    feedback = vendor_validation_metrics(db, "commercial_cleaning")
    precision = customer_facing_precision(db)
    current_count = (
        db.query(OpportunityEnrichment)
        .filter(
            OpportunityEnrichment.freshness_status.in_(["FRESH", "UPDATED"]),
            OpportunityEnrichment.cleaning_lead_tier.in_(["CLEANING_A", "CLEANING_B"]),
        )
        .count()
    )
    vendors_value = feedback.get("vendors")
    contact_value = feedback.get("would_contact_yes_maybe_pct")
    feed_value = feedback.get("wants_weekly_feed_pct")
    precision_value = precision.get("precision_pct")
    return evaluate_customer_mvp_gate(
        current_strong_leads=current_count,
        vendors=vendors_value if isinstance(vendors_value, int) else 0,
        contact_intent_pct=float(contact_value)
        if isinstance(contact_value, (int, float))
        else None,
        weekly_feed_interest_pct=float(feed_value)
        if isinstance(feed_value, (int, float))
        else None,
        precision_pct=float(precision_value) if isinstance(precision_value, (int, float)) else None,
        completed_live_weeks=completed_live_weeks,
    )


def export_current_cleaning_test(db: Session, path: Path, limit: int = 10) -> int:
    fields = [
        "opportunity_id",
        "business",
        "city_address",
        "business_type",
        "what_is_happening",
        "current_stage",
        "why_it_may_matter",
        "why_now",
        "verified_contact",
        "source_evidence",
        "last_updated",
        "freshness",
    ]
    rows = list(
        db.execute(
            select(Opportunity, OpportunityEnrichment, Location, Organization)
            .join(OpportunityEnrichment, OpportunityEnrichment.opportunity_id == Opportunity.id)
            .join(Location, Location.id == Opportunity.location_id)
            .join(Organization, Organization.id == Opportunity.organization_id)
            .where(
                Opportunity.status == "actionable",
                OpportunityEnrichment.freshness_status.in_(["FRESH", "UPDATED"]),
                OpportunityEnrichment.cleaning_lead_tier.in_(["CLEANING_A", "CLEANING_B"]),
                OpportunityEnrichment.contactability_status == "CONTACTABLE",
            )
            .order_by(
                case((OpportunityEnrichment.freshness_status == "FRESH", 0), else_=1),
                OpportunityEnrichment.cleaning_relevance_score.desc(),
            )
            .limit(limit)
        )
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for opportunity, enrichment, location, organization in rows:
            role_ids = set(
                db.scalars(
                    select(OpportunityOrganizationRole.organization_id).where(
                        OpportunityOrganizationRole.opportunity_id == opportunity.id,
                        OpportunityOrganizationRole.role.in_(["operator", "tenant", "franchisee"]),
                    )
                )
            )
            operator = db.get(Organization, next(iter(role_ids))) if role_ids else organization
            operator = operator or organization
            contact_org_ids = role_ids or {organization.id}
            contact = db.scalar(
                select(BusinessContact)
                .where(
                    BusinessContact.organization_id.in_(contact_org_ids),
                    BusinessContact.status == "active",
                    BusinessContact.is_public.is_(True),
                )
                .order_by(BusinessContact.utility_score.desc())
            )
            evidence_urls = list(
                db.scalars(
                    select(Signal.source_url)
                    .where(
                        Signal.organization_id == opportunity.organization_id,
                        Signal.location_id == opportunity.location_id,
                    )
                    .distinct()
                )
            )
            writer.writerow(
                {
                    "opportunity_id": opportunity.id,
                    "business": operator.dba_name or operator.canonical_name,
                    "city_address": ", ".join(
                        filter(None, [location.address_line_1, location.city, location.state])
                    ),
                    "business_type": organization.industry or "commercial facility",
                    "what_is_happening": opportunity.summary,
                    "current_stage": opportunity.stage,
                    "why_it_may_matter": (
                        "The facility type and project stage may create a commercial-cleaning "
                        "prospect; no cleaning need is asserted."
                    ),
                    "why_now": (
                        "The operator, location, and a verified contact route are available while "
                        "activity is current."
                    ),
                    "verified_contact": contact.value
                    if contact
                    else enrichment.contactability_reason,
                    "source_evidence": " | ".join(evidence_urls) or opportunity.why_actionable,
                    "last_updated": enrichment.last_meaningful_signal_at
                    or opportunity.last_signal_at,
                    "freshness": enrichment.freshness_status,
                }
            )
    return len(rows)
