"""assignments

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "experiment_assignments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("experiment_id", sa.Integer(), nullable=False),
        sa.Column("customer_id", sa.String(length=200), nullable=False),
        sa.Column("arm", sa.String(length=10), nullable=False),
        sa.Column("offer", sa.String(length=200), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("arm IN ('treatment', 'control')", name="ck_assignment_arm"),
        sa.ForeignKeyConstraint(["experiment_id"], ["experiments.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("experiment_id", "customer_id", name="uq_assignment_customer"),
    )
    op.create_index("ix_experiment_assignments_customer_id", "experiment_assignments",
                    ["customer_id"])
    op.create_index("ix_experiment_assignments_experiment_id", "experiment_assignments",
                    ["experiment_id"])
    with op.batch_alter_table("experiments") as batch_op:
        batch_op.add_column(sa.Column("source_session_id", sa.String(length=32), nullable=True))
        batch_op.add_column(sa.Column("design", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("assignment_summary", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("experiments") as batch_op:
        batch_op.drop_column("assignment_summary")
        batch_op.drop_column("design")
        batch_op.drop_column("source_session_id")
    op.drop_index("ix_experiment_assignments_experiment_id", table_name="experiment_assignments")
    op.drop_index("ix_experiment_assignments_customer_id", table_name="experiment_assignments")
    op.drop_table("experiment_assignments")
