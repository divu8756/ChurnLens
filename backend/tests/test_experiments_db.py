import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import delete, inspect, select, text, update
from sqlalchemy.exc import DatabaseError, IntegrityError

from app.config import get_settings
from app.experiments import db
from app.experiments.lifecycle import TransitionError, change_status
from app.experiments.models import AppendOnlyError, AuditLog, Base, Experiment


def _experiment(**overrides) -> Experiment:
    fields = dict(
        name="Annual contract offer", hypothesis="A discount lowers churn",
        segment_definition={"description": "Month-to-month", "filters": []},
        offer="10% off annual", outcome_window_days=90, guardrail_metrics=["complaints"],
        baseline_rate=0.4, mde=0.05, mde_type="absolute", alpha=0.05, power=0.8,
        control_share=0.5, n_required_treatment=1500, n_required_control=1500,
        created_by="tester",
    )
    fields.update(overrides)
    return Experiment(**fields)


def test_database_url_defaults_to_sqlite_in_data_dir():
    url = db.database_url()
    assert url.startswith("sqlite:///") and url.endswith("experiments.db")
    assert str(get_settings().DATA_DIR) in url


@pytest.mark.parametrize("given", ["postgres://u:p@h/db", "postgresql://u:p@h/db"])
def test_postgres_urls_use_psycopg(given, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", given)
    get_settings.cache_clear()
    assert db.database_url() == "postgresql+psycopg://u:p@h/db"


def test_migration_matches_models():
    engine = db.init_db()
    tables = set(inspect(engine).get_table_names())
    assert {"experiments", "experiment_audit_log", "alembic_version"} <= tables
    with engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    assert diff == []


def test_create_and_audit_status_changes():
    with db.session_scope() as s:
        exp = _experiment()
        s.add(exp)
        s.flush()
        assert exp.status == "draft"
        change_status(s, exp, "approved", "approver", note="cost reviewed")
        change_status(s, exp, "running", "system")
        exp_id = exp.id
    with db.session_scope() as s:
        rows = s.scalars(select(AuditLog).where(AuditLog.experiment_id == exp_id)
                         .order_by(AuditLog.id)).all()
        assert [(r.from_status, r.to_status, r.actor) for r in rows] == [
            ("draft", "approved", "approver"), ("approved", "running", "system")]
        assert s.get(Experiment, exp_id).status == "running"


@pytest.mark.parametrize("path", [["running"], ["decided"], ["approved", "draft"],
                                  ["approved", "approved"]])
def test_illegal_transitions_rejected(path):
    with db.session_scope() as s:
        exp = _experiment()
        s.add(exp)
        s.flush()
        with pytest.raises(TransitionError):
            for status in path:
                change_status(s, exp, status, "tester")


def test_audit_log_is_append_only_in_orm():
    with db.session_scope() as s:
        exp = _experiment()
        s.add(exp)
        s.flush()
        change_status(s, exp, "approved", "approver")
    with pytest.raises(AppendOnlyError), db.session_scope() as s:
        row = s.scalars(select(AuditLog)).first()
        row.note = "rewritten"
    with pytest.raises(AppendOnlyError), db.session_scope() as s:
        s.delete(s.scalars(select(AuditLog)).first())


def test_audit_log_is_append_only_in_database():
    with db.session_scope() as s:
        exp = _experiment()
        s.add(exp)
        s.flush()
        change_status(s, exp, "approved", "approver")
    for stmt in (update(AuditLog).values(note="x"), delete(AuditLog)):
        with pytest.raises(DatabaseError, match="append-only"), db.session_scope() as s:
            s.execute(stmt)
    with db.session_scope() as s:
        assert s.scalar(text("SELECT COUNT(*) FROM experiment_audit_log")) == 1


def test_status_check_constraint():
    with pytest.raises(IntegrityError), db.session_scope() as s:
        s.add(_experiment(status="launched"))
