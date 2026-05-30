"""App-wide theme: single source of truth for colors.

apply_theme(colors) updates the global colors and emits theme_signal.changed
so any widget with custom QSS can re-apply itself.
"""
from __future__ import annotations
from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

from .config import DEFAULT_COLORS


class _ThemeSignal(QObject):
    changed = Signal(dict)


theme_signal = _ThemeSignal()
_current: dict = dict(DEFAULT_COLORS)


def current() -> dict:
    return dict(_current)


def color(key: str) -> str:
    return _current.get(key, DEFAULT_COLORS[key])


def _lighten(hex_: str, amount: float) -> str:
    c = QColor(hex_)
    return c.lighter(int(100 + amount * 100)).name()


def _alpha(hex_: str, a: float) -> str:
    c = QColor(hex_)
    return f"rgba({c.red()},{c.green()},{c.blue()},{a})"


def apply_theme(colors: dict | None = None) -> None:
    global _current
    _current = {**DEFAULT_COLORS, **(colors or {})}
    c = _current

    bg = QColor(c["bg"]); fg = QColor(c["fg"]); accent = QColor(c["accent"])
    border = QColor(c["border"]); panel = QColor(c["panel"]); muted = QColor(c["muted"])

    pal = QPalette()
    pal.setColor(QPalette.Window, bg)
    pal.setColor(QPalette.WindowText, fg)
    pal.setColor(QPalette.Base, panel)
    pal.setColor(QPalette.AlternateBase, bg)
    pal.setColor(QPalette.Text, fg)
    pal.setColor(QPalette.Button, panel)
    pal.setColor(QPalette.ButtonText, fg)
    pal.setColor(QPalette.Highlight, accent)
    pal.setColor(QPalette.HighlightedText, QColor("#ffffff"))
    pal.setColor(QPalette.ToolTipBase, panel)
    pal.setColor(QPalette.ToolTipText, fg)
    pal.setColor(QPalette.PlaceholderText, muted)
    pal.setColor(QPalette.BrightText, fg)
    pal.setColor(QPalette.Link, accent)

    app = QApplication.instance()
    if app is None:
        return
    app.setPalette(pal)
    app.setStyleSheet(_qss(c))

    theme_signal.changed.emit(dict(c))


