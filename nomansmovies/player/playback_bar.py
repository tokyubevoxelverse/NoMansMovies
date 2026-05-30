"""Dedicated playback controls — always visible, never relies on hover.

Layout:
    [00:00]  [============ scrubber ============]  [12:34]
    [⏹] [⏪ 10s] [⏵/⏸] [10s ⏩] [⏭]  [🔊 vol]   [🔄 Resync]  [⚙]  [⛶]
"""
from __future__ import annotations
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QSlider, QLabel
)


def _fmt(ms: int) -> str:
    if ms is None or ms < 0:
        return "0:00"
    s = int(ms // 1000)
    h, s = divmod(s, 3600)
    m, s = divmod(s, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


class PlaybackControlsBar(QWidget):
    play_pause = Signal()
    stop = Signal()
    rewind = Signal()
    forward = Signal()
    next_ = Signal()
    seek = Signal(int)
    volume = Signal(int)
    resync = Signal()
    settings = Signal()
    fullscreen = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(110)

        outer = QVBoxLayout(self); outer.setContentsMargins(10, 8, 10, 10); outer.setSpacing(6)

        # ---- Row 1: scrubber + times ----
        srow = QHBoxLayout(); srow.setSpacing(8)
        self.cur_lbl = QLabel("0:00")
        self.cur_lbl.setFixedWidth(70); self.cur_lbl.setAlignment(Qt.AlignCenter)
        self.cur_lbl.setStyleSheet("font-family: 'Consolas', monospace; font-weight: 600;")

        self.scrubber = QSlider(Qt.Horizontal)
        self.scrubber.setRange(0, 0)
        self.scrubber.sliderMoved.connect(self._user_scrub)
        self.scrubber.sliderReleased.connect(self._user_release)

        self.tot_lbl = QLabel("0:00")
        self.tot_lbl.setFixedWidth(70); self.tot_lbl.setAlignment(Qt.AlignCenter)
        self.tot_lbl.setStyleSheet("font-family: 'Consolas', monospace; font-weight: 600;")

        srow.addWidget(self.cur_lbl)
        srow.addWidget(self.scrubber, 1)
        srow.addWidget(self.tot_lbl)
        outer.addLayout(srow)

        # ---- Row 2: buttons + volume + resync + settings ----
        brow = QHBoxLayout(); brow.setSpacing(6)

        def mk(text: str, tip: str, w: int | None = None, accent: bool = False) -> QPushButton:
            b = QPushButton(text); b.setToolTip(tip)
            b.setMinimumHeight(32)
            if w: b.setFixedWidth(w)
            if accent: b.setProperty("accent", True)
            return b

        self.stop_btn = mk("⏹", "Stop", 46)
        self.stop_btn.clicked.connect(self.stop)
        self.rew_btn  = mk("⏪ 10s", "Rewind 10 seconds", 84)
        self.rew_btn.clicked.connect(self.rewind)
        self.play_btn = mk("⏵", "Play / Pause", 60, accent=True)
        self.play_btn.clicked.connect(self.play_pause)
        self.ff_btn   = mk("10s ⏩", "Forward 10 seconds", 84)
        self.ff_btn.clicked.connect(self.forward)
        self.next_btn = mk("⏭", "Next", 46)
        self.next_btn.clicked.connect(self.next_)

        for b in (self.stop_btn, self.rew_btn, self.play_btn, self.ff_btn, self.next_btn):
            brow.addWidget(b)
        brow.addSpacing(12)

        brow.addWidget(QLabel("🔊"))
        self.vol = QSlider(Qt.Horizontal); self.vol.setRange(0, 100); self.vol.setValue(85)
        self.vol.setFixedWidth(110)
        self.vol.valueChanged.connect(self.volume)
        brow.addWidget(self.vol)

        brow.addStretch(1)

        self.resync_btn = mk("🔄 Resync", "Resync playback with everyone in your watch room", 110)
        self.resync_btn.setEnabled(False)
        self.resync_btn.clicked.connect(self.resync)
        brow.addWidget(self.resync_btn)

        self.settings_btn = mk("⚙", "Player settings (quality, aspect ratio)", 40)
        self.settings_btn.clicked.connect(self.settings)
        brow.addWidget(self.settings_btn)

        self.fs_btn = mk("⛶", "Fullscreen", 40)
        self.fs_btn.clicked.connect(self.fullscreen)
        brow.addWidget(self.fs_btn)

        outer.addLayout(brow)
        self._scrubbing = False

    # ============ API ============
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

    def set_resync_enabled(self, enabled: bool) -> None:
        self.resync_btn.setEnabled(enabled)

    # ============ scrubber internals ============
    def _user_scrub(self, val: int) -> None:
        self._scrubbing = True
        self.cur_lbl.setText(_fmt(val))

    def _user_release(self) -> None:
        self._scrubbing = False
        self.seek.emit(self.scrubber.value())
