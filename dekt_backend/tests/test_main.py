from __future__ import annotations

from types import SimpleNamespace

from fastapi.testclient import TestClient

import dekt_backend.main as main_module


def test_home_requires_web_key(monkeypatch) -> None:
    monkeypatch.setenv("DEKT_BACKEND_WEB_KEY", "secret-key")

    with TestClient(main_module.app) as client:
        resp = client.get("/")

    assert resp.status_code == 401
    assert "访问受限" in resp.text


def test_login_sets_cookie_and_allows_home(monkeypatch) -> None:
    monkeypatch.setenv("DEKT_BACKEND_WEB_KEY", "secret-key")

    with TestClient(main_module.app) as client:
        bad = client.post("/auth/login", data={"key": "wrong"})
        assert bad.status_code == 401

        ok = client.post("/auth/login", data={"key": "secret-key"}, follow_redirects=False)
        assert ok.status_code == 303
        assert ok.headers.get("location") == "/"

        home = client.get("/")

    assert home.status_code == 200
    assert "DEKT 控制台" in home.text


def test_calendar_events_uses_backend_config_token(monkeypatch) -> None:
    monkeypatch.setenv("DEKT_BACKEND_WEB_KEY", "secret-key")
    monkeypatch.setattr(main_module, "CALENDAR_AVAILABLE", True)
    monkeypatch.setattr(
        main_module,
        "load_backend_config",
        lambda: SimpleNamespace(token="abc-token", tls_insecure=False),
    )

    captured: dict[str, str] = {}

    def fake_list_my_courses(token: str, limit: int, timeout: float, insecure_tls: bool):
        captured["token"] = token
        return (
            True,
            "OK",
            [
                {
                    "id": 1,
                    "title": "测试活动",
                    "activity_start_time": "2026-04-16 10:00:00",
                    "activity_end_time": "2026-04-16 11:00:00",
                    "transcript_index": {"transcript_name": "理想信念"},
                }
            ],
        )

    monkeypatch.setattr(main_module, "list_my_courses", fake_list_my_courses)

    with TestClient(main_module.app) as client:
        resp = client.post(
            "/calendar/events",
            headers={"x-dekt-key": "secret-key"},
            json={"filter_mode": "mine"},
        )

    assert resp.status_code == 200
    payload = resp.json()
    assert len(payload) == 1
    assert payload[0]["id"] == "1"
    assert captured.get("token", "").startswith("Bearer ")
