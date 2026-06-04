"""Central video panel: QMediaPlayer + QVideoWidget with the hover ControlsOverlay.

Also responsible for:
    - Loading direct URLs (mp4/page urls) and local files.
    - Re-extracting YouTube/page URLs at a chosen quality via yt-dlp.
    - Notifying a connected WatchRoom of state/seek/heartbeats (when host).
    - Reacting to incoming source/state/seek/heartbeat events (when guest).
"""
from __future__ import annotations
import os
from typing import Optional
from PySide6.QtCore import Qt, QUrl, Signal, QTimer, QEvent
from PySide6.QtGui import QGuiApplication
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import QWidget, QVBoxLayout, QStackedLayout, QSizePolicy

from .controls_overlay import ControlsOverlay
from .settings_dialog import PlayerSettingsDialog
from ..config import ASPECT_RATIOS
from .. import ytdlp_manager


_ASPECT_MAP = {
    "Native":  Qt.KeepAspectRatio,
    "16:9":    Qt.KeepAspectRatio,
    "21:9":    Qt.KeepAspectRatio,
    "4:3":     Qt.KeepAspectRatio,
    "1:1":     Qt.KeepAspectRatio,
    "Stretch": Qt.IgnoreAspectRatio,
}


class VideoPanel(QWidget):
    """Wraps QMediaPlayer + QVideoWidget + overlay."""

    request_invite_target = Signal(str)   # url that guests should use (only valid for streaming sources)
    source_changed = Signal(str, str)     # (kind, original_url) — for the watch panel UI

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(320, 180)
        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        # autoFillBackground forces a SQUARE palette-coloured fill that ignores
        # border-radius — keep it OFF so QSS rounded corners actually clip.
        self.setAutoFillBackground(False)
        self.setObjectName("nmmVideoPanel")
        # ID selector beats the broad QWidget rule from theme.py.
        self.setStyleSheet("QWidget#nmmVideoPanel { background-color: #000; }")

        self._player = QMediaPlayer(self)
        self._audio = QAudioOutput(self); self._audio.setVolume(0.85)
        self._player.setAudioOutput(self._audio)

        self._video = QVideoWidget(self)
        self._video.setMouseTracking(True)
        self._video.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._video.setMinimumSize(1, 1)
        self._player.setVideoOutput(self._video)

        self._overlay = ControlsOverlay(self)
        # Always visible — the QGraphicsOpacityEffect handles the fade.
        self._overlay.show()

        # Layout: video fills the entire panel — no padding, no chrome.
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0); outer.setSpacing(0)
        outer.addWidget(self._video)

        # State
        self._aspect = "Native"
        self._quality = "Best available"
        self._current_kind = "none"       # 'mp4' | 'youtube' | 'local'
        self._original_url = ""           # what the user pasted/picked (used to re-extract on quality change)

        # connections
        self._player.positionChanged.connect(self._overlay.update_position)
        self._player.durationChanged.connect(self._overlay.update_duration)
        self._player.playbackStateChanged.connect(
            lambda st: self._overlay.set_playing(st == QMediaPlayer.PlayingState))

        self._overlay.play_pause.connect(self.toggle_play)
        self._overlay.stop.connect(self.stop)
        self._overlay.rewind.connect(lambda: self.seek_relative(-10_000))
        self._overlay.forward.connect(lambda: self.seek_relative(+10_000))
        self._overlay.next_.connect(lambda: self.stop())  # next is queue-aware; for now stop
        self._overlay.seek.connect(self.seek_to)
        self._overlay.volume.connect(self._on_volume)
        self._overlay.settings.connect(self._open_settings)
        self._overlay.fullscreen.connect(self.toggle_fullscreen)

        # Hover handling
        self._video.installEventFilter(self)
        self.installEventFilter(self)

        QTimer.singleShot(0, self._position_overlay)

        # Watch-room hooks (wired by main when joining/hosting)
        self._room = None
        self._suppress_outbound = False
        self._last_host_pos_ms: int | None = None
        self._last_host_playing: bool | None = None

    def apply_border(self, enabled: bool, color: str, width: int,
                     rounded: bool, radius: int) -> None:
        """Decorative border around the video.

        QVideoWidget uses a native Win32 surface that can't be painted over with
        a Qt border, so we fake it: VideoPanel itself paints a colored background,
        and we inset the QVideoWidget with layout margins of `width` px. Rounded
        corners apply to the OUTER frame only (the inner video stays rectangular)."""
        w = max(0, int(width))
        r = max(0, int(radius)) if rounded else 0
        if enabled and w > 0:
            self.layout().setContentsMargins(w, w, w, w)
            radius_css = f"border-radius: {r}px;" if rounded else ""
            self.setStyleSheet(
                f"QWidget#nmmVideoPanel {{ background-color: {color}; {radius_css} }}"
            )
        else:
            self.layout().setContentsMargins(0, 0, 0, 0)
            self.setStyleSheet("QWidget#nmmVideoPanel { background-color: #000; }")
        # Reposition the overlay so the controls don't sit over the border strip.
        QTimer.singleShot(0, self._position_overlay)

    def refresh_video_sink(self) -> None:
        """Call after the panel has been reparented — re-attaches the video output
        so the QVideoWidget keeps painting in its new native window."""
        try:
            self._player.setVideoOutput(None)
            self._player.setVideoOutput(self._video)
        except Exception:
            pass

    # ============ public: load sources ============
    def load_url(self, url: str, kind: str = "mp4") -> None:
        """Load a direct streaming URL (mp4 / extracted yt-dlp url) or local path."""
        self._original_url = url if kind != "local" else ""
        self._current_kind = kind
        self._player.setSource(QUrl(url) if kind != "local" else QUrl.fromLocalFile(url))
        self._player.play()
        self.source_changed.emit(kind, self._original_url or url)

    def load_youtube(self, page_url: str) -> None:
        """Extract a stream URL with yt-dlp and play it. If yt-dlp can't extract
        (usually because YouTube changed something and the local yt-dlp is out
        of date), force an update and retry once; if that still fails, surface
        a real error dialog so the user knows."""
        self._original_url = page_url
        self._current_kind = "youtube"
        url = ytdlp_manager.extract_stream_url(page_url, self._quality)
        if not url:
            # Force-update yt-dlp synchronously and try once more.
            try:
                ytdlp_manager.update()
            except Exception:
                pass
            url = ytdlp_manager.extract_stream_url(page_url, self._quality)
        if not url:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(
                self, "YouTube playback failed",
                "Could not extract a playable stream from that YouTube link.\n\n"
                "Things to check:\n"
                "  • You're connected to the internet (YouTube playback requires it — "
                "direct mp4 links and local files don't).\n"
                "  • The video isn't age-restricted or region-blocked.\n"
                "  • Try a different quality from the ⚙ Settings menu.\n\n"
                "If many videos fail, your bundled yt-dlp may be outdated. "
                "Delete the file at MoviePlugin\\ytdlp\\yt-dlp.exe and relaunch "
                "to download a fresh copy."
            )
            return
        self._player.setSource(QUrl(url))
        self._player.play()
        self.source_changed.emit("youtube", page_url)

    def load_local(self, path: str) -> None:
        self.load_url(path, kind="local")

    # ============ playback ============
    def toggle_play(self) -> None:
        if self._player.playbackState() == QMediaPlayer.PlayingState:
            self._player.pause()
        else:
            self._player.play()
        self._announce_state()

    def stop(self) -> None:
        self._player.stop()
        self._announce_state()

    def seek_to(self, ms: int) -> None:
        self._player.setPosition(int(ms))
        if self._room and not self._suppress_outbound:
            self._room.send_seek(int(ms))

    def seek_relative(self, delta_ms: int) -> None:
        new = max(0, self._player.position() + delta_ms)
        self.seek_to(new)

    def _on_volume(self, v: int) -> None:
        self._audio.setVolume(max(0.0, min(1.0, v / 100.0)))

    # Public aliases used by the dedicated playback bar.
    def set_volume(self, v: int) -> None: self._on_volume(v)
    def open_settings(self) -> None: self._open_settings()

    @property
    def player(self):
        return self._player

    def _open_settings(self) -> None:
        dlg = PlayerSettingsDialog(self._aspect, self._quality, self)
        if dlg.exec():
            a, q = dlg.values()
            self.apply_aspect(a)
            if q != self._quality:
                self._quality = q
                if self._current_kind == "youtube" and self._original_url:
                    pos = self._player.position()
                    new = ytdlp_manager.extract_stream_url(self._original_url, q)
                    if new:
                        self._player.setSource(QUrl(new))
                        self._player.setPosition(pos)
                        self._player.play()

    def apply_aspect(self, name: str) -> None:
        self._aspect = name
        self._video.setAspectRatioMode(_ASPECT_MAP.get(name, Qt.KeepAspectRatio))

    def toggle_fullscreen(self) -> None:
        win = self.window()
        if win.isFullScreen():
            win.showNormal()
        else:
            win.showFullScreen()

    # ============ watch room ============
    def attach_room(self, room, as_host: bool) -> None:
        self._room = room
        if as_host:
            room.start_heartbeat(self._snapshot)
        else:
            room.source_received.connect(self._on_remote_source)
            room.state_received.connect(self._on_remote_state)
            room.seek_received.connect(self._on_remote_seek)
            room.heartbeat_received.connect(self._on_remote_heartbeat)

    def detach_room(self) -> None:
        self._room = None

    def _snapshot(self) -> dict:
        return {
            "position_ms": int(self._player.position()),
            "playing": self._player.playbackState() == QMediaPlayer.PlayingState,
        }

    def _announce_state(self) -> None:
        if self._room and not self._suppress_outbound:
            self._room.send_state(
                self._player.playbackState() == QMediaPlayer.PlayingState,
                int(self._player.position()),
            )

    def _on_remote_source(self, payload: dict) -> None:
        url = payload.get("url"); kind = payload.get("kind", "mp4")
        if not url:
            return
        self._suppress_outbound = True
        self.load_url(url, kind)
        self._suppress_outbound = False

    def _on_remote_state(self, payload: dict) -> None:
        self._suppress_outbound = True
        pos = int(payload.get("position_ms", self._player.position()))
        self._player.setPosition(pos)
        if payload.get("playing"):
            self._player.play()
        else:
            self._player.pause()
        self._suppress_outbound = False

    def _on_remote_seek(self, pos: int) -> None:
        self._suppress_outbound = True
        self._player.setPosition(int(pos))
        self._suppress_outbound = False

    def _on_remote_heartbeat(self, payload: dict) -> None:
        host_pos = int(payload.get("position_ms", 0))
        self._last_host_pos_ms = host_pos
        self._last_host_playing = bool(payload.get("playing", True))
        drift = abs(self._player.position() - host_pos)
        if drift > 1500:
            self._suppress_outbound = True
            self._player.setPosition(host_pos)
            self._suppress_outbound = False

    def resync_with_room(self, is_host: bool) -> None:
        """Force a sync with everyone in the room. Host: rebroadcasts current state.
        Guest: snaps to the last position the host's heartbeat reported."""
        if self._room is None:
            return
        if is_host:
            from PySide6.QtMultimedia import QMediaPlayer
            self._room.send_state(
                self._player.playbackState() == QMediaPlayer.PlayingState,
                int(self._player.position()),
            )
        elif self._last_host_pos_ms is not None:
            self._suppress_outbound = True
            self._player.setPosition(int(self._last_host_pos_ms))
            self._suppress_outbound = False

    # ============ overlay positioning + hover ============
    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._position_overlay()

    def _position_overlay(self) -> None:
        # Cover the entire video area so the overlay reliably catches mouse
        # enter/move events (QVideoWidget's native window swallows them).
        self._overlay.setGeometry(0, 0, self.width(), self.height())
        self._overlay.raise_()

    def eventFilter(self, obj, e):
        t = e.type()
        if t in (QEvent.MouseMove, QEvent.Enter):
            self._overlay.kick()
        elif t == QEvent.Leave:
            self._overlay._hide_timer.start(800)
        return super().eventFilter(obj, e)

    def enterEvent(self, e):
        self._overlay.fade_in()

    def leaveEvent(self, e):
        self._overlay._hide_timer.start(800)
