from datetime import datetime

import pytest

from opportunity_intel.enrichment import (
    blind_batch_metrics,
    contactability_status,
    freeze_blind_batch,
    independent_signal_families,
    normalize_contact,
    official_website_match,
    refresh_enrichment,
    upsert_contact,
    vendor_readiness,
    vendor_readiness_tier,
)
from opportunity_intel.models import (
    BlindValidationResult,
    Location,
    ManualReview,
    Opportunity,
    OpportunityEnrichment,
    OpportunityOrganizationRole,
    Organization,
    RawRecord,
    RawSourceDocument,
    Signal,
    Source,
)
from opportunity_intel.reporting import export_vendor_ready, source_value_metrics


def _opportunity(db):
    org = Organization(
        canonical_name="Property LLC", normalized_name="property", industry="restaurant"
    )
    db.add(org)
    db.flush()
    location = Location(
        organization_id=org.id, address_line_1="1 Main St", city="Salem", physical_confidence=0.95
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
        confidence=0.8,
        first_detected_at=datetime(2026, 8, 19),
        status="actionable",
        summary="Buildout",
        why_actionable="Current permit",
        score=80,
    )
    db.add(opportunity)
    db.commit()
    return opportunity, org, location


def test_contact_normalization_and_website_mismatch_prevention():
    assert normalize_contact("phone", "(603) 555-0100") == "+16035550100"
    assert normalize_contact("email", "INFO@EXAMPLE.COM") == "info@example.com"
    assert normalize_contact("website", "www.Example.com/") == "https://example.com"
    assert official_website_match(True, 0.9, "same brand on official location page")
    assert not official_website_match(True, 0.9, "first search result")


def test_contact_provenance_status_and_idempotency(db):
    opportunity, org, location = _opportunity(db)
    args = dict(
        organization_id=org.id,
        location_id=location.id,
        contact_type="contact_page",
        value="https://example.com/contact",
        label="Business inquiries",
        is_official=True,
        is_public=True,
        source_url="https://example.com/contact",
        source_name="Example official website",
        source_type="official_company",
        confidence=0.95,
        match_reason="same brand and same city on official location page",
        observed_at=datetime(2026, 8, 19),
        utility_class="BUSINESS_GENERAL",
        relationship_to_opportunity="Operator inquiry route",
    )
    contact, created = upsert_contact(db, **args)
    db.commit()
    _, created_again = upsert_contact(db, **args)
    assert created and not created_again
    assert contact.source_url == "https://example.com/contact"
    assert contactability_status([contact])[0] == "CONTACTABLE"
    enrichment = refresh_enrichment(
        db, opportunity, "KNOWN", "CHAIN_FRANCHISE", "CONFIRMED", "Exact address match"
    )
    assert enrichment.contactability_status == "CONTACTABLE"
    assert enrichment.vendor_readiness_score > 50
    assert enrichment.first_operator_identified_at is not None
    assert enrichment.first_contactable_at is not None
    assert enrichment.contact_utility_score == 75


def test_operator_role_is_separate_from_developer(db):
    opportunity, developer, _ = _opportunity(db)
    operator = Organization(canonical_name="Real Brand", normalized_name="real brand")
    db.add(operator)
    db.flush()
    db.add(
        OpportunityOrganizationRole(
            opportunity_id=opportunity.id,
            organization_id=developer.id,
            role="developer",
            confidence=0.9,
            evidence="Planning filing",
        )
    )
    db.add(
        OpportunityOrganizationRole(
            opportunity_id=opportunity.id,
            organization_id=operator.id,
            role="operator",
            confidence=0.95,
            evidence="Official location page",
        )
    )
    db.commit()
    roles = {
        item.role: item.organization_id for item in db.query(OpportunityOrganizationRole).all()
    }
    assert roles["operator"] == operator.id
    assert roles["developer"] == developer.id


def test_multi_tenant_and_unknown_operator_are_preserved(db):
    opportunity, _, _ = _opportunity(db)
    tenants = [
        Organization(canonical_name=name, normalized_name=name.casefold())
        for name in ("Tenant A", "Tenant B")
    ]
    db.add_all(tenants)
    db.flush()
    for tenant in tenants:
        db.add(
            OpportunityOrganizationRole(
                opportunity_id=opportunity.id,
                organization_id=tenant.id,
                role="tenant",
                confidence=0.9,
                evidence="Address-first municipal tenant schedule",
            )
        )
    enrichment = refresh_enrichment(
        db,
        opportunity,
        "UNKNOWN",
        "UNKNOWN",
        "UNKNOWN",
        "Multi-tenant project; no operating tenant is confirmed.",
    )
    db.commit()
    assert db.query(OpportunityOrganizationRole).filter_by(role="tenant").count() == 2
    assert enrichment.operator_confidence == "UNKNOWN"
    assert enrichment.vendor_readiness_tier == "C"


