"""Lightweight splash window shown during PyInstaller cold-start."""
from __future__ import annotations
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QApplication

from ..config import ASSETS_DIR


class Splash(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowFlags(
            Qt.SplashScreen | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(520, 360)

        outer = QVBoxLayout(self); outer.setContentsMargins(0, 0, 0, 0)

        card = QWidget(self); card.setObjectName("splashCard")
        card.setStyleSheet(
            "QWidget#splashCard { background: #0f0f14; "
            "border: 1px solid #2a2a35; border-radius: 14px; }"
        )
        c_lay = QVBoxLayout(card)
        c_lay.setContentsMargins(20, 20, 20, 20); c_lay.setSpacing(10)
        c_lay.setAlignment(Qt.AlignCenter)

        # Logo
        logo_path = ASSETS_DIR / "icons" / "app.png"
        logo = QLabel(card)
        logo.setAlignment(Qt.AlignCenter)
        if logo_path.exists():
            pm = QPixmap(str(logo_path))
            if not pm.isNull():
                pm = pm.scaled(QSize(200, 200), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                logo.setPixmap(pm)
        c_lay.addWidget(logo)

        title = QLabel("NoMansMovies", card)
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 22pt; font-weight: 700; color: #f0f0f5; background: transparent;")
        c_lay.addWidget(title)

        sub = QLabel("Loading… first launch can take a few seconds.", card)
        sub.setAlignment(Qt.AlignCenter)
        sub.setStyleSheet("font-size: 10pt; color: #9a9aa6; background: transparent;")
        c_lay.addWidget(sub)

        outer.addWidget(card)

        screen = QApplication.primaryScreen().availableGeometry()
        self.move(screen.center() - self.rect().center())

    def show_and_pump(self) -> None:
        self.show()
        QApplication.processEvents()
