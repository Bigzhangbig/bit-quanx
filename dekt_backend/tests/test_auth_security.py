from __future__ import annotations

from types import SimpleNamespace
import time

from fastapi.testclient import TestClient

import dekt_backend.security as security
from dekt_backend.main import app


def _build_client(monkeypatch, api_key: str = "unit-test-key") -> TestClient:
    monkeypatch.setattr(
        security,
        "settings",
        SimpleNamespace(
            api_key=api_key,
            request_ttl_seconds=300,
            nonce_ttl_seconds=600,
        ),
    )
    security._NONCE_CACHE.clear()
    return TestClient(app)


def test_missing_auth_headers_rejected(monkeypatch) -> None:
    client = _build_client(monkeypatch)
    resp = client.get("/api/v1/config")
    assert resp.status_code == 401
    assert resp.json().get("error") == "missing_auth_headers"


def test_replay_request_rejected(monkeypatch) -> None:
    api_key = "unit-test-key"
    client = _build_client(monkeypatch, api_key=api_key)
    headers = security.build_signed_headers(
        api_key=api_key,
        method="GET",
        path="/api/v1/config",
        nonce="replay-nonce",
    )

    first = client.get("/api/v1/config", headers=headers)
    assert first.status_code == 200

    second = client.get("/api/v1/config", headers=headers)
    assert second.status_code == 401
    assert second.json().get("error") == "replay_detected"


def test_expired_timestamp_rejected(monkeypatch) -> None:
    api_key = "unit-test-key"
    client = _build_client(monkeypatch, api_key=api_key)
    expired_ts = int(time.time()) - 3600
    headers = security.build_signed_headers(
        api_key=api_key,
        method="GET",
        path="/api/v1/config",
        now_ts=expired_ts,
        nonce="expired-nonce",
    )

    resp = client.get("/api/v1/config", headers=headers)
    assert resp.status_code == 401
    assert resp.json().get("error") == "timestamp_expired"


def test_invalid_signature_rejected(monkeypatch) -> None:
    api_key = "unit-test-key"
    client = _build_client(monkeypatch, api_key=api_key)
    headers = security.build_signed_headers(
        api_key=api_key,
        method="GET",
        path="/api/v1/config",
        nonce="bad-signature-nonce",
    )
    headers["X-Signature"] = "0" * 64

    resp = client.get("/api/v1/config", headers=headers)
    assert resp.status_code == 401
    assert resp.json().get("error") == "invalid_signature"
