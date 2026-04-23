"""Pytest fixtures: isolated SQLite per-test-session + in-process TestClient.

Uses FastAPI's TestClient so no network server is needed; perfect for CI.
"""

from __future__ import annotations

import os
import random
import tempfile

os.environ["HEROPROTO_ENVIRONMENT"] = "test"
# Enable the mock payments processor so store tests can actually exercise purchase flow.
os.environ["HEROPROTO_MOCK_PAYMENTS_ENABLED"] = "1"

import pytest
from fastapi.testclient import TestClient

# IMPORTANT: set the DATABASE_URL *before* any app.* imports so db.engine binds correctly.
_tmp_dir = tempfile.mkdtemp(prefix="heroproto-tests-")
_db_path = os.path.join(_tmp_dir, "test.db")
os.environ["HEROPROTO_DATABASE_URL"] = f"sqlite:///{_db_path}"

from app.main import app  # noqa: E402
from app.seed import seed as run_seed  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _seed_once() -> None:
    # app.main lifespan handles migrations on startup; we just seed content once.
    # TestClient's context manager drives the lifespan.
    with TestClient(app):
        run_seed()


@pytest.fixture()
def client() -> TestClient:
    # TestClient context is already driven by the session fixture; yielding a fresh
    # one per test keeps state isolated at the HTTP layer without re-running startup.
    return TestClient(app)


@pytest.fixture()
def auth_headers(client: TestClient) -> dict[str, str]:
    email = f"pytest+{random.randint(100000, 999999)}@example.com"
    r = client.post("/auth/register", json={"email": email, "password": "hunter22"})
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}
