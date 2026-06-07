from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from dekt_gui.main_window import MainWindow


def get_resource_path(relative_path: str) -> Path:
    """获取资源文件的绝对路径，兼容开发环境和 PyInstaller 打包环境"""
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / relative_path
    return Path(__file__).resolve().parent.parent / relative_path


def main() -> int:
    app = QApplication(sys.argv)
    icon_path = get_resource_path("BIT.png")
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
