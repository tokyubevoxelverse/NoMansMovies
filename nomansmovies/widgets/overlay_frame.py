"""Frameless always-on-top overlay frame.

Wraps any content widget with:
    - draggable title strip that auto-hides when not hovered
    - resize grip (bottom-right)
    - opacity slider (0.30 — 1.00)
    - exit-overlay + close buttons
Sits over No Man's Sky in **borderless windowed** mode (true fullscreen-exclusive
will hide it).
"""
from __future__ import annotations
from PySide6.QtCore import Qt, Signal, QPoint, QPropertyAnimation, QTimer, QEvent
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSlider,
    QSizeGrip, QFrame, QSizePolicy
)


class OverlayFrame(QWidget):
    exit_overlay = Signal()
    close_requested = Signal()

    def __init__(self, content: QWidget, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setMinimumSize(360, 220)
        self.resize(800, 500)
        self.setMouseTracking(True)

        outer = QVBoxLayout(self); outer.setContentsMargins(0, 0, 0, 0); outer.setSpacing(0)

        # Rounded translucent card
        card = QFrame(); card.setObjectName("overlayCard")
        card.setMouseTracking(True)
        card_lay = QVBoxLayout(card); card_lay.setContentsMargins(0, 0, 0, 0); card_lay.setSpacing(0)

        # Title strip — auto-hides
        self.strip = _DragStrip(self)
        self.strip.setObjectName("overlayStrip")
        self.strip.setFixedHeight(34)
        self.strip.setMouseTracking(True)
        strip_lay = QHBoxLayout(self.strip); strip_lay.setContentsMargins(10, 4, 6, 4); strip_lay.setSpacing(6)

        title = QLabel("NoMansMovies  ·  Overlay")
        title.setStyleSheet("font-weight: 600; background: transparent;")
        strip_lay.addWidget(title)
        strip_lay.addStretch(1)

        strip_lay.addWidget(QLabel("Opacity"))
        self.opacity = QSlider(Qt.Horizontal)
        self.opacity.setFixedWidth(110)
        self.opacity.setRange(30, 100); self.opacity.setValue(100)
        self.opacity.valueChanged.connect(lambda v: self.setWindowOpacity(v / 100.0))
        strip_lay.addWidget(self.opacity)

        exit_btn = QPushButton("⤢ Windowed")
        exit_btn.setToolTip("Exit overlay mode")
        exit_btn.clicked.connect(self.exit_overlay.emit)
        strip_lay.addWidget(exit_btn)

        close_btn = QPushButton("✕"); close_btn.setObjectName("closeBtn")
        close_btn.setFixedWidth(28)
        close_btn.clicked.connect(self.close_requested.emit)
        strip_lay.addWidget(close_btn)

        card_lay.addWidget(self.strip)

        # Content holder fills the rest
        self._content_holder = QWidget()
        self._content_holder.setMouseTracking(True)
        self._content_holder.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        holder_lay = QVBoxLayout(self._content_holder)
        holder_lay.setContentsMargins(0, 0, 0, 0); holder_lay.setSpacing(0)
        holder_lay.addWidget(content)
        content.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        card_lay.addWidget(self._content_holder, 1)

        # Resize grip — floats over the bottom-right corner
        self._grip = QSizeGrip(card)
        self._grip.setFixedSize(18, 18)

        outer.addWidget(card)
        self._content = content
        self._card = card

        # ---- auto-hide strip ----
        self.strip.setMaximumHeight(0)
        self._strip_anim = QPropertyAnimation(self.strip, b"maximumHeight")
        self._strip_anim.setDuration(180)
        self._strip_hide_timer = QTimer(self); self._strip_hide_timer.setSingleShot(True)
        self._strip_hide_timer.timeout.connect(self._hide_strip)
        self._strip_shown = False

        # Track mouse globally inside the overlay
        content.installEventFilter(self)
        self._content_holder.installEventFilter(self)
        self.strip.installEventFilter(self)
        card.installEventFilter(self)

    # ============ events ============
    def resizeEvent(self, e):
        super().resizeEvent(e)
        # Park the size grip in bottom-right of card
        self._grip.move(self._card.width() - self._grip.width() - 2,
                        self._card.height() - self._grip.height() - 2)
        self._grip.raise_()

    def eventFilter(self, obj, e):
        t = e.type()
        if t in (QEvent.MouseMove, QEvent.Enter):
            self._show_strip()
        elif t == QEvent.Leave:
            self._strip_hide_timer.start(1200)
        return super().eventFilter(obj, e)

    def enterEvent(self, e):
        self._show_strip()

    def leaveEvent(self, e):
        self._strip_hide_timer.start(1200)

    # ============ strip animation ============
    def _show_strip(self) -> None:
        if not self._strip_shown:
            self._strip_anim.stop()
            self._strip_anim.setStartValue(self.strip.maximumHeight()); self._strip_anim.setEndValue(34)
            self._strip_anim.start()
            self._strip_shown = True
        self._strip_hide_timer.start(2200)

    def _hide_strip(self) -> None:
        self._strip_anim.stop()
        self._strip_anim.setStartValue(self.strip.maximumHeight()); self._strip_anim.setEndValue(0)
        self._strip_anim.start()
        self._strip_shown = False


class _DragStrip(QWidget):
    """Top strip — click and drag moves the parent overlay window."""
    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self._drag_offset: QPoint | None = None
        self._target = parent

    def mousePressEvent(self, e: QMouseEvent):
        if e.button() == Qt.LeftButton:
            self._drag_offset = e.globalPosition().toPoint() - self._target.frameGeometry().topLeft()
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e: QMouseEvent):
        if self._drag_offset is not None and (e.buttons() & Qt.LeftButton):
            self._target.move(e.globalPosition().toPoint() - self._drag_offset)
        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e: QMouseEvent):
        self._drag_offset = None
        super().mouseReleaseEvent(e)
