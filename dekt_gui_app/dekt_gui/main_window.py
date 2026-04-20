from __future__ import annotations

import base64
from datetime import datetime
import math
import re
from html import escape
from typing import Any

import certifi
import httpx
from PySide6.QtGui import QColor, QDesktopServices, QPainter, QPen, QPixmap
from PySide6.QtCore import QThreadPool, Qt
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QSpinBox,
    QSplitter,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from .api_client import (
    DEFAULT_TEMPLATE_ID,
    apply_course,
    cancel_course,
    fetch_token_from_gist,
    get_checkin_info,
    get_course_detail,
    get_user_id,
    list_my_courses,
    list_my_course_ids,
    list_courses,
    normalize_bearer_token,
    submit_sign_action,
    verify_token,
)
from .activities_mixin import ActivitiesMixin
from .calendar_widget import CalendarWidget
from .calendar_utils import (
    CalendarEvent,
    build_display_location,
    extract_time_place_fields,
    normalize_display_text,
    parse_event_from_list_my_courses,
    parse_event_from_list_courses,
    enrich_event_with_detail,
)
from .calendar_state import apply_enrollment_delta
from .config import AppConfig, load_config, save_config
from .constants import CATEGORIES, STATUS_MAP
from .ics_exporter import export_events_to_ics_file
from .qrcode_dialog import QRCodeDialog
from .worker import Worker


