"""Add provenance-backed contacts, readiness, and vendor feedback."""

import sqlalchemy as sa
from alembic import op

revision = "20260819_0003"
down_revision = "20260819_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "business_contacts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False
        ),
        sa.Column("location_id", sa.String(36), sa.ForeignKey("locations.id")),
        sa.Column("contact_type", sa.String(40), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("label", sa.String(120)),
        sa.Column("is_official", sa.Boolean(), nullable=False),
        sa.Column("is_public", sa.Boolean(), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("source_name", sa.String(200), nullable=False),
        sa.Column("source_type", sa.String(60), nullable=False),
        sa.Column("source_id", sa.String(36), sa.ForeignKey("sources.id")),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("match_reason", sa.Text(), nullable=False),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("organization_id", "contact_type", "value", "source_url"),
    )
    op.create_index(
        "ix_business_contacts_organization_id", "business_contacts", ["organization_id"]
    )
    op.create_index("ix_business_contacts_location_id", "business_contacts", ["location_id"])
    op.create_index("ix_business_contacts_contact_type", "business_contacts", ["contact_type"])
    op.create_table(
        "opportunity_enrichments",
        sa.Column(
            "opportunity_id", sa.String(36), sa.ForeignKey("opportunities.id"), primary_key=True
        ),
        sa.Column("operator_status", sa.String(40), nullable=False),
        sa.Column("chain_classification", sa.String(40), nullable=False),
        sa.Column("contactability_status", sa.String(40), nullable=False),
        sa.Column("contactability_reason", sa.Text(), nullable=False),
        sa.Column("vendor_readiness_score", sa.Float(), nullable=False),
        sa.Column("vendor_readiness_band", sa.String(20), nullable=False),
        sa.Column("vendor_readiness_breakdown", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    for column in (
        "operator_status",
        "chain_classification",
        "contactability_status",
        "vendor_readiness_score",
        "vendor_readiness_band",
    ):
        op.create_index(f"ix_opportunity_enrichments_{column}", "opportunity_enrichments", [column])
    op.create_table(
        "vendor_feedback",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("vendor_profile", sa.String(80), nullable=False),
        sa.Column(
            "opportunity_id", sa.String(36), sa.ForeignKey("opportunities.id"), nullable=False
        ),
        sa.Column("already_knew", sa.Boolean()),
        sa.Column("would_contact", sa.Boolean()),
        sa.Column("timing_useful", sa.Boolean()),
        sa.Column("lead_relevant", sa.Boolean()),
        sa.Column("contact_info_sufficient", sa.Boolean()),
        sa.Column("rating", sa.Integer()),
        sa.Column("comment", sa.Text()),
        sa.Column("outcome_status", sa.String(40), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("vendor_profile", "opportunity_id", "created_at"),
    )
    op.create_index("ix_vendor_feedback_vendor_profile", "vendor_feedback", ["vendor_profile"])
    op.create_index("ix_vendor_feedback_opportunity_id", "vendor_feedback", ["opportunity_id"])
    op.create_index("ix_vendor_feedback_outcome_status", "vendor_feedback", ["outcome_status"])


def downgrade() -> None:
    op.drop_table("vendor_feedback")
    op.drop_table("opportunity_enrichments")
    op.drop_table("business_contacts")
