"""Small control bar shown inside a FloatingPanel during overlay mode.

Layout:
    [👤 Profile] [🎬 Movie Player] [⊕ Recenter video]
    [show: Movie] [show: Sources] [show: Watch]
    [stretch]
    [Opacity slider]
    [🚪  LEAVE OVERLAY]
"""
from __future__ import annotations
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QSlider, QLabel
)


class OverlayControls(QWidget):
    profile_clicked = Signal()
    player_clicked = Signal()
    exit_overlay = Signal()
    opacity_changed = Signal(int)   # 30..100
    recenter_video = Signal()
    show_panel = Signal(str)        # "video" | "source" | "watch"

    def __init__(self, parent=None):
        super().__init__(parent)
        outer = QVBoxLayout(self); outer.setContentsMargins(10, 8, 10, 8); outer.setSpacing(4)

        # Row 1: mode + recenter
        row1 = QHBoxLayout(); row1.setSpacing(6)
        self.profile_btn = QPushButton("👤  Profile")
        self.profile_btn.clicked.connect(self.profile_clicked)
        row1.addWidget(self.profile_btn)

        self.player_btn = QPushButton("🎬  Movie Player")
        self.player_btn.setProperty("accent", True)
        self.player_btn.setEnabled(False)
        self.player_btn.clicked.connect(self.player_clicked)
        row1.addWidget(self.player_btn)

        self.recenter_btn = QPushButton("⊕  Recenter video")
        self.recenter_btn.setToolTip("Reset the movie panel to a centered position and default size")
        self.recenter_btn.clicked.connect(self.recenter_video)
        row1.addWidget(self.recenter_btn)
        row1.addStretch(1)
        outer.addLayout(row1)

        # Row 2: show-panel chips + opacity + leave overlay
        row2 = QHBoxLayout(); row2.setSpacing(6)

        lbl = QLabel("Show:"); lbl.setProperty("muted", True); row2.addWidget(lbl)
        self.show_movie_btn = QPushButton("Movie")
        self.show_movie_btn.setFixedWidth(72)
        self.show_movie_btn.clicked.connect(lambda: self.show_panel.emit("video"))
        row2.addWidget(self.show_movie_btn)
        self.show_sources_btn = QPushButton("Sources")
        self.show_sources_btn.setFixedWidth(80)
        self.show_sources_btn.clicked.connect(lambda: self.show_panel.emit("source"))
        row2.addWidget(self.show_sources_btn)
        self.show_watch_btn = QPushButton("Watch")
        self.show_watch_btn.setFixedWidth(72)
        self.show_watch_btn.clicked.connect(lambda: self.show_panel.emit("watch"))
        row2.addWidget(self.show_watch_btn)
        self.show_playback_btn = QPushButton("Playback")
        self.show_playback_btn.setFixedWidth(86)
        self.show_playback_btn.clicked.connect(lambda: self.show_panel.emit("playback"))
        row2.addWidget(self.show_playback_btn)

        row2.addSpacing(16)
        row2.addWidget(QLabel("Opacity"))
        self.opacity = QSlider(Qt.Horizontal)
        self.opacity.setRange(30, 100); self.opacity.setValue(100)
        self.opacity.setFixedWidth(120)
        self.opacity.valueChanged.connect(self.opacity_changed)
        row2.addWidget(self.opacity)

        row2.addStretch(1)

        self.exit_btn = QPushButton("🚪  Exit App")
        self.exit_btn.setProperty("accent", True)
        self.exit_btn.setMinimumHeight(36)
        self.exit_btn.setStyleSheet("QPushButton { font-weight: 700; font-size: 11pt; padding: 6px 18px; }")
        self.exit_btn.clicked.connect(self.exit_overlay)
        row2.addWidget(self.exit_btn)

        outer.addLayout(row2)
