from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import QMessageBox

from .api_client import (
    VerifyResult,
    backend_health_check,
    backend_signed_get,
    backend_signed_post,
    backend_signed_put,
)
from .worker import Worker


class BackendMixin:
    def _verify_token_backend_task(
        self: Any,
        base_url: str,
        api_key: str,
        token: str,
        insecure: bool,
    ) -> VerifyResult:
        ok, msg, data = backend_signed_post(
            base_url=base_url,
            path="/api/v1/auth/verify",
            api_key=api_key,
            body={"token": token, "use_stored": False},
            timeout=12.0,
            insecure_tls=insecure,
        )
        if not ok:
            return VerifyResult(ok=False, message=msg)

        user_id = ""
        if isinstance(data, dict):
            user_id = str(data.get("user_id") or "")
        return VerifyResult(ok=True, message="Token 有效", user_id=user_id)

    def on_backend_ping(self: Any) -> None:
        base_url = self.backend_base_url_input.text().strip()
        if not base_url:
            QMessageBox.warning(self, "提示", "后端地址为空")
            return

        self._set_status("正在检查后端健康状态...")
        worker = Worker(
            backend_health_check,
            base_url,
            8.0,
            self.tls_insecure_checkbox.isChecked(),
        )
        worker.signals.done.connect(self._on_backend_ping_done)
        self.pool.start(worker)

    def _on_backend_ping_done(self: Any, result: tuple[bool, str]) -> None:
        ok, msg = result
        if ok:
            self._set_status(f"后端可达：{msg}")
        else:
            self._set_status(f"后端不可达：{msg}")

    def on_backend_sync_token(self: Any) -> None:
        base_url = self.backend_base_url_input.text().strip()
        api_key = self.backend_api_key_input.text().strip()
        token = self.token_input.text().strip()

        if not token:
            QMessageBox.warning(self, "提示", "Token 为空")
            return

        self._set_status("正在同步 Token 到后端...")
        worker = Worker(
            backend_signed_post,
            base_url,
            "/api/v1/auth/set-token",
            api_key,
            {"token": token},
            10.0,
            self.tls_insecure_checkbox.isChecked(),
        )
        worker.signals.done.connect(self._on_backend_sync_token_done)
        self.pool.start(worker)

    def _on_backend_sync_token_done(self: Any, result: tuple[bool, str, dict[str, Any]]) -> None:
        ok, msg, _data = result
        if ok:
            self._set_status("Token 已同步到后端")
            return
        self._set_status(f"Token 同步失败：{msg}")

    def _csv_to_list(self: Any, raw: str) -> list[str]:
        out: list[str] = []
        for item in (raw or "").split(","):
            text = item.strip()
            if not text:
                continue
            if text not in out:
                out.append(text)
        return out

    def on_backend_push_config(self: Any) -> None:
        base_url = self.backend_base_url_input.text().strip()
        api_key = self.backend_api_key_input.text().strip()

        payload = {
            "whitelist_category_ids": self._csv_to_int_list(self.whitelist_category_ids_input.text()),
            "whitelist_grade": self._csv_to_list(self.whitelist_grade_input.text()),
            "whitelist_academy": self._csv_to_list(self.whitelist_academy_input.text()),
            "tls_insecure": self.tls_insecure_checkbox.isChecked(),
        }

        self._set_status("正在同步白名单配置到后端...")
        worker = Worker(
            backend_signed_put,
            base_url,
            "/api/v1/config",
            api_key,
            payload,
            10.0,
            self.tls_insecure_checkbox.isChecked(),
        )
        worker.signals.done.connect(self._on_backend_push_config_done)
        self.pool.start(worker)

    def _on_backend_push_config_done(self: Any, result: tuple[bool, str, dict[str, Any]]) -> None:
        ok, msg, _data = result
        if ok:
            self._set_status("后端白名单配置已同步")
            return
        self._set_status(f"同步后端配置失败：{msg}")

    def on_backend_pull_config(self: Any) -> None:
        base_url = self.backend_base_url_input.text().strip()
        api_key = self.backend_api_key_input.text().strip()
        self._set_status("正在从后端加载白名单配置...")
        worker = Worker(
            backend_signed_get,
            base_url,
            "/api/v1/config",
            api_key,
            10.0,
            self.tls_insecure_checkbox.isChecked(),
        )
        worker.signals.done.connect(self._on_backend_pull_config_done)
        self.pool.start(worker)

    def _on_backend_pull_config_done(self: Any, result: tuple[bool, str, dict[str, Any]]) -> None:
        ok, msg, data = result
        if not ok:
            self._set_status(f"加载后端配置失败：{msg}")
            return

        cfg_data = data.get("data") if isinstance(data, dict) else None
        if not isinstance(cfg_data, dict):
            self._set_status("后端配置载荷无效")
            return

        categories = cfg_data.get("whitelist_category_ids")
        grades = cfg_data.get("whitelist_grade")
        academy = cfg_data.get("whitelist_academy")

        if isinstance(categories, list):
            self.whitelist_category_ids_input.setText(",".join(str(int(x)) for x in categories if str(x).strip()))
        if isinstance(grades, list):
            self.whitelist_grade_input.setText(",".join(str(x).strip() for x in grades if str(x).strip()))
        if isinstance(academy, list):
            self.whitelist_academy_input.setText(",".join(str(x).strip() for x in academy if str(x).strip()))

        self._set_status("后端白名单配置已加载")
