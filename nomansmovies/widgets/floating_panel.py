"""Frameless, always-on-top floating panel.

Wraps a content widget with:
    - draggable title bar (drag anywhere on it to move via native window manager)
    - resize on every edge AND corner (via Qt's startSystemResize)
    - minimize → collapses to just the title bar
    - close → emits closed signal (caller decides what to do)
Used in overlay mode to give each panel (video, sources, watch, controls) its
own independent floating window.
"""
from __future__ import annotations
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QCursor, QMouseEvent
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame, QSizePolicy
)
from ..theme import theme_signal, current as current_theme

_EDGE = 10  # pixels around the border that trigger resize


def _cursor_for_edges(edges: Qt.Edges) -> QCursor:
    l = bool(edges & Qt.LeftEdge);  r = bool(edges & Qt.RightEdge)
    t = bool(edges & Qt.TopEdge);   b = bool(edges & Qt.BottomEdge)
    if (l and t) or (r and b): return QCursor(Qt.SizeFDiagCursor)
    if (r and t) or (l and b): return QCursor(Qt.SizeBDiagCursor)
    if l or r:                 return QCursor(Qt.SizeHorCursor)
    if t or b:                 return QCursor(Qt.SizeVerCursor)
    return QCursor(Qt.ArrowCursor)


class _TitleBar(QWidget):
    minimize_requested = Signal()
    close_requested = Signal()

    def __init__(self, title: str, top_window: QWidget, parent=None):
        super().__init__(parent)
        self.setObjectName("floatTitle")
        self.setFixedHeight(30)
        self._top = top_window
        self.setCursor(Qt.SizeAllCursor)

        lay = QHBoxLayout(self); lay.setContentsMargins(10, 0, 4, 0); lay.setSpacing(4)
        self._title = QLabel(title)
        self._title.setStyleSheet("font-weight: 600; background: transparent;")
        lay.addWidget(self._title, 1)

        self._extra_btns_layout = lay   # remember so we can insert before the
                                        # min/close buttons later
        self._min_btn = QPushButton("—"); self._min_btn.setObjectName("floatBtn")
        self._min_btn.setFixedSize(26, 22); self._min_btn.setToolTip("Minimize")
        self._min_btn.clicked.connect(self.minimize_requested)
        self._close_btn = QPushButton("✕"); self._close_btn.setObjectName("floatBtn")
        self._close_btn.setFixedSize(26, 22); self._close_btn.setToolTip("Exit overlay mode")
        self._close_btn.clicked.connect(self.close_requested)
        lay.addWidget(self._min_btn); lay.addWidget(self._close_btn)

    def add_button(self, text: str, tooltip: str, callback) -> QPushButton:
        """Insert a small button before the minimize / close buttons."""
        btn = QPushButton(text); btn.setObjectName("floatBtn")
        btn.setFixedSize(26, 22); btn.setToolTip(tooltip)
        btn.clicked.connect(callback)
        # Position: after the title label + stretch, before — and ✕
        # (— is currently the 3rd-from-end, ✕ the last). Insert at count-2.
        idx = self._extra_btns_layout.count() - 2
        self._extra_btns_layout.insertWidget(idx, btn)
        return btn

    def set_minimized_icon(self, minimized: bool) -> None:
        self._min_btn.setText("▢" if minimized else "—")
        self._min_btn.setToolTip("Restore" if minimized else "Minimize")

    def hide_close_button(self) -> None:
        self._close_btn.hide()

    def set_title(self, t: str) -> None:
        self._title.setText(t)

    def mousePressEvent(self, e: QMouseEvent):
        if e.button() == Qt.LeftButton:
            wh = self._top.windowHandle()
            if wh is not None:
                wh.startSystemMove()
                return
        super().mousePressEvent(e)


