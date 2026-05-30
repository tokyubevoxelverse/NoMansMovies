"""Left dock: direct link input, YouTube search, local file picker."""
from __future__ import annotations
import threading
from typing import List
from PySide6.QtCore import Qt, Signal, QSize, QThread, QObject, QTimer
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QListWidget, QListWidgetItem, QFileDialog, QFrame
)
import requests

from .. import ytdlp_manager


class _ResultRow(QFrame):
    def __init__(self, item: dict, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.NoFrame)
        h = QHBoxLayout(self); h.setContentsMargins(4, 4, 4, 4); h.setSpacing(8)
        self.thumb = QLabel(); self.thumb.setFixedSize(120, 68)
        self.thumb.setObjectName("thumbBox")
        h.addWidget(self.thumb)
        right = QVBoxLayout(); right.setSpacing(2)
        title = QLabel(item.get("title", "")); title.setWordWrap(True)
        title.setStyleSheet("font-weight: 600;")
        chan = QLabel(item.get("channel", "")); chan.setProperty("muted", True)
        desc = QLabel((item.get("description") or "")[:140] + ("…" if (item.get("description") or "")[140:] else ""))
        desc.setWordWrap(True); desc.setProperty("muted", True); desc.setStyleSheet("font-size: 9pt;")
        right.addWidget(title); right.addWidget(chan); right.addWidget(desc)
        h.addLayout(right, 1)


class _ThumbLoader(QObject):
    done = Signal(int, bytes)

    def __init__(self, idx: int, url: str):
        super().__init__()
        self.idx = idx; self.url = url

    def run(self) -> None:
        try:
            r = requests.get(self.url, timeout=10)
            r.raise_for_status()
            self.done.emit(self.idx, r.content)
        except Exception:
            self.done.emit(self.idx, b"")


class _SearchWorker(QObject):
    done = Signal(list)
    def __init__(self, q: str):
        super().__init__(); self.q = q
    def run(self) -> None:
        try:
            self.done.emit(ytdlp_manager.search_youtube(self.q, n=5))
        except Exception:
            self.done.emit([])


class SourcePanel(QWidget):
    play_url = Signal(str)        # direct mp4 etc
    play_youtube = Signal(str)    # youtube page url
    play_local = Signal(str)      # local file path

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self); lay.setContentsMargins(10, 10, 10, 10); lay.setSpacing(8)

        title = QLabel("Sources"); title.setStyleSheet("font-size: 14pt; font-weight: 700;")
        lay.addWidget(title)

        lay.addWidget(QLabel("Paste a direct movie link"))
        link_row = QHBoxLayout()
        self.link = QLineEdit(); self.link.setPlaceholderText("https://…/movie.mp4")
        self.link.returnPressed.connect(self._play_link)
        play_link = QPushButton("Play"); play_link.setProperty("accent", True); play_link.clicked.connect(self._play_link)
        link_row.addWidget(self.link, 1); link_row.addWidget(play_link)
        lay.addLayout(link_row)

        lay.addSpacing(4)
        lay.addWidget(QLabel("Search YouTube"))
        s_row = QHBoxLayout()
        self.search = QLineEdit(); self.search.setPlaceholderText("type and press Enter")
        self.search.returnPressed.connect(self._search)
        s_btn = QPushButton("Search"); s_btn.clicked.connect(self._search)
        s_row.addWidget(self.search, 1); s_row.addWidget(s_btn)
        lay.addLayout(s_row)

        self.results = QListWidget()
        self.results.setSelectionMode(QListWidget.SingleSelection)
        self.results.itemDoubleClicked.connect(self._play_result)
        lay.addWidget(self.results, 1)

        lay.addWidget(QLabel("Or stream a local file"))
        local_btn = QPushButton("Open local video…"); local_btn.clicked.connect(self._open_local)
        lay.addWidget(local_btn)

        self._results_data: List[dict] = []
        self._threads: list = []

    def _play_link(self) -> None:
        url = self.link.text().strip()
        if not url:
            return
        if "youtube.com/" in url or "youtu.be/" in url:
            self.play_youtube.emit(url)
        else:
            self.play_url.emit(url)

    def _open_local(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Open video", "", "Videos (*.mp4 *.mkv *.webm *.mov *.avi *.m4v)")
        if path:
            self.play_local.emit(path)

    def _search(self) -> None:
        q = self.search.text().strip()
        if not q:
            return
        self.results.clear()
        self.results.addItem("Searching…")
        # background search
        th = QThread(self); w = _SearchWorker(q); w.moveToThread(th)
        th.started.connect(w.run)
        w.done.connect(self._on_results); w.done.connect(th.quit); w.done.connect(w.deleteLater)
        th.finished.connect(th.deleteLater)
        self._threads.append((th, w))
        th.start()

    def _on_results(self, results: List[dict]) -> None:
        self._results_data = results
        self.results.clear()
        if not results:
            self.results.addItem("No results."); return
        for i, item in enumerate(results):
            li = QListWidgetItem(); li.setSizeHint(QSize(0, 84)); li.setData(Qt.UserRole, i)
            self.results.addItem(li)
            row = _ResultRow(item)
            self.results.setItemWidget(li, row)
            # fetch thumb
            if item.get("thumbnail"):
                th = QThread(self); w = _ThumbLoader(i, item["thumbnail"]); w.moveToThread(th)
                th.started.connect(w.run)
                w.done.connect(self._on_thumb); w.done.connect(th.quit); w.done.connect(w.deleteLater)
                th.finished.connect(th.deleteLater)
                self._threads.append((th, w))
                th.start()

    def _on_thumb(self, idx: int, data: bytes) -> None:
        if not data or idx >= self.results.count():
            return
        item = self.results.item(idx)
        widget = self.results.itemWidget(item)
        if not isinstance(widget, _ResultRow):
            return
        pm = QPixmap(); pm.loadFromData(data)
        if not pm.isNull():
            widget.thumb.setPixmap(pm.scaled(widget.thumb.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def _play_result(self, item: QListWidgetItem) -> None:
        idx = item.data(Qt.UserRole)
        if idx is None or idx >= len(self._results_data):
            return
        url = self._results_data[idx].get("url")
        if url:
            self.play_youtube.emit(url)
