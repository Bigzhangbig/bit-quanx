from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMessageBox, QTableWidgetItem

from .worker import Worker


class ActivitiesMixin:
    def on_activities_refresh(self: Any, silent_if_no_token: bool = False) -> None:
        insecure = self.tls_insecure_checkbox.isChecked()
        token = self.token_input.text().strip()
        if not token:
            if not silent_if_no_token:
                QMessageBox.warning(self, "提示", "Token 为空")
            return

        self._set_status("正在加载我的活动...")
        worker = Worker(self._fetch_my_courses, token, insecure)
        worker.signals.done.connect(self._on_activities_refresh_done)
        self.pool.start(worker)

    def _on_activities_refresh_done(self: Any, result: tuple[bool, str, list[dict[str, Any]]]) -> None:
        ok, msg, items = result
        if not ok:
            self._set_status(f"加载活动失败: {msg}")
            return

        self._activities_items_cache = [i for i in items if isinstance(i, dict)]
        self._render_activities_table(self._filtered_activities_items())
        total = len(self._activities_items_cache)
        shown = self.activities_table.rowCount()
        if shown == total:
            self._set_status(f"活动加载完成：{shown}")
        else:
            self._set_status(f"活动加载完成：显示 {shown} / 总计 {total}")

    def _has_checkin_window(self: Any, course: dict[str, Any]) -> bool:
        sign_in = self._window_text(
            str(course.get("sign_in_start_time") or ""),
            str(course.get("sign_in_end_time") or ""),
        )
        sign_out = self._window_text(
            str(course.get("sign_out_start_time") or ""),
            str(course.get("sign_out_end_time") or ""),
        )
        return bool(sign_in or sign_out)

    def _activities_checkin_only(self: Any) -> bool:
        return bool(self.activities_checkin_filter_combo.currentData())

    def _filtered_activities_items(self: Any) -> list[dict[str, Any]]:
        if not self._activities_checkin_only():
            return list(self._activities_items_cache)
        return [course for course in self._activities_items_cache if self._has_checkin_window(course)]

    def _render_activities_table(self: Any, items: list[dict[str, Any]]) -> None:
        self.activities_table.setRowCount(0)
        for row_idx, course in enumerate(items):
            if not isinstance(course, dict):
                continue

            self.activities_table.insertRow(row_idx)
            course_id = str(course.get("id") or course.get("course_id") or "")
            category = ""
            cat_obj = course.get("transcript_index")
            if isinstance(cat_obj, dict):
                category = str(cat_obj.get("transcript_name") or "")
            if not category:
                category = self._first_non_empty(course, ["transcript_name", "category_name"])

            title = str(course.get("title") or course.get("course_title") or "")
            duration = self._duration_text(course)
            sign_in = self._window_text(
                str(course.get("sign_in_start_time") or ""),
                str(course.get("sign_in_end_time") or ""),
            )
            sign_out = self._window_text(
                str(course.get("sign_out_start_time") or ""),
                str(course.get("sign_out_end_time") or ""),
            )

            self.activities_table.setItem(row_idx, 0, QTableWidgetItem(course_id))
            self._set_table_cover_cell(self.activities_table, row_idx, 1, course)
            self.activities_table.setItem(row_idx, 2, QTableWidgetItem(category))
            self.activities_table.setItem(row_idx, 3, QTableWidgetItem(title))
            self.activities_table.setItem(row_idx, 4, QTableWidgetItem(duration))
            self.activities_table.setItem(row_idx, 5, QTableWidgetItem(sign_in))
            self.activities_table.setItem(row_idx, 6, QTableWidgetItem(sign_out))

            id_item = self.activities_table.item(row_idx, 0)
            if id_item is not None:
                course_payload = dict(course)
                course_payload["__enrolled"] = True
                id_item.setData(Qt.ItemDataRole.UserRole, course_payload)

        self.activities_table.resizeColumnsToContents()
        self.activities_table.setColumnWidth(1, 72)
        if self.activities_table.columnWidth(3) > 420:
            self.activities_table.setColumnWidth(3, 420)

    def _on_activities_filter_changed(self: Any, _index: int) -> None:
        if not self._activities_items_cache:
            return
        self._render_activities_table(self._filtered_activities_items())
        total = len(self._activities_items_cache)
        shown = self.activities_table.rowCount()
        if shown == total:
            self._set_status(f"活动筛选已更新：{shown}")
        else:
            self._set_status(f"活动筛选已更新：显示 {shown} / 总计 {total}")
