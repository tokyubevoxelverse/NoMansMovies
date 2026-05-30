"""Bottom toolbar with Profile / Movie Player mode buttons, overlay toggle, and
(when in overlay mode) a drag handle + opacity slider for repositioning the window.
"""
from __future__ import annotations
from PySide6.QtCore import Qt, Signal, QPoint
from PySide6.QtGui import QAction, QActionGroup, QMouseEvent
from PySide6.QtWidgets import QToolBar, QWidget, QSizePolicy, QSlider, QLabel, QHBoxLayout


class _DragHandle(QWidget):
    """Empty stretchy widget that drags the parent window when overlay mode is active."""

    def __init__(self, target_window, parent=None):
        super().__init__(parent)
        self._target = target_window
        self._offset: QPoint | None = None
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.setMinimumHeight(28)
        self.setCursor(Qt.SizeAllCursor)
        self._enabled = False

    def set_enabled(self, on: bool) -> None:
        self._enabled = on
        self.setCursor(Qt.SizeAllCursor if on else Qt.ArrowCursor)

    def mousePressEvent(self, e: QMouseEvent):
        if self._enabled and e.button() == Qt.LeftButton:
            self._offset = e.globalPosition().toPoint() - self._target.frameGeometry().topLeft()
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e: QMouseEvent):
        if self._enabled and self._offset is not None and (e.buttons() & Qt.LeftButton):
            self._target.move(e.globalPosition().toPoint() - self._offset)
        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e: QMouseEvent):
        self._offset = None
        super().mouseReleaseEvent(e)


class BottomBar(QToolBar):
    modeChanged = Signal(int)        # 0 = profile, 1 = movie player
    overlayToggled = Signal(bool)    # True = enter overlay mode
    opacityChanged = Signal(int)     # 30..100

    def __init__(self, main_window, parent=None):
        super().__init__("Mode", parent)
        self.setObjectName("bottomBar")
        self.setMovable(False)
        self.setFloatable(False)
        self.setAllowedAreas(Qt.BottomToolBarArea)
        self.setIconSize(self.iconSize() * 1.4)

        self._group = QActionGroup(self)
        self._group.setExclusive(True)

        self.profile_act = QAction("👤  Profile", self)
        self.profile_act.setCheckable(True)
        self.profile_act.triggered.connect(lambda: self.modeChanged.emit(0))
        self._group.addAction(self.profile_act)

        self.player_act = QAction("🎬  Movie Player", self)
        self.player_act.setCheckable(True)
        self.player_act.setChecked(True)
        self.player_act.triggered.connect(lambda: self.modeChanged.emit(1))
        self._group.addAction(self.player_act)

        self.addAction(self.profile_act)
        self.addAction(self.player_act)

        # Drag handle — only active during overlay mode
        self.drag_handle = _DragHandle(main_window, self)
        self.addWidget(self.drag_handle)

        # Opacity slider — hidden until overlay mode
        self._opacity_box = QWidget(self)
        ob = QHBoxLayout(self._opacity_box); ob.setContentsMargins(0, 0, 0, 0); ob.setSpacing(6)
        self._opacity_label = QLabel("Opacity"); ob.addWidget(self._opacity_label)
        self.opacity = QSlider(Qt.Horizontal); self.opacity.setRange(30, 100); self.opacity.setValue(100)
        self.opacity.setFixedWidth(120)
        self.opacity.valueChanged.connect(self.opacityChanged)
        ob.addWidget(self.opacity)
        self._opacity_box.setVisible(False)
        self.addWidget(self._opacity_box)

        self.overlay_act = QAction("🛸  Overlay mode", self)
        self.overlay_act.setCheckable(True)
        self.overlay_act.setToolTip("Frameless always-on-top window — sits over No Man's Sky in borderless windowed mode.")
        self.overlay_act.toggled.connect(self.overlayToggled.emit)
        self.addAction(self.overlay_act)

    def set_mode(self, idx: int) -> None:
        if idx == 0:
            self.profile_act.setChecked(True)
        else:
            self.player_act.setChecked(True)

    def set_overlay(self, on: bool) -> None:
        self.overlay_act.blockSignals(True)
        self.overlay_act.setChecked(on)
        self.overlay_act.blockSignals(False)
        self.drag_handle.set_enabled(on)
        self._opacity_box.setVisible(on)
        # Disable the Profile button while overlay is active — profile UI doesn't belong in overlay.
        self.profile_act.setEnabled(not on)