class MainWindow(ActivitiesMixin, QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("DEKT 桌面版（测试版）")
        self.resize(900, 600)

        self.pool = QThreadPool.globalInstance()
        self.config = load_config()
        self._last_monitor_sign_status = 1
        self._image_bytes_cache: dict[str, bytes | None] = {}
        self._pixmap_cache: dict[str, QPixmap | None] = {}
        self._cover_waiters: dict[str, list[tuple[QTableWidget, int, int]]] = {}
        self._cover_loading_urls: set[str] = set()
        self._activities_items_cache: list[dict[str, Any]] = []
        self._calendar_events_cache: list[CalendarEvent] = []
        self._calendar_my_course_ids_cache: set[int] = set()

        self.token_input = QLineEdit(self.config.token)
        self.token_input.setPlaceholderText("Bearer xxx 或原始 token")

        self.github_token_input = QLineEdit(self.config.github_token)
        self.github_token_input.setPlaceholderText("GitHub 个人访问令牌")
        self.github_token_input.setEchoMode(QLineEdit.EchoMode.Password)

        self.gist_id_input = QLineEdit(self.config.gist_id)
        self.gist_id_input.setPlaceholderText("Gist ID")

        self.gist_filename_input = QLineEdit(self.config.gist_filename)
        self.gist_filename_input.setPlaceholderText("bit_cookies.json")

        self.tencent_map_key_input = QLineEdit(self.config.tencent_map_key)
        self.tencent_map_key_input.setPlaceholderText("腾讯地图 Key（静态地图）")

        self.tls_insecure_checkbox = QCheckBox("忽略 TLS 证书校验（仅调试）")
        self.tls_insecure_checkbox.setChecked(self.config.tls_insecure)

        self.whitelist_category_ids_input = QLineEdit(self.config.whitelist_category_ids)
        self.whitelist_category_ids_input.setPlaceholderText("1,2,3,4,5,6")

        self.whitelist_grade_input = QLineEdit(self.config.whitelist_grade)
        self.whitelist_grade_input.setPlaceholderText("2024,2025")

        self.whitelist_academy_input = QLineEdit(self.config.whitelist_academy)
        self.whitelist_academy_input.setPlaceholderText("计算机学院,睿信书院")

        self.monitor_status_combo = QComboBox()
        self.monitor_status_combo.addItem("未开始", 1)
        self.monitor_status_combo.addItem("进行中", 2)
        self.monitor_status_combo.addItem("已结束", 3)
        self.monitor_status_combo.currentIndexChanged.connect(self._on_monitor_status_changed)

        self.monitor_limit_spin = QSpinBox()
        self.monitor_limit_spin.setRange(1, 100)
        self.monitor_limit_spin.setValue(20)

        self.monitor_result_tabs = QTabWidget()
        self.monitor_tables: dict[int, QTableWidget] = {}
        for cid, name in CATEGORIES:
            table = self._create_monitor_table()
            table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            table.customContextMenuRequested.connect(
                lambda pos, t=table: self._show_monitor_context_menu(t, pos)
            )
            table.itemDoubleClicked.connect(self._on_monitor_item_double_clicked)
            self.monitor_tables[cid] = table
            tab = QWidget()
            tab_layout = QVBoxLayout(tab)
            tab_layout.addWidget(table)
            self.monitor_result_tabs.addTab(tab, name)

        self.sign_table = QTableWidget(0, 6)
        self.sign_table.setHorizontalHeaderLabels([
            "ID",
            "头图",
            "标题",
            "签到窗口",
            "签退窗口",
            "地点",
        ])
        self.sign_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.sign_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.sign_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.sign_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.sign_table.customContextMenuRequested.connect(
            lambda pos: self._show_sign_context_menu(self.sign_table, pos)
        )
        self.sign_table.itemDoubleClicked.connect(self._on_sign_item_double_clicked)

        self.activities_table = QTableWidget(0, 7)
        self.activities_table.setHorizontalHeaderLabels([
            "ID",
            "头图",
            "类别",
            "名称",
            "时长",
            "签到",
            "签退",
        ])
        self.activities_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.activities_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.activities_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.activities_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.activities_table.customContextMenuRequested.connect(
            lambda pos: self._show_activities_context_menu(self.activities_table, pos)
        )
        self.activities_table.itemDoubleClicked.connect(self._on_activities_item_double_clicked)

        self.activities_checkin_filter_combo = QComboBox()
        self.activities_checkin_filter_combo.addItem("全部活动", False)
        self.activities_checkin_filter_combo.addItem("仅有打卡", True)
        self.activities_checkin_filter_combo.setCurrentIndex(1 if self.config.activities_has_checkin_only else 0)
        self.activities_checkin_filter_combo.currentIndexChanged.connect(self._on_activities_filter_changed)

        # 日历widget
        self.calendar_widget = CalendarWidget()
        self.calendar_widget.on_signup_callback = self.on_calendar_signup
        self.calendar_widget.on_cancel_callback = self.on_calendar_cancel
        self.calendar_widget.on_checkin_callback = self.on_calendar_checkin
        self.calendar_widget.on_detail_callback = self.on_calendar_detail
        self.calendar_widget.on_export_ics_callback = self.on_calendar_export_ics

        self.status_label = QLabel("就绪")
        self.log_box = QPlainTextEdit()
        self.log_box.setReadOnly(True)

        self._build_ui()
        self._append_log("界面初始化完成")

    def _build_ui(self) -> None:
        root = QWidget()
        layout = QVBoxLayout(root)

        self.main_tabs = QTabWidget()
        self.main_tabs.addTab(self._build_credentials_tab(), "凭据")
        self.main_tabs.addTab(self._build_monitor_tab(), "监控")
        self.main_tabs.addTab(self._build_sign_tab(), "打卡")
        self.main_tabs.addTab(self._build_activities_tab(), "活动")
        self.main_tabs.addTab(self._build_calendar_tab(), "日历")
        self.main_tabs.currentChanged.connect(self._on_main_tab_changed)

        logs_panel = QWidget()
        logs_layout = QVBoxLayout(logs_panel)
        logs_layout.setContentsMargins(0, 0, 0, 0)
        logs_layout.addWidget(QLabel("日志"))
        logs_layout.addWidget(self.log_box, 1)

        main_splitter = QSplitter(Qt.Orientation.Vertical)
        main_splitter.setChildrenCollapsible(False)
        main_splitter.addWidget(self.main_tabs)
        main_splitter.addWidget(logs_panel)
        main_splitter.setStretchFactor(0, 4)
        main_splitter.setStretchFactor(1, 1)
        main_splitter.setSizes([500, 140])

        layout.addWidget(main_splitter, 1)
        layout.addWidget(self.status_label)

        self.setCentralWidget(root)

    def _build_credentials_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        cred_box = QGroupBox("凭据")
        form = QFormLayout(cred_box)
        form.addRow("DEKT Token", self.token_input)
        form.addRow("GitHub Token", self.github_token_input)
        form.addRow("Gist ID", self.gist_id_input)
        form.addRow("Gist 文件", self.gist_filename_input)
        form.addRow("腾讯地图 Key", self.tencent_map_key_input)
        form.addRow("TLS", self.tls_insecure_checkbox)
        form.addRow("白名单栏目", self.whitelist_category_ids_input)
        form.addRow("白名单年级", self.whitelist_grade_input)
        form.addRow("白名单学院", self.whitelist_academy_input)

        btn_row = QHBoxLayout()
        save_btn = QPushButton("保存凭据")
        save_btn.clicked.connect(self.on_save)

        verify_btn = QPushButton("验证 Token")
        verify_btn.clicked.connect(self.on_verify_token)

        pull_gist_btn = QPushButton("从 Gist 加载 Token")
        pull_gist_btn.clicked.connect(self.on_pull_gist)

        btn_row.addWidget(save_btn)
        btn_row.addWidget(verify_btn)
        btn_row.addWidget(pull_gist_btn)
        btn_row.addStretch(1)

        layout.addWidget(cred_box)
        layout.addLayout(btn_row)
        layout.addStretch(1)

        return tab

    def _build_monitor_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        controls = QGroupBox("手动监控查询")
        form = QFormLayout(controls)

        status_row = QWidget()
        status_row_layout = QHBoxLayout(status_row)
        status_row_layout.setContentsMargins(0, 0, 0, 0)
        status_row_layout.addWidget(self.monitor_status_combo)

        run_btn = QPushButton("立即刷新")
        run_btn.clicked.connect(lambda: self.on_monitor_once(silent_if_no_token=False))
        status_row_layout.addWidget(run_btn)
        status_row_layout.addStretch(1)

        form.addRow("活动状态", status_row)
        form.addRow("数量上限", self.monitor_limit_spin)

        layout.addWidget(controls)
        layout.addWidget(self.monitor_result_tabs, 1)
        return tab

    def _build_sign_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        controls = QGroupBox("签到/签退")
        row = QHBoxLayout(controls)
        refresh_btn = QPushButton("刷新活动")
        refresh_btn.clicked.connect(self.on_sign_refresh)
        signin_btn = QPushButton("签到")
        signin_btn.clicked.connect(lambda: self.on_sign_action("signIn"))
        signout_btn = QPushButton("签退")
        signout_btn.clicked.connect(lambda: self.on_sign_action("signOut"))
        row.addWidget(refresh_btn)
        row.addWidget(signin_btn)
        row.addWidget(signout_btn)
        row.addStretch(1)

        layout.addWidget(controls)
        layout.addWidget(self.sign_table, 1)
        return tab

    def _build_activities_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        controls = QGroupBox("我的活动")
        row = QHBoxLayout(controls)
        row.addWidget(QLabel("打卡筛选"))
        row.addWidget(self.activities_checkin_filter_combo)
        refresh_btn = QPushButton("刷新我的活动")
        refresh_btn.clicked.connect(self.on_activities_refresh)
        row.addWidget(refresh_btn)
        row.addStretch(1)

        layout.addWidget(controls)
        layout.addWidget(self.activities_table, 1)
        return tab

    def _build_calendar_tab(self) -> QWidget:
        """构建日历标签页。"""
        return self.calendar_widget

    def _on_main_tab_changed(self, index: int) -> None:
        if index < 0:
            return
        tab_name = self.main_tabs.tabText(index)
        if tab_name == "监控":
            self.on_monitor_once(silent_if_no_token=True)
        elif tab_name == "打卡":
            self.on_sign_refresh(silent_if_no_token=True)
        elif tab_name == "活动":
            self.on_activities_refresh(silent_if_no_token=True)
        elif tab_name == "日历":
            self.on_calendar_refresh(silent_if_no_token=True)

    def on_sign_refresh(self, silent_if_no_token: bool = False) -> None:
        insecure = self.tls_insecure_checkbox.isChecked()
        token = self.token_input.text().strip()
        if not token:
            if not silent_if_no_token:
                QMessageBox.warning(self, "提示", "Token 为空")
            return

        self._set_status("正在加载可签到活动...")
        worker = Worker(self._fetch_my_courses, token, insecure)
        worker.signals.done.connect(self._on_sign_refresh_done)
        self.pool.start(worker)

    def _fetch_my_courses(self, token: str, insecure: bool) -> tuple[bool, str, list[dict[str, Any]]]:
        return list_my_courses(
            token=token,
            limit=200,
            timeout=15.0,
            insecure_tls=insecure,
        )

    def _window_text(self, start: str, end: str) -> str:
        if start and end:
            return f"{start} ~ {end}"
        return ""

    def _on_sign_refresh_done(self, result: tuple[bool, str, list[dict[str, Any]]]) -> None:
        ok, msg, items = result
        if not ok:
            self._set_status(f"加载可签到活动失败: {msg}")
            return

        def _sign_sort_key(course: dict[str, Any]) -> tuple[datetime, int]:
            sign_in_start_raw = str(course.get("sign_in_start_time") or "")
            # 签到时间为空时放到最后；同为空时按活动ID升序。
            sign_in_dt = self._parse_time(sign_in_start_raw) or datetime.max
            raw_id = course.get("id") or course.get("course_id")
            try:
                cid = int(raw_id) if raw_id is not None else -1
            except (TypeError, ValueError):
                cid = -1
            return sign_in_dt, cid

        self.sign_table.setRowCount(0)
        render_courses: list[dict[str, Any]] = []
        for course in items:
            if not isinstance(course, dict):
                continue

            sign_in_window = self._window_text(
                str(course.get("sign_in_start_time") or ""),
                str(course.get("sign_in_end_time") or ""),
            )
            sign_out_window = self._window_text(
                str(course.get("sign_out_start_time") or ""),
                str(course.get("sign_out_end_time") or ""),
            )

            # 打卡 页只显示有签到或签退窗口的课程。
            if not sign_in_window and not sign_out_window:
                continue

            # 打卡 页隐藏已结束活动：优先使用签退结束时间，其次签到结束时间。
            end_raw = str(course.get("sign_out_end_time") or course.get("sign_in_end_time") or "")
            end_dt = self._parse_time(end_raw)
            if end_dt is not None and end_dt < datetime.now():
                continue

            render_courses.append(course)

        render_courses.sort(key=_sign_sort_key)

        row_idx = 0
        for course in render_courses:
            course_id = str(course.get("id") or course.get("course_id") or "")
            title = str(course.get("title") or course.get("course_title") or "")
            sign_in_window = self._window_text(
                str(course.get("sign_in_start_time") or ""),
                str(course.get("sign_in_end_time") or ""),
            )
            sign_out_window = self._window_text(
                str(course.get("sign_out_start_time") or ""),
                str(course.get("sign_out_end_time") or ""),
            )

            self.sign_table.insertRow(row_idx)

            place = ""
            sign_addr = course.get("sign_in_address")
            if isinstance(sign_addr, list) and sign_addr and isinstance(sign_addr[0], dict):
                place = str(sign_addr[0].get("address") or "")
            if not place:
                place = self._first_non_empty(course, ["time_place", "place", "location"])

            self.sign_table.setItem(row_idx, 0, QTableWidgetItem(course_id))
            self._set_table_cover_cell(self.sign_table, row_idx, 1, course)
            self.sign_table.setItem(row_idx, 2, QTableWidgetItem(title))
            self.sign_table.setItem(row_idx, 3, QTableWidgetItem(sign_in_window))
            self.sign_table.setItem(row_idx, 4, QTableWidgetItem(sign_out_window))
            self.sign_table.setItem(row_idx, 5, QTableWidgetItem(place))

            id_item = self.sign_table.item(row_idx, 0)
            if id_item is not None:
                course_payload = dict(course)
                course_payload["__enrolled"] = True
                id_item.setData(Qt.ItemDataRole.UserRole, course_payload)

            row_idx += 1

        self.sign_table.resizeColumnsToContents()
        self.sign_table.setColumnWidth(1, 72)
        if self.sign_table.columnWidth(2) > 420:
            self.sign_table.setColumnWidth(2, 420)

        self._set_status(f"可签到活动加载完成：{self.sign_table.rowCount()}")

    def _on_sign_item_double_clicked(self, item: QTableWidgetItem) -> None:
        self._open_detail_from_table_item(item)

    def _on_activities_item_double_clicked(self, item: QTableWidgetItem) -> None:
        self._open_detail_from_table_item(item)

    def _open_detail_from_table_item(self, item: QTableWidgetItem) -> None:
        table = item.tableWidget()
        if table is None:
            return
        id_item = table.item(item.row(), 0)
        if id_item is None:
            return
        self._open_course_detail_by_id_item(id_item)

    def _open_course_detail_by_id_item(self, id_item: QTableWidgetItem) -> None:
        course_id_text = (id_item.text() or "").strip()
        if not course_id_text.isdigit():
            QMessageBox.warning(self, "课程详情", f"课程 ID 无效: {course_id_text}")
            return

        fallback_obj = id_item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(fallback_obj, dict):
            fallback_obj = {}

        course_id = int(course_id_text)
        insecure = self.tls_insecure_checkbox.isChecked()

        token = self.token_input.text().strip()
        if not token:
            QMessageBox.warning(self, "课程详情", "Token 为空")
            return

        self._set_status(f"正在加载课程详情: {course_id}")
        worker = Worker(
            self._load_course_detail,
            token,
            course_id,
            fallback_obj,
            insecure,
        )
        worker.signals.done.connect(self._on_course_detail_loaded)
        self.pool.start(worker)

    def _parse_time(self, raw: str) -> datetime | None:
        text = str(raw or "").strip()
        if not text:
            return None
        normalized = text.replace("-", "/")
        for fmt in ["%Y/%m/%d %H:%M:%S", "%Y/%m/%d %H:%M"]:
            try:
                return datetime.strptime(normalized, fmt)
            except ValueError:
                continue
        return None

    def _within_window(self, now: datetime, start_raw: str, end_raw: str) -> bool:
        start_dt = self._parse_time(start_raw)
        end_dt = self._parse_time(end_raw)
        if start_dt is None or end_dt is None:
            return True
        return start_dt <= now <= end_dt

    def on_sign_action(self, action: str) -> None:
        row = self.sign_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "提示", "请先选择一条活动")
            return

        id_item = self.sign_table.item(row, 0)
        if id_item is None:
            return
        course_id_text = (id_item.text() or "").strip()
        if not course_id_text.isdigit():
            QMessageBox.warning(self, "提示", f"无效课程 ID: {course_id_text}")
            return

        token = self.token_input.text().strip()
        if not token:
            QMessageBox.warning(self, "提示", "Token 为空")
            return

        fallback_obj = id_item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(fallback_obj, dict):
            fallback_obj = {}

        course_id = int(course_id_text)
        insecure = self.tls_insecure_checkbox.isChecked()
        self._set_status(f"正在执行 {action}（课程 {course_id}）...")
        worker = Worker(self._run_sign_action_task, token, course_id, action, fallback_obj, insecure)
        worker.signals.done.connect(self._on_sign_action_done)
        self.pool.start(worker)

    def _run_sign_action_task(
        self,
        token: str,
        course_id: int,
        action: str,
        fallback_obj: dict[str, Any],
        insecure: bool,
    ) -> tuple[bool, str]:
        _ok_info, _msg_info, info = get_checkin_info(
            token=token,
            course_id=course_id,
            timeout=12.0,
            insecure_tls=insecure,
        )

        merged = dict(fallback_obj)
        if isinstance(info, dict):
            merged.update(info)

        now = datetime.now()
        if action == "signIn":
            if not self._within_window(
                now,
                str(merged.get("sign_in_start_time") or ""),
                str(merged.get("sign_in_end_time") or ""),
            ):
                return False, "当前不在签到时间窗口"
        elif action == "signOut":
            if not self._within_window(
                now,
                str(merged.get("sign_out_start_time") or ""),
                str(merged.get("sign_out_end_time") or ""),
            ):
                return False, "当前不在签退时间窗口"

        address = ""
        lat = None
        lon = None
        addr_arr = merged.get("sign_in_address")
        if isinstance(addr_arr, list) and addr_arr and isinstance(addr_arr[0], dict):
            address = str(addr_arr[0].get("address") or "")
            lat = addr_arr[0].get("latitude")
            lon = addr_arr[0].get("longitude")

        if lat is None or lon is None:
            return False, "未找到可用打卡坐标"

        if not address:
            address = self._first_non_empty(merged, ["sign_place", "checkin_location", "place", "location"])

        try:
            latitude_value = float(lat)
            longitude_value = float(lon)
        except (TypeError, ValueError):
            return False, "打卡坐标格式无效"

        ok_sign, sign_msg = submit_sign_action(
            token=token,
            course_id=course_id,
            address=address,
            latitude=latitude_value,
            longitude=longitude_value,
            timeout=12.0,
            insecure_tls=insecure,
        )

        label = "签到" if action == "signIn" else "签退"
        return ok_sign, f"{label} {course_id}: {sign_msg}"

    def _on_sign_action_done(self, result: tuple[bool, str]) -> None:
        ok, msg = result
        self._set_status(msg)
        if ok:
            self.on_sign_refresh()

    def _create_monitor_table(self) -> QTableWidget:
        table = QTableWidget(0, 7)
        table.setHorizontalHeaderLabels([
            "ID",
            "头图",
            "标题",
            "状态",
            "剩余名额",
            "报名开始",
            "栏目",
        ])
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        return table

    def _show_monitor_context_menu(self, table: QTableWidget, pos) -> None:
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

    def _show_sign_context_menu(self, table: QTableWidget, pos) -> None:
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

    def _show_activities_context_menu(self, table: QTableWidget, pos) -> None:
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

    def _run_activities_course_action(self, action: str, course_id_text: str) -> None:
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

    def _on_activities_course_action_done(self, result: tuple[bool, str]) -> None:
        ok, msg = result
        self._set_status(msg)
        if ok:
            self.on_activities_refresh(silent_if_no_token=True)

    def _on_monitor_item_double_clicked(self, item: QTableWidgetItem) -> None:
        table = item.tableWidget()
        if table is None:
            return

        id_item = table.item(item.row(), 0)
        if id_item is None:
            return
        self._open_course_detail_by_id_item(id_item)

    def _load_course_detail(
        self,
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

        # 详情接口常不返回 is_sign，补一次“我的活动”预检查，避免报名状态显示未知。
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

    def _on_course_detail_loaded(self, result: tuple[bool, str, dict[str, Any]]) -> None:
        ok, msg, course_obj = result
        if not ok:
            self._set_status(f"课程详情回退: {msg}")
        else:
            self._set_status("课程详情加载完成")

        if not isinstance(course_obj, dict) or not course_obj:
            QMessageBox.information(self, "课程详情", "未找到课程详情数据")
            return

        self._show_course_detail_dialog(course_obj)

    def _show_course_detail_dialog(self, course_obj: dict[str, Any]) -> None:
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

    def _extract_checkin_location(self, course_obj: dict[str, Any]) -> tuple[str, float | None, float | None, float | None]:
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

    def _extract_checkin_radius(self, source_obj: dict[str, Any], fallback_obj: dict[str, Any]) -> float | None:
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

    def _draw_range_circle_on_map(self, pixmap: QPixmap, lat: float, radius_m: float) -> QPixmap:
        # Web Mercator meters per pixel at given zoom and latitude.
        zoom_level = 16.0
        meters_per_pixel = 156543.03392 * math.cos(math.radians(lat)) / (2**zoom_level)
        if meters_per_pixel <= 0:
            meters_per_pixel = 1.0

        radius_px = radius_m / meters_per_pixel
        max_radius = max(10.0, min(pixmap.width(), pixmap.height()) * 0.46)
        radius_px = max(8.0, min(radius_px, max_radius))

        out = QPixmap(pixmap)
        painter = QPainter(out)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        center_x = out.width() / 2.0
        center_y = out.height() / 2.0

        fill_color = QColor(47, 124, 246, 55)
        line_color = QColor(47, 124, 246, 220)
        painter.setBrush(fill_color)
        painter.setPen(QPen(line_color, 2.0))
        painter.drawEllipse(
            int(center_x - radius_px),
            int(center_y - radius_px),
            int(radius_px * 2),
            int(radius_px * 2),
        )

        painter.setBrush(QColor(220, 53, 69, 230))
        painter.setPen(QPen(QColor(255, 255, 255, 220), 1.0))
        painter.drawEllipse(int(center_x - 4), int(center_y - 4), 8, 8)

        painter.end()
        return out

    def _normalize_media_url(self, raw_url: str) -> str:
        url = (raw_url or "").strip()
        if not url:
            return ""
        if url.startswith("http://") or url.startswith("https://"):
            return url

        clean = url.lstrip("/")
        if clean.startswith("storage/"):
            return f"https://qcbldekt.bit.edu.cn/{clean}"
        return f"https://qcbldekt.bit.edu.cn/storage/{clean}"

    def _cover_url(self, course_obj: dict[str, Any]) -> str:
        cover = self._first_non_empty(course_obj, ["cover_url", "cover", "image", "img"])
        return self._normalize_media_url(cover)

    def _fetch_image_bytes(self, url: str, timeout: float = 10.0) -> bytes | None:
        norm_url = self._normalize_media_url(url)
        if not norm_url:
            return None

        if norm_url in self._image_bytes_cache:
            return self._image_bytes_cache[norm_url]

        try:
            verify: bool | str = False if self.tls_insecure_checkbox.isChecked() else certifi.where()
            with httpx.Client(timeout=timeout, verify=verify, follow_redirects=True) as client:
                resp = client.get(norm_url)
            if 200 <= resp.status_code < 300 and resp.content:
                self._image_bytes_cache[norm_url] = resp.content
                return resp.content
        except Exception:  # noqa: BLE001
            pass

        self._image_bytes_cache[norm_url] = None
        return None

    def _pixmap_from_bytes(self, url: str, content: bytes, width: int, height: int) -> QPixmap | None:
        norm_url = self._normalize_media_url(url)
        if not norm_url:
            return None

        cache_key = f"{norm_url}|{width}x{height}"
        if cache_key in self._pixmap_cache:
            return self._pixmap_cache[cache_key]

        try:
            pixmap = QPixmap()
            if pixmap.loadFromData(content):
                scaled = pixmap.scaled(
                    width,
                    height,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                self._pixmap_cache[cache_key] = scaled
                return scaled
        except Exception:  # noqa: BLE001
            pass

        self._pixmap_cache[cache_key] = None
        return None

    def _download_image_bytes_task(
        self,
        url: str,
        insecure_tls: bool,
        timeout: float,
    ) -> tuple[str, bytes | None]:
        try:
            verify: bool | str = False if insecure_tls else certifi.where()
            with httpx.Client(timeout=timeout, verify=verify, follow_redirects=True) as client:
                resp = client.get(url)
            if 200 <= resp.status_code < 300 and resp.content:
                return url, resp.content
        except Exception:  # noqa: BLE001
            pass
        return url, None

    def _request_cover_image_async(self, table: QTableWidget, row: int, col: int, cover_url: str) -> None:
        norm_url = self._normalize_media_url(cover_url)
        if not norm_url:
            return

        cached = self._image_bytes_cache.get(norm_url)
        if cached:
            pixmap = self._pixmap_from_bytes(norm_url, cached, 56, 40)
            item = table.item(row, col)
            if item is not None and pixmap is not None:
                item.setData(Qt.ItemDataRole.DecorationRole, pixmap)
            return

        self._cover_waiters.setdefault(norm_url, []).append((table, row, col))
        if norm_url in self._cover_loading_urls:
            return

        self._cover_loading_urls.add(norm_url)
        worker = Worker(
            self._download_image_bytes_task,
            norm_url,
            self.tls_insecure_checkbox.isChecked(),
            10.0,
        )
        worker.signals.done.connect(self._on_cover_image_loaded)
        self.pool.start(worker)

    def _on_cover_image_loaded(self, payload: tuple[str, bytes | None]) -> None:
        url, content = payload
        self._cover_loading_urls.discard(url)
        self._image_bytes_cache[url] = content

        waiters = self._cover_waiters.pop(url, [])
        if not waiters or not content:
            return

        pixmap = self._pixmap_from_bytes(url, content, 56, 40)
        if pixmap is None:
            return

        for table, row, col in waiters:
            try:
                if row >= table.rowCount():
                    continue
                item = table.item(row, col)
                if item is None:
                    continue
                current_url = str(item.data(Qt.ItemDataRole.UserRole) or "")
                if current_url != url:
                    continue
                item.setData(Qt.ItemDataRole.DecorationRole, pixmap)
            except RuntimeError:
                # 表格已销毁或行已刷新，忽略即可。
                continue

    def _set_table_cover_cell(self, table: QTableWidget, row: int, col: int, course_obj: dict[str, Any]) -> None:
        item = QTableWidgetItem("")
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        cover_url = self._cover_url(course_obj)
        norm_cover = self._normalize_media_url(cover_url)
        item.setData(Qt.ItemDataRole.UserRole, norm_cover)
        table.setItem(row, col, item)
        table.setRowHeight(row, 44)
        if norm_cover:
            self._request_cover_image_async(table, row, col, norm_cover)

    def _image_mime(self, content: bytes, url: str) -> str:
        if content.startswith(b"\x89PNG\r\n\x1a\n"):
            return "image/png"
        if content.startswith(b"\xff\xd8\xff"):
            return "image/jpeg"
        if content.startswith((b"GIF87a", b"GIF89a")):
            return "image/gif"
        if content.startswith(b"RIFF") and content[8:12] == b"WEBP":
            return "image/webp"

        lower = url.lower()
        if lower.endswith(".jpg") or lower.endswith(".jpeg"):
            return "image/jpeg"
        if lower.endswith(".gif"):
            return "image/gif"
        if lower.endswith(".webp"):
            return "image/webp"
        return "image/png"

    def _embedded_image_block(self, url: str, width: int = 640) -> str:
        norm_url = self._normalize_media_url(url)
        if not norm_url:
            return ""

        content = self._fetch_image_bytes(norm_url, timeout=10.0)
        if not content:
            return ""

        mime = self._image_mime(content, norm_url)
        b64 = base64.b64encode(content).decode("ascii")
        return f"<p><img src=\"data:{mime};base64,{b64}\" width=\"{int(width)}\"></p>"

    def _show_map_preview_dialog(
        self,
        title: str,
        lat: float | None,
        lon: float | None,
        radius_m: float | None,
        insecure_tls: bool,
    ) -> None:
        if lat is None or lon is None:
            QMessageBox.information(self, "地图预览", "当前活动没有可用坐标，无法显示地图")
            return

        osm_link = f"https://www.openstreetmap.org/?mlat={lat:.6f}&mlon={lon:.6f}#map=16/{lat:.6f}/{lon:.6f}"
        tencent_key = self.tencent_map_key_input.text().strip()
        if not tencent_key:
            QDesktopServices.openUrl(QUrl(osm_link))
            QMessageBox.information(self, "地图预览", "未配置腾讯地图 Key，已自动跳转浏览器地图。")
            return

        dlg = QDialog(self)
        dlg.setWindowTitle(f"地图预览 - {title or '打卡地点'}")
        dlg.resize(720, 560)

        info_lines = [
            f"位置：{title or '打卡地点'}",
            f"坐标：{lat:.6f}, {lon:.6f}",
        ]
        if radius_m is not None:
            info_lines.append(f"范围：约 {radius_m:.0f} 米")
        info = QLabel("\n".join(info_lines))
        info.setWordWrap(True)

        image_label = QLabel("正在加载地图...")
        image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        image_label.setMinimumHeight(460)

        open_browser_btn = QPushButton("浏览器打开地图")
        open_browser_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(osm_link)))

        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(dlg.accept)

        btn_row = QHBoxLayout()
        btn_row.addWidget(open_browser_btn)
        btn_row.addStretch(1)
        btn_row.addWidget(close_btn)

        layout = QVBoxLayout(dlg)
        layout.addWidget(info)
        layout.addWidget(image_label, 1)
        layout.addLayout(btn_row)

        lat_s = f"{lat:.6f}"
        lon_s = f"{lon:.6f}"
        marker = f"size:large|color:0xFF0000|label:A|{lat_s},{lon_s}"
        map_urls = [
            (
                "https://apis.map.qq.com/ws/staticmap/v2/"
                f"?center={lat_s},{lon_s}&zoom=16&size=680*460&markers={marker}&key={tencent_key}"
            )
        ]

        errors: list[str] = []
        try:
            verify_options: list[bool | str]
            if insecure_tls:
                verify_options = [False]
            else:
                verify_options = [certifi.where(), False]

            content: bytes | None = None
            for verify in verify_options:
                for map_url in map_urls:
                    try:
                        with httpx.Client(
                            timeout=12.0,
                            verify=verify,
                            follow_redirects=True,
                            headers={
                                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
                                " (KHTML, like Gecko) Chrome/123.0 Safari/537.36",
                                "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
                                "Referer": "https://www.openstreetmap.org/",
                            },
                            http2=False,
                        ) as client:
                            resp = client.get(map_url)
                        content_type = str(resp.headers.get("content-type") or "").lower()
                        if 200 <= resp.status_code < 300 and resp.content and ("image/" in content_type or not content_type):
                            content = resp.content
                            break
                        if 200 <= resp.status_code < 300 and "image/" not in content_type:
                            errors.append(f"非图片响应: {content_type or '未知'}")
                        else:
                            errors.append(f"HTTP {resp.status_code}")
                    except Exception as inner_exc:  # noqa: BLE001
                        errors.append(str(inner_exc))
                if content:
                    break

            if content:
                pixmap = QPixmap()
                if pixmap.loadFromData(content):
                    with_circle = pixmap
                    if radius_m is not None:
                        with_circle = self._draw_range_circle_on_map(pixmap, lat, radius_m)
                    image_label.setPixmap(
                        with_circle.scaled(
                            680,
                            460,
                            Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation,
                        )
                    )
                else:
                    image_label.setText("地图图片解析失败")
            else:
                brief = errors[-1] if errors else "未知错误"
                QDesktopServices.openUrl(QUrl(osm_link))
                image_label.setText(
                    f"腾讯地图加载失败: {brief}\n已自动跳转浏览器地图。"
                )
        except Exception as exc:  # noqa: BLE001
            QDesktopServices.openUrl(QUrl(osm_link))
            image_label.setText(
                f"腾讯地图加载失败: {exc}\n已自动跳转浏览器地图。"
            )

        dlg.exec()

    def _first_non_empty(self, data: dict[str, Any], keys: list[str]) -> str:
        for key in keys:
            value = data.get(key)
            if value is None:
                continue
            text = str(value).strip()
            if text and text.lower() not in {"none", "null"}:
                return text
        return ""

    def _parse_duration_minutes(self, value: Any) -> int | None:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return int(round(float(value)))

        text = str(value).strip()
        if not text:
            return None

        if re.fullmatch(r"\d+(?:\.\d+)?", text):
            return int(round(float(text)))

        hour_match = re.search(r"(\d+(?:\.\d+)?)\s*小时", text)
        minute_match = re.search(r"(\d+(?:\.\d+)?)\s*分钟", text)
        if not hour_match and not minute_match:
            return None

        hours = float(hour_match.group(1)) if hour_match else 0.0
        minutes = float(minute_match.group(1)) if minute_match else 0.0
        return int(round(hours * 60 + minutes))

    def _duration_text(self, course_obj: dict[str, Any]) -> str:
        duration_candidates: list[Any] = [
            course_obj.get("duration"),
            course_obj.get("course_duration"),
            course_obj.get("completion_duration"),
            course_obj.get("completion_flag_text"),
        ]

        type_obj = course_obj.get("transcript_index_type")
        if isinstance(type_obj, dict):
            duration_candidates.append(type_obj.get("duration"))

        for candidate in duration_candidates:
            minutes = self._parse_duration_minutes(candidate)
            if minutes is not None and minutes > 0:
                return f"{minutes} 分钟"

        return "无"

    def _score_method_text(self, course_obj: dict[str, Any]) -> str:
        explicit = self._first_non_empty(
            course_obj,
            [
                "completion_flag_text",
                "completion_type_text",
                "score_method",
                "point_method",
                "credit_method",
            ],
        )
        if explicit:
            return explicit

        flag = self._first_non_empty(course_obj, ["completion_flag", "completion_type"]).lower()
        if flag == "time":
            return "按时长累计"
        if flag:
            return f"按{flag}方式累计"

        if self._duration_text(course_obj) != "无":
            return "按时长累计"
        return "按活动要求完成提交"

    def _enroll_status_text(self, course_obj: dict[str, Any]) -> str:
        # 优先读取显式状态字段。
        for key in ["__enrolled", "is_sign", "is_apply", "enrolled", "applied"]:
            if key not in course_obj:
                continue
            value = course_obj.get(key)
            if value in (1, True, "1", "true", "True", "yes", "YES"):
                return "已报名"
            if value in (0, False, "0", "false", "False", "no", "NO"):
                return "未报名"

        status_value = str(course_obj.get("apply_status") or course_obj.get("enroll_status") or "").strip().lower()
        if status_value in {"1", "enrolled", "applied", "success", "signed"}:
            return "已报名"
        if status_value in {"0", "not_enrolled", "none", "unsigned", "cancel"}:
            return "未报名"

        return "未知"

    def _section_html(self, title: str, lines: list[str]) -> str:
        if not lines:
            return ""
        safe_lines = "<br>".join(escape(line).replace("\n", "<br>") for line in lines)
        return f"<h3>{escape(title)}</h3><p>{safe_lines}</p>"

    def _is_image_url(self, text: str) -> bool:
        return (
            re.fullmatch(
                r"https?://\S+\.(?:png|jpg|jpeg|gif|webp|bmp)(?:\?\S*)?",
                text.strip(),
                flags=re.IGNORECASE,
            )
            is not None
        )

    def _looks_like_html(self, text: str) -> bool:
        return re.search(r"</?(?:p|div|span|br|img|ul|ol|li|strong|b|h[1-6])(?:\s|>|/)", text, re.IGNORECASE) is not None

    def _plain_text_from_html(self, text: str) -> str:
        # 用于判断 HTML 是否含有效文本，不用于最终展示。
        stripped = re.sub(r"<[^>]+>", " ", text)
        stripped = re.sub(r"\s+", " ", stripped)
        return stripped.strip()

    def _sanitize_detail_html(self, text: str) -> str:
        # 去掉大量内联样式，避免详情显示臃肿难读。
        cleaned = re.sub(r"\sstyle=(\"[^\"]*\"|'[^']*')", "", text, flags=re.IGNORECASE)
        cleaned = re.sub(r"\sclass=(\"[^\"]*\"|'[^']*')", "", cleaned, flags=re.IGNORECASE)
        return cleaned

    def _extract_image_urls(self, text: str) -> list[str]:
        urls: list[str] = []

        for src in re.findall(r"<img\b[^>]*\ssrc=['\"]([^'\"]+)['\"][^>]*>", text, flags=re.IGNORECASE):
            norm = self._normalize_media_url(src)
            if norm:
                urls.append(norm)

        for match in re.findall(
            r"https?://[^\s<\"']+\.(?:png|jpg|jpeg|gif|webp|bmp)(?:\?[^\s<\"']*)?",
            text,
            flags=re.IGNORECASE,
        ):
            norm = self._normalize_media_url(match)
            if norm:
                urls.append(norm)

        uniq: list[str] = []
        for u in urls:
            if u not in uniq:
                uniq.append(u)
        return uniq

    def _activity_detail_section_html(self, detail_text: str) -> str:
        text = (detail_text or "").strip()
        if not text:
            return self._section_html("活动详情", ["无"])

        if self._is_image_url(text):
            img_url = self._normalize_media_url(text)
            img_block = self._embedded_image_block(img_url, width=640)
            if img_block:
                return f"<h3>活动详情</h3>{img_block}"
            return self._section_html("活动详情", ["图片加载失败"])

        if self._looks_like_html(text):
            image_urls = self._extract_image_urls(text)
            cleaned = self._sanitize_detail_html(text)
            cleaned = re.sub(r"<img\b[^>]*>", "", cleaned, flags=re.IGNORECASE)
            cleaned = re.sub(
                r"https?://[^\s<\"']+\.(?:png|jpg|jpeg|gif|webp|bmp)(?:\?[^\s<\"']*)?",
                "",
                cleaned,
                flags=re.IGNORECASE,
            )
            if not self._plain_text_from_html(cleaned):
                if not image_urls:
                    return self._section_html("活动详情", ["无"])
                image_only = "".join(self._embedded_image_block(u, width=640) for u in image_urls)
                if not image_only:
                    return self._section_html("活动详情", ["图片加载失败"])
                return f"<h3>活动详情</h3>{image_only}"

            img_blocks = "".join(self._embedded_image_block(u, width=640) for u in image_urls)
            return f"<h3>活动详情</h3><div>{cleaned}</div>{img_blocks}"

        return self._section_html("活动详情", [text])

    def _coerce_detail_text(self, value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            text = value.strip()
            if text and text.lower() not in {"none", "null"}:
                return text
            return ""
        if isinstance(value, list):
            parts = [self._coerce_detail_text(v) for v in value]
            parts = [p for p in parts if p]
            return "\n".join(parts)
        if isinstance(value, dict):
            for key in ["detail", "content", "description", "intro", "text", "value", "html"]:
                if key in value:
                    text = self._coerce_detail_text(value.get(key))
                    if text:
                        return text
            return ""
        text = str(value).strip()
        if text and text.lower() not in {"none", "null"}:
            return text
        return ""

    def _activity_detail_text(self, course_obj: dict[str, Any]) -> str:
        preferred_keys = [
            "body",
            "detail",
            "content",
            "description",
            "intro",
            "course_detail",
            "course_content",
            "activity_detail",
            "activity_content",
            "summary",
            "remark",
        ]
        image_only_candidates: list[str] = []
        for key in preferred_keys:
            if key in course_obj:
                text = self._coerce_detail_text(course_obj.get(key))
                if text:
                    if self._is_image_url(text):
                        image_only_candidates.append(text)
                        continue
                    return text

        for nested_key in ["course", "info", "item"]:
            nested_obj = course_obj.get(nested_key)
            if isinstance(nested_obj, dict):
                text = self._activity_detail_text(nested_obj)
                if text:
                    if self._is_image_url(text):
                        image_only_candidates.append(text)
                    else:
                        return text

        # 最后兜底：在对象中挑选最长的可读文本字段，避免误显示“无”。
        fallback_candidates: list[str] = []
        for key, value in course_obj.items():
            if key in {
                "id",
                "title",
                "status",
                "status_label",
                "sign_in_start_time",
                "sign_in_end_time",
                "sign_out_start_time",
                "sign_out_end_time",
                "sign_in_address",
            }:
                continue
            text = self._coerce_detail_text(value)
            if self._is_image_url(text):
                image_only_candidates.append(text)
                continue
            if len(text) >= 12:
                fallback_candidates.append(text)

        if fallback_candidates:
            fallback_candidates.sort(key=len, reverse=True)
            return fallback_candidates[0]

        if image_only_candidates:
            return image_only_candidates[0]

        return ""

    def _format_course_detail_html(self, course_obj: dict[str, Any]) -> str:
        status_raw = course_obj.get("sign_status")
        try:
            if status_raw is None:
                raise ValueError("empty status")
            status_text = STATUS_MAP.get(int(status_raw), str(status_raw))
        except (TypeError, ValueError):
            status_text = "未知"

        max_count = int(course_obj.get("max", 0) or 0)
        apply_count = int(course_obj.get("course_apply_count", 0) or 0)
        surplus = course_obj.get("surplus")
        if surplus is None:
            surplus_text = str(max_count - apply_count)
        else:
            surplus_text = str(surplus)

        enroll_text = self._enroll_status_text(course_obj)

        cat_name = ""
        cat_obj = course_obj.get("transcript_index")
        if isinstance(cat_obj, dict):
            cat_name = str(cat_obj.get("transcript_name") or "")
        if not cat_name:
            cat_name = self._first_non_empty(course_obj, ["transcript_name", "category_name"]) or "未知"

        section_basic = [
            f"课程ID：{course_obj.get('id', '')}",
            f"课程标题：{self._first_non_empty(course_obj, ['title', 'transcript_name']) or '无'}",
            f"所属栏目：{cat_name}",
            f"课程状态：{status_text}",
            f"积分：{self._first_non_empty(course_obj, ['score', 'credit', 'point']) or '无'}",
            f"时长：{self._duration_text(course_obj)}",
        ]

        section_apply = [
            f"报名开始：{self._first_non_empty(course_obj, ['sign_start_time', 'apply_start_time']) or '无'}",
            f"报名截止：{self._first_non_empty(course_obj, ['sign_end_time', 'apply_end_time']) or '无'}",
            f"人数限制：{max_count if max_count > 0 else '无'}",
            f"已报名人数：{apply_count if apply_count > 0 else '0'}",
            f"剩余名额：{surplus_text}",
            f"报名状态：{enroll_text}",
        ]

        college_limit = self._first_non_empty(course_obj, ['college_limit', 'college', 'academy_limit'])
        grade_limit = self._first_non_empty(course_obj, ['grade_limit', 'grade'])
        type_limit = self._first_non_empty(course_obj, ['type_limit', 'student_type_limit'])

        section_limit_lines: list[str] = []
        if college_limit:
            section_limit_lines.append(f"学院限制：{college_limit}")
        if grade_limit:
            section_limit_lines.append(f"年级限制：{grade_limit}")
        if type_limit:
            section_limit_lines.append(f"类型限制：{type_limit}")

        detail_text = self._activity_detail_text(course_obj)
        cover_url = self._cover_url(course_obj)

        time_place_text = self._first_non_empty(course_obj, ['time_place'])
        parsed_time_text, parsed_place_text = extract_time_place_fields(time_place_text)

        place_text = build_display_location(
            time_place_text,
            self._first_non_empty(course_obj, ['place', 'location', 'address']) or parsed_place_text,
        )
        act_start_text = self._first_non_empty(course_obj, ['activity_start_time', 'start_time']) or parsed_time_text
        act_end_text = self._first_non_empty(course_obj, ['activity_end_time', 'end_time'])

        sign_in_start = self._first_non_empty(course_obj, ['sign_in_start_time'])
        sign_in_end = self._first_non_empty(course_obj, ['sign_in_end_time'])
        sign_out_start = self._first_non_empty(course_obj, ['sign_out_start_time'])
        sign_out_end = self._first_non_empty(course_obj, ['sign_out_end_time'])
        sign_place_text = self._first_non_empty(course_obj, ['sign_place', 'checkin_location'])
        map_name, map_lat, map_lon, map_radius_m = self._extract_checkin_location(course_obj)

        section_time_place = [
            f"地点：{place_text or '无'}",
            f"活动开始：{act_start_text or '无'}",
            f"活动结束：{act_end_text or '无'}",
        ]

        section_checkin_lines = [
            f"签到时间：{sign_in_start or '无'} 至 {sign_in_end or '无'}",
            f"签退时间：{sign_out_start or '无'} 至 {sign_out_end or '无'}",
        ]
        if map_radius_m is not None:
            section_checkin_lines.append(f"签到范围：约 {map_radius_m:.0f} 米")
        if map_lat is not None and map_lon is not None:
            label = map_name or sign_place_text or "打卡地点"
            section_checkin_html_place = f"打卡地点：{escape(label)}（可点下方“显示地图”）"
        elif sign_place_text:
            section_checkin_html_place = f"打卡地点：{escape(sign_place_text)}"
        else:
            section_checkin_html_place = "打卡地点：无"

        contact_name = self._first_non_empty(course_obj, ['contact', 'contact_name', 'teacher'])
        contact_phone = self._first_non_empty(course_obj, ['phone', 'contact_phone', 'mobile'])
        section_contact = [
            f"联系人：{contact_name or '无'}",
            f"联系电话：{contact_phone or '无'}",
        ]

        section_score_method = [f"积分方式：{self._score_method_text(course_obj)}"]

        blocks: list[str] = []
        if cover_url:
            cover_block = self._embedded_image_block(cover_url, width=680)
            if cover_block:
                blocks.append(cover_block)
        blocks.append(self._section_html("基础信息", section_basic))
        blocks.append(self._section_html("报名信息", section_apply))

        if section_limit_lines:
            blocks.append(self._section_html("报名限制", section_limit_lines))

        blocks.append(self._activity_detail_section_html(detail_text))

        has_time_place = any([place_text, act_start_text, act_end_text])
        if has_time_place:
            blocks.append(self._section_html("时间地点", section_time_place))

        has_checkin = any([sign_in_start, sign_in_end, sign_out_start, sign_out_end, sign_place_text])
        if has_checkin:
            checkin_html = "<h3>打卡方式</h3><p>"
            checkin_html += "<br>".join(escape(line) for line in section_checkin_lines)
            checkin_html += "<br>" + section_checkin_html_place + "</p>"
            blocks.append(checkin_html)
        else:
            # 无打卡方式时，展示积分方式。
            blocks.append(self._section_html("积分方式", section_score_method))

        has_contact = any([contact_name, contact_phone])
        if has_contact:
            blocks.append(self._section_html("联系方式", section_contact))

        return "".join(blocks)

    def _show_qrcode_dialog(self, table: QTableWidget, row: int) -> None:
        """显示二维码对话框."""
        course_id_item = table.item(row, 0)
        if course_id_item is None:
            QMessageBox.warning(self, "提示", "无法获取课程 ID")
            return

        try:
            course_id = int(course_id_item.text().strip())
        except ValueError:
            QMessageBox.warning(self, "提示", "课程 ID 格式错误")
            return

        course_payload = course_id_item.data(Qt.ItemDataRole.UserRole)

        # 获取课程标题（通常在第 2 或第 3 列）
        course_title = ""
        if isinstance(course_payload, dict):
            course_title = str(course_payload.get("title") or course_payload.get("course_title") or "").strip()

        for col in range(1, min(4, table.columnCount())):
            if course_title:
                break
            title_item = table.item(row, col)
            if title_item is not None:
                text = title_item.text().strip()
                if text and text not in ("", "加载中..."):
                    course_title = text
                    break

        sign_in_window = ""
        sign_out_window = ""
        if isinstance(course_payload, dict):
            sign_in_start = str(course_payload.get("sign_in_start_time") or "")
            sign_in_end = str(course_payload.get("sign_in_end_time") or "")
            sign_out_start = str(course_payload.get("sign_out_start_time") or "")
            sign_out_end = str(course_payload.get("sign_out_end_time") or "")
            sign_in_window = self._window_text(sign_in_start, sign_in_end)
            sign_out_window = self._window_text(sign_out_start, sign_out_end)

        # 若行数据没有完整时间字段，回退到表格列显示值。
        if not sign_in_window or not sign_out_window:
            for col in range(table.columnCount()):
                header_item = table.horizontalHeaderItem(col)
                cell_item = table.item(row, col)
                if header_item is None or cell_item is None:
                    continue

                header_text = header_item.text().strip()
                cell_text = cell_item.text().strip()
                if (not sign_in_window) and header_text in ("签到窗口", "签到"):
                    sign_in_window = cell_text
                if (not sign_out_window) and header_text in ("签退窗口", "签退"):
                    sign_out_window = cell_text

        # 创建并显示二维码对话框
        dialog = QRCodeDialog(
            parent=self,
            course_id=course_id,
            course_title=course_title,
            sign_in_window=sign_in_window,
            sign_out_window=sign_out_window,
        )
        dialog.load_qrcode()
        dialog.exec()

    def _run_monitor_course_action(self, action: str, course_id_text: str) -> None:
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
        self,
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

    def _on_monitor_course_action_done(self, result: tuple[bool, str]) -> None:
        ok, msg = result
        if ok:
            self._set_status(msg)
            self.on_monitor_once(silent_if_no_token=True)
        else:
            self._set_status(msg)

    def _on_monitor_status_changed(self, _index: int) -> None:
        self.on_monitor_once(silent_if_no_token=True)

    def _build_placeholder_tab(self, message: str) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.addWidget(QLabel(message))
        layout.addStretch(1)
        return tab

    def _cfg_from_inputs(self) -> AppConfig:
        return AppConfig(
            token=self.token_input.text().strip(),
            github_token=self.github_token_input.text().strip(),
            gist_id=self.gist_id_input.text().strip(),
            gist_filename=self.gist_filename_input.text().strip() or "bit_cookies.json",
            tencent_map_key=self.tencent_map_key_input.text().strip(),
            tls_insecure=self.tls_insecure_checkbox.isChecked(),
            signup_queue_text="",
            whitelist_category_ids=self.whitelist_category_ids_input.text().strip(),
            whitelist_grade=self.whitelist_grade_input.text().strip(),
            whitelist_academy=self.whitelist_academy_input.text().strip(),
            activities_has_checkin_only=self._activities_checkin_only(),
        )

    def _append_log(self, text: str) -> None:
        self.log_box.appendPlainText(text)

    def _set_status(self, text: str) -> None:
        self.status_label.setText(text)
        self._append_log(text)

    def on_save(self) -> None:
        self.config = self._cfg_from_inputs()
        self.config.token = normalize_bearer_token(self.config.token)
        self.token_input.setText(self.config.token)
        save_config(self.config)
        self._set_status("凭据已保存")

    def on_verify_token(self) -> None:
        token = self.token_input.text().strip()
        if not token:
            QMessageBox.warning(self, "提示", "Token 为空")
            return

        self._set_status("正在验证 Token...")
        worker = Worker(verify_token, token, 12.0, self.tls_insecure_checkbox.isChecked())
        worker.signals.done.connect(self._on_verify_done)
        self.pool.start(worker)

    def _on_verify_done(self, result) -> None:
        if result.ok:
            self._set_status(f"Token 有效，user_id={result.user_id or '未知'}")
        else:
            self._set_status(f"Token 无效：{result.message}")

    def on_pull_gist(self) -> None:
        cfg = self._cfg_from_inputs()
        self._set_status("正在从 Gist 加载 Token...")
        worker = Worker(
            fetch_token_from_gist,
            cfg.github_token,
            cfg.gist_id,
            cfg.gist_filename,
            12.0,
            cfg.tls_insecure,
        )
        worker.signals.done.connect(self._on_pull_gist_done)
        self.pool.start(worker)

    def _on_pull_gist_done(self, result) -> None:
        ok, token, msg = result
        if ok:
            self.token_input.setText(token)
            self._set_status(msg)
        else:
            self._set_status(f"从 Gist 加载 Token 失败：{msg}")

    def on_monitor_once(self, silent_if_no_token: bool = False) -> None:
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
        self,
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

    def _on_monitor_done(self, result: dict[int, dict[str, Any]]) -> None:
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

    # ============ 日历功能 ============

    def on_calendar_refresh(self, silent_if_no_token: bool = False) -> None:
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
        self, token: str, insecure: bool
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

        # my_course_ids接口偶发失败时，兜底用“我的活动”列表提取ID。
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

    def _on_calendar_refresh_done(self, result) -> None:
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

    def on_calendar_signup(self, course_id: int) -> None:
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

    def on_calendar_cancel(self, course_id: int) -> None:
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

    def _do_cancel_course(self, token: str, course_id: int, insecure: bool) -> tuple[bool, str]:
        """执行取消报名（先获取user_id）。"""
        ok, user_id, msg = get_user_id(token, 12.0, insecure)
        if not ok:
            return False, f"获取用户ID失败: {msg}"
        
        return cancel_course(token, course_id, int(user_id), 12.0, insecure)

    def on_calendar_checkin(self, course_id: int) -> None:
        """日历打卡（签到/签退）。"""
        token = self.token_input.text().strip()
        if not token:
            QMessageBox.warning(self, "提示", "Token 为空")
            return
        
        self._set_status(f"正在获取打卡信息 {course_id}...")
        insecure = self.tls_insecure_checkbox.isChecked()
        worker = Worker(self._do_checkin, token, course_id, insecure)
        worker.signals.done.connect(self._on_calendar_checkin_done)
        self.pool.start(worker)

    def _do_checkin(self, token: str, course_id: int, insecure: bool) -> tuple[bool, str, dict]:
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

    def _on_calendar_checkin_done(self, result) -> None:
        """打卡完成回调。"""
        ok, msg, _ = result
        if ok:
            self._set_status(f"打卡成功: {msg}")
            # 刷新日历
            self.on_calendar_refresh(silent_if_no_token=True)
        else:
            self._set_status(f"打卡失败: {msg}")

    def _on_calendar_action_result(self, action_name: str, course_id: int, result: object) -> None:
        """统一处理日历报名/取消报名的 worker 结果。"""
        if not isinstance(result, tuple) or len(result) != 2:
            self._set_status(f"{action_name}失败: 返回结果格式异常")
            return

        ok_raw, msg_raw = result
        self._on_calendar_action_done(action_name, bool(ok_raw), str(msg_raw), course_id)

    def _sync_calendar_enrollment_cache(self, course_id: int, enrolled: bool) -> None:
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
        self,
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

    def on_calendar_detail(self, course_id: int) -> None:
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

    def _on_calendar_detail_done(self, result) -> None:
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

    def _format_event_detail(self, detail: dict) -> str:
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

    def on_calendar_export_ics(self, events) -> None:
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

