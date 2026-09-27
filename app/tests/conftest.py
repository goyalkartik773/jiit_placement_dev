"""Shared fixtures.

Tests run against a dedicated ``app_test`` schema **inside the same**
``jiit_placement`` database (spec: one central PostgreSQL).  The engine URL
carries ``options=-c search_path=app_test`` so every unqualified statement -
including FastAPI's own sessions - resolves to the test schema, while golden
seeding reads the live corpus from ``public.`` (read-only, fully qualified).

Per-test isolation: every table in ``Base.metadata`` is truncated before
each test (autouse), and each test gets a fresh app instance, so job/status
state never leaks between tests.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
for _path in (REPO_ROOT, Path(__file__).parent):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

TEST_SCHEMA = "app_test"


@pytest.fixture(scope="session")
def db_engine():
    from sqlalchemy import create_engine, text

    from app import db as app_db
    from app.config import load_settings
    from app.models import Base

    settings = load_settings()
    admin = create_engine(
        settings.database_url, isolation_level="AUTOCOMMIT", future=True
    )
    with admin.connect() as conn:
        conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {TEST_SCHEMA}"))
    admin.dispose()

    url = f"{settings.database_url}?options=-c%20search_path%3D{TEST_SCHEMA}"
    engine = create_engine(url, future=True)
    Base.metadata.create_all(engine)
    app_db.configure(url)
    yield engine
    app_db.configure(None)
    engine.dispose()


@pytest.fixture(autouse=True)
def clean_tables(db_engine):
    from sqlalchemy import text

    from app.models import Base

    names = ", ".join(f'"{t.name}"' for t in Base.metadata.sorted_tables)
    with db_engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {names}"))
    yield


@pytest.fixture()
def session(db_engine):
    from app.db import get_session_factory

    value = get_session_factory()()
    yield value
    value.close()


@pytest.fixture()
def app(db_engine):
    from app.main import create_app

    application = create_app()
    yield application


@pytest.fixture()
def client(app):
    from fastapi.testclient import TestClient

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def fake_gmail(app):
    """Install a FakeGmailClient on the app's container; returns it."""

    def _install(client_obj):
        app.state.container.set_client_factory(lambda: client_obj)
        return client_obj

    yield _install


@pytest.fixture()
def insert_email(session):
    """Insert one raw PENDING email row directly (bypasses sync on purpose)."""
    from app.models import Email, EmailStatus

    def _insert(**overrides):
        values = {
            "gmail_message_id": "gm-test-0001",
            "thread_id": "thread-0001",
            "source_group": "jiitengg2027",
            "source_group_email": "jiitengg2027@googlegroups.com",
            "sender": "Training and Placement Cell",
            "sender_email": "tpc@example.com",
            "subject": "Test subject",
            "body_text": "Test body",
            "processing_status": EmailStatus.PENDING,
        }
        values.update(overrides)
        row = Email(**values)
        session.add(row)
        session.commit()
        return row

    return _insert
