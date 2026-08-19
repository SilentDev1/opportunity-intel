import re
from collections import Counter
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import LifecycleStage, ManualReview, Opportunity, Signal

LEGAL_SUFFIXES = re.compile(r"\b(llc|ltd|incorporated|inc|corp|corporation|pllc|lp|llp|co)\b", re.I)
NON_WORD = re.compile(r"[^a-z0-9]+")


def normalize_name(value: str) -> str:
    value = LEGAL_SUFFIXES.sub(" ", value.casefold().replace("&", " and "))
    return " ".join(NON_WORD.sub(" ", value).split())


def normalize_address(value: str) -> str:
    replacements = {
        r"\bstreet\b": "st",
        r"\broad\b": "rd",
        r"\bavenue\b": "ave",
        r"\bboulevard\b": "blvd",
        r"\bsuite\b": "ste",
    }
    result = value.casefold().strip()
    for pattern, replacement in replacements.items():
        result = re.sub(pattern, replacement, result)
    return " ".join(NON_WORD.sub(" ", result).split())


STAGE_RULES: list[tuple[set[str], LifecycleStage, float]] = [
    ({"opening_confirmed"}, LifecycleStage.OPEN, 0.98),
    ({"certificate_of_occupancy", "inspection"}, LifecycleStage.FINAL_PREP, 0.90),
    ({"hiring_started", "job_posting", "opening_date_announced"}, LifecycleStage.PRE_OPENING, 0.84),
    (
        {
            "construction_started",
            "building_permit",
            "electrical_permit",
            "plumbing_permit",
            "mechanical_permit",
        },
        LifecycleStage.BUILDOUT,
        0.80,
    ),
    ({"planning_application", "zoning_application"}, LifecycleStage.PLANNING, 0.72),
    (
        {"location_announcement", "coming_soon_page", "sign_permit"},
        LifecycleStage.LOCATION_CONFIRMED,
        0.70,
    ),
    ({"business_registration", "trade_name_registration"}, LifecycleStage.EARLY_SIGNAL, 0.35),
]


def infer_stage(signals: list[Signal]) -> tuple[LifecycleStage, float, list[str]]:
    kinds = {s.signal_type for s in signals}
    if "closure" in kinds:
        return LifecycleStage.CLOSED, 0.95, ["closure evidence"]
    if "relocation" in kinds:
        return LifecycleStage.RELOCATING, 0.88, ["relocation evidence"]
    if "expansion" in kinds:
        return LifecycleStage.EXPANDING, 0.88, ["expansion evidence"]
    for triggers, stage, base in STAGE_RULES:
        matched = triggers & kinds
        if matched:
            corroboration = min(0.08, max(0, len({s.source_id for s in signals}) - 1) * 0.04)
            return (
                stage,
                min(0.99, base + corroboration),
                [f"{kind} signal" for kind in sorted(matched)],
            )
    return LifecycleStage.UNKNOWN, 0.10, ["no decisive lifecycle evidence"]


EVIDENCE = {
    "business_registration": 15,
    "planning_application": 55,
    "zoning_application": 50,
    "building_permit": 65,
    "construction_started": 80,
    "job_posting": 65,
    "hiring_started": 75,
    "location_announcement": 75,
    "certificate_of_occupancy": 90,
    "opening_date_announced": 90,
    "opening_confirmed": 98,
}


def score_opportunity(
    signals: list[Signal],
    physical_confidence: float,
    commercial_relevance: float = 0.6,
    now: datetime | None = None,
) -> tuple[float, dict[str, Any]]:
    if not signals:
        return 0, {"reason": "no signals"}
    now = now or datetime.utcnow()
    evidence = max(EVIDENCE.get(s.signal_type, 30) * s.confidence for s in signals)
    locations = physical_confidence * 100
    days = max(0, (now.date() - max(s.detected_at.date() for s in signals)).days)
    recency = max(0, 100 - days / 1.8)
    corroboration = min(100, len({s.source_id for s in signals}) * 35)
    score = (
        evidence * 0.35
        + locations * 0.25
        + recency * 0.15
        + corroboration * 0.15
        + commercial_relevance * 100 * 0.10
    )
    breakdown = {
        "evidence": round(evidence, 1),
        "location": round(locations, 1),
        "recency": round(recency, 1),
        "corroboration": corroboration,
        "commercial_relevance": commercial_relevance * 100,
    }
    return round(min(100, score), 1), breakdown


