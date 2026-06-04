"""Frameless top-right toast notification for incoming movie invites."""
from __future__ import annotations
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame, QApplication
)


class InviteToast(QWidget):
    accepted = Signal(str)   # room_id
    dismissed = Signal()

    def __init__(self, sender_label: str, room_id: str, parent=None):
        super().__init__(parent)
        self._room_id = room_id
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(360, 120)

        outer = QVBoxLayout(self); outer.setContentsMargins(0, 0, 0, 0)
        card = QFrame(); card.setObjectName("toastCard")
        card.setStyleSheet(
            "QFrame#toastCard { background: #16161d; border: 1px solid #e50914; border-radius: 12px; }"
            "QFrame#toastCard QLabel { background: transparent; color: #f0f0f5; }"
        )
        lay = QVBoxLayout(card); lay.setContentsMargins(14, 10, 14, 10); lay.setSpacing(6)

        title = QLabel("🎬  Movie invite")
        title.setStyleSheet("font-size: 13pt; font-weight: 700;")
        lay.addWidget(title)
        sub = QLabel(f"{sender_label} wants you to watch with them.")
        sub.setWordWrap(True)
        lay.addWidget(sub)

        row = QHBoxLayout(); row.setSpacing(6)
        row.addStretch(1)
        dismiss = QPushButton("Dismiss")
        dismiss.clicked.connect(self._on_dismiss)
        row.addWidget(dismiss)
        join = QPushButton("Join")
        join.setStyleSheet("QPushButton { background: #e50914; color: #ffffff; font-weight: 700; padding: 6px 14px; border-radius: 6px; }")
        join.clicked.connect(self._on_join)
        row.addWidget(join)
        lay.addLayout(row)

        outer.addWidget(card)

        screen = QApplication.primaryScreen().availableGeometry()
        self.move(screen.right() - self.width() - 24, screen.y() + 60)

        # Auto-dismiss after 30s if ignored.
        self._auto_timer = QTimer(self); self._auto_timer.setSingleShot(True)
        self._auto_timer.timeout.connect(self._on_dismiss)
        self._auto_timer.start(30_000)

    def _on_join(self) -> None:
        self.accepted.emit(self._room_id)
        self.close()

    def _on_dismiss(self) -> None:
        self.dismissed.emit()
        self.close()
