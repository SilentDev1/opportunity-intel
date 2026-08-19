"""Initial evidence and opportunity schema."""

from alembic import op

from opportunity_intel import models  # noqa: F401
from opportunity_intel.db import Base

revision = "20260819_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind())
