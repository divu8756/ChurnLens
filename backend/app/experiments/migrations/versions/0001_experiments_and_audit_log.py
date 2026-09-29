"""experiments and audit log

Revision ID: 0001
Revises:
Create Date: 2026-09-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# The audit log is append-only in the database too, not just in the ORM.
SQLITE_TRIGGERS = [
    """CREATE TRIGGER experiment_audit_log_no_update BEFORE UPDATE ON experiment_audit_log
       BEGIN SELECT RAISE(ABORT, 'experiment_audit_log is append-only'); END""",
    """CREATE TRIGGER experiment_audit_log_no_delete BEFORE DELETE ON experiment_audit_log
       BEGIN SELECT RAISE(ABORT, 'experiment_audit_log is append-only'); END""",
]
POSTGRES_TRIGGERS = [
    """CREATE FUNCTION experiment_audit_log_append_only() RETURNS trigger AS $$
       BEGIN RAISE EXCEPTION 'experiment_audit_log is append-only'; END;
       $$ LANGUAGE plpgsql""",
    """CREATE TRIGGER experiment_audit_log_append_only
       BEFORE UPDATE OR DELETE ON experiment_audit_log
       FOR EACH ROW EXECUTE FUNCTION experiment_audit_log_append_only()""",
]


def upgrade() -> None:
    op.create_table(
        "experiments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("hypothesis", sa.Text(), nullable=False),
        sa.Column("source_recommendation_id", sa.String(length=100), nullable=True),
        sa.Column("segment_definition", sa.JSON(), nullable=False),
        sa.Column("offer", sa.String(length=200), nullable=False),
        sa.Column("primary_metric", sa.String(length=100), nullable=False),
        sa.Column("outcome_window_days", sa.Integer(), nullable=False),
        sa.Column("guardrail_metrics", sa.JSON(), nullable=False),
        sa.Column("baseline_rate", sa.Float(), nullable=False),
        sa.Column("mde", sa.Float(), nullable=False),
        sa.Column("mde_type", sa.String(length=10), nullable=False),
        sa.Column("alpha", sa.Float(), nullable=False),
        sa.Column("power", sa.Float(), nullable=False),
        sa.Column("control_share", sa.Float(), nullable=False),
        sa.Column("n_required_treatment", sa.Integer(), nullable=False),
        sa.Column("n_required_control", sa.Integer(), nullable=False),
        sa.Column("planned_start", sa.Date(), nullable=True),
        sa.Column("planned_end", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_by", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("approved_by", sa.String(length=100), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decision", sa.String(length=20), nullable=True),
        sa.Column("decision_note", sa.Text(), nullable=True),
        sa.Column("data_snapshot_hash", sa.String(length=64), nullable=True),
        sa.CheckConstraint("decision IS NULL OR decision IN ('ship', 'dont_ship', 'extend')",
                           name="ck_experiments_decision"),
        sa.CheckConstraint("mde_type IN ('absolute', 'relative')",
                           name="ck_experiments_mde_type"),
        sa.CheckConstraint(
            "status IN ('draft', 'approved', 'running', 'results_uploaded', 'decided')",
            name="ck_experiments_status"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_experiments_status", "experiments", ["status"])

    op.create_table(
        "experiment_audit_log",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("experiment_id", sa.Integer(), nullable=False),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actor", sa.String(length=100), nullable=False),
        sa.Column("action", sa.String(length=50), nullable=False),
        sa.Column("from_status", sa.String(length=20), nullable=True),
        sa.Column("to_status", sa.String(length=20), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(["experiment_id"], ["experiments.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_experiment_audit_log_experiment_id", "experiment_audit_log",
                    ["experiment_id"])

    dialect = op.get_bind().dialect.name
    for sql in {"sqlite": SQLITE_TRIGGERS, "postgresql": POSTGRES_TRIGGERS}.get(dialect, []):
        op.execute(sql)


def downgrade() -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "sqlite":
        op.execute("DROP TRIGGER IF EXISTS experiment_audit_log_no_update")
        op.execute("DROP TRIGGER IF EXISTS experiment_audit_log_no_delete")
    elif dialect == "postgresql":
        op.execute("DROP TRIGGER IF EXISTS experiment_audit_log_append_only "
                   "ON experiment_audit_log")
        op.execute("DROP FUNCTION IF EXISTS experiment_audit_log_append_only()")
    op.drop_index("ix_experiment_audit_log_experiment_id", table_name="experiment_audit_log")
    op.drop_table("experiment_audit_log")
    op.drop_index("ix_experiments_status", table_name="experiments")
    op.drop_table("experiments")