def _qss(c: dict) -> str:
    accent_hi = _lighten(c["accent"], 0.15)
    accent_lo = _lighten(c["accent"], -0.15)
    return f"""
    /* ============ base ============ */
    QMainWindow, QDialog, QWidget {{
        background-color: {c['bg']};
        color: {c['fg']};
        font-family: 'Segoe UI', sans-serif;
        font-size: 10pt;
    }}
    QLabel {{ color: {c['fg']}; background: transparent; }}
    QLabel[muted="true"] {{ color: {c['muted']}; }}

    /* ============ inputs ============ */
    QLineEdit, QTextEdit, QPlainTextEdit, QComboBox,
    QListWidget, QListView, QTreeView, QTabBar::tab {{
        background-color: {c['panel']};
        color: {c['fg']};
        border: 1px solid {c['border']};
        border-radius: 6px;
        padding: 6px 8px;
        selection-background-color: {c['accent']};
        selection-color: #ffffff;
    }}
    QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus {{
        border: 1px solid {c['accent']};
    }}

    QComboBox QAbstractItemView {{
        background: {c['panel']};
        color: {c['fg']};
        selection-background-color: {c['accent']};
        border: 1px solid {c['border']};
    }}

    /* ============ buttons ============ */
    QPushButton, QToolButton {{
        background-color: {c['panel']};
        color: {c['fg']};
        border: 1px solid {c['border']};
        border-radius: 6px;
        padding: 7px 14px;
    }}
    QPushButton:hover, QToolButton:hover {{ border-color: {c['accent']}; }}
    QPushButton:pressed, QToolButton:pressed {{ background-color: {accent_lo}; color: #ffffff; }}
    QPushButton:disabled {{ color: {c['muted']}; border-color: {c['border']}; }}

    QPushButton[accent="true"] {{
        background-color: {c['accent']};
        color: #ffffff;
        border: 1px solid {c['accent']};
        font-weight: 600;
    }}
    QPushButton[accent="true"]:hover {{ background-color: {accent_hi}; }}
    QPushButton[accent="true"]:pressed {{ background-color: {accent_lo}; }}

    /* ============ tabs ============ */
    QTabWidget::pane {{ border: 1px solid {c['border']}; border-radius: 6px; top: -1px; }}
    QTabBar::tab {{
        background: transparent;
        color: {c['muted']};
        border: 1px solid transparent;
        padding: 6px 12px;
        margin-right: 2px;
    }}
    QTabBar::tab:selected {{
        background: {c['panel']};
        color: {c['fg']};
        border: 1px solid {c['border']};
        border-bottom-color: {c['panel']};
    }}

    /* ============ docks ============ */
    QDockWidget {{ color: {c['fg']}; titlebar-close-icon: none; titlebar-normal-icon: none; }}
    QDockWidget::title {{
        background: {c['panel']};
        color: {c['fg']};
        padding: 6px 10px;
        border-bottom: 1px solid {c['border']};
        font-weight: 600;
    }}

    /* ============ toolbar / bottom bar ============ */
    QToolBar {{
        background: {c['panel']};
        border-top: 1px solid {c['border']};
        spacing: 8px;
        padding: 6px;
    }}
    QToolBar QToolButton {{
        padding: 8px 18px;
        border: 1px solid transparent;
        border-radius: 6px;
        color: {c['fg']};
        background: transparent;
    }}
    QToolBar QToolButton:hover {{ background: {_alpha(c['fg'], 0.06)}; }}
    QToolBar QToolButton:checked {{
        background: {c['accent']};
        color: #ffffff;
        border-color: {c['accent']};
    }}

    /* ============ sliders ============ */
    QSlider::groove:horizontal {{
        height: 4px; background: {c['border']}; border-radius: 2px;
    }}
    QSlider::sub-page:horizontal {{ background: {c['accent']}; border-radius: 2px; }}
    QSlider::handle:horizontal {{
        background: {c['fg']}; width: 12px; margin: -5px 0; border-radius: 6px;
    }}

    /* ============ scrollbars ============ */
    QScrollBar:vertical {{ background: transparent; width: 10px; }}
    QScrollBar::handle:vertical {{ background: {c['border']}; border-radius: 5px; min-height: 30px; }}
    QScrollBar::handle:vertical:hover {{ background: {c['accent']}; }}
    QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
    QScrollBar:horizontal {{ background: transparent; height: 10px; }}
    QScrollBar::handle:horizontal {{ background: {c['border']}; border-radius: 5px; min-width: 30px; }}
    QScrollBar::handle:horizontal:hover {{ background: {c['accent']}; }}

    /* ============ lists ============ */
    QListWidget::item {{ padding: 6px; border-radius: 4px; color: {c['fg']}; }}
    QListWidget::item:hover {{ background: {_alpha(c['fg'], 0.05)}; }}
    QListWidget::item:selected {{ background: {c['accent']}; color: #ffffff; }}

    /* ============ message boxes & misc ============ */
    QMessageBox {{ background: {c['bg']}; color: {c['fg']}; }}
    QMenu {{ background: {c['panel']}; color: {c['fg']}; border: 1px solid {c['border']}; }}
    QMenu::item:selected {{ background: {c['accent']}; color: #ffffff; }}

    /* ============ object-name targets used across the app ============ */
    QFrame#profileCard {{
        background: {c['panel']};
        border: 1px solid {c['border']};
        border-radius: 14px;
        padding: 18px;
    }}
    QFrame#overlayCard {{
        background: {_alpha(c['bg'], 0.85)};
        border: 1px solid {c['border']};
        border-radius: 12px;
    }}
    QWidget#dockTitleBar {{
        background: {c['panel']};
        border-bottom: 1px solid {c['border']};
    }}
    QWidget#dockTitleBar QToolButton {{
        background: transparent;
        color: {c['fg']};
        border: 1px solid transparent;
        border-radius: 4px;
        padding: 2px 6px;
    }}
    QWidget#dockTitleBar QToolButton:hover {{ background: {_alpha(c['fg'], 0.12)}; }}

    QWidget#overlayStrip {{
        background: {_alpha(c['panel'], 0.85)};
        border-top-left-radius: 12px;
        border-top-right-radius: 12px;
        border-bottom: 1px solid {c['border']};
    }}
    QWidget#overlayStrip QPushButton {{
        background: {_alpha(c['fg'], 0.10)};
        color: {c['fg']};
        border: 1px solid transparent;
        border-radius: 4px;
        padding: 4px 10px;
    }}
    QWidget#overlayStrip QPushButton:hover {{ background: {_alpha(c['fg'], 0.20)}; }}
    QWidget#overlayStrip QPushButton#closeBtn:hover {{ background: {c['accent']}; color: #ffffff; }}
    """