def test_vendor_readiness_tiers_are_explainable(db):
    opportunity, _, _ = _opportunity(db)
    assert vendor_readiness_tier(opportunity, "CONFIRMED", "CONTACTABLE", 75, 2) == "A"
    assert vendor_readiness_tier(opportunity, "MEDIUM", "CONTACTABLE", 60, 1) == "B"
    assert vendor_readiness_tier(opportunity, "UNKNOWN", "NOT_CONTACTABLE", 0, 1) == "C"
    with pytest.raises(ValueError, match="operator confidence"):
        refresh_enrichment(db, opportunity, operator_confidence="GUESSED")


def test_blind_results_remain_frozen_after_machine_state_changes(db):
    opportunity, _, _ = _opportunity(db)
    enrichment = OpportunityEnrichment(opportunity_id=opportunity.id, operator_status="UNKNOWN")
    db.add(enrichment)
    db.commit()
    batch = freeze_blind_batch(db, "test-freeze", "test", {opportunity.id})
    frozen = batch.id
    opportunity.score = 1
    opportunity.stage = "STALE"
    enrichment.operator_status = "KNOWN"
    db.commit()
    result = db.query(BlindValidationResult).filter_by(batch_id=frozen).one()
    assert result.machine_score == 80
    assert result.machine_stage == "BUILDOUT"
    assert result.machine_operator_status == "UNKNOWN"


def test_independent_signal_families_do_not_duplicate_municipal_event(db):
    opportunity, org, location = _opportunity(db)
    source = Source(
        name="Test",
        source_type="planning_board",
        jurisdiction="NH",
        base_url="https://example.gov",
        collector_name="test",
    )
    db.add(source)
    db.flush()
    document = RawSourceDocument(
        source_id=source.id,
        source_url="https://example.gov/a",
        content_type="text/plain",
        http_status=200,
        content_hash="a" * 64,
        storage_path="x",
    )
    db.add(document)
    db.flush()
    signals = []
    for index, signal_type in enumerate(
        ("planning_application", "zoning_application", "building_permit")
    ):
        record = RawRecord(
            raw_source_document_id=document.id,
            record_type="test",
            external_id=str(index),
            raw_payload={},
        )
        db.add(record)
        db.flush()
        signals.append(
            Signal(
                organization_id=org.id,
                location_id=location.id,
                source_id=source.id,
                raw_record_id=record.id,
                signal_type=signal_type,
                title=signal_type,
                confidence=0.9,
                source_url=document.source_url,
            )
        )
    assert independent_signal_families(signals) == {"municipal_land_use", "permit_buildout"}
    db.add_all(signals)
    db.add(ManualReview(opportunity_id=opportunity.id, verdict="actionable"))
    db.commit()
    metrics = source_value_metrics(db)
    assert metrics[0]["source"] == "Test"
    assert metrics[0]["candidate_opportunities"] == 1
    assert metrics[0]["actionable_opportunities"] == 1
    assert metrics[0]["corroborations_added"] == 1


def test_vendor_readiness_and_blind_metrics(db):
    opportunity, _, _ = _opportunity(db)
    score, band, breakdown = vendor_readiness(opportunity, "KNOWN", "CONTACTABLE", 2)
    assert score == sum(breakdown.values())
    assert band == "HIGH"
    db.add(ManualReview(opportunity_id=opportunity.id, verdict="false_positive"))
    db.commit()
    metrics = blind_batch_metrics(db, {opportunity.id})
    assert metrics["false_positive_rate"] == 100.0


def test_website_requires_match_evidence(db):
    _, org, location = _opportunity(db)
    with pytest.raises(ValueError, match="lacks strong"):
        upsert_contact(
            db,
            organization_id=org.id,
            location_id=location.id,
            contact_type="website",
            value="https://unrelated.example",
            label=None,
            is_official=True,
            is_public=True,
            source_url="https://unrelated.example",
            source_name="Unknown",
            source_type="web",
            confidence=0.9,
            match_reason="search result",
            observed_at=datetime(2026, 8, 19),
        )


def test_vendor_ready_export_requires_contact_and_readiness(db, tmp_path):
    opportunity, org, location = _opportunity(db)
    db.add(ManualReview(opportunity_id=opportunity.id, verdict="actionable"))
    upsert_contact(
        db,
        organization_id=org.id,
        location_id=location.id,
        contact_type="phone",
        value="603-555-0100",
        label="Official business phone",
        is_official=True,
        is_public=True,
        source_url="https://example.com/contact",
        source_name="Official site",
        source_type="official_company",
        confidence=0.95,
        match_reason="same brand and same address",
        observed_at=datetime(2026, 8, 19),
        utility_class="LOCAL_DIRECT",
        relationship_to_opportunity="Direct location phone",
    )
    refresh_enrichment(
        db, opportunity, "KNOWN", "INDEPENDENT_LOCAL", "CONFIRMED", "Exact address match"
    )
    db.commit()
    output = tmp_path / "vendor-ready.csv"
    assert export_vendor_ready(db, "it_msp", output) == 1
    assert "vendor_readiness_score" in output.read_text(encoding="utf-8")
