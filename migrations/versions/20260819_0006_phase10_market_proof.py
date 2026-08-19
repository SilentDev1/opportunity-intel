"""Add Phase 1.0 vendor feedback identity and attributed outcomes."""

import sqlalchemy as sa
from alembic import op

revision = "20260819_0006"
down_revision = "20260819_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("vendor_feedback") as batch:
        batch.add_column(sa.Column("response_key", sa.String(64)))
        batch.add_column(sa.Column("vendor_name", sa.String(160)))
        batch.add_column(sa.Column("vendor_type", sa.String(80)))
        batch.add_column(sa.Column("service_territory", sa.String(160)))
        batch.add_column(sa.Column("would_contact_response", sa.String(10)))
        batch.add_column(sa.Column("timing_response", sa.String(20)))
        batch.add_column(sa.Column("contact_sufficiency_response", sa.String(10)))
        batch.add_column(sa.Column("wants_weekly_feed", sa.Boolean()))
        batch.create_index("ix_vendor_feedback_response_key", ["response_key"], unique=True)
        batch.create_index("ix_vendor_feedback_vendor_name", ["vendor_name"])
    op.create_table(
        "vendor_lead_outcomes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("vendor_name", sa.String(160), nullable=False),
        sa.Column(
            "opportunity_id", sa.String(36), sa.ForeignKey("opportunities.id"), nullable=False
        ),
        sa.Column("date_shown", sa.Date()),
        sa.Column("date_contacted", sa.Date()),
        sa.Column("outcome_status", sa.String(40), nullable=False),
        sa.Column("outcome_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("notes", sa.Text()),
        sa.UniqueConstraint("vendor_name", "opportunity_id", "outcome_status", "outcome_at"),
    )
    op.create_index("ix_vendor_lead_outcomes_vendor_name", "vendor_lead_outcomes", ["vendor_name"])
    op.create_index(
        "ix_vendor_lead_outcomes_opportunity_id", "vendor_lead_outcomes", ["opportunity_id"]
    )
    op.create_index(
        "ix_vendor_lead_outcomes_outcome_status", "vendor_lead_outcomes", ["outcome_status"]
    )


def downgrade() -> None:
    op.drop_index("ix_vendor_lead_outcomes_outcome_status", table_name="vendor_lead_outcomes")
    op.drop_index("ix_vendor_lead_outcomes_opportunity_id", table_name="vendor_lead_outcomes")
    op.drop_index("ix_vendor_lead_outcomes_vendor_name", table_name="vendor_lead_outcomes")
    op.drop_table("vendor_lead_outcomes")
    with op.batch_alter_table("vendor_feedback") as batch:
        batch.drop_index("ix_vendor_feedback_vendor_name")
        batch.drop_index("ix_vendor_feedback_response_key")
        batch.drop_column("wants_weekly_feed")
        batch.drop_column("contact_sufficiency_response")
        batch.drop_column("timing_response")
        batch.drop_column("would_contact_response")
        batch.drop_column("service_territory")
        batch.drop_column("vendor_type")
        batch.drop_column("vendor_name")
        batch.drop_column("response_key")
