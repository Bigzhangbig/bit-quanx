from __future__ import annotations

import random
import threading
import time
from dataclasses import dataclass, field
from typing import Any

from dekt_gui.api_client import get_qrcode_url, list_courses, list_my_courses

from .settings import settings
from .storage import load_backend_config

_CATEGORY_IDS = [1, 2, 3, 4, 5, 6]


@dataclass
class RuntimeSnapshot:
    enabled: bool = False
    running: bool = False
    last_started_at: float | None = None
    last_finished_at: float | None = None
    last_duration_seconds: float | None = None
    last_error: str = ""
    last_run_summary: dict[str, Any] = field(default_factory=dict)


class BackendRuntime:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._snapshot = RuntimeSnapshot(enabled=settings.runtime_enabled)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "enabled": self._snapshot.enabled,
                "running": self._snapshot.running,
                "last_started_at": self._snapshot.last_started_at,
                "last_finished_at": self._snapshot.last_finished_at,
                "last_duration_seconds": self._snapshot.last_duration_seconds,
                "last_error": self._snapshot.last_error,
                "last_run_summary": dict(self._snapshot.last_run_summary),
            }

    def start(self) -> None:
        if not settings.runtime_enabled:
            return

        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._run_loop, name="dekt-backend-runtime", daemon=True)
            self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        with self._lock:
            thread = self._thread
        if thread and thread.is_alive():
            thread.join(timeout=2.0)

    def run_once(self) -> dict[str, Any]:
        started_at = time.time()
        with self._lock:
            self._snapshot.running = True
            self._snapshot.last_started_at = started_at
            self._snapshot.last_error = ""

        try:
            summary = self._collect_summary()
            finished_at = time.time()
            with self._lock:
                self._snapshot.running = False
                self._snapshot.last_finished_at = finished_at
                self._snapshot.last_duration_seconds = round(finished_at - started_at, 3)
                self._snapshot.last_run_summary = summary
            return summary
        except Exception as exc:  # noqa: BLE001
            finished_at = time.time()
            with self._lock:
                self._snapshot.running = False
                self._snapshot.last_finished_at = finished_at
                self._snapshot.last_duration_seconds = round(finished_at - started_at, 3)
                self._snapshot.last_error = str(exc)
            return {"ok": False, "error": str(exc)}

    def _run_loop(self) -> None:
        if settings.runtime_initial_delay_seconds > 0:
            if self._wait_with_stop(self._random_delay(settings.runtime_initial_delay_seconds)):
                return

        while not self._stop_event.is_set():
            self.run_once()
            wait_seconds = max(1.0, float(settings.runtime_interval_seconds))
            if self._wait_with_stop(self._random_delay(wait_seconds)):
                break

    def _wait_with_stop(self, seconds: float) -> bool:
        return self._stop_event.wait(max(0.0, seconds))

    def _random_delay(self, upper_bound: float) -> float:
        if upper_bound <= 0:
            return 0.0
        return random.uniform(0.0, upper_bound)

    def _collect_summary(self) -> dict[str, Any]:
        cfg = load_backend_config()
        if not cfg.token:
            return {"ok": False, "error": "backend_token_not_configured"}

        requested_ids = list(_CATEGORY_IDS)
        if cfg.whitelist_category_ids:
            allowed = {int(item) for item in cfg.whitelist_category_ids}
            requested_ids = [cid for cid in requested_ids if cid in allowed]

        started_items: list[dict[str, Any]] = []
        unstarted_items: list[dict[str, Any]] = []
        errors: list[dict[str, Any]] = []

        for sign_status, target_bucket in ((2, started_items), (1, unstarted_items)):
            for category_id in requested_ids:
                ok, msg, items = list_courses(
                    token=cfg.token,
                    sign_status=sign_status,
                    transcript_index_id=category_id,
                    limit=20,
                    timeout=15.0,
                    insecure_tls=cfg.tls_insecure,
                )
                if not ok:
                    errors.append({"category_id": category_id, "sign_status": sign_status, "message": msg})
                else:
                    for course in items:
                        raw_id = course.get("id") or course.get("course_id") or 0
                        target_bucket.append({
                            "course": course,
                            "qrcode_url": get_qrcode_url(int(raw_id)),
                        })

                if settings.runtime_fetch_delay_max_seconds > 0:
                    time.sleep(self._random_delay(settings.runtime_fetch_delay_max_seconds))

        ok_my, my_msg, my_courses = list_my_courses(
            token=cfg.token,
            limit=200,
            timeout=15.0,
            insecure_tls=cfg.tls_insecure,
        )
        if not ok_my:
            errors.append({"scope": "my_courses", "message": my_msg})

        return {
            "ok": True,
            "started_count": len(started_items),
            "unstarted_count": len(unstarted_items),
            "my_courses_count": len(my_courses),
            "started_items": started_items,
            "unstarted_items": unstarted_items,
            "my_courses": my_courses,
            "errors": errors,
        }


runtime = BackendRuntime()
