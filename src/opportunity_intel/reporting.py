import csv
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import (
    InferredNeed,
    Location,
    ManualReview,
    Opportunity,
    Organization,
    ReviewItem,
    Signal,
    Source,
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


def export_validation_csv(db: Session, path: Path) -> int:
    reviews = latest_reviews(db)
    fields = [
        "organization",
        "brand",
        "city",
        "address",
        "industry",
        "stage",
        "opportunity_type",
        "score",
        "stage_confidence",
        "signal_count",
        "first_detected_at",
        "first_actionable_at",
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
            writer.writerow(
                {
                    "organization": org.legal_name or org.canonical_name,
                    "brand": org.dba_name or org.canonical_name,
                    "city": location.city,
                    "address": location.address_line_1,
                    "industry": org.industry,
                    "stage": opportunity.stage,
                    "opportunity_type": opportunity.opportunity_type,
                    "score": opportunity.score,
                    "stage_confidence": opportunity.stage_confidence,
                    "signal_count": len(signals),
                    "first_detected_at": opportunity.first_detected_at,
                    "first_actionable_at": opportunity.first_actionable_at,
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
