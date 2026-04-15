from __future__ import annotations

from types import SimpleNamespace

import dekt_backend.runtime as runtime_module


def test_runtime_run_once_collects_started_unstarted_and_my_courses(monkeypatch) -> None:
    monkeypatch.setattr(runtime_module, "load_backend_config", lambda: SimpleNamespace(
        token="Bearer abc",
        tls_insecure=False,
        whitelist_category_ids=[1, 2],
        whitelist_grade=[],
        whitelist_academy=[],
    ))

    def fake_list_courses(token, sign_status, transcript_index_id, limit, timeout, insecure_tls):
        return True, "OK", [{"id": sign_status * 100 + transcript_index_id, "title": "活动"}]

    monkeypatch.setattr(runtime_module, "list_courses", fake_list_courses)
    monkeypatch.setattr(runtime_module, "list_my_courses", lambda token, limit, timeout, insecure_tls: (True, "OK", [{"id": 1}, {"id": 2}]))
    monkeypatch.setattr(
        runtime_module,
        "settings",
        SimpleNamespace(
            runtime_enabled=False,
            runtime_interval_seconds=300,
            runtime_initial_delay_seconds=0,
            runtime_fetch_delay_max_seconds=0,
        ),
    )

    result = runtime_module.runtime.run_once()

    assert result.get("ok") is True
    assert result.get("started_count") == 2
    assert result.get("unstarted_count") == 2
    assert result.get("my_courses_count") == 2