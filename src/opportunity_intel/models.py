import enum
import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def uid() -> str:
    return str(uuid.uuid4())


class LifecycleStage(enum.StrEnum):
    UNKNOWN = "UNKNOWN"
    EARLY_SIGNAL = "EARLY_SIGNAL"
    PLANNED = "PLANNED"
    LOCATION_CONFIRMED = "LOCATION_CONFIRMED"
    PLANNING = "PLANNING"
    PRE_BUILDOUT = "PRE_BUILDOUT"
    BUILDOUT = "BUILDOUT"
    PRE_OPENING = "PRE_OPENING"
    FINAL_PREP = "FINAL_PREP"
    OPEN = "OPEN"
    EXPANDING = "EXPANDING"
    RELOCATING = "RELOCATING"
    CLOSED = "CLOSED"
    CANCELLED = "CANCELLED"
    STALE = "STALE"


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )


class Source(Base, TimestampMixin):
    __tablename__ = "sources"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(String(200), unique=True)
    source_type: Mapped[str] = mapped_column(String(50))
    jurisdiction: Mapped[str] = mapped_column(String(120))
    base_url: Mapped[str] = mapped_column(Text)
    authority_level: Mapped[int] = mapped_column(Integer, default=3)
    is_official: Mapped[bool] = mapped_column(Boolean, default=True)
    collector_name: Mapped[str] = mapped_column(String(100))
    collector_version: Mapped[str] = mapped_column(String(30), default="1")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    schedule: Mapped[str] = mapped_column(String(20), default="weekly")
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
    failure_count: Mapped[int] = mapped_column(Integer, default=0)


class CollectionRun(Base):
    __tablename__ = "collection_runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    source_id: Mapped[str] = mapped_column(ForeignKey("sources.id"))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), default="running")
    trigger: Mapped[str] = mapped_column(String(20), default="manual")
    documents_discovered: Mapped[int] = mapped_column(Integer, default=0)
    documents_new: Mapped[int] = mapped_column(Integer, default=0)
    records_parsed: Mapped[int] = mapped_column(Integer, default=0)
    signals_produced: Mapped[int] = mapped_column(Integer, default=0)
    entities_matched: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text)


