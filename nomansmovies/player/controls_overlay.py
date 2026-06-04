"""Translucent hover-fade control bar that sits at the bottom of the video panel."""
from __future__ import annotations
from PySide6.QtCore import Qt, Signal, QPropertyAnimation, QTimer, QEvent
from PySide6.QtGui import QPainter, QColor, QLinearGradient, QCursor
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QSlider, QLabel,
    QGraphicsOpacityEffect,
)
from ..theme import theme_signal, current as current_theme


def _fmt(ms: int) -> str:
    if ms is None or ms < 0:
        return "0:00"
    s = int(ms // 1000)
    h, s = divmod(s, 3600)
    m, s = divmod(s, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


class ControlsOverlay(QWidget):
    play_pause = Signal()
    stop = Signal()
    rewind = Signal()       # -10s
    forward = Signal()      # +10s
    next_ = Signal()
    seek = Signal(int)      # ms
    volume = Signal(int)    # 0..100
    settings = Signal()
    fullscreen = Signal()

    BOTTOM_BAR_H = 130   # height of the visual gradient strip at the bottom

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        # Catch ALL mouse events across the entire video area. QVideoWidget uses
        # a native window so it doesn't deliver Enter events to Qt event filters;
        # making this overlay cover the whole panel lets US drive the hover logic.
        self.setAttribute(Qt.WA_NoMousePropagation, False)
        # Override theme.py's broad `QWidget { background-color }` rule, which
        # would otherwise paint a solid theme bg over the video border area.
        self.setObjectName("nmmControlsOverlay")

        lay = QVBoxLayout(self); lay.setContentsMargins(16, 8, 16, 12); lay.setSpacing(4)
        lay.addStretch(1)  # pushes the controls to the bottom

        # scrubber row
        srow = QHBoxLayout()
        self.cur_lbl = QLabel("0:00")
        self.scrubber = QSlider(Qt.Horizontal)
        self.scrubber.setRange(0, 0)
        self.scrubber.sliderMoved.connect(self._user_scrub)
        self.scrubber.sliderReleased.connect(self._user_release)
        self.tot_lbl = QLabel("0:00")
        srow.addWidget(self.cur_lbl); srow.addWidget(self.scrubber, 1); srow.addWidget(self.tot_lbl)
        lay.addLayout(srow)

        # button row
        brow = QHBoxLayout(); brow.setSpacing(6)
        self.stop_btn = self._mk("⏹", "Stop")
        self.rew_btn = self._mk("⏪ 10s", "Rewind 10 seconds")
        self.play_btn = self._mk("⏵", "Play / Pause", big=True)
        self.ff_btn = self._mk("10s ⏩", "Forward 10 seconds")
        self.next_btn = self._mk("⏭", "Next")
        self.stop_btn.clicked.connect(self.stop)
        self.rew_btn.clicked.connect(self.rewind)
        self.play_btn.clicked.connect(self.play_pause)
        self.ff_btn.clicked.connect(self.forward)
        self.next_btn.clicked.connect(self.next_)
        brow.addWidget(self.stop_btn); brow.addWidget(self.rew_btn)
        brow.addWidget(self.play_btn); brow.addWidget(self.ff_btn)
        brow.addWidget(self.next_btn)
        brow.addStretch(1)

        self.vol_icon = QLabel("🔊")
        self.vol = QSlider(Qt.Horizontal); self.vol.setRange(0, 100); self.vol.setValue(85)
        self.vol.setFixedWidth(120)
        self.vol.valueChanged.connect(self.volume)
        brow.addWidget(self.vol_icon)
        brow.addWidget(self.vol)
        self.settings_btn = self._mk("⚙", "Settings")
        self.settings_btn.clicked.connect(self.settings)
        self.fs_btn = self._mk("⛶", "Fullscreen")
        self.fs_btn.clicked.connect(self.fullscreen)
        brow.addWidget(self.settings_btn); brow.addWidget(self.fs_btn)
        lay.addLayout(brow)

        # fade — windowOpacity is a no-op on non-top-level widgets, so use a graphics effect.
        self._fx = QGraphicsOpacityEffect(self)
        self._fx.setOpacity(0.0)
        self.setGraphicsEffect(self._fx)
        self._anim = QPropertyAnimation(self._fx, b"opacity")
        self._anim.setDuration(200)
        self._hide_timer = QTimer(self); self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self.fade_out)
        self._scrubbing = False

        self._apply_theme(current_theme())
        theme_signal.changed.connect(self._apply_theme)

        # Keep the overlay visible while the mouse is over any child widget
        # (buttons / slider). Their events don't bubble up to the parent.
        for child in self.findChildren(QWidget):
            child.setMouseTracking(True)
            child.installEventFilter(self)

        # QVideoWidget uses a native Win32 surface that absorbs mouse events
        # before Qt sees them — so even covering the panel doesn't reliably
        # deliver Enter to us. Poll the cursor at 80 ms instead.
        self._cursor_poll = QTimer(self)
        self._cursor_poll.setInterval(80)
        self._cursor_poll.timeout.connect(self._poll_cursor)
        self._cursor_poll.start()

    def _poll_cursor(self) -> None:
        parent = self.parentWidget()
        if parent is None or not parent.isVisible():
            return
        pos_local = parent.mapFromGlobal(QCursor.pos())
        if parent.rect().contains(pos_local):
            self.kick()

    def eventFilter(self, obj, e):
        t = e.type()
        if t in (QEvent.Enter, QEvent.MouseMove, QEvent.MouseButtonPress):
            self.kick()
        return super().eventFilter(obj, e)

    def _mk(self, text: str, tip: str, big: bool = False) -> QPushButton:
        b = QPushButton(text); b.setToolTip(tip); b.setCursor(Qt.PointingHandCursor)
        b.setProperty("overlayBtn", "big" if big else "std")
        return b

    def _apply_theme(self, c: dict) -> None:
        # Always white — these controls sit on a hardcoded dark gradient, and the
        # theme's foreground may be dark (e.g., Daylight theme) which would be unreadable.
        accent = c.get("accent", "#e50914")
        self.setStyleSheet(
            # CRITICAL: overlay itself must be transparent so the video border
            # underneath is visible. The bottom gradient is painted in paintEvent.
            "QWidget#nmmControlsOverlay { background: transparent; }"
            "QLabel { color: #ffffff; background: transparent; font-weight: 600; }"
            "QPushButton[overlayBtn=\"std\"] { background: rgba(255,255,255,0.18); color: #ffffff; "
            "border: 1px solid rgba(255,255,255,0.25); border-radius: 6px; padding: 6px 10px; "
            "font-size: 11pt; font-weight: 600; } "
            "QPushButton[overlayBtn=\"std\"]:hover { background: rgba(255,255,255,0.30); } "
            "QPushButton[overlayBtn=\"big\"] { background: rgba(255,255,255,0.22); color: #ffffff; "
            "border: 1px solid rgba(255,255,255,0.30); border-radius: 6px; padding: 8px 14px; "
            "font-size: 14pt; font-weight: 700; } "
            "QPushButton[overlayBtn=\"big\"]:hover { background: rgba(255,255,255,0.35); } "
            "QSlider::groove:horizontal { height: 4px; background: rgba(255,255,255,0.25); border-radius: 2px; } "
            f"QSlider::sub-page:horizontal {{ background: {accent}; border-radius: 2px; }} "
            "QSlider::handle:horizontal { background: #ffffff; width: 12px; margin: -5px 0; border-radius: 6px; } "
        )

    # ============ paint — gradient only in the bottom strip ============
    def paintEvent(self, e):
        p = QPainter(self)
        h = min(self.BOTTOM_BAR_H, max(110, self.height() // 4))
        if self.height() < 80:
            h = self.height()
        grad = QLinearGradient(0, self.height() - h, 0, self.height())
        grad.setColorAt(0, QColor(0, 0, 0, 0))
        grad.setColorAt(1, QColor(0, 0, 0, 220))
        p.fillRect(0, self.height() - h, self.width(), h, grad)

    def enterEvent(self, e):
        self.fade_in()
        super().enterEvent(e)

    def leaveEvent(self, e):
        self._hide_timer.start(800)
        super().leaveEvent(e)

    def mouseMoveEvent(self, e):
        self.kick()
        super().mouseMoveEvent(e)

    # ============ fade ============
    def fade_in(self) -> None:
        self._anim.stop()
        self._anim.setStartValue(self._fx.opacity()); self._anim.setEndValue(1.0)
        self._anim.start()
        self.show()
        self.raise_()
        self._hide_timer.start(2500)

    def fade_out(self) -> None:
        if self._scrubbing:
            self._hide_timer.start(1500); return
        self._anim.stop()
        self._anim.setStartValue(self._fx.opacity()); self._anim.setEndValue(0.0)
        self._anim.start()

    def kick(self) -> None:
        if self._fx.opacity() < 0.95:
            self.fade_in()
        else:
            self._hide_timer.start(2500)

    # ============ scrubber ============
    def update_position(self, ms: int) -> None:
        if not self._scrubbing:
            self.scrubber.blockSignals(True)
            self.scrubber.setValue(ms)
            self.scrubber.blockSignals(False)
        self.cur_lbl.setText(_fmt(ms))

    def update_duration(self, ms: int) -> None:
        self.scrubber.setRange(0, max(0, ms))
        self.tot_lbl.setText(_fmt(ms))

    def set_playing(self, playing: bool) -> None:
        self.play_btn.setText("⏸" if playing else "⏵")

    def _user_scrub(self, val: int) -> None:
        self._scrubbing = True
        self.cur_lbl.setText(_fmt(val))

    def _user_release(self) -> None:
        self._scrubbing = False
        self.seek.emit(self.scrubber.value())
