"""workspace scoping for experiments

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("experiments") as batch_op:
        batch_op.add_column(sa.Column("workspace_hash", sa.String(length=64), nullable=True))
    op.create_index("ix_experiments_workspace_hash", "experiments", ["workspace_hash"])


def downgrade() -> None:
    op.drop_index("ix_experiments_workspace_hash", table_name="experiments")
    with op.batch_alter_table("experiments") as batch_op:
        batch_op.drop_column("workspace_hash")
