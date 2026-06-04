"""Mixin class providing monitoring, context menu, course detail, and batch query functionality.

This module extracts monitor-related methods from MainWindow to keep the main
window file manageable.  All methods reference ``self`` attributes that live on
the host class (MainWindow), so the type of *self* is annotated as ``Any``.
"""

from __future__ import annotations

import re
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QMenu,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QTableWidget,
    QTableWidgetItem,
    QTextBrowser,
    QVBoxLayout,
)

from .api_client import (
    DEFAULT_TEMPLATE_ID,
    apply_course,
    cancel_course,
    get_course_detail,
    get_user_id,
    list_courses,
    list_my_course_ids,
)
from .constants import CATEGORIES, STATUS_MAP
from .worker import Worker


class MonitorMixin:
    """Mixin that adds monitoring, context-menu actions, course-detail loading,
    checkin-location extraction, and batch-monitoring logic to MainWindow."""

    # ------------------------------------------------------------------
    # Context menu methods
    # ------------------------------------------------------------------

    def _show_monitor_context_menu(self: Any, table: QTableWidget, pos) -> None:
        row = table.rowAt(pos.y())
        if row < 0:
            return

        course_item = table.item(row, 0)
        if course_item is None:
            return

        menu = QMenu(table)
        signup_action = menu.addAction("报名")
        cancel_action = menu.addAction("取消报名")
        menu.addSeparator()
        qrcode_action = menu.addAction("查看二维码")

        selected = menu.exec(table.viewport().mapToGlobal(pos))
        if selected is signup_action:
            self._run_monitor_course_action("signup", course_item.text().strip())
        elif selected is cancel_action:
            self._run_monitor_course_action("cancel", course_item.text().strip())
        elif selected is qrcode_action:
            self._show_qrcode_dialog(table, row)

    def _show_sign_context_menu(self: Any, table: QTableWidget, pos) -> None:
        row = table.rowAt(pos.y())
        if row < 0:
            return

        course_item = table.item(row, 0)
        if course_item is None:
            return

        menu = QMenu(table)
        qrcode_action = menu.addAction("查看二维码")

        selected = menu.exec(table.viewport().mapToGlobal(pos))
        if selected is qrcode_action:
            self._show_qrcode_dialog(table, row)

    def _show_activities_context_menu(self: Any, table: QTableWidget, pos) -> None:
        row = table.rowAt(pos.y())
        if row < 0:
            return

        course_item = table.item(row, 0)
        if course_item is None:
            return

        menu = QMenu(table)
        cancel_action = menu.addAction("取消报名")
        menu.addSeparator()
        qrcode_action = menu.addAction("查看二维码")

        selected = menu.exec(table.viewport().mapToGlobal(pos))
        if selected is cancel_action:
            self._run_activities_course_action("cancel", course_item.text().strip())
        elif selected is qrcode_action:
            self._show_qrcode_dialog(table, row)

    # ------------------------------------------------------------------
    # Monitor actions
    # ------------------------------------------------------------------

    def _run_activities_course_action(self: Any, action: str, course_id_text: str) -> None:
        token = self.token_input.text().strip()
        if not token:
            QMessageBox.warning(self, "提示", "Token 为空")
            return

        if not course_id_text.isdigit():
            QMessageBox.warning(self, "提示", f"无效课程 ID: {course_id_text}")
            return

        course_id = int(course_id_text)
        insecure = self.tls_insecure_checkbox.isChecked()
        self._set_status(f"正在执行 {action}（课程 {course_id}）...")

        worker = Worker(self._monitor_course_action_task, token, action, course_id, insecure)
        worker.signals.done.connect(self._on_activities_course_action_done)
        self.pool.start(worker)

    def _on_activities_course_action_done(self: Any, result: tuple[bool, str]) -> None:
        ok, msg = result
        self._set_status(msg)
        if ok:
            self.on_activities_refresh(silent_if_no_token=True)

    def _run_monitor_course_action(self: Any, action: str, course_id_text: str) -> None:
        token = self.token_input.text().strip()
        if not token:
            QMessageBox.warning(self, "提示", "Token 为空")
            return

        if not course_id_text.isdigit():
            QMessageBox.warning(self, "提示", f"无效课程 ID: {course_id_text}")
            return

        course_id = int(course_id_text)
        insecure = self.tls_insecure_checkbox.isChecked()
        self._set_status(f"正在执行 {action}（课程 {course_id}）...")

        worker = Worker(self._monitor_course_action_task, token, action, course_id, insecure)
        worker.signals.done.connect(self._on_monitor_course_action_done)
        self.pool.start(worker)

    def _monitor_course_action_task(
        self: Any,
        token: str,
        action: str,
        course_id: int,
        insecure: bool,
    ) -> tuple[bool, str]:
        ok, msg, enrolled_ids = list_my_course_ids(
            token=token,
            limit=300,
            timeout=12.0,
            insecure_tls=insecure,
        )
        if not ok:
            return False, f"预检查失败: {msg}"

        is_enrolled = course_id in enrolled_ids

        if action == "signup":
            if is_enrolled:
                return False, f"课程 {course_id} 已报名"
            ok_apply, apply_msg = apply_course(
                token=token,
                course_id=course_id,
                template_id=DEFAULT_TEMPLATE_ID,
                timeout=12.0,
                insecure_tls=insecure,
            )
            return ok_apply, f"报名课程 {course_id}: {apply_msg}"

        if action == "cancel":
            if not is_enrolled:
                return False, f"课程 {course_id} 未报名"

            ok_uid, user_id, uid_msg = get_user_id(
                token=token,
                timeout=12.0,
                insecure_tls=insecure,
            )
            if not ok_uid:
                return False, f"获取 user_id 失败：{uid_msg}"

            ok_cancel, cancel_msg = cancel_course(
                token=token,
                course_id=course_id,
                user_id=int(user_id),
                timeout=12.0,
                insecure_tls=insecure,
            )
            return ok_cancel, f"取消报名课程 {course_id}: {cancel_msg}"

        return False, f"未知操作: {action}"

    def _on_monitor_course_action_done(self: Any, result: tuple[bool, str]) -> None:
        ok, msg = result
        if ok:
            self._set_status(msg)
            self.on_monitor_once(silent_if_no_token=True)
        else:
            self._set_status(msg)

    # ------------------------------------------------------------------
    # Course detail loading
    # ------------------------------------------------------------------

    def _load_course_detail(
        self: Any,
        token: str,
        course_id: int,
        fallback_obj: dict[str, Any],
        insecure: bool,
    ) -> tuple[bool, str, dict[str, Any]]:
        ok, msg, detail = get_course_detail(
            token=token,
            course_id=course_id,
            timeout=12.0,
            insecure_tls=insecure,
        )
        merged = dict(fallback_obj)
        if isinstance(detail, dict):
            merged.update(detail)
            # 某些接口会把核心字段包在 data.course / data.info / data.item 中。
            for nested_key in ["course", "info", "item"]:
                nested_obj = detail.get(nested_key)
                if isinstance(nested_obj, dict):
                    merged.update(nested_obj)

        # 详情接口常不返回 is_sign，补一次"我的活动"预检查，避免报名状态显示未知。
        if "__enrolled" not in merged:
            ok_ids, _ids_msg, enrolled_ids = list_my_course_ids(
                token=token,
                limit=300,
                timeout=12.0,
                insecure_tls=insecure,
            )
            if ok_ids:
                merged["__enrolled"] = course_id in enrolled_ids

        # 仅在点进课程详情时预加载该课程封面，避免列表页并发抢网络。
        cover_url = self._normalize_media_url(self._cover_url(merged))
        if cover_url and cover_url not in self._image_bytes_cache:
            _u, content = self._download_image_bytes_task(cover_url, insecure, 10.0)
            self._image_bytes_cache[cover_url] = content

        return ok, msg, merged

    def _on_course_detail_loaded(self: Any, result: tuple[bool, str, dict[str, Any]]) -> None:
        ok, msg, course_obj = result
        if not ok:
            self._set_status(f"课程详情回退: {msg}")
        else:
            self._set_status("课程详情加载完成")

        if not isinstance(course_obj, dict) or not course_obj:
            QMessageBox.information(self, "课程详情", "未找到课程详情数据")
            return

        self._show_course_detail_dialog(course_obj)

    def _show_course_detail_dialog(self: Any, course_obj: dict[str, Any]) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle(f"课程详情 - {course_obj.get('id', '')}")
        dialog.resize(760, 520)

        body = QTextBrowser(dialog)
        body.setReadOnly(True)
        body.setOpenExternalLinks(False)
        body.setHtml(self._format_course_detail_html(course_obj))

        map_name, map_lat, map_lon, map_radius_m = self._extract_checkin_location(course_obj)
        show_map_btn = QPushButton("显示地图", dialog)
        show_map_btn.setEnabled(map_lat is not None and map_lon is not None)
        show_map_btn.clicked.connect(
            lambda: self._show_map_preview_dialog(
                map_name or "打卡地点",
                map_lat,
                map_lon,
                map_radius_m,
                self.tls_insecure_checkbox.isChecked(),
            )
        )

        close_btn = QPushButton("关闭", dialog)
        close_btn.clicked.connect(dialog.accept)

        btn_row = QHBoxLayout()
        btn_row.addWidget(show_map_btn)
        btn_row.addStretch(1)
        btn_row.addWidget(close_btn)

        layout = QVBoxLayout(dialog)
        layout.addWidget(body, 1)
        layout.addLayout(btn_row)
        dialog.exec()

    # ------------------------------------------------------------------
    # Checkin location extraction
    # ------------------------------------------------------------------

    def _extract_checkin_location(self: Any, course_obj: dict[str, Any]) -> tuple[str, float | None, float | None, float | None]:
        sign_addr = course_obj.get("sign_in_address")
        if isinstance(sign_addr, list) and sign_addr and isinstance(sign_addr[0], dict):
            first = sign_addr[0]
            name = str(first.get("address") or "").strip()
            radius = self._extract_checkin_radius(first, course_obj)
            raw_lat = first.get("latitude")
            raw_lon = first.get("longitude")
            try:
                if raw_lat is None or raw_lon is None:
                    return name, None, None, radius
                lat = float(raw_lat)
                lon = float(raw_lon)
                return name, lat, lon, radius
            except (TypeError, ValueError):
                return name, None, None, radius

        place = self._first_non_empty(course_obj, ["sign_place", "checkin_location", "place", "location"])
        radius = self._extract_checkin_radius(course_obj, course_obj)
        return place, None, None, radius

    def _extract_checkin_radius(self: Any, source_obj: dict[str, Any], fallback_obj: dict[str, Any]) -> float | None:
        keys = [
            "radius",
            "distance",
            "range",
            "checkin_radius",
            "checkin_distance",
            "sign_radius",
            "sign_distance",
        ]

        def parse_radius(raw: Any) -> float | None:
            if raw is None:
                return None
            if isinstance(raw, (int, float)):
                value = float(raw)
                return value if value > 0 else None

            text = str(raw).strip()
            if not text:
                return None
            match = re.search(r"(\d+(?:\.\d+)?)", text)
            if not match:
                return None
            try:
                value = float(match.group(1))
            except ValueError:
                return None
            return value if value > 0 else None

        for key in keys:
            value = parse_radius(source_obj.get(key))
            if value is not None:
                return value

        for key in keys:
            value = parse_radius(fallback_obj.get(key))
            if value is not None:
                return value
        return None

    # ------------------------------------------------------------------
    # Monitor batch
    # ------------------------------------------------------------------

    def on_monitor_once(self: Any, silent_if_no_token: bool = False) -> None:
        sign_status = int(self.monitor_status_combo.currentData())
        self._last_monitor_sign_status = sign_status
        limit = int(self.monitor_limit_spin.value())
        insecure = self.tls_insecure_checkbox.isChecked()

        token = self.token_input.text().strip()
        if not token:
            if not silent_if_no_token:
                QMessageBox.warning(self, "提示", "Token 为空")
            return

        self._set_status("正在查询全部栏目监控数据...")
        worker = Worker(self._run_monitor_batch, token, sign_status, limit, insecure)
        worker.signals.done.connect(self._on_monitor_done)
        self.pool.start(worker)

    def _run_monitor_batch(
        self: Any,
        token: str,
        sign_status: int,
        limit: int,
        insecure: bool,
    ) -> dict[int, dict[str, Any]]:
        result: dict[int, dict[str, Any]] = {}
        for cid, _name in CATEGORIES:
            ok, msg, items = list_courses(
                token=token,
                sign_status=sign_status,
                transcript_index_id=cid,
                limit=limit,
                timeout=15.0,
                insecure_tls=insecure,
            )
            result[cid] = {
                "ok": ok,
                "message": msg,
                "items": items,
            }
        return result

    def _on_monitor_done(self: Any, result: dict[int, dict[str, Any]]) -> None:
        total_count = 0
        failed_count = 0

        for tab_idx, (category_id, category_name) in enumerate(CATEGORIES):
            table = self.monitor_tables[category_id]
            cat_result = result.get(category_id, {"ok": False, "message": "无结果", "items": []})
            ok = bool(cat_result.get("ok", False))
            items = cat_result.get("items")
            if not isinstance(items, list):
                items = []

            if not ok:
                failed_count += 1

            self.monitor_result_tabs.setTabText(tab_idx, f"{category_name} ({len(items)})")
            table.setRowCount(0)

            for row_idx, course in enumerate(items):
                if not isinstance(course, dict):
                    continue

                table.insertRow(row_idx)
                course_id_text = str(course.get("id", ""))
                title = str(course.get("title") or course.get("transcript_name") or "")

                status_raw = course.get("sign_status")
                if status_raw is None:
                    status_raw = self._last_monitor_sign_status
                try:
                    status_int = int(status_raw)
                except (TypeError, ValueError):
                    status_int = self._last_monitor_sign_status
                status = STATUS_MAP.get(status_int, str(status_int))

                if course.get("surplus") is not None:
                    surplus = str(course.get("surplus"))
                else:
                    max_count = int(course.get("max", 0) or 0)
                    apply_count = int(course.get("course_apply_count", 0) or 0)
                    surplus = str(max_count - apply_count)

                sign_start = str(course.get("sign_start_time") or "")
                cat_name = ""
                cat_obj = course.get("transcript_index")
                if isinstance(cat_obj, dict):
                    cat_name = str(cat_obj.get("transcript_name") or "")
                if not cat_name:
                    cat_name = category_name

                table.setItem(row_idx, 0, QTableWidgetItem(course_id_text))
                self._set_table_cover_cell(table, row_idx, 1, course)
                table.setItem(row_idx, 2, QTableWidgetItem(title))
                table.setItem(row_idx, 3, QTableWidgetItem(status))
                table.setItem(row_idx, 4, QTableWidgetItem(surplus))
                table.setItem(row_idx, 5, QTableWidgetItem(sign_start))
                table.setItem(row_idx, 6, QTableWidgetItem(cat_name))
                id_item = table.item(row_idx, 0)
                if id_item is not None:
                    course_payload = dict(course)
                    if "is_sign" in course_payload and "__enrolled" not in course_payload:
                        is_sign_value = course_payload.get("is_sign")
                        course_payload["__enrolled"] = is_sign_value in (1, True, "1", "true", "True")
                    id_item.setData(Qt.ItemDataRole.UserRole, course_payload)

            table.resizeColumnsToContents()
            table.setColumnWidth(1, 72)
            if table.columnWidth(2) > 420:
                table.setColumnWidth(2, 420)

            total_count += len(items)

        if failed_count > 0:
            self._set_status(f"监控已加载 {total_count} 门课程；{failed_count}/6 个栏目查询失败")
        else:
            self._set_status(f"监控已加载 {total_count} 门课程（共 6 个栏目）")
