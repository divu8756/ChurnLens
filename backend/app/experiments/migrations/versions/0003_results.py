"""results: outcomes table, pre-registered segments, analysis

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "experiment_outcomes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("experiment_id", sa.Integer(), nullable=False),
        sa.Column("customer_id", sa.String(length=200), nullable=False),
        sa.Column("arm", sa.String(length=10), nullable=False),
        sa.Column("offer_accepted", sa.Integer(), nullable=True),
        sa.Column("churned", sa.Integer(), nullable=False),
        sa.Column("revenue", sa.Float(), nullable=True),
        sa.Column("complaints", sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(["experiment_id"], ["experiments.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("experiment_id", "customer_id", name="uq_outcome_customer"),
    )
    op.create_index("ix_experiment_outcomes_experiment_id", "experiment_outcomes",
                    ["experiment_id"])
    with op.batch_alter_table("experiments") as batch_op:
        batch_op.add_column(sa.Column("preregistered_segments", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("analysis", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("results_uploaded_at", sa.DateTime(timezone=True),
                                      nullable=True))
    with op.batch_alter_table("experiment_assignments") as batch_op:
        batch_op.add_column(sa.Column("segments", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("experiment_assignments") as batch_op:
        batch_op.drop_column("segments")
    with op.batch_alter_table("experiments") as batch_op:
        batch_op.drop_column("results_uploaded_at")
        batch_op.drop_column("analysis")
        batch_op.drop_column("preregistered_segments")
    op.drop_index("ix_experiment_outcomes_experiment_id", table_name="experiment_outcomes")
    op.drop_table("experiment_outcomes")
