"""图片、地图预览、二维码相关功能 Mixin。"""
from __future__ import annotations

import base64
import math
from typing import Any

import certifi
import httpx
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from .worker import Worker


class ImageMixin:
    """为 MainWindow 提供图片缓存、封面加载、地图预览和二维码功能。

    要求宿主类提供：
    - self.pool: QThreadPool
    - self.tls_insecure_checkbox: QCheckBox
    - self.tencent_map_key_input: QLineEdit
    - self._image_bytes_cache: dict[str, bytes | None]
    - self._pixmap_cache: dict[str, QPixmap | None]
    - self._cover_waiters: dict[str, list[tuple]]
    - self._cover_loading_urls: set[str]
    - self._open_dialogs: list
    """

    # --- 图片缓存与加载 ---

    def _normalize_media_url(self: Any, raw_url: str) -> str:
        url = (raw_url or "").strip()
        if not url:
            return ""
        if url.startswith("http://") or url.startswith("https://"):
            return url
        clean = url.lstrip("/")
        if clean.startswith("storage/"):
            return f"https://qcbldekt.bit.edu.cn/{clean}"
        return f"https://qcbldekt.bit.edu.cn/storage/{clean}"

    def _cover_url(self: Any, course_obj: dict[str, Any]) -> str:
        cover = self._first_non_empty(course_obj, ["cover_url", "cover", "image", "img"])
        return self._normalize_media_url(cover)

    def _fetch_image_bytes(self: Any, url: str, timeout: float = 10.0) -> bytes | None:
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

    def _pixmap_from_bytes(self: Any, url: str, content: bytes, width: int, height: int) -> QPixmap | None:
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
                    width, height,
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
        self: Any, url: str, insecure_tls: bool, timeout: float,
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

    def _request_cover_image_async(self: Any, table: QTableWidget, row: int, col: int, cover_url: str) -> None:
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
            self._download_image_bytes_task, norm_url,
            self.tls_insecure_checkbox.isChecked(), 10.0,
        )
        worker.signals.done.connect(self._on_cover_image_loaded)
        self.pool.start(worker)

    def _on_cover_image_loaded(self: Any, payload: tuple[str, bytes | None]) -> None:
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
                continue

    def _set_table_cover_cell(self: Any, table: QTableWidget, row: int, col: int, course_obj: dict[str, Any]) -> None:
        item = QTableWidgetItem("")
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        cover_url = self._cover_url(course_obj)
        norm_cover = self._normalize_media_url(cover_url)
        item.setData(Qt.ItemDataRole.UserRole, norm_cover)
        table.setItem(row, col, item)
        table.setRowHeight(row, 44)
        if norm_cover:
            self._request_cover_image_async(table, row, col, norm_cover)

    def _image_mime(self: Any, content: bytes, url: str) -> str:
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

    def _embedded_image_block(self: Any, url: str, width: int = 640) -> str:
        norm_url = self._normalize_media_url(url)
        if not norm_url:
            return ""
        content = self._fetch_image_bytes(norm_url, timeout=10.0)
        if not content:
            return ""
        mime = self._image_mime(content, norm_url)
        b64 = base64.b64encode(content).decode("ascii")
        return f'<p><img src="data:{mime};base64,{b64}" width="{int(width)}"></p>'

    # --- 地图预览 ---

    def _draw_range_circle_on_map(self: Any, pixmap: QPixmap, lat: float, radius_m: float) -> QPixmap:
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
            int(center_x - radius_px), int(center_y - radius_px),
            int(radius_px * 2), int(radius_px * 2),
        )
        painter.setBrush(QColor(220, 53, 69, 230))
        painter.setPen(QPen(QColor(255, 255, 255, 220), 1.0))
        painter.drawEllipse(int(center_x - 4), int(center_y - 4), 8, 8)
        painter.end()
        return out

    def _show_map_preview_dialog(
        self: Any,
        title: str, lat: float | None, lon: float | None,
        radius_m: float | None, insecure_tls: bool,
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
        info_lines = [f"位置：{title or '打卡地点'}", f"坐标：{lat:.6f}, {lon:.6f}"]
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
        map_url = (
            "https://apis.map.qq.com/ws/staticmap/v2/"
            f"?center={lat_s},{lon_s}&zoom=16&size=680*460&markers={marker}&key={tencent_key}"
        )
        errors: list[str] = []
        try:
            verify: bool | str = False if insecure_tls else certifi.where()
            content: bytes | None = None
            try:
                with httpx.Client(
                    timeout=12.0, verify=verify, follow_redirects=True,
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
                else:
                    errors.append(f"HTTP {resp.status_code}")
            except Exception as inner_exc:  # noqa: BLE001
                errors.append(str(inner_exc))
            if content:
                pixmap = QPixmap()
                if pixmap.loadFromData(content):
                    with_circle = pixmap
                    if radius_m is not None:
                        with_circle = self._draw_range_circle_on_map(pixmap, lat, radius_m)
                    image_label.setPixmap(
                        with_circle.scaled(680, 460, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                    )
                else:
                    image_label.setText("地图图片解析失败")
            else:
                brief = errors[-1] if errors else "未知错误"
                QDesktopServices.openUrl(QUrl(osm_link))
                image_label.setText(f"腾讯地图加载失败: {brief}\n已自动跳转浏览器地图。")
        except Exception as exc:  # noqa: BLE001
            QDesktopServices.openUrl(QUrl(osm_link))
            image_label.setText(f"腾讯地图加载失败: {exc}\n已自动跳转浏览器地图。")
        dlg.exec()

    # --- 二维码 ---

    def _show_qrcode_dialog(self: Any, table: QTableWidget, row: int) -> None:
        """显示二维码对话框。"""
        from .qrcode_dialog import QRCodeDialog

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
        dialog = QRCodeDialog(
            parent=self, course_id=course_id, course_title=course_title,
            sign_in_window=sign_in_window, sign_out_window=sign_out_window,
        )
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        dialog.load_qrcode()
        self._open_dialogs.append(dialog)

        def _release_dialog(*_args: Any, dlg: QDialog = dialog) -> None:
            if dlg in self._open_dialogs:
                self._open_dialogs.remove(dlg)

        dialog.finished.connect(_release_dialog)
        dialog.open()
