"""Initial evidence and opportunity schema."""

from alembic import op

from opportunity_intel import models  # noqa: F401
from opportunity_intel.db import Base

revision = "20260819_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # This prototype migration intentionally uses metadata, but must remain frozen at the
    # Phase 0 schema so later explicit migrations also work on a brand-new database.
    later_tables = {"opportunity_organization_roles", "stage_history"}
    Base.metadata.create_all(
        bind=op.get_bind(),
        tables=[table for name, table in Base.metadata.tables.items() if name not in later_tables],
    )


def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind())
