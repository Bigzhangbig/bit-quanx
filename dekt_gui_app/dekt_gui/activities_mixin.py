from __future__ import annotations

from datetime import datetime
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QMessageBox, QTableWidgetItem

from .worker import Worker


class ActivitiesMixin:
    def _course_id_int(self: Any, course: dict[str, Any]) -> int:
        raw_id = course.get("id") or course.get("course_id")
        try:
            return int(raw_id)
        except (TypeError, ValueError):
            return -1

    def _sign_in_start_dt(self: Any, course: dict[str, Any]) -> datetime:
        raw = str(course.get("sign_in_start_time") or "").strip()
        if not raw:
            return datetime.max

        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
            try:
                return datetime.strptime(raw, fmt)
            except ValueError:
                continue
        return datetime.max

    def _sort_activities_items(self: Any, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """活动页排序：未完成优先，未完成按签到时间升序，已完成按ID降序。"""
        unfinished: list[dict[str, Any]] = []
        completed: list[dict[str, Any]] = []

        for course in items:
            if self._is_course_completed(course):
                completed.append(course)
            else:
                unfinished.append(course)

        unfinished.sort(
            key=lambda course: (
                self._sign_in_start_dt(course),
                self._course_id_int(course),
            )
        )
        completed.sort(key=self._course_id_int, reverse=True)
        return unfinished + completed

    def _is_course_completed(self: Any, course: dict[str, Any]) -> bool:
        """判断活动是否已完成（用于活动页灰显）。"""
        if not isinstance(course, dict):
            return False

        # 优先使用课程签到状态。
        sign_status = course.get("sign_status")
        try:
            if sign_status is not None and int(sign_status) == 3:
                return True
        except (TypeError, ValueError):
            pass

        labels = [
            str(course.get("sign_status_label") or "").strip(),
            str(course.get("checkin_status_label") or "").strip(),
            str(course.get("status_label") or "").strip(),
        ]
        for label in labels:
            if not label:
                continue
            if any(key in label for key in ("已完成", "完成", "已结束")):
                return True

        # 有些接口会给完成时间字段。
        if course.get("complate_time") or course.get("complete_time"):
            return True

        return False

    def _apply_completed_row_style(self: Any, row_idx: int) -> None:
        text_color = QColor("#8A8F98")
        bg_color = QColor("#F6F7F9")
        for col in range(self.activities_table.columnCount()):
            item = self.activities_table.item(row_idx, col)
            if item is None:
                continue
            item.setForeground(text_color)
            item.setBackground(bg_color)

    def _is_course_in_progress(self: Any, course: dict[str, Any]) -> bool:
        """判断活动是否进行中（用于活动页浅绿高亮）。"""
        if not isinstance(course, dict):
            return False

        sign_status = course.get("sign_status")
        try:
            if sign_status is not None and int(sign_status) == 2:
                return True
        except (TypeError, ValueError):
            pass

        labels = [
            str(course.get("sign_status_label") or "").strip(),
            str(course.get("checkin_status_label") or "").strip(),
        ]
        for label in labels:
            if not label:
                continue
            if any(key in label for key in ("进行中", "待签到", "待签退", "待打卡")):
                return True

        return False

    def _apply_in_progress_row_style(self: Any, row_idx: int) -> None:
        text_color = QColor("#1F6F43")
        bg_color = QColor("#EEF9F1")
        for col in range(self.activities_table.columnCount()):
            item = self.activities_table.item(row_idx, col)
            if item is None:
                continue
            item.setForeground(text_color)
            item.setBackground(bg_color)

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
            return self._sort_activities_items(list(self._activities_items_cache))
        filtered = [course for course in self._activities_items_cache if self._has_checkin_window(course)]
        return self._sort_activities_items(filtered)

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

            if self._is_course_completed(course):
                self._apply_completed_row_style(row_idx)
            elif self._is_course_in_progress(course):
                self._apply_in_progress_row_style(row_idx)

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
