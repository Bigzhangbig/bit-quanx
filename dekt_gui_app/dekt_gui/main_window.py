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
    get_transcript_score,
    get_user_id,
    list_my_courses,
    list_my_course_ids,
    list_courses,
    normalize_bearer_token,
    submit_sign_action,
    verify_token,
)
from .activities_mixin import ActivitiesMixin
from .calendar_mixin import CalendarMixin
from .calendar_widget import CalendarWidget
from .detail_mixin import DetailMixin
from .image_mixin import ImageMixin
from .monitor_mixin import MonitorMixin
from .profile_widget import ProfileWidget
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


class MainWindow(CalendarMixin, MonitorMixin, ImageMixin, DetailMixin, ActivitiesMixin, QMainWindow):
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
        self._open_dialogs: list[QDialog] = []

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

        # 个人详情widget
        self.profile_widget = ProfileWidget()

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
        self.main_tabs.addTab(self.profile_widget, "个人")
        self.main_tabs.currentChanged.connect(self._on_main_tab_changed)

        logs_panel = QWidget()
        self.logs_panel = logs_panel  # 保存引用以便切换
        logs_layout = QVBoxLayout(logs_panel)
        logs_layout.setContentsMargins(0, 0, 0, 0)
        logs_layout.addWidget(QLabel("日志"))
        logs_layout.addWidget(self.log_box, 1)
        logs_panel.hide()  # 默认隐藏

        main_splitter = QSplitter(Qt.Orientation.Vertical)
        main_splitter.setChildrenCollapsible(False)
        main_splitter.addWidget(self.main_tabs)
        main_splitter.addWidget(logs_panel)
        main_splitter.setStretchFactor(0, 4)
        main_splitter.setStretchFactor(1, 1)
        main_splitter.setSizes([500, 140])

        layout.addWidget(main_splitter, 1)
        
        # 底部状态栏和切换日志按钮
        bottom_bar = QWidget()
        bottom_layout = QHBoxLayout(bottom_bar)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_layout.addWidget(self.status_label, 1)
        
        self.toggle_log_btn = QPushButton("显示日志")
        self.toggle_log_btn.setFixedWidth(80)
        self.toggle_log_btn.clicked.connect(self._toggle_logs)
        bottom_layout.addWidget(self.toggle_log_btn)
        
        layout.addWidget(bottom_bar)

        self.setCentralWidget(root)

    def _toggle_logs(self) -> None:
        """切换日志面板的显示/隐藏。"""
        if self.logs_panel.isVisible():
            self.logs_panel.hide()
            self.toggle_log_btn.setText("显示日志")
        else:
            self.logs_panel.show()
            self.toggle_log_btn.setText("隐藏日志")

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
        elif tab_name == "个人":
            self.on_profile_refresh(silent_if_no_token=True)

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

    def _on_monitor_item_double_clicked(self, item: QTableWidgetItem) -> None:
        table = item.tableWidget()
        if table is None:
            return

        id_item = table.item(item.row(), 0)
        if id_item is None:
            return
        self._open_course_detail_by_id_item(id_item)

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

