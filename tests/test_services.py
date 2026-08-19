from datetime import datetime, timedelta

from opportunity_intel.models import Signal
from opportunity_intel.services import (
    infer_needs,
    infer_stage,
    is_stale,
    match_profile,
    normalize_address,
    normalize_name,
    score_opportunity,
)


def signal(kind, source="a", days=0, confidence=0.9):
    return Signal(
        id=kind + source,
        raw_record_id=kind + source,
        source_id=source,
        signal_type=kind,
        title=kind,
        source_url="https://example.gov",
        confidence=confidence,
        detected_at=datetime.utcnow() - timedelta(days=days),
    )


def test_normalization():
    assert normalize_name("The ACME, LLC") == "the acme"
    assert normalize_name("A & B Inc.") == "a and b"
    assert normalize_address("125 South Broadway Street, Suite 2") == "125 s broadway st ste 2"


def test_stage_uses_strongest_signal_and_corroboration():
    stage, confidence, reasons = infer_stage(
        [signal("business_registration"), signal("job_posting", "b")]
    )
    assert stage.value == "PRE_OPENING" and confidence > 0.84 and "job_posting signal" in reasons


def test_scoring_is_explainable_and_recency_sensitive():
    recent, _ = score_opportunity([signal("building_permit")], 0.9, now=datetime.utcnow())
    old, breakdown = score_opportunity(
        [signal("building_permit", days=200)], 0.9, now=datetime.utcnow()
    )
    assert recent > old and set(breakdown) == {
        "evidence",
        "location",
        "recency",
        "corroboration",
        "commercial_relevance",
    }


def test_need_inference():
    needs = dict(infer_needs("restaurant", "BUILDOUT"))
    assert "post_construction_cleaning" in needs and "Ruleset" in needs["pos"]


def test_staleness():
    stale, deadline = is_stale(datetime.utcnow() - timedelta(days=200), "PLANNING")
    assert stale and deadline < datetime.utcnow().date()


def test_matcher():
    result = match_profile(
        {
            "industry": "restaurant",
            "city": "Salem",
            "stage": "BUILDOUT",
            "score": 80,
            "service_categories": ["commercial_cleaning"],
        },
        {
            "target_industries": ["restaurant"],
            "cities": ["Salem"],
            "service_categories": ["commercial_cleaning"],
        },
    )
    assert result["match_score"] == 98 and result["recommended_timing"] == "contact now"
