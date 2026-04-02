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


def _signed_post_headers(api_key: str, path: str, nonce: str, body: dict | None = None) -> dict[str, str]:
    return security.build_signed_headers(
        api_key=api_key,
        method="POST",
        path=path,
        nonce=nonce,
        body=body,
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


def test_started_and_unstarted_list_endpoints(monkeypatch) -> None:
    api_key = "unit-test-key"
    client = _build_client(monkeypatch, api_key=api_key)

    monkeypatch.setattr(courses_routes, "load_backend_config", lambda: BackendConfig(token="Bearer abc"))

    def fake_list_courses(token, sign_status, transcript_index_id, limit, timeout, insecure_tls):
        return True, "OK", [{"id": sign_status * 100 + transcript_index_id, "title": f"课程-{sign_status}-{transcript_index_id}"}]

    monkeypatch.setattr(courses_routes, "list_courses", fake_list_courses)

    started_headers = _signed_get_headers(api_key, "/api/v1/courses/started", "started-list")
    started_resp = client.get("/api/v1/courses/started", headers=started_headers)
    assert started_resp.status_code == 200
    assert started_resp.json().get("meta", {}).get("sign_status") == 2

    unstarted_headers = _signed_get_headers(api_key, "/api/v1/courses/unstarted", "unstarted-list")
    unstarted_resp = client.get("/api/v1/courses/unstarted", headers=unstarted_headers)
    assert unstarted_resp.status_code == 200
    assert unstarted_resp.json().get("meta", {}).get("sign_status") == 1


def test_course_qrcode_endpoint(monkeypatch) -> None:
    api_key = "unit-test-key"
    client = _build_client(monkeypatch, api_key=api_key)

    headers = _signed_get_headers(api_key, "/api/v1/courses/123/qrcode", "qrcode-success")
    resp = client.get("/api/v1/courses/123/qrcode", headers=headers)

    assert resp.status_code == 200
    body = resp.json()
    assert body.get("ok") is True
    assert body.get("data", {}).get("course_id") == 123
    assert str(body.get("data", {}).get("qrcode_url", "")).endswith("course_id=123")


def test_sign_in_and_sign_out_endpoints(monkeypatch) -> None:
    api_key = "unit-test-key"
    client = _build_client(monkeypatch, api_key=api_key)

    monkeypatch.setattr(courses_routes, "load_backend_config", lambda: BackendConfig(token="Bearer abc"))
    monkeypatch.setattr(courses_routes, "submit_sign_action", lambda token, course_id, address, latitude, longitude, timeout, insecure_tls: (True, f"sign-{course_id}"))

    sign_in_payload = {"address": "A", "latitude": 1.0, "longitude": 2.0}
    sign_in_headers = _signed_post_headers(api_key, "/api/v1/courses/321/sign-in", "sign-in-success", sign_in_payload)
    sign_in_resp = client.post("/api/v1/courses/321/sign-in", headers=sign_in_headers, json=sign_in_payload)
    assert sign_in_resp.status_code == 200
    assert sign_in_resp.json().get("message") == "sign-321"

    sign_out_headers = _signed_post_headers(api_key, "/api/v1/courses/321/sign-out", "sign-out-success", sign_in_payload)
    sign_out_resp = client.post("/api/v1/courses/321/sign-out", headers=sign_out_headers, json=sign_in_payload)
    assert sign_out_resp.status_code == 200
    assert sign_out_resp.json().get("message") == "sign-321"


def test_cancel_and_checkin_endpoints(monkeypatch) -> None:
    api_key = "unit-test-key"
    client = _build_client(monkeypatch, api_key=api_key)

    monkeypatch.setattr(courses_routes, "load_backend_config", lambda: BackendConfig(token="Bearer abc"))
    monkeypatch.setattr(courses_routes, "get_user_id", lambda token, timeout, insecure_tls: (True, "88", "OK"))
    monkeypatch.setattr(courses_routes, "cancel_course", lambda token, course_id, user_id, timeout, insecure_tls: (True, f"cancel-{course_id}-{user_id}"))
    monkeypatch.setattr(courses_routes, "get_checkin_info", lambda token, course_id, timeout, insecure_tls: (True, "OK", {"course_id": course_id}))

    cancel_headers = _signed_post_headers(api_key, "/api/v1/courses/456/cancel", "cancel-success")
    cancel_resp = client.post("/api/v1/courses/456/cancel", headers=cancel_headers)
    assert cancel_resp.status_code == 200
    assert cancel_resp.json().get("message") == "cancel-456-88"

    checkin_headers = _signed_get_headers(api_key, "/api/v1/courses/456/checkin-info", "checkin-success")
    checkin_resp = client.get("/api/v1/courses/456/checkin-info", headers=checkin_headers)
    assert checkin_resp.status_code == 200
    assert checkin_resp.json().get("data", {}).get("course_id") == 456