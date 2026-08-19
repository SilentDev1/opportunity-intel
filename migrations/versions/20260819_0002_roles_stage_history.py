"""Add organization roles and lifecycle stage history."""

import sqlalchemy as sa
from alembic import op

revision = "20260819_0002"
down_revision = "20260819_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "opportunity_organization_roles",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "opportunity_id", sa.String(36), sa.ForeignKey("opportunities.id"), nullable=False
        ),
        sa.Column(
            "organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False
        ),
        sa.Column("role", sa.String(40), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("evidence", sa.Text(), nullable=False),
        sa.Column("source_id", sa.String(36), sa.ForeignKey("sources.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("opportunity_id", "organization_id", "role"),
    )
    op.create_index(
        "ix_opportunity_role_opportunity", "opportunity_organization_roles", ["opportunity_id"]
    )
    op.create_index(
        "ix_opportunity_role_organization", "opportunity_organization_roles", ["organization_id"]
    )
    op.create_table(
        "stage_history",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "opportunity_id", sa.String(36), sa.ForeignKey("opportunities.id"), nullable=False
        ),
        sa.Column("from_stage", sa.String(30)),
        sa.Column("to_stage", sa.String(30), nullable=False),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("triggering_signal_id", sa.String(36), sa.ForeignKey("signals.id")),
    )
    op.create_index("ix_stage_history_opportunity", "stage_history", ["opportunity_id"])


def downgrade() -> None:
    op.drop_index("ix_stage_history_opportunity", table_name="stage_history")
    op.drop_table("stage_history")
    op.drop_index("ix_opportunity_role_organization", table_name="opportunity_organization_roles")
    op.drop_index("ix_opportunity_role_opportunity", table_name="opportunity_organization_roles")
    op.drop_table("opportunity_organization_roles")
