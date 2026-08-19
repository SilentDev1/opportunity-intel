"""Add Phase 0.9 freshness, cleaning relevance, and vendor economics fields."""

import sqlalchemy as sa
from alembic import op

revision = "20260819_0005"
down_revision = "20260819_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("opportunity_enrichments") as batch:
        batch.add_column(
            sa.Column(
                "freshness_status", sa.String(20), nullable=False, server_default="HISTORICAL"
            )
        )
        batch.add_column(sa.Column("source_event_at", sa.DateTime(timezone=True)))
        batch.add_column(sa.Column("source_published_at", sa.DateTime(timezone=True)))
        batch.add_column(sa.Column("first_observed_live_at", sa.DateTime(timezone=True)))
        batch.add_column(sa.Column("first_actionable_live_at", sa.DateTime(timezone=True)))
        batch.add_column(sa.Column("last_meaningful_signal_at", sa.DateTime(timezone=True)))
        batch.add_column(
            sa.Column("cleaning_relevance_score", sa.Float(), nullable=False, server_default="0")
        )
        batch.add_column(
            sa.Column(
                "cleaning_lead_tier", sa.String(20), nullable=False, server_default="NOT_RELEVANT"
            )
        )
        batch.add_column(
            sa.Column("cleaning_score_breakdown", sa.JSON(), nullable=False, server_default="{}")
        )
        batch.create_index("ix_opportunity_enrichments_freshness_status", ["freshness_status"])
        batch.create_index(
            "ix_opportunity_enrichments_cleaning_relevance_score", ["cleaning_relevance_score"]
        )
        batch.create_index("ix_opportunity_enrichments_cleaning_lead_tier", ["cleaning_lead_tier"])
    with op.batch_alter_table("vendor_feedback") as batch:
        batch.add_column(sa.Column("weekly_list_saves_time", sa.Boolean()))
        batch.add_column(sa.Column("good_leads_per_month", sa.Integer()))
        batch.add_column(sa.Column("missing_information", sa.Text()))
        batch.add_column(sa.Column("willing_to_pay_49", sa.Boolean()))
        batch.add_column(sa.Column("willing_to_pay_79", sa.Boolean()))
        batch.add_column(sa.Column("willing_to_pay_99", sa.Boolean()))
        batch.add_column(sa.Column("willing_to_pay_149", sa.Boolean()))
        batch.add_column(sa.Column("reasonable_monthly_price", sa.Float()))


def downgrade() -> None:
    with op.batch_alter_table("vendor_feedback") as batch:
        batch.drop_column("reasonable_monthly_price")
        batch.drop_column("willing_to_pay_149")
        batch.drop_column("willing_to_pay_99")
        batch.drop_column("willing_to_pay_79")
        batch.drop_column("willing_to_pay_49")
        batch.drop_column("missing_information")
        batch.drop_column("good_leads_per_month")
        batch.drop_column("weekly_list_saves_time")
    with op.batch_alter_table("opportunity_enrichments") as batch:
        batch.drop_index("ix_opportunity_enrichments_cleaning_lead_tier")
        batch.drop_index("ix_opportunity_enrichments_cleaning_relevance_score")
        batch.drop_index("ix_opportunity_enrichments_freshness_status")
        batch.drop_column("cleaning_score_breakdown")
        batch.drop_column("cleaning_lead_tier")
        batch.drop_column("cleaning_relevance_score")
        batch.drop_column("last_meaningful_signal_at")
        batch.drop_column("first_actionable_live_at")
        batch.drop_column("first_observed_live_at")
        batch.drop_column("source_published_at")
        batch.drop_column("source_event_at")
        batch.drop_column("freshness_status")
