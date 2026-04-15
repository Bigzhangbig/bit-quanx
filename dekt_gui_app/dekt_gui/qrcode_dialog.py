from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QKeySequence, QPainter, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .api_client import get_qrcode_image


class QRCodeDialog(QDialog):
    """二维码展示对话框。"""

    def __init__(
        self,
        parent: QMainWindow | None = None,
        course_id: int = 0,
        course_title: str = "",
        sign_in_window: str = "",
        sign_out_window: str = "",
    ):
        super().__init__(parent)
        self.setWindowTitle(f"活动二维码 - ID: {course_id}")
        self.resize(580, 680)
        self.course_id = course_id
        self.course_title = course_title
        self.sign_in_window = sign_in_window
        self.sign_out_window = sign_out_window
        self._composed_pixmap: QPixmap | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        self.qr_label = QLabel()
        self.qr_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.qr_label.setFixedSize(470, 594)
        self.qr_label.setStyleSheet(
            "background-color: #ffffff; border: 0; padding: 0;"
        )
        self.qr_label.setText("初始化中...")

        qr_container = QWidget()
        qr_layout = QHBoxLayout(qr_container)
        qr_layout.setContentsMargins(0, 0, 0, 0)
        qr_layout.setSpacing(0)
        qr_layout.addStretch(1)
        qr_layout.addWidget(self.qr_label)
        qr_layout.addStretch(1)

        layout.addWidget(qr_container, 1)

        btn_layout = QHBoxLayout()

        save_btn = QPushButton("下载二维码图片")
        save_btn.clicked.connect(self._save_qrcode_image)
        btn_layout.addWidget(save_btn)

        copy_img_btn = QPushButton("复制二维码图片")
        copy_img_btn.clicked.connect(self._copy_qrcode_image_to_clipboard)
        btn_layout.addWidget(copy_img_btn)

        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

        self._close_shortcut = QShortcut(QKeySequence.StandardKey.Close, self)
        self._close_shortcut.activated.connect(self.accept)
        self._esc_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Escape), self)
        self._esc_shortcut.activated.connect(self.reject)

    def load_qrcode(self) -> None:
        if not self.course_id:
            QMessageBox.warning(self, "提示", "课程 ID 为空")
            return

        self.qr_label.setText("生成二维码中...")

        ok, msg, qr_data = get_qrcode_image(course_id=self.course_id)

        print(f"[QRCode] 生成结果: ok={ok}, msg={msg}, 数据大小={len(qr_data)}")

        if not ok:
            error_msg = f"生成失败: {msg}"
            self.qr_label.setText(error_msg)
            print(f"[QRCode] {error_msg}")
            return

        if not qr_data:
            self.qr_label.setText("二维码数据为空")
            print("[QRCode] 二维码数据为空")
            return

        try:
            pixmap = QPixmap()
            loaded = pixmap.loadFromData(qr_data)
            print(f"[QRCode] QPixmap 加载结果: {loaded}, 原始大小: {pixmap.width()}x{pixmap.height()}")

            if not loaded or pixmap.isNull():
                self.qr_label.setText("无法加载二维码图像")
                print("[QRCode] 无法加载二维码图像")
                return

            composed = self._build_annotated_qrcode(pixmap)
            if composed.isNull():
                self.qr_label.setText("无法生成带标注的二维码")
                print("[QRCode] 无法生成带标注的二维码")
                return

            self._composed_pixmap = composed
            self.qr_label.setFixedSize(self._composed_pixmap.size())
            self._refresh_preview_pixmap()

            self.qr_label.setText("")
            print("[QRCode] 二维码已显示")
        except Exception as exc:  # noqa: BLE001
            error_msg = f"显示二维码失败: {exc}"
            self.qr_label.setText(error_msg)
            print(f"[QRCode] {error_msg}")
            import traceback

            traceback.print_exc()

    def resizeEvent(self, event) -> None:  # noqa: ANN001
        super().resizeEvent(event)
        self._refresh_preview_pixmap()

    def _refresh_preview_pixmap(self) -> None:
        if self._composed_pixmap is None or self._composed_pixmap.isNull():
            return

        display = self._composed_pixmap.scaled(
                self.qr_label.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
        )
        self.qr_label.setPixmap(display)

    def _wrap_text(self, text: str, font: QFont, max_width: int, max_lines: int) -> list[str]:
        if not text:
            return [""]

        probe = QPixmap(1, 1)
        painter = QPainter(probe)
        painter.setFont(font)
        metrics = painter.fontMetrics()

        lines: list[str] = []
        current = ""
        for ch in text:
            candidate = f"{current}{ch}"
            if metrics.horizontalAdvance(candidate) <= max_width:
                current = candidate
                continue

            if current:
                lines.append(current)
            current = ch
            if len(lines) >= max_lines:
                break

        if len(lines) < max_lines and current:
            lines.append(current)

        if len(lines) > max_lines:
            lines = lines[:max_lines]

        if len(lines) == max_lines:
            tail = lines[-1]
            ellipsis = "..."
            while tail and metrics.horizontalAdvance(f"{tail}{ellipsis}") > max_width:
                tail = tail[:-1]
            lines[-1] = f"{tail}{ellipsis}" if tail else ellipsis

        painter.end()
        return lines or [""]

    def _build_annotated_qrcode(self, qr_pixmap: QPixmap) -> QPixmap:
        qr_size = 450
        margin = 10
        spacing = 8

        qr_view = qr_pixmap.scaled(
            qr_size,
            qr_size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

        title_text = self.course_title.strip() or f"活动 {self.course_id}"
        sign_in_text = self.sign_in_window.strip() or "无"
        sign_out_text = self.sign_out_window.strip() or "无"

        line1 = title_text
        line2 = f"签到时间：{sign_in_text}"
        line3 = f"签退时间：{sign_out_text}"

        title_font = QFont()
        title_font.setPointSize(19)
        title_font.setBold(True)
        body_font = QFont()
        body_font.setPointSize(11)

        tmp = QPixmap(1, 1)
        painter = QPainter(tmp)
        painter.setFont(title_font)
        title_h = painter.fontMetrics().height()
        painter.setFont(body_font)
        body_h = painter.fontMetrics().height()
        body_w_2 = painter.fontMetrics().horizontalAdvance(line2)
        body_w_3 = painter.fontMetrics().horizontalAdvance(line3)
        painter.end()

        content_w = max(qr_view.width(), body_w_2, body_w_3)
        canvas_w = content_w + margin * 2
        title_lines = self._wrap_text(line1, title_font, content_w, max_lines=2)
        text_h = (len(title_lines) * title_h) + spacing + body_h + 6 + body_h
        canvas_h = margin + text_h + 14 + qr_view.height() + margin

        canvas = QPixmap(canvas_w, canvas_h)
        canvas.fill(Qt.GlobalColor.white)

        painter = QPainter(canvas)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        y = margin + title_h
        painter.setFont(title_font)
        for title_line in title_lines:
            title_w = painter.fontMetrics().horizontalAdvance(title_line)
            x_title = (canvas_w - title_w) // 2
            painter.drawText(x_title, y, title_line)
            y += title_h

        y += spacing
        painter.setFont(body_font)
        line2_w = painter.fontMetrics().horizontalAdvance(line2)
        x_line2 = (canvas_w - line2_w) // 2
        painter.drawText(x_line2, y, line2)

        y += 6 + body_h
        line3_w = painter.fontMetrics().horizontalAdvance(line3)
        x_line3 = (canvas_w - line3_w) // 2
        painter.drawText(x_line3, y, line3)

        qr_x = (canvas_w - qr_view.width()) // 2
        qr_y = margin + text_h + 14
        painter.drawPixmap(qr_x, qr_y, qr_view)
        painter.end()

        return canvas

    def _copy_qrcode_image_to_clipboard(self) -> None:
        if self._composed_pixmap is None or self._composed_pixmap.isNull():
            QMessageBox.warning(self, "提示", "暂无可复制的二维码图片")
            return

        try:
            QApplication.clipboard().setPixmap(self._composed_pixmap)
            QMessageBox.information(self, "提示", "二维码图片已复制到剪贴板")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "错误", f"复制二维码图片失败: {exc}")

    def _save_qrcode_image(self) -> None:
        if self._composed_pixmap is None or self._composed_pixmap.isNull():
            QMessageBox.warning(self, "提示", "暂无可保存的二维码图片")
            return

        default_name = f"dekt_qrcode_{self.course_id}.png"
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "保存二维码图片",
            default_name,
            "PNG 图片 (*.png);;JPEG 图片 (*.jpg *.jpeg)",
        )

        if not file_path:
            return

        if self._composed_pixmap.save(file_path):
            QMessageBox.information(self, "提示", f"已保存到: {file_path}")
        else:
            QMessageBox.warning(self, "错误", "保存二维码图片失败")