NEEDS = {
    "restaurant": {
        "BUILDOUT": [
            "security_cameras",
            "networking",
            "pos",
            "signage",
            "post_construction_cleaning",
            "waste_management",
            "pest_control",
            "commercial_insurance",
        ],
        "PRE_OPENING": [
            "commercial_cleaning",
            "pest_control",
            "linen_service",
            "food_distribution",
            "payroll",
            "staffing",
            "internet",
            "pos",
        ],
    },
    "childcare": {
        "*": [
            "access_control",
            "commercial_cleaning",
            "pest_control",
            "landscaping",
            "snow_removal",
            "commercial_insurance",
            "it_msp",
            "telecom",
        ]
    },
    "medical": {
        "*": [
            "it_msp",
            "networking",
            "security_cameras",
            "commercial_cleaning",
            "waste_management",
            "commercial_insurance",
            "telecom",
            "signage",
            "payroll",
        ]
    },
    "dental": {
        "*": [
            "it_msp",
            "networking",
            "security_cameras",
            "commercial_cleaning",
            "commercial_insurance",
            "telecom",
            "signage",
            "payroll",
        ]
    },
}


def infer_needs(industry: str | None, stage: str) -> list[tuple[str, str]]:
    rules = NEEDS.get(industry or "", {})
    categories = rules.get(
        stage, rules.get("*", ["commercial_insurance", "internet", "commercial_cleaning"])
    )
    return [
        (category, f"Ruleset: {industry or 'general commercial'} at {stage}")
        for category in categories
    ]


def is_stale(last_signal_at: datetime, stage: str, today: date | None = None) -> tuple[bool, date]:
    today = today or date.today()
    days = 180 if stage in {"EARLY_SIGNAL", "PLANNED", "PLANNING"} else 120
    stale_after = last_signal_at.date() + timedelta(days=days)
    return today > stale_after, stale_after


def match_profile(opportunity: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
    reasons = []
    score = 0.0
    if opportunity.get("industry") in profile.get("target_industries", []):
        score += 35
        reasons.append("target industry")
    if opportunity.get("city") in profile.get("cities", []):
        score += 30
        reasons.append("service city")
    overlap = set(opportunity.get("service_categories", [])) & set(
        profile.get("service_categories", [])
    )
    if overlap:
        score += 25
        reasons.append("relevant services: " + ", ".join(sorted(overlap)))
    score += min(10, float(opportunity.get("score", 0)) / 10)
    timing = (
        "contact now"
        if opportunity.get("stage") in {"BUILDOUT", "PRE_OPENING", "FINAL_PREP"}
        else "monitor"
    )
    return {
        "match_score": round(score, 1),
        "why_it_matches": reasons,
        "recommended_timing": timing,
        "relevant_services": sorted(overlap),
    }


def validation_summary(db: Session) -> dict[str, Any]:
    from .models import Location, Organization, RawRecord, RawSourceDocument, Source

    counts: dict[str, Any] = {
        name: db.scalar(select(func.count()).select_from(model)) or 0
        for name, model in {
            "sources": Source,
            "raw_documents": RawSourceDocument,
            "raw_records": RawRecord,
            "signals": Signal,
            "organizations": Organization,
            "locations": Location,
            "opportunities": Opportunity,
        }.items()
    }
    reviews = Counter(db.scalars(select(ManualReview.verdict)).all())
    counts.update(
        {
            "high_confidence_opportunities": db.scalar(
                select(func.count()).select_from(Opportunity).where(Opportunity.score >= 80)
            )
            or 0,
            "manual_reviews": dict(reviews),
            "manually_verified_actionable": reviews.get("true_positive", 0),
            "false_positives": reviews.get("false_positive", 0),
        }
    )
    counts["actionable_conversion_rate"] = (
        round(reviews.get("true_positive", 0) / sum(reviews.values()) * 100, 1) if reviews else None
    )
    return counts
