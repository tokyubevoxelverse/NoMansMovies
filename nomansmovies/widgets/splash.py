"""Lightweight splash window shown during PyInstaller cold-start.

Now also displays the current version + a short changelog so users can see
what's new at launch.
"""
from __future__ import annotations
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QApplication

from ..config import ASSETS_DIR, VERSION, CHANGELOG_BULLETS


class Splash(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowFlags(
            Qt.SplashScreen | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(560, 470)

        outer = QVBoxLayout(self); outer.setContentsMargins(0, 0, 0, 0)

        card = QWidget(self); card.setObjectName("splashCard")
        card.setStyleSheet(
            "QWidget#splashCard { background: #0f0f14; "
            "border: 1px solid #2a2a35; border-radius: 14px; }"
        )
        c_lay = QVBoxLayout(card)
        c_lay.setContentsMargins(20, 20, 20, 20); c_lay.setSpacing(6)
        c_lay.setAlignment(Qt.AlignCenter)

        # Logo
        logo_path = ASSETS_DIR / "icons" / "app.png"
        logo = QLabel(card)
        logo.setAlignment(Qt.AlignCenter)
        if logo_path.exists():
            pm = QPixmap(str(logo_path))
            if not pm.isNull():
                pm = pm.scaled(QSize(160, 160), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                logo.setPixmap(pm)
        c_lay.addWidget(logo)

        title = QLabel("NoMansMovies", card)
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 22pt; font-weight: 700; color: #f0f0f5; background: transparent;")
        c_lay.addWidget(title)

        version = QLabel(f"v{VERSION}", card)
        version.setAlignment(Qt.AlignCenter)
        version.setStyleSheet("font-size: 11pt; color: #c0c0cc; background: transparent;")
        c_lay.addWidget(version)

        if CHANGELOG_BULLETS:
            bullets_html = "<div style='line-height: 145%;'>" + "<br>".join(
                f"• {b}" for b in CHANGELOG_BULLETS
            ) + "</div>"
            bullets = QLabel(bullets_html, card)
            bullets.setAlignment(Qt.AlignLeft)
            bullets.setTextFormat(Qt.RichText)
            bullets.setWordWrap(True)
            bullets.setStyleSheet(
                "font-size: 8pt; color: #8a8a99; background: transparent; "
                "padding: 6px 18px 0 18px;"
            )
            c_lay.addWidget(bullets)

        sub = QLabel("Loading…", card)
        sub.setAlignment(Qt.AlignCenter)
        sub.setStyleSheet("font-size: 9pt; color: #6a6a78; background: transparent; padding-top: 6px;")
        c_lay.addWidget(sub)

        outer.addWidget(card)

        screen = QApplication.primaryScreen().availableGeometry()
        self.move(screen.center() - self.rect().center())

    def show_and_pump(self) -> None:
        self.show()
        QApplication.processEvents()
