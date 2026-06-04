"""NoMansMovies — entry point."""
from __future__ import annotations
import sys
import time
from typing import Dict, Optional, List
from PySide6.QtCore import Qt, QSettings, QTimer, QPoint, QSize, QEventLoop, QEvent
from PySide6.QtGui import QMovie, QIcon
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QStackedWidget, QWidget, QHBoxLayout, QVBoxLayout,
    QLabel, QLineEdit, QTextEdit, QPlainTextEdit, QMessageBox
)

from . import ytdlp_manager
from .config import (
    APP_NAME, ORG_NAME, DEFAULT_COLORS, ASSETS_DIR,
    LAYOUTS, LAYOUT_LABELS, LAYOUT_DEFAULT, LAYOUT_MOVIE_SOURCES, LAYOUT_MOVIE_ONLY,
    CUSTOM_LAYOUT_PREFIX, MAX_CUSTOM_LAYOUTS,
)
from .theme import apply_theme
from .supabase_client import supabase, try_restore_session, clear_session, current_user_id

from .auth.login_window import AuthDialog
from .profile.profile_view import ProfileView
from .profile.profile_edit import ProfileEditDialog
from .profile.friends_panel import FriendsPanel
from .messaging.chat_window import ChatWindow
from .player.video_panel import VideoPanel
from .player.source_panel import SourcePanel
from .player.watch_panel import WatchPanel
from .player.playback_bar import PlaybackControlsBar
from .sync.room import WatchRoom
from .widgets.bottom_bar import BottomBar
from .widgets.collapsible_dock import CollapsibleDock
from .widgets.floating_panel import FloatingPanel
from .widgets.overlay_controls import OverlayControls
from .widgets.appearance_panel import AppearancePanel
from .widgets.controls_help import ControlsHelpPanel
from .discord_presence import DiscordPresence
from .presence import PresenceTracker
from .widgets.invite_toast import InviteToast
from .messaging.chat_window import JOIN_SCHEME


