import csv
from datetime import datetime

from opportunity_intel.models import Location, Opportunity, Organization
from opportunity_intel.reporting import (
    detailed_validation_report,
    export_validation_csv,
    review_opportunity,
)


def _candidate(db):
    org = Organization(canonical_name="Example Clinic", normalized_name="example clinic")
    db.add(org)
    db.flush()
    location = Location(
        organization_id=org.id,
        address_line_1="1 Main Street",
        city="Bedford",
        physical_confidence=0.95,
    )
    db.add(location)
    db.flush()
    opportunity = Opportunity(
        organization_id=org.id,
        location_id=location.id,
        opportunity_type="new_location",
        stage="BUILDOUT",
        entity_confidence=0.9,
        stage_confidence=0.8,
        confidence=0.85,
        first_detected_at=datetime(2026, 8, 1),
        summary="Medical office buildout",
        why_actionable="Current permit activity",
        score=82,
    )
    db.add(opportunity)
    db.commit()
    return opportunity


def test_review_is_idempotent_and_report_uses_latest_verdict(db):
    opportunity = _candidate(db)
    review_opportunity(db, opportunity.id, "uncertain", "Tenant unclear")
    review_opportunity(db, opportunity.id, "actionable", "Tenant and address confirmed")
    review_opportunity(db, opportunity.id, "actionable", "Tenant and address confirmed")

    report = detailed_validation_report(db)
    assert report["reviewed_candidates"] == 1
    assert report["manually_verified_actionable"] == 1
    assert report["actionable_rate"] == 100.0
    assert report["by_city"]["Bedford"]["actionable"] == 1


def test_validation_export_contains_review_and_timing_fields(db, tmp_path):
    opportunity = _candidate(db)
    review_opportunity(db, opportunity.id, "actionable", "Ready for outreach")
    output = tmp_path / "validation.csv"

    assert export_validation_csv(db, output) == 1
    with output.open(newline="", encoding="utf-8") as handle:
        row = next(csv.DictReader(handle))
    assert row["review_status"] == "actionable"
    assert row["first_detected_at"].startswith("2026-08-01")
    assert row["city"] == "Bedford"
