"""Tests for device-token registration/unregister endpoints (Phase 4.1)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.db import get_db
from app.models import DeviceToken
from sqlalchemy import select


@pytest.fixture()
def client():
    return TestClient(app)


def _register(client, email="push_user@example.com", password="Pass1234!"):
    client.post("/auth/register", json={"email": email, "password": password})
    r = client.post("/auth/login", json={"email": email, "password": password})
    return r.json()["access_token"]


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_register_device_token(client):
    jwt = _register(client, "pt1@example.com")
    r = client.post(
        "/notifications/device-token",
        json={"token": "fcm-test-token-abc", "platform": "fcm"},
        headers=auth(jwt),
    )
    assert r.status_code == 204


def test_register_device_token_idempotent(client):
    jwt = _register(client, "pt2@example.com")
    payload = {"token": "fcm-token-idempotent", "platform": "fcm"}
    r1 = client.post("/notifications/device-token", json=payload, headers=auth(jwt))
    r2 = client.post("/notifications/device-token", json=payload, headers=auth(jwt))
    assert r1.status_code == 204
    assert r2.status_code == 204


def test_register_apns_token(client):
    jwt = _register(client, "pt3@example.com")
    r = client.post(
        "/notifications/device-token",
        json={"token": "apns-device-token-xyz", "platform": "apns"},
        headers=auth(jwt),
    )
    assert r.status_code == 204


def test_invalid_platform_rejected(client):
    jwt = _register(client, "pt4@example.com")
    r = client.post(
        "/notifications/device-token",
        json={"token": "some-token", "platform": "webpush"},
        headers=auth(jwt),
    )
    assert r.status_code == 400


def test_empty_token_rejected(client):
    jwt = _register(client, "pt5@example.com")
    r = client.post(
        "/notifications/device-token",
        json={"token": "   ", "platform": "fcm"},
        headers=auth(jwt),
    )
    assert r.status_code == 400


def test_unregister_device_token(client):
    jwt = _register(client, "pt6@example.com")
    token_val = "fcm-token-to-delete"
    client.post(
        "/notifications/device-token",
        json={"token": token_val, "platform": "fcm"},
        headers=auth(jwt),
    )
    r = client.request(
        "DELETE",
        "/notifications/device-token",
        json={"token": token_val, "platform": "fcm"},
        headers=auth(jwt),
    )
    assert r.status_code == 204


def test_unregister_nonexistent_is_noop(client):
    jwt = _register(client, "pt7@example.com")
    r = client.request(
        "DELETE",
        "/notifications/device-token",
        json={"token": "does-not-exist", "platform": "fcm"},
        headers=auth(jwt),
    )
    assert r.status_code == 204


def test_requires_auth(client):
    r = client.post(
        "/notifications/device-token",
        json={"token": "tok", "platform": "fcm"},
    )
    assert r.status_code == 401
