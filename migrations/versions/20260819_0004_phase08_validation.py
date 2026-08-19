"""Add Phase 0.8 operator, contact utility, readiness tier, and blind freeze fields."""

import sqlalchemy as sa
from alembic import op

revision = "20260819_0004"
down_revision = "20260819_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("business_contacts") as batch:
        batch.add_column(
            sa.Column("utility_class", sa.String(40), nullable=False, server_default="UNKNOWN")
        )
        batch.add_column(
            sa.Column("utility_score", sa.Integer(), nullable=False, server_default="0")
        )
        batch.add_column(
            sa.Column(
                "relationship_to_opportunity",
                sa.Text(),
                nullable=False,
                server_default="Unspecified",
            )
        )
        batch.create_index("ix_business_contacts_utility_class", ["utility_class"])
    with op.batch_alter_table("opportunity_enrichments") as batch:
        batch.add_column(
            sa.Column(
                "operator_confidence", sa.String(20), nullable=False, server_default="UNKNOWN"
            )
        )
        batch.add_column(
            sa.Column(
                "operator_resolution_reason",
                sa.Text(),
                nullable=False,
                server_default="No operator resolved.",
            )
        )
        batch.add_column(sa.Column("first_operator_identified_at", sa.DateTime(timezone=True)))
        batch.add_column(
            sa.Column(
                "contact_utility_class", sa.String(40), nullable=False, server_default="UNKNOWN"
            )
        )
        batch.add_column(
            sa.Column("contact_utility_score", sa.Integer(), nullable=False, server_default="0")
        )
        batch.add_column(sa.Column("first_contactable_at", sa.DateTime(timezone=True)))
        batch.add_column(
            sa.Column(
                "vendor_readiness_tier", sa.String(20), nullable=False, server_default="NOT_READY"
            )
        )
        batch.create_index(
            "ix_opportunity_enrichments_operator_confidence", ["operator_confidence"]
        )
        batch.create_index(
            "ix_opportunity_enrichments_contact_utility_class", ["contact_utility_class"]
        )
        batch.create_index(
            "ix_opportunity_enrichments_vendor_readiness_tier", ["vendor_readiness_tier"]
        )
    op.create_table(
        "blind_validation_batches",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(160), nullable=False, unique=True),
        sa.Column("source_scope", sa.Text(), nullable=False),
        sa.Column("frozen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("notes", sa.Text()),
    )
    op.create_table(
        "blind_validation_results",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "batch_id", sa.String(36), sa.ForeignKey("blind_validation_batches.id"), nullable=False
        ),
        sa.Column(
            "opportunity_id", sa.String(36), sa.ForeignKey("opportunities.id"), nullable=False
        ),
        sa.Column("machine_status", sa.String(40), nullable=False),
        sa.Column("machine_stage", sa.String(40), nullable=False),
        sa.Column("machine_score", sa.Float(), nullable=False),
        sa.Column("machine_operator_status", sa.String(40), nullable=False),
        sa.Column("machine_contactability_status", sa.String(40), nullable=False),
        sa.Column("machine_payload", sa.JSON(), nullable=False),
        sa.Column("manual_verdict", sa.String(40)),
        sa.Column("manual_notes", sa.Text()),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("batch_id", "opportunity_id"),
    )
    op.create_index(
        "ix_blind_validation_results_batch_id", "blind_validation_results", ["batch_id"]
    )
    op.create_index(
        "ix_blind_validation_results_opportunity_id", "blind_validation_results", ["opportunity_id"]
    )


def downgrade() -> None:
    op.drop_table("blind_validation_results")
    op.drop_table("blind_validation_batches")
    with op.batch_alter_table("opportunity_enrichments") as batch:
        batch.drop_index("ix_opportunity_enrichments_vendor_readiness_tier")
        batch.drop_index("ix_opportunity_enrichments_contact_utility_class")
        batch.drop_index("ix_opportunity_enrichments_operator_confidence")
        batch.drop_column("vendor_readiness_tier")
        batch.drop_column("first_contactable_at")
        batch.drop_column("contact_utility_score")
        batch.drop_column("contact_utility_class")
        batch.drop_column("first_operator_identified_at")
        batch.drop_column("operator_resolution_reason")
        batch.drop_column("operator_confidence")
    with op.batch_alter_table("business_contacts") as batch:
        batch.drop_index("ix_business_contacts_utility_class")
        batch.drop_column("relationship_to_opportunity")
        batch.drop_column("utility_score")
        batch.drop_column("utility_class")
