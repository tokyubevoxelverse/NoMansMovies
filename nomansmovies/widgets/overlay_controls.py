"""Floating control bar shown during overlay mode.

Row 1:  [👤 Profile…] [⊕ Recenter video] [⟳ Layout: <name>] [💾 Save Custom Layout]
Row 2:  [👁 Show All] [↺ Restore All]               [Opacity slider]

Overlay-only build: there's no windowed mode, so no Leave Overlay. ✕ on the
NoMansMovies controls panel quits the app (handled in main).
"""
from __future__ import annotations
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QSlider, QLabel, QSizePolicy
)
from ..config import LAYOUT_LABELS, LAYOUT_DEFAULT, CUSTOM_LAYOUT_PREFIX


class OverlayControls(QWidget):
    profile_clicked = Signal()       # opens the floating AppearancePanel
    opacity_changed = Signal(int)    # 30..100
    recenter_video = Signal()
    cycle_layout = Signal()
    show_all_panels = Signal()
    restore_all_panels = Signal()
    save_layout = Signal()
    minimize_all = Signal()
    show_controls_help = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        outer = QVBoxLayout(self); outer.setContentsMargins(10, 8, 10, 8); outer.setSpacing(6)

        # ---- Row 1: mode + recenter + layout cycle ----
        row1 = QHBoxLayout(); row1.setSpacing(6)

        self.profile_btn = QPushButton("👤  Profile…")
        self.profile_btn.setToolTip("Open the appearance editor (colors, fonts, default layout)")
        self.profile_btn.clicked.connect(self.profile_clicked)
        row1.addWidget(self.profile_btn)

        self.recenter_btn = QPushButton("⊕  Recenter video")
        self.recenter_btn.setToolTip("Reset the movie panel to a centered position and default size")
        self.recenter_btn.clicked.connect(self.recenter_video)
        row1.addWidget(self.recenter_btn)

        self.cycle_btn = QPushButton(f"⟳  Layout: {LAYOUT_LABELS[LAYOUT_DEFAULT]}")
        self.cycle_btn.setToolTip("Cycle through layout presets")
        self.cycle_btn.clicked.connect(self.cycle_layout)
        row1.addWidget(self.cycle_btn)

        self.save_layout_btn = QPushButton("💾  Save Custom Layout")
        self.save_layout_btn.setToolTip(
            "Save the current position, size, and minimized state of every floating panel.\n"
            "Restored the next time you enter overlay mode."
        )
        self.save_layout_btn.clicked.connect(self.save_layout)
        row1.addWidget(self.save_layout_btn)

        row1.addStretch(1)
        outer.addLayout(row1)

        # ---- Row 2: show / restore / opacity / leave ----
        row2 = QHBoxLayout(); row2.setSpacing(6)

        self.show_all_btn = QPushButton("👁  Show All")
        self.show_all_btn.setToolTip("Make every hidden floating panel visible again (keeps positions)")
        self.show_all_btn.clicked.connect(self.show_all_panels)
        row2.addWidget(self.show_all_btn)

        self.restore_all_btn = QPushButton("↺  Restore All Panels")
        self.restore_all_btn.setToolTip("Reset every floating panel to its default position and size")
        self.restore_all_btn.clicked.connect(self.restore_all_panels)
        row2.addWidget(self.restore_all_btn)

        self.minimize_all_btn = QPushButton("—  Minimize All Tabs")
        self.minimize_all_btn.setToolTip(
            "Hide every floating panel and put NoMansMovies in your Windows taskbar.\n"
            "Click the taskbar icon to bring everything back."
        )
        self.minimize_all_btn.clicked.connect(self.minimize_all)
        row2.addWidget(self.minimize_all_btn)

        self.controls_btn = QPushButton("?  Controls")
        self.controls_btn.setToolTip("Show the keyboard shortcuts and panel controls cheatsheet")
        self.controls_btn.clicked.connect(self.show_controls_help)
        row2.addWidget(self.controls_btn)

        row2.addSpacing(12)
        row2.addWidget(QLabel("Opacity"))
        self.opacity = QSlider(Qt.Horizontal)
        self.opacity.setRange(30, 100); self.opacity.setValue(100)
        self.opacity.setMinimumWidth(80)
        self.opacity.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.opacity.valueChanged.connect(self.opacity_changed)
        row2.addWidget(self.opacity, 1)

        outer.addLayout(row2)

    def set_layout_label(self, layout_key: str) -> None:
        if isinstance(layout_key, str) and layout_key.startswith(CUSTOM_LAYOUT_PREFIX):
            idx = layout_key[len(CUSTOM_LAYOUT_PREFIX):]
            label = f"Custom {idx}"
        else:
            label = LAYOUT_LABELS.get(layout_key, layout_key)
        self.cycle_btn.setText(f"⟳  Layout: {label}")

    def flash_saved(self) -> None:
        """Brief visual confirmation that the layout was saved."""
        self.save_layout_btn.setText("✓  Saved")
        from PySide6.QtCore import QTimer
        QTimer.singleShot(1500,
            lambda: self.save_layout_btn.setText("💾  Save Custom Layout"))
