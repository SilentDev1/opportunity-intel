import csv
from datetime import date, datetime

from opportunity_intel.enrichment import import_vendor_feedback_csv, import_vendor_outcomes_csv
from opportunity_intel.models import (
    BlindValidationBatch,
    BlindValidationResult,
    Location,
    Opportunity,
    OpportunityEnrichment,
    Organization,
    VendorFeedback,
    VendorLeadOutcome,
)
from opportunity_intel.phase10 import (
    classify_currentness,
    customer_facing_precision,
    evaluate_customer_mvp_gate,
    export_current_cleaning_test,
    live_geographic_flow,
    meaningful_update,
    outcome_metrics,
    vendor_validation_metrics,
)


def _opportunity(db, name="Lead", city="Salem"):
    organization = Organization(
        canonical_name=name, normalized_name=name.casefold(), industry="restaurant"
    )
    db.add(organization)
    db.flush()
    location = Location(
        organization_id=organization.id, address_line_1="1 Main", city=city, state="NH"
    )
    db.add(location)
    db.flush()
    opportunity = Opportunity(
        organization_id=organization.id,
        location_id=location.id,
        opportunity_type="new_location",
        stage="BUILDOUT",
        status="actionable",
        first_detected_at=datetime(2026, 8, 19),
        last_signal_at=datetime(2026, 8, 19),
        summary="Restaurant buildout",
        why_actionable="Official permit evidence",
    )
    db.add(opportunity)
    db.flush()
    return opportunity


def test_feedback_import_is_idempotent_and_metrics_preserve_categories(db, tmp_path):
    opportunity = _opportunity(db)
    db.commit()
    path = tmp_path / "feedback.csv"
    fields = [
        "vendor_profile",
        "vendor_name",
        "vendor_type",
        "service_territory",
        "opportunity_id",
        "date_shown",
        "already_knew",
        "would_contact_response",
        "timing_response",
        "contact_sufficiency_response",
        "rating",
        "wants_weekly_feed",
        "willing_to_pay_79",
    ]
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerow(
            {
                "vendor_profile": "commercial_cleaning",
                "vendor_name": "Clean Co",
                "vendor_type": "commercial cleaner",
                "service_territory": "Southern NH",
                "opportunity_id": opportunity.id,
                "date_shown": "2026-08-19",
                "already_knew": "no",
                "would_contact_response": "MAYBE",
                "timing_response": "GOOD",
                "contact_sufficiency_response": "PARTIAL",
                "rating": "4",
                "wants_weekly_feed": "yes",
                "willing_to_pay_79": "no",
            }
        )
    assert import_vendor_feedback_csv(db, path) == 1
    assert import_vendor_feedback_csv(db, path) == 0
    assert db.query(VendorFeedback).count() == 1
    metrics = vendor_validation_metrics(db, "commercial_cleaning")
    assert metrics["vendors"] == 1
    assert metrics["would_contact_yes_pct"] == 0.0
    assert metrics["would_contact_yes_maybe_pct"] == 100.0
    assert metrics["timing_good_pct"] == 100.0
    assert metrics["contact_sufficient_pct"] == 0.0
    assert metrics["wants_weekly_feed_pct"] == 100.0


def test_no_feedback_state(db):
    assert vendor_validation_metrics(db, "commercial_cleaning") == {
        "status": "No external vendor feedback has been received yet.",
        "vendors": 0,
        "leads_reviewed": 0,
    }


def test_vendor_outcomes_are_attributed_and_idempotent(db, tmp_path):
    opportunity = _opportunity(db)
    db.commit()
    path = tmp_path / "outcomes.csv"
    path.write_text(
        "vendor_name,opportunity_id,date_shown,date_contacted,outcome_status,outcome_at,notes\n"
        f"Clean Co,{opportunity.id},2026-08-19,2026-08-20,CONTACT_ATTEMPTED,"
        "2026-08-20T10:00:00,Called\n"
    )
    assert import_vendor_outcomes_csv(db, path) == 1
    assert import_vendor_outcomes_csv(db, path) == 0
    assert db.query(VendorLeadOutcome).count() == 1
    assert outcome_metrics(db)["outcomes"] == {"CONTACT_ATTEMPTED": 1}


def test_customer_facing_precision_uses_reviewed_blind_ab(db):
    opportunity = _opportunity(db)
    db.add(OpportunityEnrichment(opportunity_id=opportunity.id, cleaning_lead_tier="CLEANING_A"))
    batch = BlindValidationBatch(name="blind", source_scope="test")
    db.add(batch)
    db.flush()
    db.add(
        BlindValidationResult(
            batch_id=batch.id,
            opportunity_id=opportunity.id,
            machine_status="candidate",
            machine_stage="BUILDOUT",
            machine_score=90,
            machine_operator_status="KNOWN",
            machine_contactability_status="CONTACTABLE",
            manual_verdict="actionable",
        )
    )
    db.commit()
    assert customer_facing_precision(db, "blind") == {
        "blind_ab_count": 1,
        "true_usable_ab": 1,
        "false_ab": 0,
        "precision_pct": 100.0,
    }


def test_currentness_and_meaningful_update_classification():
    today = date(2026, 8, 19)
    assert classify_currentness(today, today) == "DAILY"
    assert classify_currentness(date(2026, 8, 12), today) == "WEEKLY"
    assert classify_currentness(date(2026, 7, 20), today) == "MONTHLY"
    assert classify_currentness(date(2025, 1, 1), today) == "HISTORICAL"
    assert meaningful_update("operator_identified")
    assert not meaningful_update("operator_identified", duplicate_evidence=True)
    assert not meaningful_update("duplicate_document")


def test_live_geography_and_current_packet_exclude_historical(db, tmp_path):
    current = _opportunity(db, "Current", "Manchester")
    historical = _opportunity(db, "Historical", "Portsmouth")
    db.add_all(
        [
            OpportunityEnrichment(
                opportunity_id=current.id,
                freshness_status="FRESH",
                cleaning_lead_tier="CLEANING_A",
                contactability_status="CONTACTABLE",
                contactability_reason="Official contact page",
            ),
            OpportunityEnrichment(
                opportunity_id=historical.id,
                freshness_status="HISTORICAL",
                cleaning_lead_tier="CLEANING_A",
                contactability_status="CONTACTABLE",
            ),
        ]
    )
    db.commit()
    assert live_geographic_flow(db) == {
        "statewide_fresh_cleaning_ab": 1,
        "southern_nh_fresh_cleaning_ab": 1,
    }
    path = tmp_path / "current.csv"
    assert export_current_cleaning_test(db, path) == 1
    assert "Current" in path.read_text()
    assert "Historical" not in path.read_text()


def test_customer_mvp_gate_requires_all_market_evidence():
    assert (
        evaluate_customer_mvp_gate(
            current_strong_leads=10,
            vendors=3,
            contact_intent_pct=60,
            weekly_feed_interest_pct=60,
            precision_pct=90,
            completed_live_weeks=4,
        )["passed"]
        is True
    )
    assert (
        evaluate_customer_mvp_gate(
            current_strong_leads=10,
            vendors=0,
            contact_intent_pct=None,
            weekly_feed_interest_pct=None,
            precision_pct=100,
            completed_live_weeks=0,
        )["passed"]
        is False
    )
