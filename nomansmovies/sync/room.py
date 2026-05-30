"""Watch-together room using Supabase Realtime broadcast channels.

One channel per room: `watch:<room_id>`. Events:
    - source  : {url, kind, quality, original}
    - state   : {playing: bool, position_ms: int}
    - seek    : {position_ms: int}
    - heartbeat: {position_ms: int, playing: bool}  (host -> guests, ~1 Hz)
"""
from __future__ import annotations
import uuid
from typing import Callable, Optional
from PySide6.QtCore import QObject, Signal, QTimer

from ..supabase_client import supabase


class WatchRoom(QObject):
    source_received = Signal(dict)
    state_received = Signal(dict)
    seek_received = Signal(int)
    heartbeat_received = Signal(dict)

    def __init__(self, room_id: Optional[str] = None, is_host: bool = False, parent=None):
        super().__init__(parent)
        self.room_id = room_id or str(uuid.uuid4())
        self.is_host = is_host
        self._channel = None
        self._hb_timer: Optional[QTimer] = None
        self._hb_provider: Optional[Callable[[], dict]] = None

    # ============ lifecycle ============
    def open(self) -> None:
        try:
            self._channel = supabase().channel(f"watch:{self.room_id}")
            self._channel.on_broadcast("source",   lambda p: self.source_received.emit(p.get("payload") or {}))
            self._channel.on_broadcast("state",    lambda p: self.state_received.emit(p.get("payload") or {}))
            self._channel.on_broadcast("seek",     lambda p: self.seek_received.emit(int((p.get("payload") or {}).get("position_ms", 0))))
            self._channel.on_broadcast("heartbeat",lambda p: self.heartbeat_received.emit(p.get("payload") or {}))
            self._channel.subscribe()
        except Exception:
            self._channel = None

    def close(self) -> None:
        if self._hb_timer:
            self._hb_timer.stop(); self._hb_timer = None
        try:
            if self._channel is not None:
                supabase().remove_channel(self._channel)
        except Exception:
            pass
        self._channel = None

    # ============ host -> guests ============
    def send_source(self, url: str, kind: str, quality: str, original: str = "") -> None:
        self._send("source", {"url": url, "kind": kind, "quality": quality, "original": original})

    def send_state(self, playing: bool, position_ms: int) -> None:
        self._send("state", {"playing": playing, "position_ms": position_ms})

    def send_seek(self, position_ms: int) -> None:
        self._send("seek", {"position_ms": position_ms})

    def start_heartbeat(self, provider: Callable[[], dict], interval_ms: int = 1000) -> None:
        """provider() -> {'position_ms': int, 'playing': bool}"""
        self._hb_provider = provider
        if self._hb_timer is None:
            self._hb_timer = QTimer(self)
            self._hb_timer.timeout.connect(self._tick_hb)
        self._hb_timer.start(interval_ms)

    def _tick_hb(self) -> None:
        if not self._hb_provider:
            return
        try:
            payload = self._hb_provider()
        except Exception:
            return
        self._send("heartbeat", payload)

    def _send(self, event: str, payload: dict) -> None:
        if self._channel is None:
            return
        try:
            self._channel.send_broadcast(event, payload)
        except Exception:
            try:
                # supabase-py v2 API variant
                self._channel.send({"type": "broadcast", "event": event, "payload": payload})
            except Exception:
                pass