class RawSourceDocument(Base):
    __tablename__ = "raw_source_documents"
    __table_args__ = (UniqueConstraint("source_id", "content_hash"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    source_id: Mapped[str] = mapped_column(ForeignKey("sources.id"), index=True)
    source_url: Mapped[str] = mapped_column(Text)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    content_type: Mapped[str] = mapped_column(String(100))
    http_status: Mapped[int] = mapped_column(Integer)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    storage_path: Mapped[str] = mapped_column(Text)
    title: Mapped[str | None] = mapped_column(Text)
    document_metadata: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict)
    parser_version: Mapped[str] = mapped_column(String(30), default="1")
    processing_status: Mapped[str] = mapped_column(String(30), default="pending")
    extraction_quality: Mapped[float | None] = mapped_column(Float)
    error: Mapped[str | None] = mapped_column(Text)


class RawRecord(Base):
    __tablename__ = "raw_records"
    __table_args__ = (UniqueConstraint("raw_source_document_id", "external_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    raw_source_document_id: Mapped[str] = mapped_column(
        ForeignKey("raw_source_documents.id"), index=True
    )
    record_type: Mapped[str] = mapped_column(String(50))
    external_id: Mapped[str] = mapped_column(String(255))
    raw_payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    extracted_text: Mapped[str | None] = mapped_column(Text)
    parser_version: Mapped[str] = mapped_column(String(30), default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class Organization(Base, TimestampMixin):
    __tablename__ = "organizations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    canonical_name: Mapped[str] = mapped_column(String(255))
    normalized_name: Mapped[str] = mapped_column(String(255), index=True)
    legal_name: Mapped[str | None] = mapped_column(String(255))
    dba_name: Mapped[str | None] = mapped_column(String(255))
    organization_type: Mapped[str | None] = mapped_column(String(50))
    industry: Mapped[str | None] = mapped_column(String(80), index=True)
    industry_code: Mapped[str | None] = mapped_column(String(30))
    website: Mapped[str | None] = mapped_column(Text)
    phone: Mapped[str | None] = mapped_column(String(40))
    email: Mapped[str | None] = mapped_column(String(255))
    state_registration_id: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(30), default="active")
    suppressed: Mapped[bool] = mapped_column(Boolean, default=False)
    suppression_reason: Mapped[str | None] = mapped_column(Text)
    aliases: Mapped[list["OrganizationAlias"]] = relationship(cascade="all, delete-orphan")


class OrganizationAlias(Base):
    __tablename__ = "organization_aliases"
    __table_args__ = (UniqueConstraint("organization_id", "normalized_alias"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    alias: Mapped[str] = mapped_column(String(255))
    normalized_alias: Mapped[str] = mapped_column(String(255), index=True)
    source_id: Mapped[str | None] = mapped_column(ForeignKey("sources.id"))


class BusinessContact(Base, TimestampMixin):
    __tablename__ = "business_contacts"
    __table_args__ = (UniqueConstraint("organization_id", "contact_type", "value", "source_url"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    location_id: Mapped[str | None] = mapped_column(ForeignKey("locations.id"), index=True)
    contact_type: Mapped[str] = mapped_column(String(40), index=True)
    value: Mapped[str] = mapped_column(Text)
    label: Mapped[str | None] = mapped_column(String(120))
    is_official: Mapped[bool] = mapped_column(Boolean, default=False)
    is_public: Mapped[bool] = mapped_column(Boolean, default=True)
    source_url: Mapped[str] = mapped_column(Text)
    source_name: Mapped[str] = mapped_column(String(200))
    source_type: Mapped[str] = mapped_column(String(60))
    source_id: Mapped[str | None] = mapped_column(ForeignKey("sources.id"))
    confidence: Mapped[float] = mapped_column(Float)
    match_reason: Mapped[str] = mapped_column(Text)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    verified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(30), default="active")
    utility_class: Mapped[str] = mapped_column(String(40), default="UNKNOWN", index=True)
    utility_score: Mapped[int] = mapped_column(Integer, default=0)
    relationship_to_opportunity: Mapped[str] = mapped_column(Text, default="Unspecified")


class Location(Base, TimestampMixin):
    __tablename__ = "locations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    name: Mapped[str | None] = mapped_column(String(255))
    address_line_1: Mapped[str | None] = mapped_column(String(255))
    address_line_2: Mapped[str | None] = mapped_column(String(100))
    city: Mapped[str | None] = mapped_column(String(100), index=True)
    state: Mapped[str] = mapped_column(String(2), default="NH")
    postal_code: Mapped[str | None] = mapped_column(String(10))
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    county: Mapped[str | None] = mapped_column(String(100))
    municipality: Mapped[str | None] = mapped_column(String(100))
    location_status: Mapped[str] = mapped_column(String(30), default="candidate")
    physical_confidence: Mapped[float] = mapped_column(Float, default=0)
    opened_at: Mapped[date | None] = mapped_column(Date)
    closed_at: Mapped[date | None] = mapped_column(Date)


class Signal(Base):
    __tablename__ = "signals"
    __table_args__ = (
        UniqueConstraint("raw_record_id", "signal_type", "organization_id", "location_id"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str | None] = mapped_column(ForeignKey("organizations.id"), index=True)
    location_id: Mapped[str | None] = mapped_column(ForeignKey("locations.id"), index=True)
    source_id: Mapped[str] = mapped_column(ForeignKey("sources.id"))
    raw_record_id: Mapped[str] = mapped_column(ForeignKey("raw_records.id"))
    signal_type: Mapped[str] = mapped_column(String(60), index=True)
    signal_date: Mapped[date | None] = mapped_column(Date)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    title: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    structured_data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    confidence: Mapped[float] = mapped_column(Float)
    source_url: Mapped[str] = mapped_column(Text)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class Opportunity(Base, TimestampMixin):
    __tablename__ = "opportunities"
    __table_args__ = (UniqueConstraint("organization_id", "location_id", "opportunity_type"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    location_id: Mapped[str | None] = mapped_column(ForeignKey("locations.id"), index=True)
    opportunity_type: Mapped[str] = mapped_column(String(40))
    stage: Mapped[str] = mapped_column(String(30), default=LifecycleStage.UNKNOWN.value, index=True)
    entity_confidence: Mapped[float] = mapped_column(Float, default=0)
    stage_confidence: Mapped[float] = mapped_column(Float, default=0)
    confidence: Mapped[float] = mapped_column(Float, default=0)
    stage_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    stage_reasoning: Mapped[list[str]] = mapped_column(JSON, default=list)
    first_detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    first_actionable_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_signal_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    stale_after: Mapped[date | None] = mapped_column(Date)
    stale_reason: Mapped[str | None] = mapped_column(Text)
    estimated_open_start: Mapped[date | None] = mapped_column(Date)
    estimated_open_end: Mapped[date | None] = mapped_column(Date)
    announced_open_date: Mapped[date | None] = mapped_column(Date)
    confirmed_open_date: Mapped[date | None] = mapped_column(Date)
    first_seen_open_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    opening_date_confidence: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(30), default="candidate")
    summary: Mapped[str] = mapped_column(Text)
    why_actionable: Mapped[str] = mapped_column(Text)
    score: Mapped[float] = mapped_column(Float, default=0, index=True)
    score_breakdown: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class InferredNeed(Base):
    __tablename__ = "inferred_needs"
    __table_args__ = (UniqueConstraint("opportunity_id", "service_category"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    opportunity_id: Mapped[str] = mapped_column(ForeignKey("opportunities.id"), index=True)
    service_category: Mapped[str] = mapped_column(String(80))
    confidence: Mapped[float] = mapped_column(Float)
    reason: Mapped[str] = mapped_column(Text)


class ReviewItem(Base, TimestampMixin):
    __tablename__ = "review_items"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    review_type: Mapped[str] = mapped_column(String(50), index=True)
    entity_type: Mapped[str] = mapped_column(String(50))
    entity_id: Mapped[str] = mapped_column(String(36))
    candidate_entity_id: Mapped[str | None] = mapped_column(String(36))
    confidence: Mapped[float | None] = mapped_column(Float)
    reason: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default="pending")
    resolution: Mapped[str | None] = mapped_column(String(50))
    notes: Mapped[str | None] = mapped_column(Text)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ManualReview(Base):
    __tablename__ = "manual_reviews"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    opportunity_id: Mapped[str] = mapped_column(ForeignKey("opportunities.id"), index=True)
    verdict: Mapped[str] = mapped_column(String(30))
    notes: Mapped[str | None] = mapped_column(Text)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class OpportunityOrganizationRole(Base):
    __tablename__ = "opportunity_organization_roles"
    __table_args__ = (UniqueConstraint("opportunity_id", "organization_id", "role"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    opportunity_id: Mapped[str] = mapped_column(ForeignKey("opportunities.id"), index=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    role: Mapped[str] = mapped_column(String(40))
    confidence: Mapped[float] = mapped_column(Float)
    evidence: Mapped[str] = mapped_column(Text)
    source_id: Mapped[str | None] = mapped_column(ForeignKey("sources.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class OpportunityEnrichment(Base, TimestampMixin):
    __tablename__ = "opportunity_enrichments"
    opportunity_id: Mapped[str] = mapped_column(ForeignKey("opportunities.id"), primary_key=True)
    operator_status: Mapped[str] = mapped_column(String(40), default="UNKNOWN", index=True)
    operator_confidence: Mapped[str] = mapped_column(String(20), default="UNKNOWN", index=True)
    operator_resolution_reason: Mapped[str] = mapped_column(Text, default="No operator resolved.")
    first_operator_identified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    chain_classification: Mapped[str] = mapped_column(String(40), default="UNKNOWN", index=True)
    contactability_status: Mapped[str] = mapped_column(
        String(40), default="NOT_CONTACTABLE", index=True
    )
    contactability_reason: Mapped[str] = mapped_column(Text, default="No verified route stored.")
    contact_utility_class: Mapped[str] = mapped_column(String(40), default="UNKNOWN", index=True)
    contact_utility_score: Mapped[int] = mapped_column(Integer, default=0)
    first_contactable_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    vendor_readiness_score: Mapped[float] = mapped_column(Float, default=0, index=True)
    vendor_readiness_band: Mapped[str] = mapped_column(String(20), default="LOW", index=True)
    vendor_readiness_tier: Mapped[str] = mapped_column(String(20), default="NOT_READY", index=True)
    vendor_readiness_breakdown: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    freshness_status: Mapped[str] = mapped_column(String(20), default="HISTORICAL", index=True)
    source_event_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source_published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    first_observed_live_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    first_actionable_live_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_meaningful_signal_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cleaning_relevance_score: Mapped[float] = mapped_column(Float, default=0, index=True)
    cleaning_lead_tier: Mapped[str] = mapped_column(String(20), default="NOT_RELEVANT", index=True)
    cleaning_score_breakdown: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class VendorFeedback(Base):
    __tablename__ = "vendor_feedback"
    __table_args__ = (UniqueConstraint("vendor_profile", "opportunity_id", "created_at"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    vendor_profile: Mapped[str] = mapped_column(String(80), index=True)
    opportunity_id: Mapped[str] = mapped_column(ForeignKey("opportunities.id"), index=True)
    already_knew: Mapped[bool | None] = mapped_column(Boolean)
    would_contact: Mapped[bool | None] = mapped_column(Boolean)
    timing_useful: Mapped[bool | None] = mapped_column(Boolean)
    lead_relevant: Mapped[bool | None] = mapped_column(Boolean)
    contact_info_sufficient: Mapped[bool | None] = mapped_column(Boolean)
    rating: Mapped[int | None] = mapped_column(Integer)
    comment: Mapped[str | None] = mapped_column(Text)
    outcome_status: Mapped[str] = mapped_column(String(40), default="NOT_REVIEWED", index=True)
    weekly_list_saves_time: Mapped[bool | None] = mapped_column(Boolean)
    good_leads_per_month: Mapped[int | None] = mapped_column(Integer)
    missing_information: Mapped[str | None] = mapped_column(Text)
    willing_to_pay_49: Mapped[bool | None] = mapped_column(Boolean)
    willing_to_pay_79: Mapped[bool | None] = mapped_column(Boolean)
    willing_to_pay_99: Mapped[bool | None] = mapped_column(Boolean)
    willing_to_pay_149: Mapped[bool | None] = mapped_column(Boolean)
    reasonable_monthly_price: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class BlindValidationBatch(Base):
    __tablename__ = "blind_validation_batches"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(String(160), unique=True)
    source_scope: Mapped[str] = mapped_column(Text)
    frozen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    notes: Mapped[str | None] = mapped_column(Text)


class BlindValidationResult(Base):
    __tablename__ = "blind_validation_results"
    __table_args__ = (UniqueConstraint("batch_id", "opportunity_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    batch_id: Mapped[str] = mapped_column(ForeignKey("blind_validation_batches.id"), index=True)
    opportunity_id: Mapped[str] = mapped_column(ForeignKey("opportunities.id"), index=True)
    machine_status: Mapped[str] = mapped_column(String(40))
    machine_stage: Mapped[str] = mapped_column(String(40))
    machine_score: Mapped[float] = mapped_column(Float)
    machine_operator_status: Mapped[str] = mapped_column(String(40))
    machine_contactability_status: Mapped[str] = mapped_column(String(40))
    machine_payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    manual_verdict: Mapped[str | None] = mapped_column(String(40))
    manual_notes: Mapped[str | None] = mapped_column(Text)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class StageHistory(Base):
    __tablename__ = "stage_history"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    opportunity_id: Mapped[str] = mapped_column(ForeignKey("opportunities.id"), index=True)
    from_stage: Mapped[str | None] = mapped_column(String(30))
    to_stage: Mapped[str] = mapped_column(String(30))
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    reason: Mapped[str] = mapped_column(Text)
    triggering_signal_id: Mapped[str | None] = mapped_column(ForeignKey("signals.id"))


Index("ix_location_normalized", Location.city, Location.address_line_1)
