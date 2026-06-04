from __future__ import annotations

import math
from typing import Any
from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QPainter, QPolygonF, QColor, QPen, QBrush, QFont
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QGroupBox,
    QFormLayout,
    QScrollArea,
    QHeaderView,
)

class RadarChartWidget(QWidget):
    """自定义雷达图组件"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(300, 300)
        self.data: list[dict[str, Any]] = []

    def set_data(self, data: list[dict[str, Any]]):
        self.data = data
        self.update()

    def paintEvent(self, event):
        if not self.data:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        width = self.width()
        height = self.height()
        center = QPointF(width / 2, height / 2)
        radius = min(width, height) / 2 * 0.7  # 留出标签空间

        num_vars = len(self.data)
        angle_step = 360 / num_vars if num_vars > 0 else 0

        # 1. 绘制网格背景 (5层)
        grid_pen = QPen(QColor(200, 200, 200), 1, Qt.PenStyle.DashLine)
        painter.setPen(grid_pen)
        for i in range(1, 6):
            r = radius * i / 5
            points = []
            for j in range(num_vars):
                angle = math.radians(j * angle_step - 90)
                px = center.x() + r * math.cos(angle)
                py = center.y() + r * math.sin(angle)
                points.append(QPointF(px, py))
            painter.drawPolygon(QPolygonF(points))

        # 2. 绘制轴线和标签
        painter.setPen(QPen(QColor(150, 150, 150), 1))
        font = QFont("PingFang SC", 9)
        painter.setFont(font)
        for j in range(num_vars):
            angle = math.radians(j * angle_step - 90)
            # 轴线
            end_point = QPointF(
                center.x() + radius * math.cos(angle),
                center.y() + radius * math.sin(angle)
            )
            painter.drawLine(center, end_point)
            
            # 标签
            name = self.data[j].get("name", "")
            score_val = str(int(float(self.data[j].get("score") or 0.0)))
            label_text = f"{name} ({score_val})"
            
            label_r = radius + 25
            lx = center.x() + label_r * math.cos(angle)
            ly = center.y() + label_r * math.sin(angle)
            
            # 简单对齐调整
            rect_w = 100
            rect_h = 20
            painter.drawText(int(lx - rect_w/2), int(ly - rect_h/2), rect_w, rect_h, Qt.AlignmentFlag.AlignCenter, label_text)

        # 3. 绘制数据区域
        if num_vars > 0:
            data_points = []
            for j in range(num_vars):
                score = float(self.data[j].get("score") or 0.0)
                r = radius * (score / 100.0)
                angle = math.radians(j * angle_step - 90)
                px = center.x() + r * math.cos(angle)
                py = center.y() + r * math.sin(angle)
                data_points.append(QPointF(px, py))

            path = QPolygonF(data_points)
            # 填充色
            painter.setBrush(QBrush(QColor(15, 118, 110, 80)))  # #0f766e 且透明
            painter.setPen(QPen(QColor(15, 118, 110), 2))
            painter.drawPolygon(path)
            
            # 绘制小圆点
            painter.setBrush(QBrush(QColor(15, 118, 110)))
            for pt in data_points:
                painter.drawEllipse(pt, 3, 3)

class ProfileWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        
        container = QWidget()
        container_layout = QVBoxLayout(container)
        
        # 1. 个人基本信息 + 雷达图
        self.header_group = QGroupBox("个人信息与能力画像")
        header_hbox = QHBoxLayout(self.header_group)
        
        # 左侧文字信息
        info_widget = QWidget()
        self.info_layout = QFormLayout(info_widget)
        self.name_label = QLabel("-")
        self.student_no_label = QLabel("-")
        self.college_label = QLabel("-")
        self.major_label = QLabel("-")
        self.class_label = QLabel("-")
        self.total_score_label = QLabel("-")
        self.total_score_label.setStyleSheet("font-weight: bold; color: #0f766e; font-size: 20px;")
        
        self.info_layout.addRow("姓名:", self.name_label)
        self.info_layout.addRow("学号:", self.student_no_label)
        self.info_layout.addRow("学院:", self.college_label)
        self.info_layout.addRow("专业:", self.major_label)
        self.info_layout.addRow("班级:", self.class_label)
        self.info_layout.addRow("总分:", self.total_score_label)
        
        # 右侧雷达图
        self.radar_chart = RadarChartWidget()
        
        header_hbox.addWidget(info_widget, 1)
        header_hbox.addWidget(self.radar_chart, 1)
        
        container_layout.addWidget(self.header_group)
        
        # 2. 详细成绩单表格 (transcriptScore)
        self.score_group = QGroupBox("成绩单详情")
        score_vbox = QVBoxLayout(self.score_group)
        self.score_table = QTableWidget(0, 5)
        self.score_table.setHorizontalHeaderLabels(["能力项", "基础分", "领军分", "单项积分", "加权积分"])
        self.score_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.score_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        score_vbox.addWidget(self.score_table)
        
        container_layout.addWidget(self.score_group)
        container_layout.addStretch(1)
        
        scroll.setWidget(container)
        layout.addWidget(scroll)

    def update_data(self, data: dict[str, Any]):
        model = data.get("model", {})
        student = model.get("student", {})
        
        def fmt_int(v):
            if v is None: return "0"
            try:
                return str(int(float(v)))
            except (ValueError, TypeError):
                return str(v)

        def fmt_float(v):
            if v is None: return "0.0"
            try:
                return f"{float(v):.1f}"
            except (ValueError, TypeError):
                return str(v)

        # 更新基本信息
        self.name_label.setText(str(student.get("name") or "-"))
        self.student_no_label.setText(str(student.get("student_no") or "-"))
        self.college_label.setText(str(student.get("college") or "-"))
        self.major_label.setText(str(student.get("major") or "-"))
        self.class_label.setText(str(student.get("class_name") or "-"))
        self.total_score_label.setText(fmt_float(model.get("score")))
        
        # 更新雷达图 (leaderScore)
        leader_scores = data.get("leaderScore", [])
        self.radar_chart.set_data(leader_scores)
            
        # 更新详细成绩表格 (transcriptScore)
        transcript_scores = data.get("transcriptScore", [])
        self.score_table.setRowCount(0)
        for idx, item in enumerate(transcript_scores):
            self.score_table.insertRow(idx)
            name = item.get("transcript_name", "")
            rate_val = 0.0
            try:
                rate_val = float(item.get("rate") or 0.0)
            except ValueError:
                rate_val = 0.0
            
            # score 嵌套在 score 对象里
            s_obj = item.get("score") or {}
            base = s_obj.get("base_score")
            leader = s_obj.get("leader_score")
            score_val_raw = s_obj.get("score")
            
            score_val = 0.0
            try:
                score_val = float(score_val_raw or 0.0)
            except ValueError:
                score_val = 0.0
                
            # 计算加权分：单项积分 * (权重 / 100)
            weighted_val = score_val * (rate_val / 100.0)
            
            self.score_table.setItem(idx, 0, QTableWidgetItem(name))
            self.score_table.setItem(idx, 1, QTableWidgetItem(fmt_int(base)))
            self.score_table.setItem(idx, 2, QTableWidgetItem(fmt_int(leader)))
            self.score_table.setItem(idx, 3, QTableWidgetItem(fmt_int(score_val_raw)))
            self.score_table.setItem(idx, 4, QTableWidgetItem(f"{weighted_val:.1f}"))
