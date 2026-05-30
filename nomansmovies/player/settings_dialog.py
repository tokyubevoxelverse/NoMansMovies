"""Aspect ratio + quality picker (low -> 8K)."""
from __future__ import annotations
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QPushButton
)
from ..config import ASPECT_RATIOS, QUALITY_FORMATS


class PlayerSettingsDialog(QDialog):
    def __init__(self, current_aspect: str = "Native",
                 current_quality: str = "Best available", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Player settings")
        self.setMinimumWidth(360)

        lay = QVBoxLayout(self); lay.setContentsMargins(20, 20, 20, 20); lay.setSpacing(10)
        lay.addWidget(QLabel("Aspect ratio"))
        self.aspect = QComboBox(); self.aspect.addItems(ASPECT_RATIOS)
        if current_aspect in ASPECT_RATIOS:
            self.aspect.setCurrentText(current_aspect)
        lay.addWidget(self.aspect)

        lay.addWidget(QLabel("Quality"))
        self.quality = QComboBox(); self.quality.addItems(list(QUALITY_FORMATS.keys()))
        if current_quality in QUALITY_FORMATS:
            self.quality.setCurrentText(current_quality)
        lay.addWidget(self.quality)

        row = QHBoxLayout()
        cancel = QPushButton("Cancel"); cancel.clicked.connect(self.reject)
        ok = QPushButton("Apply"); ok.setProperty("accent", True); ok.clicked.connect(self.accept)
        row.addStretch(1); row.addWidget(cancel); row.addWidget(ok)
        lay.addLayout(row)

    def values(self) -> tuple[str, str]:
        return self.aspect.currentText(), self.quality.currentText()
