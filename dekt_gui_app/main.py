from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from dekt_gui.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    icon_path = Path(__file__).resolve().parent.parent / "BIT.png"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
