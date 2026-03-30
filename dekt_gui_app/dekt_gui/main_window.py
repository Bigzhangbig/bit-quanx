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
from PySide6.QtCore import QObject, QRunnable, QThreadPool, Qt, Signal
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
    VerifyResult,
    apply_course,
    backend_health_check,
    backend_signed_get,
    backend_signed_post,
    backend_signed_put,
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
from .config import AppConfig, load_config, save_config


CATEGORIES = [
    (1, "理想信念"),
    (2, "科学素养"),
    (3, "社会贡献"),
    (4, "团队协作"),
    (5, "文化互鉴"),
    (6, "健康生活"),
]

STATUS_MAP = {
    1: "未开始",
    2: "进行中",
    3: "已结束",
}


class WorkerSignals(QObject):
    done = Signal(object)


class Worker(QRunnable):
    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()

    def run(self):
        result = self.fn(*self.args, **self.kwargs)
        self.signals.done.emit(result)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("DEKT Desktop (alpha)")
        self.resize(900, 600)

        self.pool = QThreadPool.globalInstance()
        self.config = load_config()
        self._last_monitor_sign_status = 1
        self._image_bytes_cache: dict[str, bytes | None] = {}
        self._pixmap_cache: dict[str, QPixmap | None] = {}
        self._cover_waiters: dict[str, list[tuple[QTableWidget, int, int]]] = {}
        self._cover_loading_urls: set[str] = set()

        self.token_input = QLineEdit(self.config.token)
        self.token_input.setPlaceholderText("Bearer xxx or raw token")

        self.github_token_input = QLineEdit(self.config.github_token)
        self.github_token_input.setPlaceholderText("GitHub personal access token")
        self.github_token_input.setEchoMode(QLineEdit.EchoMode.Password)

        self.gist_id_input = QLineEdit(self.config.gist_id)
        self.gist_id_input.setPlaceholderText("Gist ID")

        self.gist_filename_input = QLineEdit(self.config.gist_filename)
        self.gist_filename_input.setPlaceholderText("bit_cookies.json")

        self.tencent_map_key_input = QLineEdit(self.config.tencent_map_key)
        self.tencent_map_key_input.setPlaceholderText("Tencent map key (for static map)")

        self.tls_insecure_checkbox = QCheckBox("Ignore TLS certificate verification (debug only)")
        self.tls_insecure_checkbox.setChecked(self.config.tls_insecure)

        self.backend_mode_checkbox = QCheckBox("Use backend mode (signed API calls)")
        self.backend_mode_checkbox.setChecked(self.config.backend_mode)

        self.backend_base_url_input = QLineEdit(self.config.backend_base_url)
        self.backend_base_url_input.setPlaceholderText("https://backend.example.com")

        self.backend_api_key_input = QLineEdit(self.config.backend_api_key)
        self.backend_api_key_input.setPlaceholderText("Backend API key")
        self.backend_api_key_input.setEchoMode(QLineEdit.EchoMode.Password)

        self.whitelist_category_ids_input = QLineEdit(self.config.whitelist_category_ids)
        self.whitelist_category_ids_input.setPlaceholderText("1,2,3,4,5,6")

        self.whitelist_grade_input = QLineEdit(self.config.whitelist_grade)
        self.whitelist_grade_input.setPlaceholderText("2024,2025")

        self.whitelist_academy_input = QLineEdit(self.config.whitelist_academy)
        self.whitelist_academy_input.setPlaceholderText("计算机学院,睿信书院")

        self.monitor_status_combo = QComboBox()
        self.monitor_status_combo.addItem("未开始", 1)
        self.monitor_status_combo.addItem("进行中", 2)
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
        self.activities_table.itemDoubleClicked.connect(self._on_activities_item_double_clicked)

        self.status_label = QLabel("Ready")
        self.log_box = QPlainTextEdit()
        self.log_box.setReadOnly(True)

        self._build_ui()
        self._append_log("GUI initialized")

    def _build_ui(self) -> None:
        root = QWidget()
        layout = QVBoxLayout(root)

        self.main_tabs = QTabWidget()
        self.main_tabs.addTab(self._build_credentials_tab(), "Credentials")
        self.main_tabs.addTab(self._build_monitor_tab(), "Monitor")
        self.main_tabs.addTab(self._build_sign_tab(), "Sign")
        self.main_tabs.addTab(self._build_activities_tab(), "Activities")
        self.main_tabs.currentChanged.connect(self._on_main_tab_changed)

        logs_panel = QWidget()
        logs_layout = QVBoxLayout(logs_panel)
        logs_layout.setContentsMargins(0, 0, 0, 0)
        logs_layout.addWidget(QLabel("Logs"))
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

        cred_box = QGroupBox("Credentials")
        form = QFormLayout(cred_box)
        form.addRow("DEKT token", self.token_input)
        form.addRow("GitHub token", self.github_token_input)
        form.addRow("Gist ID", self.gist_id_input)
        form.addRow("Gist file", self.gist_filename_input)
        form.addRow("Tencent map key", self.tencent_map_key_input)
        form.addRow("TLS", self.tls_insecure_checkbox)
        form.addRow("Backend mode", self.backend_mode_checkbox)
        form.addRow("Backend URL", self.backend_base_url_input)
        form.addRow("Backend API key", self.backend_api_key_input)
        form.addRow("Whitelist categories", self.whitelist_category_ids_input)
        form.addRow("Whitelist grade", self.whitelist_grade_input)
        form.addRow("Whitelist academy", self.whitelist_academy_input)

        btn_row = QHBoxLayout()
        save_btn = QPushButton("Save credentials")
        save_btn.clicked.connect(self.on_save)

        verify_btn = QPushButton("Verify token")
        verify_btn.clicked.connect(self.on_verify_token)

        pull_gist_btn = QPushButton("Load token from Gist")
        pull_gist_btn.clicked.connect(self.on_pull_gist)

        backend_ping_btn = QPushButton("Test backend connection")
        backend_ping_btn.clicked.connect(self.on_backend_ping)

        backend_sync_token_btn = QPushButton("Sync token to backend")
        backend_sync_token_btn.clicked.connect(self.on_backend_sync_token)

        backend_push_cfg_btn = QPushButton("Sync whitelist to backend")
        backend_push_cfg_btn.clicked.connect(self.on_backend_push_config)

        backend_pull_cfg_btn = QPushButton("Load whitelist from backend")
        backend_pull_cfg_btn.clicked.connect(self.on_backend_pull_config)

        btn_row.addWidget(save_btn)
        btn_row.addWidget(verify_btn)
        btn_row.addWidget(pull_gist_btn)
        btn_row.addWidget(backend_ping_btn)
        btn_row.addWidget(backend_sync_token_btn)
        btn_row.addWidget(backend_push_cfg_btn)
        btn_row.addWidget(backend_pull_cfg_btn)
        btn_row.addStretch(1)

        layout.addWidget(cred_box)
        layout.addLayout(btn_row)
        layout.addStretch(1)

        return tab

    def _build_monitor_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        controls = QGroupBox("Manual monitor run")
        form = QFormLayout(controls)

        status_row = QWidget()
        status_row_layout = QHBoxLayout(status_row)
        status_row_layout.setContentsMargins(0, 0, 0, 0)
        status_row_layout.addWidget(self.monitor_status_combo)

        run_btn = QPushButton("Refresh now")
        run_btn.clicked.connect(lambda: self.on_monitor_once(silent_if_no_token=False))
        status_row_layout.addWidget(run_btn)
        status_row_layout.addStretch(1)

        form.addRow("Sign status", status_row)
        form.addRow("Limit", self.monitor_limit_spin)

        layout.addWidget(controls)
        layout.addWidget(self.monitor_result_tabs, 1)
        return tab

    def _build_sign_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        controls = QGroupBox("Sign-in/out")
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

        controls = QGroupBox("My activities")
        row = QHBoxLayout(controls)
        refresh_btn = QPushButton("刷新我的活动")
        refresh_btn.clicked.connect(self.on_activities_refresh)
        row.addWidget(refresh_btn)
        row.addStretch(1)

        layout.addWidget(controls)
        layout.addWidget(self.activities_table, 1)
        return tab

    def _on_main_tab_changed(self, index: int) -> None:
        if index < 0:
            return
        tab_name = self.main_tabs.tabText(index)
        if tab_name == "Monitor":
            self.on_monitor_once(silent_if_no_token=True)
        elif tab_name == "Sign":
            self.on_sign_refresh(silent_if_no_token=True)
        elif tab_name == "Activities":
            self.on_activities_refresh(silent_if_no_token=True)

    def on_sign_refresh(self, silent_if_no_token: bool = False) -> None:
        insecure = self.tls_insecure_checkbox.isChecked()
        if self.backend_mode_checkbox.isChecked():
            base_url = self.backend_base_url_input.text().strip()
            api_key = self.backend_api_key_input.text().strip()
            if not base_url or not api_key:
                if not silent_if_no_token:
                    QMessageBox.warning(self, "Warning", "Backend URL/API key is empty")
                return

            self._set_status("Loading signable activities from backend...")
            worker = Worker(self._fetch_my_courses_backend, base_url, api_key, insecure)
        else:
            token = self.token_input.text().strip()
            if not token:
                if not silent_if_no_token:
                    QMessageBox.warning(self, "Warning", "Token is empty")
                return

            self._set_status("Loading signable activities...")
            worker = Worker(self._fetch_my_courses, token, insecure)
        worker.signals.done.connect(self._on_sign_refresh_done)
        self.pool.start(worker)

    def on_activities_refresh(self, silent_if_no_token: bool = False) -> None:
        insecure = self.tls_insecure_checkbox.isChecked()
        if self.backend_mode_checkbox.isChecked():
            base_url = self.backend_base_url_input.text().strip()
            api_key = self.backend_api_key_input.text().strip()
            if not base_url or not api_key:
                if not silent_if_no_token:
                    QMessageBox.warning(self, "Warning", "Backend URL/API key is empty")
                return

            self._set_status("Loading my activities from backend...")
            worker = Worker(self._fetch_my_courses_backend, base_url, api_key, insecure)
        else:
            token = self.token_input.text().strip()
            if not token:
                if not silent_if_no_token:
                    QMessageBox.warning(self, "Warning", "Token is empty")
                return

            self._set_status("Loading my activities...")
            worker = Worker(self._fetch_my_courses, token, insecure)
        worker.signals.done.connect(self._on_activities_refresh_done)
        self.pool.start(worker)

    def _fetch_my_courses(self, token: str, insecure: bool) -> tuple[bool, str, list[dict[str, Any]]]:
        return list_my_courses(
            token=token,
            limit=200,
            timeout=15.0,
            insecure_tls=insecure,
        )

    def _fetch_my_courses_backend(
        self,
        base_url: str,
        api_key: str,
        insecure: bool,
    ) -> tuple[bool, str, list[dict[str, Any]]]:
        ok, msg, data = backend_signed_get(
            base_url=base_url,
            path="/api/v1/courses/my",
            api_key=api_key,
            timeout=15.0,
            insecure_tls=insecure,
        )
        if not ok:
            return False, msg, []

        items_obj = data.get("data") if isinstance(data, dict) else []
        items = items_obj if isinstance(items_obj, list) else []
        return True, "OK", [i for i in items if isinstance(i, dict)]

    def _window_text(self, start: str, end: str) -> str:
        if start and end:
            return f"{start} ~ {end}"
        return ""

    def _on_sign_refresh_done(self, result: tuple[bool, str, list[dict[str, Any]]]) -> None:
        ok, msg, items = result
        if not ok:
            self._set_status(f"Load sign activities failed: {msg}")
            return

        self.sign_table.setRowCount(0)
        row_idx = 0
        for course in items:
            if not isinstance(course, dict):
                continue

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

            # Sign 页只显示有签到或签退窗口的课程。
            if not sign_in_window and not sign_out_window:
                continue

            # Sign 页隐藏已结束活动：优先使用签退结束时间，其次签到结束时间。
            end_raw = str(course.get("sign_out_end_time") or course.get("sign_in_end_time") or "")
            end_dt = self._parse_time(end_raw)
            if end_dt is not None and end_dt < datetime.now():
                continue

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

        self._set_status(f"Sign activities loaded: {self.sign_table.rowCount()}")

    def _on_activities_refresh_done(self, result: tuple[bool, str, list[dict[str, Any]]]) -> None:
        ok, msg, items = result
        if not ok:
            self._set_status(f"Load activities failed: {msg}")
            return

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

        self._set_status(f"Activities loaded: {self.activities_table.rowCount()}")

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

        if self.backend_mode_checkbox.isChecked():
            base_url = self.backend_base_url_input.text().strip()
            api_key = self.backend_api_key_input.text().strip()
            if not base_url or not api_key:
                QMessageBox.warning(self, "课程详情", "Backend URL/API key is empty")
                return

            self._set_status(f"Loading course detail from backend: {course_id}")
            worker = Worker(
                self._load_course_detail_backend,
                base_url,
                api_key,
                course_id,
                fallback_obj,
                insecure,
            )
            worker.signals.done.connect(self._on_course_detail_loaded)
            self.pool.start(worker)
            return

        token = self.token_input.text().strip()
        if not token:
            QMessageBox.warning(self, "课程详情", "Token is empty")
            return

        self._set_status(f"Loading course detail: {course_id}")
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
            QMessageBox.warning(self, "Warning", "请先选择一条活动")
            return

        id_item = self.sign_table.item(row, 0)
        if id_item is None:
            return
        course_id_text = (id_item.text() or "").strip()
        if not course_id_text.isdigit():
            QMessageBox.warning(self, "Warning", f"无效课程 ID: {course_id_text}")
            return

        token = self.token_input.text().strip()
        if (not self.backend_mode_checkbox.isChecked()) and (not token):
            QMessageBox.warning(self, "Warning", "Token is empty")
            return

        fallback_obj = id_item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(fallback_obj, dict):
            fallback_obj = {}

        course_id = int(course_id_text)
        insecure = self.tls_insecure_checkbox.isChecked()
        self._set_status(f"Running {action} for {course_id}...")
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
        if self.backend_mode_checkbox.isChecked():
            base_url = self.backend_base_url_input.text().strip()
            api_key = self.backend_api_key_input.text().strip()
            ok_info, msg_info, data_info = backend_signed_get(
                base_url=base_url,
                path=f"/api/v1/courses/{course_id}/checkin-info",
                api_key=api_key,
                timeout=12.0,
                insecure_tls=insecure,
            )
            info_obj = data_info.get("data") if isinstance(data_info, dict) else {}
            if not ok_info:
                return False, f"获取打卡信息失败: {msg_info}"
            info = info_obj if isinstance(info_obj, dict) else {}
        else:
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

        if self.backend_mode_checkbox.isChecked():
            base_url = self.backend_base_url_input.text().strip()
            api_key = self.backend_api_key_input.text().strip()
            action_path = "sign-in" if action == "signIn" else "sign-out"
            ok_sign, sign_msg, _data = backend_signed_post(
                base_url=base_url,
                path=f"/api/v1/courses/{course_id}/{action_path}",
                api_key=api_key,
                body={
                    "address": address,
                    "latitude": latitude_value,
                    "longitude": longitude_value,
                },
                timeout=12.0,
                insecure_tls=insecure,
            )
        else:
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

        selected = menu.exec(table.viewport().mapToGlobal(pos))
        if selected is signup_action:
            self._run_monitor_course_action("signup", course_item.text().strip())
        elif selected is cancel_action:
            self._run_monitor_course_action("cancel", course_item.text().strip())

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

    def _load_course_detail_backend(
        self,
        base_url: str,
        api_key: str,
        course_id: int,
        fallback_obj: dict[str, Any],
        insecure: bool,
    ) -> tuple[bool, str, dict[str, Any]]:
        ok, msg, data = backend_signed_get(
            base_url=base_url,
            path=f"/api/v1/courses/{course_id}/detail",
            api_key=api_key,
            timeout=12.0,
            insecure_tls=insecure,
        )

        merged = dict(fallback_obj)
        detail_obj = data.get("data") if isinstance(data, dict) else {}
        if isinstance(detail_obj, dict):
            merged.update(detail_obj)
            for nested_key in ["course", "info", "item"]:
                nested_obj = detail_obj.get(nested_key)
                if isinstance(nested_obj, dict):
                    merged.update(nested_obj)

        # Activities 列表来自 /courses/my，详情默认视为已报名。
        if "__enrolled" not in merged:
            merged["__enrolled"] = True

        cover_url = self._normalize_media_url(self._cover_url(merged))
        if cover_url and cover_url not in self._image_bytes_cache:
            _u, content = self._download_image_bytes_task(cover_url, insecure, 10.0)
            self._image_bytes_cache[cover_url] = content

        return ok, msg, merged

    def _on_course_detail_loaded(self, result: tuple[bool, str, dict[str, Any]]) -> None:
        ok, msg, course_obj = result
        if not ok:
            self._set_status(f"Course detail fallback: {msg}")
        else:
            self._set_status("Course detail loaded")

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
            try:
                lat = float(first.get("latitude"))
                lon = float(first.get("longitude"))
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
                            errors.append(f"非图片响应: {content_type or 'unknown'}")
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

        place_text = self._first_non_empty(course_obj, ['place', 'location', 'address'])
        act_start_text = self._first_non_empty(course_obj, ['activity_start_time', 'start_time'])
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

    def _run_monitor_course_action(self, action: str, course_id_text: str) -> None:
        token = self.token_input.text().strip()
        if (not self.backend_mode_checkbox.isChecked()) and (not token):
            QMessageBox.warning(self, "Warning", "Token is empty")
            return

        if not course_id_text.isdigit():
            QMessageBox.warning(self, "Warning", f"Invalid course id: {course_id_text}")
            return

        course_id = int(course_id_text)
        insecure = self.tls_insecure_checkbox.isChecked()
        self._set_status(f"Running {action} for course {course_id}...")

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
        if self.backend_mode_checkbox.isChecked():
            base_url = self.backend_base_url_input.text().strip()
            api_key = self.backend_api_key_input.text().strip()

            if action == "signup":
                ok, msg, _data = backend_signed_post(
                    base_url=base_url,
                    path=f"/api/v1/courses/{course_id}/apply",
                    api_key=api_key,
                    body={},
                    timeout=12.0,
                    insecure_tls=insecure,
                )
                return ok, f"Signup course {course_id}: {msg}"

            if action == "cancel":
                ok, msg, _data = backend_signed_post(
                    base_url=base_url,
                    path=f"/api/v1/courses/{course_id}/cancel",
                    api_key=api_key,
                    body={},
                    timeout=12.0,
                    insecure_tls=insecure,
                )
                return ok, f"Cancel course {course_id}: {msg}"

            return False, f"Unknown action: {action}"

        ok, msg, enrolled_ids = list_my_course_ids(
            token=token,
            limit=300,
            timeout=12.0,
            insecure_tls=insecure,
        )
        if not ok:
            return False, f"Pre-check failed: {msg}"

        is_enrolled = course_id in enrolled_ids

        if action == "signup":
            if is_enrolled:
                return False, f"Course {course_id} already enrolled"
            ok_apply, apply_msg = apply_course(
                token=token,
                course_id=course_id,
                template_id=DEFAULT_TEMPLATE_ID,
                timeout=12.0,
                insecure_tls=insecure,
            )
            return ok_apply, f"Signup course {course_id}: {apply_msg}"

        if action == "cancel":
            if not is_enrolled:
                return False, f"Course {course_id} is not enrolled"

            ok_uid, user_id, uid_msg = get_user_id(
                token=token,
                timeout=12.0,
                insecure_tls=insecure,
            )
            if not ok_uid:
                return False, f"Failed to get user_id: {uid_msg}"

            ok_cancel, cancel_msg = cancel_course(
                token=token,
                course_id=course_id,
                user_id=int(user_id),
                timeout=12.0,
                insecure_tls=insecure,
            )
            return ok_cancel, f"Cancel course {course_id}: {cancel_msg}"

        return False, f"Unknown action: {action}"

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
            backend_mode=self.backend_mode_checkbox.isChecked(),
            backend_base_url=self.backend_base_url_input.text().strip() or "https://127.0.0.1:8000",
            backend_api_key=self.backend_api_key_input.text().strip(),
            whitelist_category_ids=self.whitelist_category_ids_input.text().strip(),
            whitelist_grade=self.whitelist_grade_input.text().strip(),
            whitelist_academy=self.whitelist_academy_input.text().strip(),
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
        self._set_status("Credentials saved")

    def on_verify_token(self) -> None:
        token = self.token_input.text().strip()
        if not token:
            QMessageBox.warning(self, "Warning", "Token is empty")
            return

        self._set_status("Verifying token...")
        if self.backend_mode_checkbox.isChecked():
            worker = Worker(
                self._verify_token_backend_task,
                self.backend_base_url_input.text().strip(),
                self.backend_api_key_input.text().strip(),
                token,
                self.tls_insecure_checkbox.isChecked(),
            )
        else:
            worker = Worker(verify_token, token, 12.0, self.tls_insecure_checkbox.isChecked())
        worker.signals.done.connect(self._on_verify_done)
        self.pool.start(worker)

    def _verify_token_backend_task(
        self,
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
        return VerifyResult(ok=True, message="Token is valid", user_id=user_id)

    def _on_verify_done(self, result) -> None:
        if result.ok:
            self._set_status(f"Token valid. user_id={result.user_id or 'unknown'}")
        else:
            self._set_status(f"Token invalid: {result.message}")

    def on_pull_gist(self) -> None:
        cfg = self._cfg_from_inputs()
        self._set_status("Loading token from Gist...")
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
            self._set_status(f"Failed to load token from Gist: {msg}")

    def on_backend_ping(self) -> None:
        base_url = self.backend_base_url_input.text().strip()
        if not base_url:
            QMessageBox.warning(self, "Warning", "Backend URL is empty")
            return

        self._set_status("Checking backend health...")
        worker = Worker(
            backend_health_check,
            base_url,
            8.0,
            self.tls_insecure_checkbox.isChecked(),
        )
        worker.signals.done.connect(self._on_backend_ping_done)
        self.pool.start(worker)

    def _on_backend_ping_done(self, result: tuple[bool, str]) -> None:
        ok, msg = result
        if ok:
            self._set_status(f"Backend reachable: {msg}")
        else:
            self._set_status(f"Backend unreachable: {msg}")

    def on_backend_sync_token(self) -> None:
        base_url = self.backend_base_url_input.text().strip()
        api_key = self.backend_api_key_input.text().strip()
        token = self.token_input.text().strip()

        if not token:
            QMessageBox.warning(self, "Warning", "Token is empty")
            return

        self._set_status("Syncing token to backend...")
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

    def _on_backend_sync_token_done(self, result: tuple[bool, str, dict[str, Any]]) -> None:
        ok, msg, _data = result
        if ok:
            self._set_status("Token synced to backend")
            return
        self._set_status(f"Token sync failed: {msg}")

    def _csv_to_list(self, raw: str) -> list[str]:
        out: list[str] = []
        for item in (raw or "").split(","):
            text = item.strip()
            if not text:
                continue
            if text not in out:
                out.append(text)
        return out

    def _csv_to_int_list(self, raw: str) -> list[int]:
        out: list[int] = []
        for text in self._csv_to_list(raw):
            try:
                value = int(text)
            except ValueError:
                continue
            if 1 <= value <= 6 and value not in out:
                out.append(value)
        return out

    def on_backend_push_config(self) -> None:
        base_url = self.backend_base_url_input.text().strip()
        api_key = self.backend_api_key_input.text().strip()

        payload = {
            "whitelist_category_ids": self._csv_to_int_list(self.whitelist_category_ids_input.text()),
            "whitelist_grade": self._csv_to_list(self.whitelist_grade_input.text()),
            "whitelist_academy": self._csv_to_list(self.whitelist_academy_input.text()),
            "tls_insecure": self.tls_insecure_checkbox.isChecked(),
        }

        self._set_status("Syncing whitelist config to backend...")
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

    def _on_backend_push_config_done(self, result: tuple[bool, str, dict[str, Any]]) -> None:
        ok, msg, _data = result
        if ok:
            self._set_status("Backend whitelist config synced")
            return
        self._set_status(f"Sync backend config failed: {msg}")

    def on_backend_pull_config(self) -> None:
        base_url = self.backend_base_url_input.text().strip()
        api_key = self.backend_api_key_input.text().strip()
        self._set_status("Loading whitelist config from backend...")
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

    def _on_backend_pull_config_done(self, result: tuple[bool, str, dict[str, Any]]) -> None:
        ok, msg, data = result
        if not ok:
            self._set_status(f"Load backend config failed: {msg}")
            return

        cfg_data = data.get("data") if isinstance(data, dict) else None
        if not isinstance(cfg_data, dict):
            self._set_status("Backend config payload is invalid")
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

        self._set_status("Backend whitelist config loaded")

    def on_monitor_once(self, silent_if_no_token: bool = False) -> None:
        sign_status = int(self.monitor_status_combo.currentData())
        self._last_monitor_sign_status = sign_status
        limit = int(self.monitor_limit_spin.value())
        insecure = self.tls_insecure_checkbox.isChecked()

        if self.backend_mode_checkbox.isChecked():
            base_url = self.backend_base_url_input.text().strip()
            api_key = self.backend_api_key_input.text().strip()
            if not base_url or not api_key:
                if not silent_if_no_token:
                    QMessageBox.warning(self, "Warning", "Backend URL/API key is empty")
                return

            self._set_status("Running monitor query from backend...")
            worker = Worker(self._run_monitor_batch_backend, base_url, api_key, sign_status, limit, insecure)
            worker.signals.done.connect(self._on_monitor_done)
            self.pool.start(worker)
            return

        token = self.token_input.text().strip()
        if not token:
            if not silent_if_no_token:
                QMessageBox.warning(self, "Warning", "Token is empty")
            return

        self._set_status("Running monitor query for all categories...")
        worker = Worker(self._run_monitor_batch, token, sign_status, limit, insecure)
        worker.signals.done.connect(self._on_monitor_done)
        self.pool.start(worker)

    def _parse_category_whitelist_text(self) -> list[int]:
        raw = self.whitelist_category_ids_input.text().strip()
        if not raw:
            return []
        out: list[int] = []
        for item in raw.split(","):
            text = item.strip()
            if not text:
                continue
            try:
                cid = int(text)
            except ValueError:
                continue
            if cid not in out and 1 <= cid <= 6:
                out.append(cid)
        return out

    def _run_monitor_batch_backend(
        self,
        base_url: str,
        api_key: str,
        sign_status: int,
        limit: int,
        insecure: bool,
    ) -> dict[int, dict[str, Any]]:
        category_ids = self._parse_category_whitelist_text() or [cid for cid, _name in CATEGORIES]
        result: dict[int, dict[str, Any]] = {}

        for cid in category_ids:
            path = f"/api/v1/courses/list?sign_status={int(sign_status)}&limit={int(limit)}&category_ids={cid}"
            ok, msg, data = backend_signed_get(
                base_url=base_url,
                path=path,
                api_key=api_key,
                timeout=15.0,
                insecure_tls=insecure,
            )
            items_obj = data.get("data") if isinstance(data, dict) else []
            items = items_obj if isinstance(items_obj, list) else []
            result[cid] = {
                "ok": ok,
                "message": msg,
                "items": items,
            }

        # Keep all tabs stable even if category whitelist excludes some categories.
        for cid, _name in CATEGORIES:
            if cid not in result:
                result[cid] = {
                    "ok": True,
                    "message": "skipped_by_whitelist",
                    "items": [],
                }
        return result

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
            cat_result = result.get(category_id, {"ok": False, "message": "No result", "items": []})
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
            self._set_status(
                f"Monitor loaded {total_count} course(s); {failed_count}/6 categories failed"
            )
        else:
            self._set_status(f"Monitor loaded {total_count} course(s) across 6 categories")
