"""offer evidence from decided experiments

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "offer_evidence",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("experiment_id", sa.Integer(), nullable=False),
        sa.Column("offer", sa.String(length=200), nullable=False),
        sa.Column("segment_description", sa.Text(), nullable=True),
        sa.Column("decision", sa.String(length=20), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("n_treatment", sa.Integer(), nullable=False),
        sa.Column("n_control", sa.Integer(), nullable=False),
        sa.Column("treatment_churn", sa.Float(), nullable=False),
        sa.Column("control_churn", sa.Float(), nullable=False),
        sa.Column("itt_difference", sa.Float(), nullable=False),
        sa.Column("ci_low", sa.Float(), nullable=False),
        sa.Column("ci_high", sa.Float(), nullable=False),
        sa.Column("acceptance_rate", sa.Float(), nullable=True),
        sa.Column("retention_lift_per_acceptor", sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(["experiment_id"], ["experiments.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("experiment_id"),
    )
    op.create_index("ix_offer_evidence_offer", "offer_evidence", ["offer"])


def downgrade() -> None:
    op.drop_index("ix_offer_evidence_offer", table_name="offer_evidence")
    op.drop_table("offer_evidence")
