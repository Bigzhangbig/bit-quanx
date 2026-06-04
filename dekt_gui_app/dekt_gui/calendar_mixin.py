"""CalendarMixin: 日历相关功能的 Mixin 类。

从 MainWindow 中提取的日历操作方法，包括：
- 刷新日历数据
- 报名/取消报名
- 查看活动详情
- 导出 ICS 文件
"""

from __future__ import annotations

from html import escape
from typing import Any

from PySide6.QtWidgets import (
    QDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
)

from .api_client import (
    DEFAULT_TEMPLATE_ID,
    apply_course,
    cancel_course,
    get_checkin_info,
    get_course_detail,
    get_user_id,
    list_courses,
    list_my_course_ids,
    list_my_courses,
    submit_sign_action,
)
from .calendar_state import apply_enrollment_delta
from .calendar_utils import (
    CalendarEvent,
    build_display_location,
    extract_time_place_fields,
    parse_event_from_list_courses,
    parse_event_from_list_my_courses,
)
from .constants import CATEGORIES
from .ics_exporter import export_events_to_ics_file
from .worker import Worker


class CalendarMixin:
    """日历功能 Mixin，提供日历相关的所有操作方法。"""

    # 由 MainWindow 提供的属性和方法
    token_input: Any
    tls_insecure_checkbox: Any
    pool: Any
    calendar_widget: Any
    _calendar_events_cache: list[CalendarEvent]
    _calendar_my_course_ids_cache: set[int]
    _set_status: Any
    _first_non_empty: Any
    _activity_detail_text: Any
    _activity_detail_section_html: Any

    def on_calendar_refresh(self: Any, silent_if_no_token: bool = False) -> None:
        """刷新日历数据。"""
        insecure = self.tls_insecure_checkbox.isChecked()
        token = self.token_input.text().strip()

        if not token:
            if not silent_if_no_token:
                QMessageBox.warning(self, "提示", "Token 为空")
            return

        if self._calendar_events_cache:
            # 优先展示最近一次成功数据，避免刷新期间页面空白。
            self.calendar_widget.load_events(
                list(self._calendar_events_cache),
                set(self._calendar_my_course_ids_cache),
            )
            self._set_status(f"正在加载日历数据...（先显示缓存 {len(self._calendar_events_cache)} 个活动）")
        else:
            self._set_status("正在加载日历数据...")

        worker = Worker(self._fetch_calendar_events, token, insecure)
        worker.signals.done.connect(self._on_calendar_refresh_done)
        self.pool.start(worker)

    def _fetch_calendar_events(
        self: Any, token: str, insecure: bool
    ) -> tuple[list[CalendarEvent], set[int], str]:
        """获取日历事件数据。"""
        # 获取已报名的活动
        ok1, msg1, my_courses = list_my_courses(
            token=token,
            limit=200,
            timeout=15.0,
            insecure_tls=insecure,
        )

        if not ok1:
            return [], set(), f"获取已报名活动失败: {msg1}"

        # 获取已报名的ID集合
        ok2, msg2, my_course_ids = list_my_course_ids(
            token=token,
            limit=200,
            timeout=15.0,
            insecure_tls=insecure,
        )

        # 转换为CalendarEvent
        my_events = parse_event_from_list_my_courses(my_courses)

        # my_course_ids接口偶发失败时，兜底用"我的活动"列表提取ID。
        if not ok2:
            my_course_ids = set()
        if not my_course_ids:
            my_course_ids = {event.id for event in my_events if event.id > 0}

        # 获取未报名的活动（6个栏目）
        all_events = my_events.copy()
        for cid, _ in CATEGORIES:
            ok3, msg3, courses = list_courses(
                token=token,
                sign_status=2,  # 进行中
                transcript_index_id=cid,
                limit=20,
                timeout=15.0,
                insecure_tls=insecure,
            )

            if ok3:
                unrolled_events = parse_event_from_list_courses(courses)
                # 过滤已报名的
                for event in unrolled_events:
                    if event.id not in my_course_ids:
                        all_events.append(event)

        # 按活动ID去重，保留首次出现（优先保留已报名活动信息）。
        unique_events: list[CalendarEvent] = []
        seen_ids: set[int] = set()
        for event in all_events:
            if event.id <= 0:
                unique_events.append(event)
                continue
            if event.id in seen_ids:
                continue
            seen_ids.add(event.id)
            unique_events.append(event)

        return unique_events, my_course_ids, "OK"

    def _on_calendar_refresh_done(self: Any, result: tuple) -> None:
        """日历加载完成回调。"""
        all_events, my_course_ids, msg = result

        if msg != "OK":
            if self._calendar_events_cache:
                self._set_status(f"{msg}（已保留并显示缓存数据）")
            else:
                self._set_status(msg)
            return

        self._calendar_events_cache = list(all_events)
        self._calendar_my_course_ids_cache = set(my_course_ids)

        # 加载到calendar_widget
        self.calendar_widget.load_events(all_events, my_course_ids)
        self._set_status(f"日历已加载 {len(all_events)} 个活动")

    def on_calendar_signup(self: Any, course_id: int) -> None:
        """日历报名。"""
        token = self.token_input.text().strip()
        if not token:
            QMessageBox.warning(self, "提示", "Token 为空")
            return

        self._set_status(f"正在报名活动 {course_id}...")
        insecure = self.tls_insecure_checkbox.isChecked()
        worker = Worker(apply_course, token, course_id, DEFAULT_TEMPLATE_ID, 12.0, insecure)
        worker.signals.done.connect(
            lambda result: self._on_calendar_action_result("报名", course_id, result)
        )
        self.pool.start(worker)

    def on_calendar_cancel(self: Any, course_id: int) -> None:
        """日历取消报名。"""
        token = self.token_input.text().strip()
        if not token:
            QMessageBox.warning(self, "提示", "Token 为空")
            return

        # 先获取user_id
        self._set_status(f"正在取消报名活动 {course_id}...")
        insecure = self.tls_insecure_checkbox.isChecked()
        worker = Worker(self._do_cancel_course, token, course_id, insecure)
        worker.signals.done.connect(
            lambda result: self._on_calendar_action_result("取消报名", course_id, result)
        )
        self.pool.start(worker)

    def _do_cancel_course(self: Any, token: str, course_id: int, insecure: bool) -> tuple[bool, str]:
        """执行取消报名（先获取user_id）。"""
        ok, user_id, msg = get_user_id(token, 12.0, insecure)
        if not ok:
            return False, f"获取用户ID失败: {msg}"

        return cancel_course(token, course_id, int(user_id), 12.0, insecure)

    def on_calendar_checkin(self: Any, course_id: int) -> None:
        """日历打卡（签到/签退）。"""
        QMessageBox.information(self, "提示", "打卡功能目前不可用，请等待修复。")
        return

    def _do_checkin(self: Any, token: str, course_id: int, insecure: bool) -> tuple[bool, str, dict]:
        """执行打卡。"""
        ok, msg, checkin_info = get_checkin_info(token, course_id, 12.0, insecure)
        if not ok:
            return False, f"获取打卡信息失败: {msg}", {}

        # 获取打卡地点
        addresses = checkin_info.get("sign_in_address", [])
        if not addresses:
            return False, "无可用的打卡地点", {}

        address_obj = addresses[0]
        address = address_obj.get("address", "")
        latitude = float(address_obj.get("latitude", 0))
        longitude = float(address_obj.get("longitude", 0))

        ok, msg = submit_sign_action(token, course_id, address, latitude, longitude, 12.0, insecure)
        return ok, msg, checkin_info

    def _on_calendar_checkin_done(self: Any, result: tuple) -> None:
        """打卡完成回调。"""
        ok, msg, _ = result
        if ok:
            self._set_status(f"打卡成功: {msg}")
            # 刷新日历
            self.on_calendar_refresh(silent_if_no_token=True)
        else:
            self._set_status(f"打卡失败: {msg}")

    def _on_calendar_action_result(self: Any, action_name: str, course_id: int, result: object) -> None:
        """统一处理日历报名/取消报名的 worker 结果。"""
        if not isinstance(result, tuple) or len(result) != 2:
            self._set_status(f"{action_name}失败: 返回结果格式异常")
            return

        ok_raw, msg_raw = result
        self._on_calendar_action_done(action_name, bool(ok_raw), str(msg_raw), course_id)

    def _sync_calendar_enrollment_cache(self: Any, course_id: int, enrolled: bool) -> None:
        """同步已报名活动缓存，并立即刷新日历视图。"""
        self._calendar_my_course_ids_cache = apply_enrollment_delta(
            self._calendar_my_course_ids_cache,
            course_id,
            enrolled,
        )

        if self._calendar_events_cache:
            self.calendar_widget.load_events(
                list(self._calendar_events_cache),
                set(self._calendar_my_course_ids_cache),
            )

    def _on_calendar_action_done(
        self: Any,
        action_name: str,
        ok: bool,
        msg: str,
        course_id: int | None = None,
    ) -> None:
        """日历操作完成回调。"""
        if ok:
            if course_id is not None:
                if action_name == "取消报名":
                    self._sync_calendar_enrollment_cache(course_id, enrolled=False)
                elif action_name == "报名":
                    self._sync_calendar_enrollment_cache(course_id, enrolled=True)

            self._set_status(f"{action_name}成功: {msg}")
            # 刷新日历
            self.on_calendar_refresh(silent_if_no_token=True)
        else:
            self._set_status(f"{action_name}失败: {msg}")

    def on_calendar_detail(self: Any, course_id: int) -> None:
        """查看日历活动详情。"""
        token = self.token_input.text().strip()
        if not token:
            QMessageBox.warning(self, "提示", "Token 为空")
            return

        self._set_status(f"正在加载活动详情 {course_id}...")
        insecure = self.tls_insecure_checkbox.isChecked()
        worker = Worker(get_course_detail, token, course_id, 12.0, insecure)
        worker.signals.done.connect(self._on_calendar_detail_done)
        self.pool.start(worker)

    def _on_calendar_detail_done(self: Any, result: tuple) -> None:
        """活动详情加载完成。"""
        ok, msg, detail = result

        if not ok:
            QMessageBox.warning(self, "错误", f"加载详情失败: {msg}")
            return

        # 显示详情对话框（复用现有的dialog风格）
        dialog = QDialog(self)
        dialog.setWindowTitle(detail.get("title", "活动详情"))
        dialog.resize(600, 500)

        layout = QVBoxLayout(dialog)

        # 创建详情内容
        details_text = self._format_event_detail(detail)
        text_browser = QTextBrowser()
        text_browser.setHtml(details_text)
        layout.addWidget(text_browser)

        # 关闭按钮
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn)

        dialog.exec()

    def _format_event_detail(self: Any, detail: dict) -> str:
        """格式化活动详情为HTML。"""
        html_parts = []

        # 标题
        title = detail.get("title", "未命名")
        html_parts.append(f"<h2>{escape(title)}</h2>")

        # 基础信息表格
        html_parts.append("<table style='width:100%; border-collapse:collapse;'>")

        # 时间
        time_place_text = self._first_non_empty(detail, ["time_place"])
        parsed_time_text, parsed_place_text = extract_time_place_fields(time_place_text)

        start_time = detail.get("activity_start_time", "") or parsed_time_text
        end_time = detail.get("activity_end_time", "")
        if start_time or end_time:
            html_parts.append(f"<tr><td style='padding:5px;'><b>时间:</b></td><td style='padding:5px;'>{escape(start_time or '')} ~ {escape(end_time or '')}</td></tr>")

        # 地点
        location = build_display_location(time_place_text, detail.get("location", "") or parsed_place_text)
        if location:
            html_parts.append(f"<tr><td style='padding:5px;'><b>地点:</b></td><td style='padding:5px;'>{escape(location)}</td></tr>")

        # 报名信息
        max_num = detail.get("max", "")
        apply_count = detail.get("course_apply_count", "")
        if max_num and apply_count:
            html_parts.append(f"<tr><td style='padding:5px;'><b>报名:</b></td><td style='padding:5px;'>{apply_count}/{max_num}</td></tr>")

        # 时长
        duration = detail.get("duration", "")
        if duration:
            html_parts.append(f"<tr><td style='padding:5px;'><b>时长:</b></td><td style='padding:5px;'>{escape(str(duration))}</td></tr>")

        # 联系方式
        contact_name = detail.get("contact_name", "")
        contact_phone = detail.get("contact_phone", "")
        if contact_name or contact_phone:
            contact = f"{contact_name or ''} {contact_phone or ''}".strip()
            html_parts.append(f"<tr><td style='padding:5px;'><b>联系:</b></td><td style='padding:5px;'>{escape(contact)}</td></tr>")

        html_parts.append("</table>")

        # 详情内容
        detail_text = self._activity_detail_text(detail)
        html_parts.append(self._activity_detail_section_html(detail_text))

        return "".join(html_parts)

    def on_calendar_export_ics(self: Any, events: list) -> None:
        """导出日历为ICS文件。"""
        if not events:
            QMessageBox.warning(self, "提示", "没有活动可导出")
            return

        # 打开保存对话框
        from PySide6.QtWidgets import QFileDialog

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "导出ICS文件",
            "calendar.ics",
            "iCalendar Files (*.ics)"
        )

        if not file_path:
            return

        # 导出
        ok = export_events_to_ics_file(events, file_path, "DEKT活动日历")
        if ok:
            self._set_status(f"ICS文件已导出: {file_path}")
            QMessageBox.information(self, "成功", "ICS文件导出成功")
        else:
            self._set_status("ICS文件导出失败")
            QMessageBox.warning(self, "失败", "ICS文件导出失败")
