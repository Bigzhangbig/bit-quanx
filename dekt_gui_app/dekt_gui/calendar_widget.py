"""日历Widget UI和交互实现。"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Callable

from PySide6.QtCore import Qt, QDate, QTimer
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QCalendarWidget,
    QAbstractItemView,
    QTableWidget,
    QTableWidgetItem,
    QComboBox,
    QLabel,
    QLineEdit,
    QPushButton,
    QMenu,
    QHeaderView,
)
from PySide6.QtGui import QColor, QFont, QTextCharFormat

from .calendar_utils import (
    CalendarEvent,
    is_event_ended,
    is_in_checkin_window,
    is_in_checkout_window,
    normalize_display_text,
    summarize_event_day_completion,
)


class CalendarWidget(QWidget):
    """日历显示和交互Widget。"""
    
    def __init__(self):
        super().__init__()
        self.events: list[CalendarEvent] = []
        self.all_events: list[CalendarEvent] = []
        self.my_course_ids: set[int] = set()
        self._highlighted_dates: set[QDate] = set()
        self.current_filter_mode: str = "mine"  # "mine" 或 "all"
        
        # 回调函数
        self.on_signup_callback: Callable[[int], None] | None = None
        self.on_cancel_callback: Callable[[int], None] | None = None
        self.on_checkin_callback: Callable[[int], None] | None = None
        self.on_detail_callback: Callable[[int], None] | None = None
        self.on_export_ics_callback: Callable[[list[CalendarEvent]], None] | None = None

        # 搜索防抖定时器
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(300)
        self._search_timer.timeout.connect(self._apply_filter)

        self._init_ui()
    
    def _init_ui(self):
        """初始化UI。"""
        main_layout = QVBoxLayout(self)
        
        # 顶部工具栏
        toolbar_layout = QHBoxLayout()
        
        toolbar_layout.addWidget(QLabel("筛选:"))
        self.filter_combo = QComboBox()
        self.filter_combo.addItem("已报名的活动", "mine")
        self.filter_combo.addItem("全部活动", "all")
        self.filter_combo.currentIndexChanged.connect(self._on_filter_changed)
        toolbar_layout.addWidget(self.filter_combo)
        
        toolbar_layout.addWidget(QLabel("搜索:"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("活动名称...")
        self.search_input.textChanged.connect(self._on_search_changed)
        toolbar_layout.addWidget(self.search_input)

        today_btn = QPushButton("回到今天")
        today_btn.clicked.connect(self._jump_to_today)
        toolbar_layout.addWidget(today_btn)
        
        toolbar_layout.addStretch()
        
        export_btn = QPushButton("导出ICS")
        export_btn.clicked.connect(self._on_export_clicked)
        toolbar_layout.addWidget(export_btn)
        
        main_layout.addLayout(toolbar_layout)
        
        # 中部：日历和事件列表（水平分割）
        content_layout = QHBoxLayout()
        
        # 日历控件
        self.calendar = QCalendarWidget()
        self.calendar.setMinimumWidth(300)
        self.calendar.clicked.connect(self._on_calendar_date_changed)
        content_layout.addWidget(self.calendar)
        
        # 右侧：选定日期的事件列表
        right_layout = QVBoxLayout()
        right_layout.addWidget(QLabel("该日期的活动:"))
        
        self.events_table = QTableWidget()
        self.events_table.setColumnCount(3)
        self.events_table.setHorizontalHeaderLabels([
            "活动名称", "时间", "地点"
        ])
        self.events_table.horizontalHeader().setStretchLastSection(False)
        self.events_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.events_table.setWordWrap(False)
        self.events_table.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.events_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.events_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.events_table.customContextMenuRequested.connect(self._show_event_context_menu)
        self.events_table.itemDoubleClicked.connect(self._on_event_item_double_clicked)
        right_layout.addWidget(self.events_table)
        
        content_layout.addLayout(right_layout, 1)
        main_layout.addLayout(content_layout, 1)
    
    def load_events(self, all_events: list[CalendarEvent], my_course_ids: set[int]):
        """加载事件数据。
        
        Args:
            all_events: 所有事件（已报名+未报名）
            my_course_ids: 已报名的活动ID集合
        """
        self.all_events = all_events
        self.my_course_ids = my_course_ids
        
        # 应用当前筛选模式
        self._apply_filter()
    
    def _apply_filter(self):
        """应用筛选模式。"""
        if self.current_filter_mode == "mine":
            self.events = [e for e in self.all_events if e.id in self.my_course_ids]
        else:
            self.events = self.all_events
        
        # 应用搜索过滤
        search_text = self.search_input.text().strip()
        if search_text:
            search_lower = search_text.lower()
            self.events = [
                e for e in self.events
                if search_lower in e.title.lower() or search_lower in e.category.lower()
            ]
        
        # 重新突出显示有事件的日期
        self._highlight_event_days()
        
        # 刷新当前选中日期的事件列表
        self._refresh_selected_date_events()
    
    def _on_filter_changed(self):
        """筛选模式改变。"""
        self.current_filter_mode = self.filter_combo.currentData()
        self._apply_filter()
    
    def _on_search_changed(self):
        """搜索文本改变（防抖）。"""
        self._search_timer.start()

    def _jump_to_today(self):
        """跳转到今天。"""
        today = QDate.currentDate()
        self.calendar.setSelectedDate(today)
        self.calendar.setCurrentPage(today.year(), today.month())
        self._refresh_selected_date_events()
    
    def _highlight_event_days(self):
        """标记日历上有事件的日期。"""
        # 先清理上一次高亮，避免筛选切换后残留。
        default_fmt = QTextCharFormat()
        for date in self._highlighted_dates:
            self.calendar.setDateTextFormat(date, default_fmt)
        self._highlighted_dates.clear()

        # 统计筛选后事件日期（用于高亮）。
        event_dates: set[QDate] = set()
        for event in self.events:
            if not event.start_time:
                continue
            date_key = QDate(event.start_time.year, event.start_time.month, event.start_time.day)
            event_dates.add(date_key)

        if not event_dates:
            return

        completed_days = summarize_event_day_completion(self.events)

        active_fmt = QTextCharFormat()
        active_fmt.setBackground(QColor("#E6F4EA"))
        active_fmt.setForeground(QColor("#0B6B3A"))
        active_fmt.setFontWeight(QFont.Weight.Bold)

        completed_fmt = QTextCharFormat()
        completed_fmt.setBackground(QColor("#F3F4F6"))
        completed_fmt.setForeground(QColor("#9AA0A6"))
        completed_fmt.setFontWeight(QFont.Weight.Normal)

        for date in event_dates:
            if completed_days.get((date.year(), date.month(), date.day()), False):
                self.calendar.setDateTextFormat(date, completed_fmt)
            else:
                self.calendar.setDateTextFormat(date, active_fmt)
            self._highlighted_dates.add(date)
    
    def _on_calendar_date_changed(self):
        """日历日期改变。"""
        self._refresh_selected_date_events()
    
    def _refresh_selected_date_events(self):
        """刷新选定日期的事件列表。"""
        selected_date = self.calendar.selectedDate()
        selected_datetime = datetime(
            selected_date.year(),
            selected_date.month(),
            selected_date.day()
        )
        
        # 找到该日期的所有事件
        date_events: list[tuple[CalendarEvent, int]] = []
        for i, event in enumerate(self.events):
            if not event.start_time:
                continue
            
            # 检查是否在同一天
            if (event.start_time.year == selected_datetime.year and
                event.start_time.month == selected_datetime.month and
                event.start_time.day == selected_datetime.day):
                date_events.append((event, i))
        
        # 更新表格
        self.events_table.setRowCount(len(date_events))
        for row, (event, _) in enumerate(date_events):
            ended = is_event_ended(event)

            # 活动名称
            name_item = QTableWidgetItem(event.title)
            name_item.setData(Qt.ItemDataRole.UserRole, event.id)  # 存储ID
            self.events_table.setItem(row, 0, name_item)
            
            # 时间
            time_str = ""
            if event.start_time and event.end_time:
                time_str = f"{event.start_time.strftime('%H:%M')}-{event.end_time.strftime('%H:%M')}"
            elif event.start_time:
                time_str = event.start_time.strftime("%H:%M")
            self.events_table.setItem(row, 1, QTableWidgetItem(time_str))
            
            # 地点
            self.events_table.setItem(row, 2, QTableWidgetItem(normalize_display_text(event.location)))

            if ended:
                ended_text_color = QColor("#9AA0A6")
                ended_bg_color = QColor("#F5F5F5")
                for col in range(3):
                    item = self.events_table.item(row, col)
                    if item is None:
                        continue
                    item.setForeground(ended_text_color)
                    item.setBackground(ended_bg_color)
    
    def _show_event_context_menu(self, pos):
        """显示事件的右键菜单。"""
        current_row = self.events_table.rowAt(pos.y())
        if current_row < 0:
            return

        item = self.events_table.item(current_row, 0)
        if item is None:
            return
        course_id = item.data(Qt.ItemDataRole.UserRole)
        
        # 找到对应的事件
        event = None
        for e in self.events:
            if e.id == course_id:
                event = e
                break
        
        if not event:
            return
        
        menu = QMenu()
        
        event_dict = self._event_to_dict(event)
        
        # 根据状态显示不同的菜单选项
        if event.is_enrolled:
            # 已报名
            if is_in_checkin_window(event_dict):
                action = menu.addAction("签到")
                action.triggered.connect(lambda: self._handle_checkin(event.id))
            elif is_in_checkout_window(event_dict):
                action = menu.addAction("签退")
                action.triggered.connect(lambda: self._handle_checkin(event.id))
            else:
                action = menu.addAction("取消报名")
                action.triggered.connect(lambda: self._handle_cancel(event.id))
        else:
            # 未报名
            action = menu.addAction("报名")
            action.triggered.connect(lambda: self._handle_signup(event.id))
        
        # 始终显示查看详情
        menu.addSeparator()
        detail_action = menu.addAction("查看详情")
        detail_action.triggered.connect(lambda: self._handle_detail(event.id))
        
        menu.exec(self.events_table.viewport().mapToGlobal(pos))
    
    def _on_event_item_double_clicked(self):
        """双击事件项。"""
        current_row = self.events_table.currentRow()
        if current_row >= 0:
            item = self.events_table.item(current_row, 0)
            if item is not None:
                course_id = item.data(Qt.ItemDataRole.UserRole)
                self._handle_detail(course_id)
    
    def _handle_signup(self, course_id: int):
        """处理报名。"""
        if self.on_signup_callback:
            self.on_signup_callback(course_id)
    
    def _handle_cancel(self, course_id: int):
        """处理取消报名。"""
        if self.on_cancel_callback:
            self.on_cancel_callback(course_id)
    
    def _handle_checkin(self, course_id: int):
        """处理签到/签退。"""
        if self.on_checkin_callback:
            self.on_checkin_callback(course_id)
    
    def _handle_detail(self, course_id: int):
        """处理查看详情。"""
        if self.on_detail_callback:
            self.on_detail_callback(course_id)
    
    def _on_export_clicked(self):
        """处理导出ICS。"""
        if self.on_export_ics_callback:
            self.on_export_ics_callback(self.events)
    
    def _event_to_dict(self, event: CalendarEvent) -> dict[str, Any]:
        """将CalendarEvent转换为字典，供is_in_checkin_window等函数使用。"""
        return {
            "sign_in_start_time": event.sign_in_start_time,
            "sign_in_end_time": event.sign_in_end_time,
            "sign_out_start_time": event.sign_out_start_time,
            "sign_out_end_time": event.sign_out_end_time,
        }
