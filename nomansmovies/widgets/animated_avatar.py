"""QLabel that auto-plays animated GIFs and falls back to static images."""
from __future__ import annotations
import io
import os
import tempfile
from typing import Optional

import requests
from PySide6.QtCore import Qt, QSize, QThread, Signal, QObject
from PySide6.QtGui import QMovie, QPixmap, QPainter, QPainterPath, QColor
from PySide6.QtWidgets import QLabel


class _Downloader(QObject):
    done = Signal(str)  # path

    def __init__(self, url: str):
        super().__init__()
        self.url = url

    def run(self) -> None:
        try:
            r = requests.get(self.url, timeout=20)
            r.raise_for_status()
            ext = os.path.splitext(self.url.split("?")[0])[1].lower() or ".img"
            fd, path = tempfile.mkstemp(suffix=ext, prefix="nmm_av_")
            with os.fdopen(fd, "wb") as f:
                f.write(r.content)
            self.done.emit(path)
        except Exception:
            self.done.emit("")


class AnimatedAvatar(QLabel):
    """Round avatar that plays GIFs via QMovie or shows a static pixmap."""

    def __init__(self, size: int = 96, parent=None):
        super().__init__(parent)
        self._size = size
        self.setFixedSize(QSize(size, size))
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet("background: rgba(255,255,255,0.05); border-radius: %dpx;" % (size // 2))
        self._movie: Optional[QMovie] = None
        self._thread: Optional[QThread] = None
        self._worker: Optional[_Downloader] = None
        self._placeholder()

    def _placeholder(self) -> None:
        pm = QPixmap(self._size, self._size)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)
        p.setBrush(QColor(255, 255, 255, 30))
        p.setPen(Qt.NoPen)
        p.drawEllipse(0, 0, self._size, self._size)
        p.setPen(QColor(255, 255, 255, 200))
        f = p.font(); f.setPointSize(int(self._size * 0.35)); f.setBold(True); p.setFont(f)
        p.drawText(pm.rect(), Qt.AlignCenter, "?")
        p.end()
        self.setPixmap(pm)

    def set_url(self, url: Optional[str]) -> None:
        if not url:
            self._placeholder()
            return
        # Local path?
        if os.path.exists(url):
            self._load(url); return
        # Spawn downloader thread
        self._thread = QThread(self)
        self._worker = _Downloader(url)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.done.connect(self._load)
        self._worker.done.connect(self._thread.quit)
        self._worker.done.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.start()

    def _load(self, path: str) -> None:
        if not path or not os.path.exists(path):
            self._placeholder(); return
        ext = os.path.splitext(path)[1].lower()
        if ext == ".gif":
            self._movie = QMovie(path)
            self._movie.setScaledSize(QSize(self._size, self._size))
            self.setMovie(self._movie)
            self._movie.start()
        else:
            pm = QPixmap(path)
            if pm.isNull():
                self._placeholder(); return
            pm = pm.scaled(self._size, self._size, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            rounded = QPixmap(self._size, self._size)
            rounded.fill(Qt.transparent)
            p = QPainter(rounded)
            p.setRenderHint(QPainter.Antialiasing)
            path_ = QPainterPath()
            path_.addEllipse(0, 0, self._size, self._size)
            p.setClipPath(path_)
            p.drawPixmap(0, 0, pm)
            p.end()
            self.setPixmap(rounded)
