"""Experiment tables. Portable types only (SQLite and Postgres): JSON, not JSONB."""

from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    event,
    false,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

STATUSES = ("draft", "approved", "running", "results_uploaded", "decided")
DECISIONS = ("ship", "dont_ship", "extend")


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    type_annotation_map = {dict[str, Any]: JSON, list[Any]: JSON}


class Experiment(Base):
    __tablename__ = "experiments"
    __table_args__ = (
        CheckConstraint(f"status IN {STATUSES}", name="ck_experiments_status"),
        CheckConstraint(f"decision IS NULL OR decision IN {DECISIONS}",
                        name="ck_experiments_decision"),
        CheckConstraint("mde_type IN ('absolute', 'relative')", name="ck_experiments_mde_type"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    hypothesis: Mapped[str] = mapped_column(Text)
    source_recommendation_id: Mapped[str | None] = mapped_column(String(100))
    # {"description": str, "filters": [{"column", "op", "value"}]}
    segment_definition: Mapped[dict[str, Any]] = mapped_column(JSON)
    offer: Mapped[str] = mapped_column(String(200))
    primary_metric: Mapped[str] = mapped_column(String(100), default="churn")
    outcome_window_days: Mapped[int] = mapped_column(Integer)
    guardrail_metrics: Mapped[list[Any]] = mapped_column(JSON, default=list)
    baseline_rate: Mapped[float] = mapped_column(Float)
    mde: Mapped[float] = mapped_column(Float)
    mde_type: Mapped[str] = mapped_column(String(10), default="absolute")
    alpha: Mapped[float] = mapped_column(Float)
    power: Mapped[float] = mapped_column(Float)
    control_share: Mapped[float] = mapped_column(Float)
    # Unequal splits need different sizes per arm, so both are stored.
    n_required_treatment: Mapped[int] = mapped_column(Integer)
    n_required_control: Mapped[int] = mapped_column(Integer)
    planned_start: Mapped[date | None] = mapped_column(Date)
    planned_end: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), default="draft", index=True)
    created_by: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    approved_by: Mapped[str | None] = mapped_column(String(100))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decision: Mapped[str | None] = mapped_column(String(20))
    decision_note: Mapped[str | None] = mapped_column(Text)
    data_snapshot_hash: Mapped[str | None] = mapped_column(String(64))
    # Session the design and assignment came from (sessions expire; the IDs stay here).
    source_session_id: Mapped[str | None] = mapped_column(String(32))
    # Full sample-size output (experiment_design.sample_size) plus its assumptions.
    design: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    # Balance check and assignment counts from the assign step.
    assignment_summary: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    # [{"name", "filters"}]: segments analysed separately, fixed before approval.
    preregistered_segments: Mapped[list[Any] | None] = mapped_column(JSON)
    # Latest results analysis (stats/experiment_analysis.analyse) and upload checks.
    analysis: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    results_uploaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Demo experiments (simulated results on the sample data) never block real ones.
    demo: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())


class Assignment(Base):
    __tablename__ = "experiment_assignments"
    __table_args__ = (
        UniqueConstraint("experiment_id", "customer_id", name="uq_assignment_customer"),
        CheckConstraint("arm IN ('treatment', 'control')", name="ck_assignment_arm"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    experiment_id: Mapped[int] = mapped_column(ForeignKey("experiments.id"), index=True)
    customer_id: Mapped[str] = mapped_column(String(200), index=True)
    arm: Mapped[str] = mapped_column(String(10))
    offer: Mapped[str | None] = mapped_column(String(200))
    message: Mapped[str | None] = mapped_column(Text)
    # Names of the pre-registered segments this customer belonged to at assignment.
    segments: Mapped[list[Any] | None] = mapped_column(JSON)
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AuditLog(Base):
    """Append-only: rows can be inserted, never updated or deleted (see listeners below)."""

    __tablename__ = "experiment_audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    experiment_id: Mapped[int] = mapped_column(ForeignKey("experiments.id"), index=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    actor: Mapped[str] = mapped_column(String(100))
    action: Mapped[str] = mapped_column(String(50))
    from_status: Mapped[str | None] = mapped_column(String(20))
    to_status: Mapped[str | None] = mapped_column(String(20))
    note: Mapped[str | None] = mapped_column(Text)
    details: Mapped[dict[str, Any] | None] = mapped_column(JSON)


class AppendOnlyError(RuntimeError):
    """Raised on an attempt to change or remove an audit log row."""


@event.listens_for(AuditLog, "before_update")
def _block_update(mapper: Any, connection: Any, target: AuditLog) -> None:
    raise AppendOnlyError("Audit log rows cannot be changed.")


@event.listens_for(AuditLog, "before_delete")
def _block_delete(mapper: Any, connection: Any, target: AuditLog) -> None:
    raise AppendOnlyError("Audit log rows cannot be deleted.")


class Outcome(Base):
    """One row per assigned customer from the latest results upload (replaced on re-upload)."""

    __tablename__ = "experiment_outcomes"
    __table_args__ = (
        UniqueConstraint("experiment_id", "customer_id", name="uq_outcome_customer"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    experiment_id: Mapped[int] = mapped_column(ForeignKey("experiments.id"), index=True)
    customer_id: Mapped[str] = mapped_column(String(200))
    arm: Mapped[str] = mapped_column(String(10))
    offer_accepted: Mapped[int | None] = mapped_column(Integer)
    churned: Mapped[int] = mapped_column(Integer)
    revenue: Mapped[float | None] = mapped_column(Float)
    complaints: Mapped[float | None] = mapped_column(Float)


class OfferEvidence(Base):
    """Measured effect of an offer from a decided experiment (feeds next best offer)."""

    __tablename__ = "offer_evidence"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    experiment_id: Mapped[int] = mapped_column(ForeignKey("experiments.id"), unique=True)
    offer: Mapped[str] = mapped_column(String(200), index=True)
    segment_description: Mapped[str | None] = mapped_column(Text)
    decision: Mapped[str] = mapped_column(String(20))
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    n_treatment: Mapped[int] = mapped_column(Integer)
    n_control: Mapped[int] = mapped_column(Integer)
    treatment_churn: Mapped[float] = mapped_column(Float)
    control_churn: Mapped[float] = mapped_column(Float)
    itt_difference: Mapped[float] = mapped_column(Float)
    ci_low: Mapped[float] = mapped_column(Float)
    ci_high: Mapped[float] = mapped_column(Float)
    acceptance_rate: Mapped[float | None] = mapped_column(Float)
    # ITT churn reduction / acceptance rate (effect per acceptor, clipped to [0, 1]).
    retention_lift_per_acceptor: Mapped[float | None] = mapped_column(Float)