class ProfilePage(QWidget):
    """Profile mode: own profile + friends list side by side."""
    def __init__(self, on_message, on_view_profile, on_edit, parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self); lay.setContentsMargins(0, 0, 0, 0); lay.setSpacing(0)

        self.profile_view = ProfileView()
        self.profile_view.edit_requested.connect(on_edit)
        self.profile_view.message_requested.connect(on_message)

        self.friends = FriendsPanel()
        self.friends.view_profile.connect(self._show_profile)
        self.friends.message.connect(on_message)

        self._on_view_profile = on_view_profile

        left = QWidget(); ll = QVBoxLayout(left); ll.setContentsMargins(0, 0, 0, 0); ll.addWidget(self.profile_view)
        lay.addWidget(left, 2)
        lay.addWidget(self.friends, 1)

    def _show_profile(self, uid: str) -> None:
        self.profile_view.load(uid)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(1280, 800)

        # Central stacked widget: 0=profile, 1=movie player (central video)
        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        # ---------- Profile page ----------
        self.profile_page = ProfilePage(
            on_message=self.open_chat,
            on_view_profile=lambda uid: self.profile_page._show_profile(uid),
            on_edit=self.edit_profile,
        )
        self.stack.addWidget(self.profile_page)

        # ---------- Movie player page (central placeholder; real video is set as central while in player mode) ----------
        self.video_panel = VideoPanel()
        self.video_panel.source_changed.connect(self._on_source_changed)
        self.stack.addWidget(self.video_panel)

        # ---------- Docks (only visible in player mode) ----------
        # objectName MUST be unique and set BEFORE restoreState() — Qt uses it as a key.
        self.source_dock = CollapsibleDock("Sources", self)
        self.source_dock.setObjectName("sourceDock")
        self.source_panel = SourcePanel()
        self.source_panel.play_url.connect(lambda u: self.video_panel.load_url(u, "mp4"))
        self.source_panel.play_youtube.connect(self.video_panel.load_youtube)
        self.source_panel.play_local.connect(self.video_panel.load_local)
        self.source_dock.setWidget(self.source_panel)
        self.source_dock.setMinimumWidth(280)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.source_dock)

        self.watch_dock = CollapsibleDock("Watch together", self)
        self.watch_dock.setObjectName("watchDock")
        self.watch_panel = WatchPanel()
        self.watch_panel.invite_clicked.connect(self._invite_friend)
        self.watch_panel.leave_room.connect(self._leave_room)
        self.watch_dock.setWidget(self.watch_panel)
        self.watch_dock.setMinimumWidth(260)
        self.addDockWidget(Qt.RightDockWidgetArea, self.watch_dock)

        # ---------- Playback controls dock (always visible in Movie Player mode) ----------
        self.playback_dock = CollapsibleDock("Playback controls", self)
        self.playback_dock.setObjectName("playbackDock")
        self.playback_bar = PlaybackControlsBar()
        self.playback_dock.setWidget(self.playback_bar)
        self.playback_dock.setMinimumHeight(140)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.playback_dock)
        self._wire_playback_bar(self.playback_bar)

        # ---------- Bottom bar ----------
        self.bottom = BottomBar(self, self)
        self.addToolBar(Qt.BottomToolBarArea, self.bottom)
        self.bottom.modeChanged.connect(self.set_mode)
        self.bottom.overlayToggled.connect(self.set_overlay_mode)
        self.bottom.opacityChanged.connect(lambda v: self.setWindowOpacity(v / 100.0))

        # ---------- State ----------
        self.room: Optional[WatchRoom] = None
        self.is_host: bool = False
        self._open_chats: Dict[str, ChatWindow] = {}

        # Overlay state — each visible panel becomes its own floating window.
        self._overlay_active = False
        self._saved_geom = None
        self._float_video: Optional[FloatingPanel] = None
        self._float_source: Optional[FloatingPanel] = None
        self._float_watch: Optional[FloatingPanel] = None
        self._float_playback: Optional[FloatingPanel] = None
        self._float_controls: Optional[FloatingPanel] = None
        self._float_appearance: Optional[FloatingPanel] = None
        self._overlay_controls: Optional[OverlayControls] = None
        self._was_source_visible = False
        self._was_watch_visible = False
        self._was_playback_visible = False
        # Remember floating state of docks so we can restore on exit overlay.
        self._dock_was_floating: Dict[CollapsibleDock, bool] = {}

        # Layout state — current layout key + saved per-layout snapshot of which
        # panels were visible before triple-9 / Cycle Layouts changed things.
        self._current_layout: str = LAYOUT_DEFAULT
        self._previous_layout: str = LAYOUT_DEFAULT

        # Triple-9 hotkey for cinema mode (Movie only).
        self._key9_presses: List[float] = []
        QApplication.instance().installEventFilter(self)

        # Discord Rich Presence — only connects if the user linked Discord.
        self._discord = DiscordPresence()
        QTimer.singleShot(500, self._maybe_start_discord_presence)
        self.video_panel.source_changed.connect(self._on_source_changed_for_presence)

        # Supabase online presence — broadcasts that I'm online and tracks who else is.
        self._presence = PresenceTracker()
        self._presence.online_changed.connect(self._on_online_changed)
        QTimer.singleShot(0, self._start_online_presence)

        # Incoming-message subscription for invite toasts.
        self._inbox_channel = None
        self._active_toasts: list = []
        QTimer.singleShot(0, self._subscribe_incoming_messages)
        # Overlay-only build: profile opens as its own floating panel (never a
        # separate windowed mode). _saved_flags is referenced by closeEvent.
        self._saved_flags = None

        # Restore window + dock layout from QSettings (must come AFTER objectNames are set).
        s = QSettings(ORG_NAME, APP_NAME)
        geo = s.value("ui/geometry"); state = s.value("ui/state")
        if geo: self.restoreGeometry(geo)
        if state: self.restoreState(state)

        # Restore per-panel state: friends tab index, source/watch dock visibility.
        last_friends_tab = s.value("ui/friends_tab")
        if last_friends_tab is not None:
            try:
                self.profile_page.friends.tabs.setCurrentIndex(int(last_friends_tab))
            except Exception:
                pass

        # Restore CollapsibleDock collapsed state — Qt's saveState/restoreState
        # doesn't know about our custom collapse, so persist separately.
        self.source_dock.set_collapsed(self._read_bool(s, "ui/source_collapsed", False))
        self.watch_dock.set_collapsed(self._read_bool(s, "ui/watch_collapsed", False))
        self.playback_dock.set_collapsed(self._read_bool(s, "ui/playback_collapsed", False))

        self.set_mode(1)

    @staticmethod
    def _read_bool(s: QSettings, key: str, default: bool) -> bool:
        v = s.value(key, default)
        if isinstance(v, bool): return v
        return str(v).lower() in ("true", "1", "yes")

    @staticmethod
    def _read_int(s: QSettings, key: str, default: int) -> int:
        v = s.value(key, default)
        try: return int(v)
        except (TypeError, ValueError): return default

    def _wire_playback_bar(self, bar: PlaybackControlsBar) -> None:
        """Hook a PlaybackControlsBar instance to the shared VideoPanel."""
        bar.play_pause.connect(self.video_panel.toggle_play)
        bar.stop.connect(self.video_panel.stop)
        bar.rewind.connect(lambda: self.video_panel.seek_relative(-10_000))
        bar.forward.connect(lambda: self.video_panel.seek_relative(+10_000))
        bar.next_.connect(self.video_panel.stop)
        bar.seek.connect(self.video_panel.seek_to)
        bar.volume.connect(self.video_panel.set_volume)
        bar.settings.connect(self.video_panel.open_settings)
        bar.fullscreen.connect(self.video_panel.toggle_fullscreen)
        bar.resync.connect(self._on_resync)

        p = self.video_panel.player
        p.positionChanged.connect(bar.update_position)
        p.durationChanged.connect(bar.update_duration)
        from PySide6.QtMultimedia import QMediaPlayer
        p.playbackStateChanged.connect(
            lambda st: bar.set_playing(st == QMediaPlayer.PlayingState))

        # Resync only meaningful in a watch room.
        bar.set_resync_enabled(getattr(self, "room", None) is not None)

    def _on_resync(self) -> None:
        if self.room is None:
            return
        self.video_panel.resync_with_room(self.is_host)

    # ============ mode switching ============
    def set_mode(self, idx: int) -> None:
        # In overlay mode the profile UI must never be shown.
        if self._overlay_active and idx == 0:
            idx = 1
        self.stack.setCurrentIndex(idx)
        in_player = (idx == 1)
        # Only flip dock visibility based on mode if we have no saved per-dock visibility
        # (Qt's saveState/restoreState already handles dock visibility — don't fight it.)
        if not in_player:
            self.source_dock.setVisible(False)
            self.watch_dock.setVisible(False)
        else:
            # Restore docks if user previously had them visible (state restored from QSettings).
            # If both are hidden after restore, default to showing them.
            if not self.source_dock.isVisible() and not self.watch_dock.isVisible():
                self.source_dock.setVisible(True)
                self.watch_dock.setVisible(True)
        self.bottom.set_mode(idx)
        if idx == 0:
            uid = current_user_id()
            if uid:
                self.profile_page.profile_view.load(uid)
                self.profile_page.friends.refresh()

    # ============ profile edit ============
    def edit_profile(self) -> None:
        dlg = ProfileEditDialog(self)
        if dlg.exec():
            uid = current_user_id()
            if uid:
                self.profile_page.profile_view.load(uid)
                # reload color scheme from server
                try:
                    r = supabase().table("profiles").select("color_scheme").eq("id", uid).single().execute()
                    apply_theme((r.data or {}).get("color_scheme") or DEFAULT_COLORS)
                except Exception:
                    pass

    # ============ chat ============
    def open_chat(self, other_id: str) -> None:
        if other_id in self._open_chats and self._open_chats[other_id].isVisible():
            self._open_chats[other_id].raise_(); self._open_chats[other_id].activateWindow(); return
        try:
            r = supabase().table("profiles").select("username").eq("id", other_id).single().execute()
            name = (r.data or {}).get("username") or "friend"
        except Exception:
            name = "friend"
        win = ChatWindow(other_id, name, self)
        win.invite_accepted.connect(self.join_room_as_guest)
        win.show()
        self._open_chats[other_id] = win

    # ============ watch room ============
    def _ensure_host_room(self) -> WatchRoom:
        if self.room and self.is_host:
            return self.room
        if self.room:
            self.room.close()
        self.room = WatchRoom(is_host=True)
        self.room.open()
        self.is_host = True
        self.video_panel.attach_room(self.room, as_host=True)
        self.watch_panel.set_room(self.room.room_id)
        self.playback_bar.set_resync_enabled(True)
        return self.room

    def _invite_friend(self, friend_id: str, username: str) -> None:
        # Only meaningful for streaming sources
        if self.video_panel._current_kind == "local":
            QMessageBox.information(self, "Local file",
                "Local files can't be shared — invite friends to a direct link or a YouTube video instead.")
            return
        room = self._ensure_host_room()
        # Broadcast current source so future joins get it immediately
        original = self.video_panel._original_url or ""
        if original:
            room.send_source(original, self.video_panel._current_kind, self.video_panel._quality, original)
        # Send invite via DM
        self.open_chat(friend_id)
        chat = self._open_chats.get(friend_id)
        if chat:
            chat.send_invite(room.room_id)

    def join_room_as_guest(self, room_id: str) -> None:
        if self.room:
            self.room.close()
        self.room = WatchRoom(room_id=room_id, is_host=False)
        self.is_host = False
        self.video_panel.attach_room(self.room, as_host=False)
        self.room.open()
        self.watch_panel.set_room(room_id)
        self.playback_bar.set_resync_enabled(True)
        self.set_mode(1)

    def _leave_room(self) -> None:
        if self.room:
            self.room.close(); self.room = None
        self.is_host = False
        self.video_panel.detach_room()
        self.watch_panel.set_room(None)
        self.playback_bar.set_resync_enabled(False)

    def _on_source_changed(self, kind: str, original: str) -> None:
        self.watch_panel.set_invite_enabled(kind != "local")
        if self.room and self.is_host and original:
            self.room.send_source(original, kind, self.video_panel._quality, original)

    # ============ overlay mode ============
    OVERLAY_KEYS = ("video", "source", "watch", "playback", "controls")

    def _restore_panel(self, panel: FloatingPanel, key: str, default_xywh: tuple,
                       s: QSettings) -> None:
        """Show + size + position + minimized state, using saved INT values if present."""
        dx, dy, dw, dh = default_xywh
        x = self._read_int(s, f"overlay/{key}_x", dx)
        y = self._read_int(s, f"overlay/{key}_y", dy)
        w = self._read_int(s, f"overlay/{key}_w", dw)
        h = self._read_int(s, f"overlay/{key}_h", dh)
        minimized = self._read_bool(s, f"overlay/{key}_minimized", False)
        panel.show_with_geometry(x, y, w, h)
        panel.apply_minimized(minimized)

    def set_overlay_mode(self, on: bool) -> None:
        """Hide the main window and turn every visible panel into its own
        frameless always-on-top floating window (draggable, edge-resizable,
        minimizable). Exiting puts everything back."""
        s = QSettings(ORG_NAME, APP_NAME)
        screen_geom = QApplication.primaryScreen().availableGeometry()

        if on and not self._overlay_active:
            self._overlay_active = True
            self._saved_geom = self.saveGeometry()

            # Overlay-only build: the overlay IS the app, so the essential panels
            # must always appear — otherwise (e.g. when booting straight into
            # overlay with docks hidden from restored state) the user gets no
            # Sources panel and nowhere to paste a link / search / open a file.
            # Sources + Playback are always floated; Watch follows prior state
            # (it's only meaningful inside a watch-together room).
            self._was_source_visible = True
            self._was_playback_visible = True
            self._was_watch_visible = self.watch_dock.isVisible()

            # Remember + un-float docks BEFORE hiding so floating docks don't remain
            # as separate top-level windows (which is what caused the double panels).
            for dock in (self.source_dock, self.watch_dock, self.playback_dock):
                self._dock_was_floating[dock] = dock.isFloating()
                if dock.isFloating():
                    dock.setFloating(False)
                dock.setVisible(False)

            # Overlay-only build: there is no windowed mode to return to, so the
            # exit button quits the app entirely.
            exit_overlay = lambda: self.close()
            # ✕ on a floating panel just HIDES that panel — does not exit overlay.
            # The exit button in the overlay controls is the only way out (quit).
            def _hide_panel(panel):
                panel.hide()

            # --- video panel ---
            self.stack.removeWidget(self.video_panel)
            self._float_video = FloatingPanel("Movie player", self.video_panel)
            self._float_video.closed.connect(lambda: _hide_panel(self._float_video))
            cw, ch_ = 1024, 600
            self._restore_panel(self._float_video, "video", (
                screen_geom.x() + (screen_geom.width() - cw) // 2,
                screen_geom.y() + (screen_geom.height() - ch_) // 2,
                cw, ch_,
            ), s)
            self.video_panel.refresh_video_sink()
            QTimer.singleShot(120, self.video_panel.refresh_video_sink)

            # --- source panel (left dock content) ---
            if self._was_source_visible:
                sp = self.source_panel
                self.source_dock.setWidget(QWidget())
                self._float_source = FloatingPanel("Sources", sp)
                self._float_source.closed.connect(lambda: _hide_panel(self._float_source))
                self._restore_panel(self._float_source, "source", (
                    screen_geom.x() + 30, screen_geom.y() + 80, 320, 560,
                ), s)

            # --- watch panel (right dock content) ---
            if self._was_watch_visible:
                wp = self.watch_panel
                self.watch_dock.setWidget(QWidget())
                self._float_watch = FloatingPanel("Watch together", wp)
                self._float_watch.closed.connect(lambda: _hide_panel(self._float_watch))
                self._restore_panel(self._float_watch, "watch", (
                    screen_geom.right() - 330, screen_geom.y() + 80, 300, 560,
                ), s)

            # --- playback controls bar (dedicated, dockable) ---
            if self._was_playback_visible:
                pb = self.playback_bar
                self.playback_dock.setWidget(QWidget())
                self._float_playback = FloatingPanel("Playback controls", pb)
                self._float_playback.closed.connect(lambda: _hide_panel(self._float_playback))
                self._restore_panel(self._float_playback, "playback", (
                    screen_geom.x() + (screen_geom.width() - 820) // 2,
                    screen_geom.bottom() - 290, 820, 130,
                ), s)

            # --- overlay controls (floating bar) ---
            controls = OverlayControls()
            controls.profile_clicked.connect(self._open_appearance_panel)
            controls.opacity_changed.connect(self._set_overlay_opacity)
            controls.recenter_video.connect(self._recenter_video)
            controls.cycle_layout.connect(self._cycle_layout)
            controls.show_all_panels.connect(self._show_all_overlay_panels)
            controls.restore_all_panels.connect(self._restore_all_overlay_panels)
            controls.save_layout.connect(self._save_custom_layout)
            controls.minimize_all.connect(self._minimize_all_overlay)
            controls.show_controls_help.connect(self._open_controls_help)
            controls.set_layout_label(self._current_layout)
            self._overlay_controls = controls
            self._float_controls = FloatingPanel("NoMansMovies", controls)
            self._float_controls.setMinimumSize(560, 130)
            # ✕ on the controls panel = quit app (overlay-only build, no windowed mode).
            self._float_controls.closed.connect(QApplication.instance().quit)
            self._restore_panel(self._float_controls, "controls", (
                screen_geom.x() + (screen_geom.width() - 760) // 2,
                screen_geom.bottom() - 150, 760, 130,
            ), s)

            self.bottom.set_overlay(True)
            self.hide()

        elif not on and self._overlay_active:
            # Save overlay layout before tearing down so it persists for next time.
            self._save_overlay_layout(s)

            self._overlay_active = False
            # Detach panels from their floating windows and put them back in their original homes.
            if self._float_video:
                vp = self._float_video.take_content()
                self.stack.insertWidget(1, vp)
                self._float_video.hide(); self._float_video.deleteLater()
                self._float_video = None
                self.video_panel.refresh_video_sink()
                QTimer.singleShot(120, self.video_panel.refresh_video_sink)

            if self._float_source:
                sp = self._float_source.take_content()
                self.source_dock.setWidget(sp)
                self._float_source.hide(); self._float_source.deleteLater()
                self._float_source = None

            if self._float_watch:
                wp = self._float_watch.take_content()
                self.watch_dock.setWidget(wp)
                self._float_watch.hide(); self._float_watch.deleteLater()
                self._float_watch = None

            if self._float_playback:
                pb = self._float_playback.take_content()
                self.playback_dock.setWidget(pb)
                self._float_playback.hide(); self._float_playback.deleteLater()
                self._float_playback = None

            if self._float_controls:
                self._float_controls.hide(); self._float_controls.deleteLater()
                self._float_controls = None
                self._overlay_controls = None

            if self._float_appearance:
                self._float_appearance.hide(); self._float_appearance.deleteLater()
                self._float_appearance = None

            # Restore the original dock visibility + floating state.
            self.source_dock.setVisible(self._was_source_visible)
            self.watch_dock.setVisible(self._was_watch_visible)
            self.playback_dock.setVisible(self._was_playback_visible)
            for dock, was_floating in self._dock_was_floating.items():
                if was_floating:
                    dock.setFloating(True)
            self._dock_was_floating.clear()

            self.bottom.set_overlay(False)
            self.setWindowOpacity(1.0)
            self.show()
            self.set_mode(1)
            if self._saved_geom is not None:
                self.restoreGeometry(self._saved_geom)

    def _save_overlay_layout(self, s: QSettings) -> None:
        """Persist overlay layout as plain ints + bool. QPoint/QSize round-trip via
        QSettings has been flaky on some Windows installs — ints always work."""
        for key, fp in [
            ("video",      self._float_video),
            ("source",     self._float_source),
            ("watch",      self._float_watch),
            ("playback",   self._float_playback),
            ("controls",   self._float_controls),
            ("appearance", self._float_appearance),
        ]:
            if fp is None:
                continue
            # When the panel is currently minimized, persist the EXPANDED height so
            # restoring "minimized" leaves a sane size to come back to.
            h = (fp._restore_height or fp.height()) if fp.minimized else fp.height()
            s.setValue(f"overlay/{key}_x",         int(fp.x()))
            s.setValue(f"overlay/{key}_y",         int(fp.y()))
            s.setValue(f"overlay/{key}_w",         int(fp.width()))
            s.setValue(f"overlay/{key}_h",         int(h))
            s.setValue(f"overlay/{key}_minimized", "true" if fp.minimized else "false")
        s.sync()

    def _set_overlay_opacity(self, v: int) -> None:
        op = max(0.30, min(1.0, v / 100.0))
        # The video panel ALWAYS stays fully opaque — translucent video on a
        # game background reads as garbage.
        if self._float_video is not None:
            self._float_video.setWindowOpacity(1.0)
        for fp in (self._float_source, self._float_watch, self._float_playback,
                   self._float_controls, self._float_appearance):
            if fp is not None:
                fp.setWindowOpacity(op)

    # ============ triple-9 cinema-mode hotkey ============
    def eventFilter(self, obj, e):
        if e.type() == QEvent.KeyPress and e.key() == Qt.Key_9:
            focused = QApplication.focusWidget()
            if not isinstance(focused, (QLineEdit, QTextEdit, QPlainTextEdit)):
                now = time.monotonic()
                self._key9_presses = [t for t in self._key9_presses if now - t < 1.0]
                self._key9_presses.append(now)
                if len(self._key9_presses) >= 3:
                    self._key9_presses.clear()
                    if self._current_layout == LAYOUT_MOVIE_ONLY:
                        self._apply_layout(self._previous_layout or LAYOUT_DEFAULT)
                    else:
                        self._previous_layout = self._current_layout
                        self._apply_layout(LAYOUT_MOVIE_ONLY)
        return super().eventFilter(obj, e)

    # ============ layouts ============
    def _apply_layout(self, layout: str) -> None:
        # Custom slots: load saved per-panel geometry + visibility for that slot.
        if isinstance(layout, str) and layout.startswith(CUSTOM_LAYOUT_PREFIX):
            if self._overlay_active:
                slot = layout[len(CUSTOM_LAYOUT_PREFIX):]
                s = QSettings(ORG_NAME, APP_NAME)
                for key, fp in (("video", self._float_video), ("source", self._float_source),
                                ("watch", self._float_watch), ("playback", self._float_playback),
                                ("controls", self._float_controls), ("appearance", self._float_appearance)):
                    if fp is None: continue
                    visible = self._read_bool(s, f"layouts/{slot}/{key}_visible", True)
                    x = self._read_int(s, f"layouts/{slot}/{key}_x", fp.x())
                    y = self._read_int(s, f"layouts/{slot}/{key}_y", fp.y())
                    w = self._read_int(s, f"layouts/{slot}/{key}_w", fp.width())
                    h = self._read_int(s, f"layouts/{slot}/{key}_h", fp.height())
                    minimized = self._read_bool(s, f"layouts/{slot}/{key}_minimized", False)
                    if visible:
                        fp.show_with_geometry(x, y, w, h)
                        fp.apply_minimized(minimized)
                    else:
                        fp.hide()
                if self._float_video is not None:
                    self.video_panel.refresh_video_sink()
            self._current_layout = layout
            if self._overlay_controls is not None:
                self._overlay_controls.set_layout_label(layout)
            return

        if layout not in LAYOUTS:
            return
        self._current_layout = layout
        wants = {
            LAYOUT_DEFAULT:       {"video": True,  "source": True,  "watch": True,  "playback": True},
            LAYOUT_MOVIE_SOURCES: {"video": True,  "source": True,  "watch": False, "playback": True},
            LAYOUT_MOVIE_ONLY:    {"video": True,  "source": False, "watch": False, "playback": False},
        }[layout]

        if self._overlay_active:
            for key, fp in (("video", self._float_video), ("source", self._float_source),
                            ("watch", self._float_watch), ("playback", self._float_playback)):
                if fp is None: continue
                fp.show() if wants[key] else fp.hide()
            # Controls panel always visible so the user can navigate back out.
            if self._float_controls: self._float_controls.show()
        else:
            self.video_panel.setVisible(wants["video"])
            self.source_dock.setVisible(wants["source"])
            self.watch_dock.setVisible(wants["watch"])
            self.playback_dock.setVisible(wants["playback"])

        if self._overlay_controls is not None:
            self._overlay_controls.set_layout_label(layout)

    def _all_layouts(self) -> list:
        """Built-ins followed by any saved Custom slots."""
        s = QSettings(ORG_NAME, APP_NAME)
        count = self._read_int(s, "layouts/custom_count", 0)
        return list(LAYOUTS) + [f"{CUSTOM_LAYOUT_PREFIX}{i}" for i in range(1, count + 1)]

    def _cycle_layout(self) -> None:
        order = self._all_layouts()
        try:
            idx = order.index(self._current_layout)
        except ValueError:
            idx = 0
        self._apply_layout(order[(idx + 1) % len(order)])

    def _show_all_overlay_panels(self) -> None:
        """Show every hidden floating panel (does NOT change positions)."""
        for fp in (self._float_video, self._float_source, self._float_watch,
                   self._float_playback, self._float_controls):
            if fp is not None:
                fp.show()
                fp.raise_()
        if self._float_video is not None:
            self.video_panel.refresh_video_sink()
        self._current_layout = LAYOUT_DEFAULT
        if self._overlay_controls is not None:
            self._overlay_controls.set_layout_label(LAYOUT_DEFAULT)

    def _restore_all_overlay_panels(self) -> None:
        """Reset every floating panel to its default size and position, and show it."""
        if not self._overlay_active:
            return
        screen = QApplication.primaryScreen().availableGeometry()
        defaults = {
            self._float_video: (
                screen.x() + (screen.width() - 1024) // 2,
                screen.y() + (screen.height() - 600) // 2, 1024, 600),
            self._float_source:   (screen.x() + 30, screen.y() + 80, 320, 560),
            self._float_watch:    (screen.right() - 330, screen.y() + 80, 300, 560),
            self._float_playback: (
                screen.x() + (screen.width() - 820) // 2,
                screen.bottom() - 290, 820, 130),
            self._float_controls: (
                screen.x() + (screen.width() - 760) // 2,
                screen.bottom() - 150, 760, 130),
        }
        for fp, geom in defaults.items():
            if fp is None: continue
            if fp.minimized:
                fp.apply_minimized(False)
            x, y, w, h = geom
            fp.show_with_geometry(x, y, w, h)
        if self._float_video is not None:
            self.video_panel.refresh_video_sink()
        self._current_layout = LAYOUT_DEFAULT
        if self._overlay_controls is not None:
            self._overlay_controls.set_layout_label(LAYOUT_DEFAULT)

    # ============ profile + appearance panel ============
    def _open_appearance_panel(self) -> None:
        if self._float_appearance is not None and self._float_appearance.isVisible():
            self._float_appearance.raise_(); self._float_appearance.activateWindow(); return
        if self._float_appearance is None:
            ap = AppearancePanel()
            ap.saved.connect(self._on_appearance_saved)
            ap.logout_requested.connect(self._on_logout)
            ap.border_changed.connect(self._apply_video_border)
            self._float_appearance = FloatingPanel("Profile & Appearance", ap)
            self._float_appearance.setMinimumSize(720, 520)
            screen = QApplication.primaryScreen().availableGeometry()
            s = QSettings(ORG_NAME, APP_NAME)
            self._restore_panel(self._float_appearance, "appearance", (
                screen.x() + (screen.width() - 980) // 2,
                screen.y() + (screen.height() - 660) // 2, 980, 660,
            ), s)
        else:
            self._float_appearance.show()
        self._float_appearance.raise_()

    def _apply_video_border(self, payload: dict) -> None:
        try:
            self.video_panel.apply_border(
                bool(payload.get("enabled")),
                str(payload.get("color") or "#e50914"),
                int(payload.get("width") or 4),
                bool(payload.get("rounded")),
                int(payload.get("radius") or 0),
            )
        except Exception:
            pass

    def _on_logout(self) -> None:
        """Sign out and quit the app — main.py's startup handles relaunch via login dialog."""
        try:
            supabase().auth.sign_out()
        except Exception:
            pass
        clear_session()
        QMessageBox.information(
            self, "Logged out",
            "You've been signed out. Relaunch NoMansMovies to log back in.")
        QApplication.instance().quit()

    def _on_appearance_saved(self) -> None:
        # Theme is already applied app-wide by AppearancePanel — no modal needed.
        # (Showing a QMessageBox parented to a hidden window during overlay mode
        # can block input on some setups.)
        pass

    def _open_controls_help(self) -> None:
        """Open the Controls cheatsheet in its own floating panel."""
        if getattr(self, "_float_help", None) is not None and self._float_help.isVisible():
            self._float_help.raise_(); self._float_help.activateWindow(); return
        if getattr(self, "_float_help", None) is None:
            help_widget = ControlsHelpPanel()
            self._float_help = FloatingPanel("Controls", help_widget)
            self._float_help.setMinimumSize(480, 400)
            screen = QApplication.primaryScreen().availableGeometry()
            self._float_help.show_with_geometry(
                screen.x() + (screen.width() - 620) // 2,
                screen.y() + (screen.height() - 720) // 2, 620, 720,
            )
        else:
            self._float_help.show()
        self._float_help.raise_()

    def _minimize_all_overlay(self) -> None:
        """Hide every floating panel and put MainWindow in the taskbar (minimized).
        Clicking the taskbar icon triggers changeEvent → we restore the panels."""
        if not self._overlay_active:
            return
        self._minimized_panel_state: Dict[str, bool] = {}
        for key, fp in [("video", self._float_video), ("source", self._float_source),
                        ("watch", self._float_watch), ("playback", self._float_playback),
                        ("controls", self._float_controls), ("appearance", self._float_appearance)]:
            if fp is not None:
                self._minimized_panel_state[key] = fp.isVisible()
                fp.hide()
        self._panels_in_tray = True
        self.showMinimized()

    def changeEvent(self, e):
        if (e.type() == QEvent.WindowStateChange
                and getattr(self, "_panels_in_tray", False)
                and not (self.windowState() & Qt.WindowMinimized)):
            # User clicked the taskbar icon — restore the floating panels.
            self._panels_in_tray = False
            for key, was_visible in (self._minimized_panel_state or {}).items():
                if not was_visible:
                    continue
                fp = {
                    "video":      self._float_video,
                    "source":     self._float_source,
                    "watch":      self._float_watch,
                    "playback":   self._float_playback,
                    "controls":   self._float_controls,
                    "appearance": self._float_appearance,
                }.get(key)
                if fp is not None:
                    fp.show(); fp.raise_()
            if self._float_video is not None:
                self.video_panel.refresh_video_sink()
            self._minimized_panel_state = None
            # Hide MainWindow again — we only used it as a taskbar handle.
            QTimer.singleShot(0, self.hide)
        super().changeEvent(e)

    # ============ Discord Rich Presence ============
    def _maybe_start_discord_presence(self) -> None:
        """Only connect if the user has linked their Discord (silent no-op if not)."""
        uid = current_user_id()
        if not uid:
            return
        try:
            r = supabase().table("profiles").select("discord_id").eq("id", uid).single().execute()
            linked = bool((r.data or {}).get("discord_id"))
        except Exception:
            linked = False
        if linked:
            self._discord.connect()

    def _start_online_presence(self) -> None:
        uid = current_user_id()
        if uid:
            self._presence.connect(uid)

    def _subscribe_incoming_messages(self) -> None:
        uid = current_user_id()
        if not uid:
            return
        try:
            ch = supabase().channel(f"inbox:{uid}")
            def on_insert(payload):
                row = (payload or {}).get("record") or (payload or {}).get("new") or {}
                if not isinstance(row, dict):
                    return
                if row.get("recipient") != uid:
                    return
                body = str(row.get("body") or "")
                if not body.startswith(JOIN_SCHEME):
                    return
                room_id = body[len(JOIN_SCHEME):].strip()
                if not room_id:
                    return
                # Resolve sender's username for the toast.
                sender_id = row.get("sender")
                sender_label = "A friend"
                try:
                    r = supabase().table("profiles").select("username").eq("id", sender_id).single().execute()
                    uname = (r.data or {}).get("username")
                    if uname: sender_label = f"@{uname}"
                except Exception:
                    pass
                QTimer.singleShot(0, lambda: self._show_invite_toast(sender_label, room_id))
            try:
                ch.on_postgres_changes(
                    event="INSERT", schema="public", table="messages",
                    callback=on_insert,
                )
            except TypeError:
                ch.on_postgres_changes("INSERT", schema="public", table="messages", callback=on_insert)
            ch.subscribe()
            self._inbox_channel = ch
        except Exception:
            self._inbox_channel = None

    def _show_invite_toast(self, sender_label: str, room_id: str) -> None:
        toast = InviteToast(sender_label, room_id)
        toast.accepted.connect(self.join_room_as_guest)
        toast.accepted.connect(lambda *_: self._active_toasts.remove(toast) if toast in self._active_toasts else None)
        toast.dismissed.connect(lambda: self._active_toasts.remove(toast) if toast in self._active_toasts else None)
        # Stack multiple toasts vertically.
        offset = sum(t.height() + 10 for t in self._active_toasts)
        p = toast.pos(); toast.move(p.x(), p.y() + offset)
        self._active_toasts.append(toast)
        toast.show()

    def _on_online_changed(self, ids) -> None:
        try:
            self.profile_page.friends.set_online_ids(ids)
        except Exception:
            pass
        try:
            self.watch_panel.set_online_ids(ids)
        except Exception:
            pass

    def _on_source_changed_for_presence(self, kind: str, original: str) -> None:
        # Try to find a friendlier label than the raw URL.
        label = original or ""
        if kind == "local":
            label = label.replace("\\", "/").rsplit("/", 1)[-1]
        elif kind == "youtube":
            label = label.split("?", 1)[0].rsplit("/", 1)[-1]
        self._discord.set_source(kind, label)

    def _save_custom_layout(self) -> None:
        """Save current panel geometry/visibility/minimized into a NEW Custom slot
        (Custom 1 → Custom 9). Each save creates a new entry that shows up in the
        cycler — older custom layouts are kept."""
        if not self._overlay_active:
            return
        s = QSettings(ORG_NAME, APP_NAME)
        # Also persist the standard auto-save so a restart-without-cycle still works.
        self._save_overlay_layout(s)
        count = self._read_int(s, "layouts/custom_count", 0)
        if count >= MAX_CUSTOM_LAYOUTS:
            # Roll over the oldest slot (slot 1) by shifting everything down.
            for i in range(1, count):
                self._copy_layout_slot(s, str(i + 1), str(i))
            slot = str(count)
        else:
            count += 1
            slot = str(count)
            s.setValue("layouts/custom_count", count)

        for key, fp in (("video", self._float_video), ("source", self._float_source),
                        ("watch", self._float_watch), ("playback", self._float_playback),
                        ("controls", self._float_controls), ("appearance", self._float_appearance)):
            if fp is None:
                continue
            h = (fp._restore_height or fp.height()) if fp.minimized else fp.height()
            s.setValue(f"layouts/{slot}/{key}_x", int(fp.x()))
            s.setValue(f"layouts/{slot}/{key}_y", int(fp.y()))
            s.setValue(f"layouts/{slot}/{key}_w", int(fp.width()))
            s.setValue(f"layouts/{slot}/{key}_h", int(h))
            s.setValue(f"layouts/{slot}/{key}_visible", "true" if fp.isVisible() else "false")
            s.setValue(f"layouts/{slot}/{key}_minimized", "true" if fp.minimized else "false")
        s.sync()

        self._current_layout = f"{CUSTOM_LAYOUT_PREFIX}{slot}"
        if self._overlay_controls is not None:
            self._overlay_controls.set_layout_label(self._current_layout)
            self._overlay_controls.flash_saved()

    @staticmethod
    def _copy_layout_slot(s: QSettings, src: str, dst: str) -> None:
        for key in ("video", "source", "watch", "playback", "controls", "appearance"):
            for prop in ("_x", "_y", "_w", "_h", "_visible", "_minimized"):
                v = s.value(f"layouts/{src}/{key}{prop}")
                if v is not None:
                    s.setValue(f"layouts/{dst}/{key}{prop}", v)

    def _recenter_video(self) -> None:
        if not self._float_video:
            return
        screen = QApplication.primaryScreen().availableGeometry()
        w, h = 1024, 600
        self._float_video.resize(w, h)
        self._float_video.move(
            screen.x() + (screen.width() - w) // 2,
            screen.y() + (screen.height() - h) // 2,
        )
        self._float_video.raise_()
        self.video_panel.refresh_video_sink()

    # ============ persistence ============
    def closeEvent(self, e):
        # If user closes while in overlay mode, persist the pre-overlay layout so
        # next launch comes back to a normal windowed state instead of frameless.
        if self._overlay_active and self._saved_geom is not None:
            geo_to_save = self._saved_geom
            flags_to_save = self._saved_flags
        else:
            geo_to_save = self.saveGeometry()
            flags_to_save = None
        s = QSettings(ORG_NAME, APP_NAME)
        s.setValue("ui/geometry", geo_to_save)
        s.setValue("ui/state", self.saveState())
        s.setValue("ui/friends_tab", self.profile_page.friends.tabs.currentIndex())
        s.setValue("ui/source_collapsed",   bool(self.source_dock.is_collapsed()))
        s.setValue("ui/watch_collapsed",    bool(self.watch_dock.is_collapsed()))
        s.setValue("ui/playback_collapsed", bool(self.playback_dock.is_collapsed()))
        # Persist overlay panel positions even when closing while still in overlay.
        if self._overlay_active:
            self._save_overlay_layout(s)
        s.sync()
        try:
            if self.room: self.room.close()
        except Exception:
            pass
        try:
            self._discord.disconnect()
        except Exception:
            pass
        try:
            self._presence.disconnect()
        except Exception:
            pass
        try:
            if self._inbox_channel is not None:
                supabase().remove_channel(self._inbox_channel)
        except Exception:
            pass
        super().closeEvent(e)


def _make_splash() -> Optional[QLabel]:
    """Frameless, centered, always-on-top animated splash (assets/splash.gif).

    Returns the splash widget (still running) or None if the gif is missing.
    Caller is responsible for showing it, waiting, and closing it.
    """
    gif = ASSETS_DIR / "splash.gif"
    if not gif.exists():
        return None
    lbl = QLabel(None)
    lbl.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.SplashScreen)
    lbl.setAttribute(Qt.WA_TranslucentBackground, True)
    lbl.setAttribute(Qt.WA_DeleteOnClose, True)
    movie = QMovie(str(gif))
    lbl.setMovie(movie)
    movie.jumpToFrame(0)
    sz = movie.currentPixmap().size()
    if sz.isValid() and not sz.isEmpty():
        lbl.resize(sz)
    lbl._movie = movie  # keep a reference alive on the widget
    movie.start()
    scr = QApplication.primaryScreen().availableGeometry()
    lbl.move(scr.center().x() - lbl.width() // 2, scr.center().y() - lbl.height() // 2)
    return lbl


def main() -> int:
    app = QApplication(sys.argv)
    app.setOrganizationName(ORG_NAME); app.setApplicationName(APP_NAME)
    # Set the app icon for the taskbar (and Minimize All Tabs taskbar entry).
    icon_path = ASSETS_DIR / "icons" / "app.ico"
    png_path = ASSETS_DIR / "icons" / "app.png"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))
    elif png_path.exists():
        app.setWindowIcon(QIcon(str(png_path)))
    apply_theme(DEFAULT_COLORS)

    # Show a quick splash NOW (before any slow work) so the user sees activity
    # the instant they double-click the exe. Closes as soon as the main window
    # is ready — no artificial wait.
    from .widgets.splash import Splash
    splash = Splash()
    splash.show_and_pump()

    # Kick off yt-dlp install/update in background (non-blocking)
    QTimer.singleShot(0, ytdlp_manager.maybe_update_async)

    # Auth
    if not try_restore_session():
        splash.close()
        dlg = AuthDialog()
        if dlg.exec() != AuthDialog.Accepted:
            return 0
        splash = Splash(); splash.show_and_pump()

    # Pull user's saved color scheme
    saved_scheme: dict = {}
    uid = current_user_id()
    if uid:
        try:
            r = supabase().table("profiles").select("color_scheme").eq("id", uid).single().execute()
            saved_scheme = (r.data or {}).get("color_scheme") or {}
            apply_theme(saved_scheme or DEFAULT_COLORS)
        except Exception:
            apply_theme(DEFAULT_COLORS)

    # Overlay-only build: boot straight into the floating overlay (over your
    # game). The windowed/docked profile+player mode no longer launches.
    w = MainWindow()
    # Apply video border from the saved theme on startup, before showing.
    if saved_scheme:
        try:
            w.video_panel.apply_border(
                bool(saved_scheme.get("video_border", False)),
                str(saved_scheme.get("video_border_color") or "#e50914"),
                int(saved_scheme.get("video_border_width") or 4),
                bool(saved_scheme.get("video_rounded", False)),
                int(saved_scheme.get("video_corner_radius") or 0),
            )
        except Exception:
            pass
    w.show()
    splash.close()
    QTimer.singleShot(0, lambda: w.set_overlay_mode(True))
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
