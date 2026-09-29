"""A/B experiments (Phase 5c): designs, approval gate, assignment, results, decisions.

Stored in a database (SQLite at DATA_DIR/experiments.db, Postgres when DATABASE_URL
is set), not in session folders, because experiments outlive the 24-hour sessions.
"""
