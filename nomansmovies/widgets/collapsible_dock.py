"""QDockWidget with a custom title bar that supports minimize-to-tab."""
from __future__ import annotations
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QDockWidget, QWidget, QHBoxLayout, QLabel, QToolButton, QSizePolicy
)


class CollapsibleDock(QDockWidget):
    """A QDockWidget you can move, float, close, AND minimize to a thin strip."""

    def __init__(self, title: str, parent=None):
        super().__init__(title, parent)
        self.setFeatures(
            QDockWidget.DockWidgetMovable
            | QDockWidget.DockWidgetFloatable
            | QDockWidget.DockWidgetClosable
        )
        self._title = title
        self._collapsed = False
        self._content: QWidget | None = None

        self._titlebar = self._build_titlebar()
        self.setTitleBarWidget(self._titlebar)

    def _build_titlebar(self) -> QWidget:
        bar = QWidget()
        bar.setObjectName("dockTitleBar")
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(8, 4, 4, 4)
        lay.setSpacing(4)

        self._lbl = QLabel(self._title)
        self._lbl.setStyleSheet("font-weight: 600;")
        self._lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        lay.addWidget(self._lbl)

        self._btn_min = QToolButton()
        self._btn_min.setText("—")
        self._btn_min.setToolTip("Minimize")
        self._btn_min.setFixedSize(22, 22)
        self._btn_min.clicked.connect(self.toggle_collapsed)
        lay.addWidget(self._btn_min)

        self._btn_float = QToolButton()
        self._btn_float.setText("⧉")
        self._btn_float.setToolTip("Float / dock")
        self._btn_float.setFixedSize(22, 22)
        self._btn_float.clicked.connect(lambda: self.setFloating(not self.isFloating()))
        lay.addWidget(self._btn_float)

        self._btn_close = QToolButton()
        self._btn_close.setText("✕")
        self._btn_close.setToolTip("Close")
        self._btn_close.setFixedSize(22, 22)
        self._btn_close.clicked.connect(self.close)
        lay.addWidget(self._btn_close)

        # Styling lives in theme.py — targets QWidget#dockTitleBar
        return bar

    def setWidget(self, w: QWidget) -> None:
        self._content = w
        super().setWidget(w)

    def toggle_collapsed(self) -> None:
        self.set_collapsed(not self._collapsed)

    def is_collapsed(self) -> bool:
        return self._collapsed

    def set_collapsed(self, collapsed: bool) -> None:
        if not self._content:
            return
        self._collapsed = collapsed
        if self._collapsed:
            self._content.setMaximumHeight(0)
            self._btn_min.setText("▢")
            self._btn_min.setToolTip("Restore")
        else:
            self._content.setMaximumHeight(16777215)
            self._btn_min.setText("—")
            self._btn_min.setToolTip("Minimize")