class FloatingPanel(QWidget):
    closed = Signal()
    minimized_changed = Signal(bool)

    def __init__(self, title: str, content: QWidget, parent=None):
        super().__init__(parent)
        # No Qt.Tool — that flag breaks QVideoWidget's native window on Windows.
        self.setWindowFlags(
            Qt.Window
            | Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
        )
        self.setMouseTracking(True)
        self.setMinimumSize(280, 160)

        outer = QVBoxLayout(self); outer.setContentsMargins(0, 0, 0, 0); outer.setSpacing(0)

        self._card = QFrame(); self._card.setObjectName("floatCard")
        self._card.setMouseTracking(True)
        card_lay = QVBoxLayout(self._card); card_lay.setContentsMargins(0, 0, 0, 0); card_lay.setSpacing(0)

        self.title_bar = _TitleBar(title, self, self._card)
        self.title_bar.minimize_requested.connect(self._toggle_minimize)
        self.title_bar.close_requested.connect(self._on_close)
        card_lay.addWidget(self.title_bar, 0)

        self._content_holder = QWidget()
        self._content_holder.setMouseTracking(True)
        self._content_holder.setMinimumSize(200, 100)
        self._content_holder.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        ch = QVBoxLayout(self._content_holder); ch.setContentsMargins(0, 0, 0, 0); ch.setSpacing(0)
        ch.addWidget(content)
        content.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        # CRITICAL: QStackedWidget.removeWidget() and QDockWidget.setWidget() leave
        # the previous widget HIDDEN. Force-show it here or the panel ends up empty.
        content.setVisible(True)
        card_lay.addWidget(self._content_holder, 1)
        self._content = content

        outer.addWidget(self._card)

        self._minimized = False
        self._restore_height: int | None = None
        # Captured the first time we minimize so we can restore the panel's
        # NATURAL minimum height (which main may have set to something other
        # than the FloatingPanel default of 160 — e.g. controls is 130).
        self._saved_min_height: int | None = None

        self._apply_theme(current_theme())
        theme_signal.changed.connect(self._apply_theme)

    # ---- show helper ----
    def show_with_geometry(self, x: int, y: int, w: int, h: int) -> None:
        """Show then resize/move — frameless windows on Windows are more reliable
        if you show first and resize after."""
        self.show()
        self.resize(max(self.minimumWidth(), w), max(self.minimumHeight(), h))
        self.move(x, y)
        self.raise_()
        self._force_show_children()

    def _force_show_children(self) -> None:
        """QStackedWidget.removeWidget() and QDockWidget.setWidget() leave the
        OLD widget and many of its children in the explicitly-hidden state.
        Walk the content tree and un-hide everything so the user actually sees
        the form fields inside Source / Watch panels.

        If the panel is currently minimized, do NOT un-hide content — the
        title-bar-only look must persist."""
        if self._minimized:
            return
        self._content_holder.setVisible(True)
        self._content.setVisible(True)
        from PySide6.QtWidgets import QWidget as _QW
        for child in self._content.findChildren(_QW):
            child.setVisible(True)
        self._content.updateGeometry()
        self._content.update()

    # ---- minimize state ----
    @property
    def minimized(self) -> bool:
        return self._minimized

    def apply_minimized(self, minimized: bool) -> None:
        """Force the panel into the given minimized state. Idempotent — calling
        twice with the same value is safe and re-asserts the visual state in
        case _force_show_children or external code un-hid the content."""
        # On the very first call, remember the panel's natural minimum height
        # so a later restoration uses it (rather than a hardcoded 160).
        if self._saved_min_height is None and not self._minimized:
            self._saved_min_height = self.minimumHeight()

        if minimized != self._minimized:
            self._toggle_minimize()
        # Re-assert visual state — handles the case where _force_show_children
        # un-hid content while we were "minimized" (or content got hidden while
        # we should be un-minimized).
        if minimized:
            self._content_holder.hide()
            new_h = self.title_bar.height() + 2
            self.resize(self.width(), new_h)
            self.title_bar.set_minimized_icon(True)
        else:
            self._content_holder.show()
            # NOTE: do NOT call setMinimumHeight here — the toggle path already
            # restored the saved minimum, and overriding with a constant would
            # break per-panel minimums set from main (e.g., controls is 130).
            self.title_bar.set_minimized_icon(False)

    # ---- API ----
    def set_title(self, t: str) -> None:
        self.title_bar.set_title(t)

    def hide_close_button(self) -> None:
        """Remove the ✕ button from the title bar (only minimize will remain)."""
        self.title_bar.hide_close_button()

    def add_title_button(self, text: str, tooltip: str, callback):
        """Insert a custom button into the title strip, before the — / ✕ icons."""
        return self.title_bar.add_button(text, tooltip, callback)

    def take_content(self) -> QWidget:
        """Detach the content widget and return it (caller becomes responsible for it)."""
        layout = self._content_holder.layout()
        layout.removeWidget(self._content)
        self._content.setParent(None)
        return self._content

    # ---- minimize ----
    def _toggle_minimize(self) -> None:
        if self._minimized:
            self._content_holder.show()
            # Restore the natural minimum height we captured before minimizing
            # (NOT a hardcoded 160 — that would override main's setMinimumSize
            # for panels like the NoMansMovies controls bar, which is 130).
            self.setMinimumHeight(self._saved_min_height if self._saved_min_height is not None else 160)
            if self._restore_height:
                self.resize(self.width(), self._restore_height)
            self._minimized = False
        else:
            self._restore_height = self.height()
            # Capture BEFORE we change it.
            self._saved_min_height = self.minimumHeight()
            self._content_holder.hide()
            new_h = self.title_bar.height() + 2
            self.setMinimumHeight(new_h)
            self.resize(self.width(), new_h)
            self._minimized = True
        self.title_bar.set_minimized_icon(self._minimized)
        self.minimized_changed.emit(self._minimized)

    def _on_close(self) -> None:
        self.hide()
        self.closed.emit()

    # ---- theme ----
    def _apply_theme(self, c: dict) -> None:
        self.setStyleSheet(f"""
            QFrame#floatCard {{
                background: {c['bg']};
                border: 1px solid {c['border']};
            }}
            QWidget#floatTitle {{
                background: {c['panel']};
                border-bottom: 1px solid {c['border']};
            }}
            QWidget#floatTitle QLabel {{ color: {c['fg']}; background: transparent; }}
            QPushButton#floatBtn {{
                background: transparent;
                color: {c['fg']};
                border: 1px solid transparent;
                border-radius: 4px;
                padding: 0;
                font-weight: 600;
            }}
            QPushButton#floatBtn:hover {{ background: rgba(255,255,255,0.15); }}
        """)

    # ---- edge resize via native system resize ----
    def _edges_at(self, pos) -> Qt.Edges:
        e = Qt.Edges()
        if pos.x() <= _EDGE: e |= Qt.LeftEdge
        if pos.x() >= self.width() - _EDGE: e |= Qt.RightEdge
        if pos.y() <= _EDGE: e |= Qt.TopEdge
        if pos.y() >= self.height() - _EDGE: e |= Qt.BottomEdge
        return e

    def mouseMoveEvent(self, e: QMouseEvent):
        if not self._minimized:
            self.setCursor(_cursor_for_edges(self._edges_at(e.position().toPoint())))
        super().mouseMoveEvent(e)

    def mousePressEvent(self, e: QMouseEvent):
        if e.button() == Qt.LeftButton and not self._minimized:
            edges = self._edges_at(e.position().toPoint())
            if edges:
                wh = self.windowHandle()
                if wh is not None:
                    wh.startSystemResize(edges)
                    return
        super().mousePressEvent(e)

    def leaveEvent(self, e):
        self.unsetCursor()
        super().leaveEvent(e)
