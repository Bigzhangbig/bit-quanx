from __future__ import annotations

from PySide6.QtCore import QObject, QRunnable, Signal


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
        try:
            result = self.fn(*self.args, **self.kwargs)
        except Exception as exc:  # noqa: BLE001
            result = (False, f"Worker exception: {exc}", {})
        self.signals.done.emit(result)
