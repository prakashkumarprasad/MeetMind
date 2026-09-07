# Pytest fixtures (in-memory DB, Redis, S3, auth helpers) shared across the test suite.

"""
Test infrastructure. Key points, since this stuff is non-obvious:

1. Settings() runs at import time (app/core/config.py does
   `settings = get_settings()` at module load). So every required env
   var — including DATABASE_URL pointing at the Docker test DB — must
   be set BEFORE anything under `app` gets imported. That's why the
   os.environ assignments below come first, ahead of the `from app...`
   imports, with a `noqa: E402` on each import to silence the linter
   complaint about imports-not-at-top-of-file (justified here).

2. Each test runs inside a transaction that's rolled back afterward, so
   tests never leak data into each other and we don't need to drop/
   recreate tables between tests. But your endpoints call db.commit()
   internally (see chat.py), which would normally end our test
   transaction early. The nested SAVEPOINT + event-listener pattern
   below is SQLAlchemy's own documented recipe for this exact problem —
   not something improvised. See:
   https://docs.sqlalchemy.org/en/20/orm/session_transaction.html#joining-a-session-into-an-external-transaction-such-as-for-test-suites

3. generate_chat_completion is patched at its USAGE site
   (app.api.v1.chat.generate_chat_completion), not its definition
   (app.services.llm.generate_chat_completion). chat.py does
   `from app.services.llm import generate_chat_completion`, which binds
   a local name in chat.py's own namespace — patching the original
   module doesn't touch that already-bound reference.
"""
import os
import subprocess
import sys
from pathlib import Path

import pytest
import redis
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

TEST_DB_URL = "postgresql+psycopg://postgres:postgres@localhost:5433/meetmind_test"
TEST_REDIS_URL = "redis://localhost:6380/0"

os.environ["DATABASE_URL"] = TEST_DB_URL
os.environ["REDIS_URL"] = TEST_REDIS_URL
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-not-for-production-use")
os.environ.setdefault("GOOGLE_CLIENT_ID", "test-google-client-id")
os.environ.setdefault("GOOGLE_CLIENT_SECRET", "test-google-client-secret")
os.environ.setdefault("S3_BUCKET_NAME", "test-bucket")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "test-access-key")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "test-secret-key")
os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("REFRESH_REUSE_GRACE_SECONDS", "0")
os.environ.setdefault("LLM_PROVIDER", "groq")
os.environ.setdefault("LLM_API_KEY", "test-llm-key-unused-since-mocked")

_test_redis_client = redis.from_url(TEST_REDIS_URL, decode_responses=True)

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.db.session import get_db  # noqa: E402
from app.core.security import create_access_token  # noqa: E402
from app.models.user import User  # noqa: E402
from app.models.workspace import Workspace, WorkspaceMember  # noqa: E402

@pytest.fixture(scope="session", autouse=True)
def _run_migrations():
    """Runs Alembic migrations against the Docker test DB once per test session.

    Requires `docker compose -f docker-compose.test.yml up -d` to already
    be running — this fixture does not start Docker for you.
    """
    backend_dir = Path(__file__).resolve().parent.parent
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=backend_dir,
        check=True,
        env=os.environ,
    )
    yield

@pytest.fixture(scope="session")
def test_engine(_run_migrations):
    engine = create_engine(TEST_DB_URL)
    yield engine
    engine.dispose()

@pytest.fixture()
def db_session(test_engine):
    connection = test_engine.connect()
    outer_transaction = connection.begin()
    SessionLocal = sessionmaker(bind=connection, autocommit=False, autoflush=False)
    session = SessionLocal()

    nested = connection.begin_nested()

    @event.listens_for(session, "after_transaction_end")
    def _restart_savepoint(sess, trans):
        nonlocal nested
        if not nested.is_active:
            nested = connection.begin_nested()

    yield session

    session.close()
    outer_transaction.rollback()
    connection.close()

@pytest.fixture()
def client(db_session):
    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()

@pytest.fixture(autouse=True)
def _clear_rate_limits():
    """Clear all rate limit keys before each test to avoid cross-test interference."""
    keys = _test_redis_client.keys("ratelimit:*")
    if keys:
        _test_redis_client.delete(*keys)
    yield

@pytest.fixture(autouse=True)
def _mock_llm(monkeypatch):
    """
    Prevents every chat test from making a real Groq API call.
    Patched at the usage site — see module docstring point 3.
    """
    monkeypatch.setattr(
        "app.api.v1.chat.generate_chat_completion",
        lambda messages: "mocked answer",
    )

@pytest.fixture(autouse=True)
def _mock_s3_delete(monkeypatch):
    """
    delete_object makes a real network call to S3, unlike the presigned-URL
    helpers (which only build URLs locally). Mock it at its usage site so the
    meeting-delete endpoints don't try to reach real AWS during tests.
    """
    monkeypatch.setattr("app.api.v1.meetings.delete_object", lambda storage_key: None)

@pytest.fixture()
def make_user(db_session):
    """Factory fixture: creates a user + personal workspace, returns (user, workspace, headers)."""

    def _make(email="test@example.com"):
        user = User(email=email, hashed_password=None, full_name="Test User")
        db_session.add(user)
        db_session.flush()

        workspace = Workspace(name=f"{email}'s workspace")
        db_session.add(workspace)
        db_session.flush()

        membership = WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role="owner")
        db_session.add(membership)
        db_session.flush()

        token = create_access_token(str(user.id))
        headers = {"Authorization": f"Bearer {token}"}

        return user, workspace, headers

    return _make
