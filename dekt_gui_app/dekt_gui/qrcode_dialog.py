from __future__ import annotations

import subprocess

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from .api_client import get_qrcode_image, get_qrcode_url


class QRCodeDialog(QDialog):
    """二维码展示对话框。"""

    def __init__(self, parent: QMainWindow | None = None, course_id: int = 0, course_title: str = ""):
        super().__init__(parent)
        self.setWindowTitle("活动二维码")
        self.resize(600, 650)
        self.course_id = course_id
        self.course_title = course_title

        layout = QVBoxLayout(self)

        title_label = QLabel(f"活动二维码: {course_title}")
        title_font = title_label.font()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title_label.setFont(title_font)
        layout.addWidget(title_label)

        info_label = QLabel(f"课程 ID: {course_id}")
        layout.addWidget(info_label)

        self.qr_label = QLabel()
        self.qr_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.qr_label.setMinimumSize(400, 400)
        self.qr_label.setMaximumSize(500, 500)
        self.qr_label.setFixedSize(450, 450)
        self.qr_label.setStyleSheet(
            "border: 1px solid #ccc; background-color: #f5f5f5; padding: 5px;"
        )
        self.qr_label.setText("初始化中...")

        qr_container = QWidget()
        qr_layout = QHBoxLayout(qr_container)
        qr_layout.addStretch(1)
        qr_layout.addWidget(self.qr_label)
        qr_layout.addStretch(1)

        layout.addWidget(qr_container, 1)

        self.url_browser = QTextBrowser()
        self.url_browser.setMaximumHeight(60)
        layout.addWidget(QLabel("二维码链接:"))
        layout.addWidget(self.url_browser)

        btn_layout = QHBoxLayout()

        refresh_btn = QPushButton("刷新二维码")
        refresh_btn.clicked.connect(self.load_qrcode)
        btn_layout.addWidget(refresh_btn)

        copy_url_btn = QPushButton("复制链接")
        copy_url_btn.clicked.connect(self._copy_url_to_clipboard)
        btn_layout.addWidget(copy_url_btn)

        open_url_btn = QPushButton("浏览器打开")
        open_url_btn.clicked.connect(self._open_url_in_browser)
        btn_layout.addWidget(open_url_btn)

        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)

        btn_layout.addStretch(1)
        layout.addLayout(btn_layout)

    def load_qrcode(self) -> None:
        if not self.course_id:
            QMessageBox.warning(self, "提示", "课程 ID 为空")
            return

        self.qr_label.setText("生成二维码中...")
        qr_url = get_qrcode_url(self.course_id)
        self.url_browser.setText(qr_url)

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

            label_size = 450
            if pixmap.width() != label_size or pixmap.height() != label_size:
                pixmap = pixmap.scaledToWidth(label_size - 10, Qt.TransformationMode.SmoothTransformation)
                print(f"[QRCode] 缩放后: {pixmap.width()}x{pixmap.height()}")

            self.qr_label.setPixmap(pixmap)
            self.qr_label.setText("")
            print("[QRCode] 二维码已显示")
        except Exception as exc:  # noqa: BLE001
            error_msg = f"显示二维码失败: {exc}"
            self.qr_label.setText(error_msg)
            print(f"[QRCode] {error_msg}")
            import traceback

            traceback.print_exc()

    def _copy_url_to_clipboard(self) -> None:
        qr_url = get_qrcode_url(self.course_id)
        try:
            process = subprocess.Popen(["pbcopy"], stdin=subprocess.PIPE)
            process.communicate(qr_url.encode("utf-8"))
            QMessageBox.information(self, "提示", "已复制到剪贴板")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "错误", f"复制失败: {exc}")

    def _open_url_in_browser(self) -> None:
        qr_url = get_qrcode_url(self.course_id)
        QDesktopServices.openUrl(QUrl(qr_url))
