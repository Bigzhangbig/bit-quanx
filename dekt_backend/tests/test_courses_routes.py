from __future__ import annotations

from types import SimpleNamespace

from fastapi.testclient import TestClient

import dekt_backend.routes.courses as courses_routes
import dekt_backend.security as security
from dekt_backend.main import app
from dekt_backend.storage import BackendConfig


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


def _signed_get_headers(api_key: str, path: str, nonce: str) -> dict[str, str]:
    return security.build_signed_headers(
        api_key=api_key,
        method="GET",
        path=path,
        nonce=nonce,
    )


def test_list_my_courses_success(monkeypatch) -> None:
    api_key = "unit-test-key"
    client = _build_client(monkeypatch, api_key=api_key)

    monkeypatch.setattr(courses_routes, "load_backend_config", lambda: BackendConfig(token="Bearer abc"))
    monkeypatch.setattr(
        courses_routes,
        "list_my_courses",
        lambda token, limit, timeout, insecure_tls: (
            True,
            "OK",
            [{"id": 101, "title": "活动A"}, {"id": 102, "title": "活动B"}],
        ),
    )

    headers = _signed_get_headers(api_key, "/api/v1/courses/my", "my-list-success")
    resp = client.get("/api/v1/courses/my", headers=headers)

    assert resp.status_code == 200
    body = resp.json()
    assert body.get("ok") is True
    assert isinstance(body.get("data"), list)
    assert body.get("meta", {}).get("count") == 2


def test_list_my_courses_requires_backend_token(monkeypatch) -> None:
    api_key = "unit-test-key"
    client = _build_client(monkeypatch, api_key=api_key)

    monkeypatch.setattr(courses_routes, "load_backend_config", lambda: BackendConfig(token=""))
    headers = _signed_get_headers(api_key, "/api/v1/courses/my", "my-list-no-token")

    resp = client.get("/api/v1/courses/my", headers=headers)
    assert resp.status_code == 400
    assert resp.json().get("detail") == "backend_token_not_configured"


def test_course_detail_success(monkeypatch) -> None:
    api_key = "unit-test-key"
    client = _build_client(monkeypatch, api_key=api_key)

    monkeypatch.setattr(courses_routes, "load_backend_config", lambda: BackendConfig(token="Bearer abc"))
    monkeypatch.setattr(
        courses_routes,
        "get_course_detail",
        lambda token, course_id, timeout, insecure_tls: (True, "OK", {"id": course_id, "title": "详情活动"}),
    )

    headers = _signed_get_headers(api_key, "/api/v1/courses/123/detail", "detail-success")
    resp = client.get("/api/v1/courses/123/detail", headers=headers)

    assert resp.status_code == 200
    body = resp.json()
    assert body.get("ok") is True
    assert body.get("data", {}).get("id") == 123


def test_course_detail_failure_propagates(monkeypatch) -> None:
    api_key = "unit-test-key"
    client = _build_client(monkeypatch, api_key=api_key)

    monkeypatch.setattr(courses_routes, "load_backend_config", lambda: BackendConfig(token="Bearer abc"))
    monkeypatch.setattr(
        courses_routes,
        "get_course_detail",
        lambda token, course_id, timeout, insecure_tls: (False, "detail_failed", {}),
    )

    headers = _signed_get_headers(api_key, "/api/v1/courses/123/detail", "detail-failure")
    resp = client.get("/api/v1/courses/123/detail", headers=headers)

    assert resp.status_code == 400
    assert resp.json().get("detail") == "detail_failed"