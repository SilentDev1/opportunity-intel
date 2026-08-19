import csv
import re
from collections import Counter
from datetime import date, datetime, time
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from .enrichment import independent_signal_families
from .models import (
    BusinessContact,
    Location,
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

HISTORICAL_SOURCE_PATTERN = re.compile(r"historical|archive|backfill", re.I)
SOUTHERN_NH = {"Nashua", "Manchester", "Salem", "Bedford", "Merrimack"}

INDUSTRY_CLEANING_VALUE = {
    "restaurant": 20,
    "medical": 20,
    "dental": 20,
    "childcare": 20,
    "fitness": 20,
    "hospitality": 20,
    "entertainment": 18,
    "professional office": 16,
    "retail": 16,
    "automotive": 16,
    "warehouse/logistics": 10,
    "other": 8,
}
STAGE_CLEANING_VALUE = {
    "BUILDOUT": 25,
    "PRE_OPENING": 25,
    "FINAL_PREP": 22,
    "LOCATION_CONFIRMED": 20,
    "EXPANDING": 18,
    "RELOCATING": 18,
    "PLANNING": 10,
    "PRE_BUILDOUT": 10,
    "PLANNED": 8,
    "OPEN": 5,
}
OPERATOR_VALUE = {"CONFIRMED": 15, "HIGH": 12, "MEDIUM": 8, "LOW": 3, "UNKNOWN": 0}
FRESHNESS_VALUE = {"FRESH": 10, "UPDATED": 7, "HISTORICAL": 2}


def _date_from_url(url: str) -> date | None:
    compact = re.search(r"_(\d{2})(\d{2})(\d{4})(?:-|\D)", url)
    if compact:
        return date(int(compact.group(3)), int(compact.group(1)), int(compact.group(2)))
    iso = re.search(r"(?<!\d)(20\d{2})[-_/](\d{2})[-_/](\d{2})(?!\d)", url)
    if iso:
        return date(int(iso.group(1)), int(iso.group(2)), int(iso.group(3)))
    year = re.search(r"/(20\d{2})/", url)
    return date(int(year.group(1)), 1, 1) if year else None


def classify_freshness(
    *,
    first_detected_at: datetime,
    signals: list[Signal],
    source_by_id: dict[str, Source],
    period_start: date,
    period_end: date,
) -> tuple[str, datetime | None, datetime | None]:
    live_events: list[datetime] = []
    update_events: list[datetime] = []
    for signal in signals:
        source = source_by_id[signal.source_id]
        event_date = _date_from_url(signal.source_url) or signal.signal_date
        is_historical = bool(HISTORICAL_SOURCE_PATTERN.search(source.name))
        observed_in_period = period_start <= signal.detected_at.date() <= period_end
        event_is_current = event_date is None or event_date >= period_start
        if source.enabled and not is_historical and observed_in_period and event_is_current:
            live_events.append(signal.detected_at)
        elif observed_in_period and not is_historical and event_is_current and signal.is_verified:
            update_events.append(signal.detected_at)
    first_live = min(live_events) if live_events else None
    last_meaningful = max(live_events + update_events, default=None)
    if first_live and period_start <= first_detected_at.date() <= period_end:
        return "FRESH", first_live, last_meaningful
    if live_events or update_events:
        return "UPDATED", first_live, last_meaningful
    return "HISTORICAL", None, last_meaningful


def cleaning_score(
    *,
    industry: str | None,
    stage: str,
    operator_confidence: str,
    contact_utility_score: int,
    freshness_status: str,
    evidence_family_count: int,
    vendor_readiness_tier: str,
    actionable: bool,
) -> tuple[float, str, dict[str, float]]:
    breakdown = {
        "industry_fit": float(INDUSTRY_CLEANING_VALUE.get(industry or "other", 8)),
        "timing": float(STAGE_CLEANING_VALUE.get(stage, 0)),
        "operator": float(OPERATOR_VALUE.get(operator_confidence, 0)),
        "contact_utility": round(min(15, contact_utility_score * 0.15), 1),
        "freshness": float(FRESHNESS_VALUE.get(freshness_status, 0)),
        "corroboration": 10.0 if evidence_family_count >= 2 else 4.0,
    }
    score = round(sum(breakdown.values()), 1)
    preferred_stage = stage in {"BUILDOUT", "PRE_OPENING", "FINAL_PREP", "LOCATION_CONFIRMED"}
    has_contact = contact_utility_score >= 60
    operator_known = operator_confidence in {"CONFIRMED", "HIGH", "MEDIUM"}
    if not actionable or industry is None:
        tier = "NOT_RELEVANT"
    elif (
        score >= 75
        and preferred_stage
        and contact_utility_score >= 75
        and operator_confidence in {"CONFIRMED", "HIGH"}
        and vendor_readiness_tier in {"A", "B"}
    ):
        tier = "CLEANING_A"
    elif score >= 60 and has_contact and operator_known and vendor_readiness_tier in {"A", "B"}:
        tier = "CLEANING_B"
    else:
        tier = "CLEANING_C"
    return score, tier, breakdown


def refresh_phase09_metrics(db: Session, period_start: date, period_end: date) -> Counter[str]:
    counts: Counter[str] = Counter()
    source_by_id = {item.id: item for item in db.scalars(select(Source))}
    for opportunity, organization in db.execute(
        select(Opportunity, Organization).join(
            Organization, Opportunity.organization_id == Organization.id
        )
    ):
        signals = list(
            db.scalars(
                select(Signal).where(
                    Signal.organization_id == opportunity.organization_id,
                    Signal.location_id == opportunity.location_id,
                )
            )
        )
        enrichment = db.get(OpportunityEnrichment, opportunity.id) or OpportunityEnrichment(
            opportunity_id=opportunity.id
        )
        status, first_live, last_meaningful = classify_freshness(
            first_detected_at=opportunity.first_detected_at,
            signals=signals,
            source_by_id=source_by_id,
            period_start=period_start,
            period_end=period_end,
        )
        enrichment.freshness_status = status
        enrichment.first_observed_live_at = enrichment.first_observed_live_at or first_live
        enrichment.last_meaningful_signal_at = last_meaningful
        dated = [item.signal_date for item in signals if item.signal_date]
        enrichment.source_event_at = datetime.combine(min(dated), time.min) if dated else None
        documents = (
            list(
                db.scalars(
                    select(RawSourceDocument)
                    .join(RawRecord, RawRecord.raw_source_document_id == RawSourceDocument.id)
                    .join(Signal, Signal.raw_record_id == RawRecord.id)
                    .where(Signal.id.in_([item.id for item in signals]))
                )
            )
            if signals
            else []
        )
        published = [item.published_at for item in documents if item.published_at]
        enrichment.source_published_at = min(published) if published else None
        if status == "FRESH" and opportunity.status == "actionable":
            enrichment.first_actionable_live_at = (
                enrichment.first_actionable_live_at or datetime.combine(period_start, time.min)
            )
        score, tier, breakdown = cleaning_score(
            industry=organization.industry,
            stage=opportunity.stage,
            operator_confidence=enrichment.operator_confidence,
            contact_utility_score=enrichment.contact_utility_score,
            freshness_status=status,
            evidence_family_count=len(independent_signal_families(signals)),
            vendor_readiness_tier=enrichment.vendor_readiness_tier,
            actionable=opportunity.status == "actionable",
        )
        enrichment.cleaning_relevance_score = score
        enrichment.cleaning_lead_tier = tier
        enrichment.cleaning_score_breakdown = breakdown
        db.add(enrichment)
        counts[status] += 1
        counts[tier] += 1
    db.commit()
    return counts


def weekly_cleaning_flow(db: Session, period_start: date, period_end: date) -> dict[str, int]:
    enrichments = list(db.scalars(select(OpportunityEnrichment)))
    fresh_ids = {item.opportunity_id for item in enrichments if item.freshness_status == "FRESH"}
    fresh_opportunities = [db.get(Opportunity, item_id) for item_id in fresh_ids]
    actionable = [item for item in fresh_opportunities if item and item.status == "actionable"]
    cleaning = [
        item
        for item in actionable
        if (enrichment := db.get(OpportunityEnrichment, item.id))
        and enrichment.cleaning_lead_tier != "NOT_RELEVANT"
    ]
    contactable = [
        item
        for item in cleaning
        if (enrichment := db.get(OpportunityEnrichment, item.id))
        and enrichment.contactability_status == "CONTACTABLE"
    ]
    ready = [
        item
        for item in cleaning
        if (enrichment := db.get(OpportunityEnrichment, item.id))
        and enrichment.cleaning_lead_tier in {"CLEANING_A", "CLEANING_B"}
    ]
    start = datetime.combine(period_start, time.min)
    end = datetime.combine(period_end, time.max)
    meaningful_updates: set[str] = set()
    for history, signal, source in db.execute(
        select(StageHistory, Signal, Source)
        .join(Signal, StageHistory.triggering_signal_id == Signal.id)
        .join(Source, Signal.source_id == Source.id)
        .where(StageHistory.changed_at >= start, StageHistory.changed_at <= end)
    ):
        event_date = _date_from_url(signal.source_url) or signal.signal_date
        if (
            history.opportunity_id not in fresh_ids
            and not HISTORICAL_SOURCE_PATTERN.search(source.name)
            and event_date is not None
            and event_date >= period_start
        ):
            meaningful_updates.add(history.opportunity_id)
    return {
        "fresh_opportunities": len(fresh_ids),
        "fresh_actionable": len(actionable),
        "fresh_cleaning_relevant": len(cleaning),
        "fresh_cleaning_contactable": len(contactable),
        "fresh_cleaning_ab": len(ready),
        "meaningful_updates": len(meaningful_updates),
    }


def geographic_cleaning_simulation(db: Session, territory: str) -> list[str]:
    rows = db.execute(
        select(Opportunity, OpportunityEnrichment, Location)
        .join(OpportunityEnrichment, OpportunityEnrichment.opportunity_id == Opportunity.id)
        .join(Location, Opportunity.location_id == Location.id)
        .where(
            Opportunity.status == "actionable",
            OpportunityEnrichment.cleaning_lead_tier.in_(["CLEANING_A", "CLEANING_B"]),
        )
    )
    return [
        opportunity.id
        for opportunity, _, location in rows
        if territory == "statewide" or location.city in SOUTHERN_NH
    ]


def pricing_scenarios(monthly_leads: float) -> dict[int, float | None]:
    return {
        price: round(price / monthly_leads, 2) if monthly_leads > 0 else None
        for price in (49, 79, 99, 149)
    }


def classify_stale_reason(*, source_names: set[str], stage: str, review_note: str = "") -> str:
    text = review_note.casefold()
    if any(HISTORICAL_SOURCE_PATTERN.search(name) for name in source_names):
        return "historical backfill"
    if stage == "CANCELLED" or any(word in text for word in ("withdrawn", "cancelled")):
        return "withdrawn/cancelled"
    if "superseded" in text:
        return "superseded"
    if "already open" in text or "business is open" in text:
        return "business already open"
    if "completed" in text:
        return "project completed"
    if "old planning" in text:
        return "old planning record with no activity"
    return "no recent corroboration"


def vendor_feedback_summary(db: Session, vendor_profile: str) -> dict[str, float | int | None]:
    rows = list(
        db.scalars(select(VendorFeedback).where(VendorFeedback.vendor_profile == vendor_profile))
    )

    def percent(values: list[bool | None], desired: bool = True) -> float | None:
        known = [value for value in values if value is not None]
        return (
            round(sum(value is desired for value in known) / len(known) * 100, 1) if known else None
        )

    ratings = [item.rating for item in rows if item.rating is not None]
    return {
        "responses": len(rows),
        "previously_unknown_pct": percent([item.already_knew for item in rows], False),
        "would_contact_pct": percent([item.would_contact for item in rows]),
        "timing_useful_pct": percent([item.timing_useful for item in rows]),
        "contact_sufficient_pct": percent([item.contact_info_sufficient for item in rows]),
        "average_rating": round(sum(ratings) / len(ratings), 2) if ratings else None,
        "willing_49_pct": percent([item.willing_to_pay_49 for item in rows]),
        "willing_79_pct": percent([item.willing_to_pay_79 for item in rows]),
        "willing_99_pct": percent([item.willing_to_pay_99 for item in rows]),
        "willing_149_pct": percent([item.willing_to_pay_149 for item in rows]),
    }


def source_combination_metrics(db: Session) -> list[dict[str, float | int | str | None]]:
    groups: dict[str, list[tuple[Opportunity, OpportunityEnrichment]]] = {}
    for opportunity, enrichment in db.execute(
        select(Opportunity, OpportunityEnrichment).join(
            OpportunityEnrichment, OpportunityEnrichment.opportunity_id == Opportunity.id
        )
    ):
        signals = list(
            db.scalars(
                select(Signal).where(
                    Signal.organization_id == opportunity.organization_id,
                    Signal.location_id == opportunity.location_id,
                )
            )
        )
        key = " + ".join(sorted(independent_signal_families(signals))) or "none"
        groups.setdefault(key, []).append((opportunity, enrichment))
    result: list[dict[str, float | int | str | None]] = []
    for combination, rows in groups.items():
        actionable = sum(item.status == "actionable" for item, _ in rows)
        contactable = sum(
            item.status == "actionable" and enrichment.contactability_status == "CONTACTABLE"
            for item, enrichment in rows
        )
        ready = sum(
            item.status == "actionable" and enrichment.vendor_readiness_tier in {"A", "B"}
            for item, enrichment in rows
        )
        result.append(
            {
                "combination": combination,
                "sample_size": len(rows),
                "actionable": actionable,
                "actionable_rate": round(actionable / len(rows) * 100, 1),
                "contactability_rate": round(contactable / actionable * 100, 1)
                if actionable
                else None,
                "ab_readiness_rate": round(ready / actionable * 100, 1) if actionable else None,
            }
        )
    return sorted(
        result,
        key=lambda item: (
            -(item["sample_size"] if isinstance(item["sample_size"], (int, float)) else 0),
            str(item["combination"]),
        ),
    )


def export_cleaning_packet(
    db: Session, path: Path, territory: str = "statewide", fresh_only: bool = False
) -> int:
    eligible = set(geographic_cleaning_simulation(db, territory))
    if fresh_only:
        eligible = {
            opportunity_id
            for opportunity_id in eligible
            if (enrichment := db.get(OpportunityEnrichment, opportunity_id))
            and enrichment.freshness_status == "FRESH"
        }
    fields = [
        "opportunity_id",
        "business",
        "location",
        "business_type",
        "what_is_happening",
        "stage",
        "why_this_may_matter",
        "why_now",
        "verified_contact_route",
        "evidence",
        "last_updated",
        "cleaning_tier",
        "freshness",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        rows = db.execute(
            select(Opportunity, OpportunityEnrichment, Location, Organization)
            .join(OpportunityEnrichment, OpportunityEnrichment.opportunity_id == Opportunity.id)
            .join(Location, Opportunity.location_id == Location.id)
            .join(Organization, Opportunity.organization_id == Organization.id)
            .where(Opportunity.id.in_(eligible))
            .order_by(
                OpportunityEnrichment.cleaning_lead_tier,
                OpportunityEnrichment.cleaning_relevance_score.desc(),
            )
        )
        for opportunity, enrichment, location, owner in rows:
            role_ids = set(
                db.scalars(
                    select(OpportunityOrganizationRole.organization_id).where(
                        OpportunityOrganizationRole.opportunity_id == opportunity.id,
                        OpportunityOrganizationRole.role.in_(["operator", "tenant", "franchisee"]),
                    )
                )
            )
            contact_org_ids = role_ids or {owner.id}
            contacts = list(
                db.scalars(
                    select(BusinessContact)
                    .where(
                        BusinessContact.organization_id.in_(contact_org_ids),
                        BusinessContact.status == "active",
                    )
                    .order_by(BusinessContact.utility_score.desc())
                )
            )
            operator = db.get(Organization, next(iter(role_ids))) if role_ids else owner
            if operator is None:
                operator = owner
            contact = contacts[0].value if contacts else ""
            writer.writerow(
                {
                    "opportunity_id": opportunity.id,
                    "business": operator.dba_name or operator.canonical_name,
                    "location": ", ".join(
                        value
                        for value in (location.address_line_1, location.city, location.state)
                        if value
                    ),
                    "business_type": owner.industry or "commercial facility",
                    "what_is_happening": opportunity.summary,
                    "stage": opportunity.stage,
                    "why_this_may_matter": (
                        "Likely commercial-cleaning opportunity based on facility type, project "
                        "stage, and verified business identity; no service need is asserted."
                    ),
                    "why_now": (
                        "Buildout or pre-opening work may create a vendor-selection window."
                        if opportunity.stage
                        in {"BUILDOUT", "PRE_OPENING", "FINAL_PREP", "LOCATION_CONFIRMED"}
                        else (
                            "The operator and location are known; monitor the early project timing."
                        )
                    ),
                    "verified_contact_route": contact,
                    "evidence": opportunity.why_actionable,
                    "last_updated": enrichment.last_meaningful_signal_at
                    or opportunity.last_signal_at,
                    "cleaning_tier": enrichment.cleaning_lead_tier,
                    "freshness": enrichment.freshness_status,
                }
            )
            count += 1
    return count
