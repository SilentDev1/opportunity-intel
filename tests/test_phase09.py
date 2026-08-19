from datetime import date, datetime

from opportunity_intel.models import (
    Location,
    Opportunity,
    OpportunityEnrichment,
    Organization,
    Signal,
    Source,
    VendorFeedback,
)
from opportunity_intel.phase09 import (
    classify_freshness,
    classify_stale_reason,
    cleaning_score,
    geographic_cleaning_simulation,
    pricing_scenarios,
    vendor_feedback_summary,
    weekly_cleaning_flow,
)


def _source(name: str, enabled: bool = True) -> Source:
    return Source(
        id=name,
        name=name,
        source_type="planning_board",
        jurisdiction="NH",
        base_url="https://example.gov",
        collector_name="test",
        enabled=enabled,
    )


def _signal(source_id: str, url: str, signal_date: date) -> Signal:
    return Signal(
        id=url,
        source_id=source_id,
        raw_record_id="record",
        signal_type="planning_application",
        signal_date=signal_date,
        detected_at=datetime(2026, 8, 19),
        title="Project",
        confidence=0.9,
        source_url=url,
        is_verified=True,
    )


def test_fresh_vs_historical_uses_event_provenance_not_insert_date():
    live = _source("Live planning")
    historical = _source("Historical permit backfill")
    current = _signal(live.id, "https://example.gov/_08202026-1", date(2026, 8, 19))
    old = _signal(historical.id, "https://example.gov/2024/permit.pdf", date(2024, 1, 1))
    assert (
        classify_freshness(
            first_detected_at=datetime(2026, 8, 19),
            signals=[current],
            source_by_id={live.id: live},
            period_start=date(2026, 8, 17),
            period_end=date(2026, 8, 23),
        )[0]
        == "FRESH"
    )
    assert (
        classify_freshness(
            first_detected_at=datetime(2026, 8, 19),
            signals=[old],
            source_by_id={historical.id: historical},
            period_start=date(2026, 8, 17),
            period_end=date(2026, 8, 23),
        )[0]
        == "HISTORICAL"
    )


def test_cleaning_tiers_and_contact_utility_impact():
    common = dict(
        industry="restaurant",
        stage="BUILDOUT",
        operator_confidence="CONFIRMED",
        freshness_status="FRESH",
        evidence_family_count=2,
        vendor_readiness_tier="A",
        actionable=True,
    )
    high = cleaning_score(contact_utility_score=100, **common)
    weak = cleaning_score(contact_utility_score=40, **common)
    assert high[1] == "CLEANING_A"
    assert weak[1] == "CLEANING_C"
    assert high[0] > weak[0]


def test_stale_reasons_and_pricing():
    assert (
        classify_stale_reason(source_names={"Salem Historical Permits"}, stage="STALE")
        == "historical backfill"
    )
    assert pricing_scenarios(8)[79] == 9.88
    assert pricing_scenarios(0)[99] is None


def test_weekly_unique_and_geographic_simulation(db):
    org = Organization(canonical_name="Clinic", normalized_name="clinic", industry="medical")
    db.add(org)
    db.flush()
    location = Location(organization_id=org.id, address_line_1="1 Main", city="Manchester")
    db.add(location)
    db.flush()
    opportunity = Opportunity(
        organization_id=org.id,
        location_id=location.id,
        opportunity_type="new_location",
        stage="BUILDOUT",
        first_detected_at=datetime(2026, 8, 19),
        status="actionable",
        summary="Clinic buildout",
        why_actionable="Permit",
    )
    db.add(opportunity)
    db.flush()
    db.add(
        OpportunityEnrichment(
            opportunity_id=opportunity.id,
            freshness_status="FRESH",
            contactability_status="CONTACTABLE",
            cleaning_lead_tier="CLEANING_A",
        )
    )
    db.commit()
    flow = weekly_cleaning_flow(db, date(2026, 8, 17), date(2026, 8, 23))
    assert flow["fresh_opportunities"] == 1
    assert flow["fresh_cleaning_ab"] == 1
    assert geographic_cleaning_simulation(db, "southern_nh") == [opportunity.id]
    assert geographic_cleaning_simulation(db, "statewide") == [opportunity.id]


def test_vendor_feedback_summary_supports_pricing(db):
    opportunity_org = Organization(canonical_name="Lead", normalized_name="lead")
    db.add(opportunity_org)
    db.flush()
    location = Location(organization_id=opportunity_org.id, city="Salem")
    db.add(location)
    db.flush()
    opportunity = Opportunity(
        organization_id=opportunity_org.id,
        location_id=location.id,
        opportunity_type="new_location",
        stage="BUILDOUT",
        first_detected_at=datetime(2026, 8, 19),
        summary="Lead",
        why_actionable="Permit",
    )
    db.add(opportunity)
    db.flush()
    db.add(
        VendorFeedback(
            vendor_profile="commercial_cleaning",
            opportunity_id=opportunity.id,
            already_knew=False,
            would_contact=True,
            timing_useful=True,
            contact_info_sufficient=True,
            rating=5,
            willing_to_pay_79=True,
        )
    )
    db.commit()
    summary = vendor_feedback_summary(db, "commercial_cleaning")
    assert summary["previously_unknown_pct"] == 100.0
    assert summary["average_rating"] == 5.0
    assert summary["willing_79_pct"] == 100.0
