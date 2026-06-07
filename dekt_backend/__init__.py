"""DEKT backend service package."""

from __future__ import annotations

import sys
from pathlib import Path

# 让 dekt_gui_app.dekt_gui.* 的导入能直接用短名 dekt_gui.*,
# 与 dekt_backend 包内所有模块的导入风格保持一致。
_gui_app_path = Path(__file__).resolve().parent.parent / "dekt_gui_app"
if str(_gui_app_path) not in sys.path:
    sys.path.insert(0, str(_gui_app_path))
