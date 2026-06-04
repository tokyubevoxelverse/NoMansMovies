"""Discord Rich Presence — shows what the user is watching.

Uses pypresence over the local Discord IPC pipe. No network calls, no auth —
just the user's running Discord client. If Discord isn't running or pypresence
isn't installed, all calls are silent no-ops.

Setup in the Discord developer portal (https://discord.com/developers):
    1. Open your application → Rich Presence → Art Assets.
    2. Upload images with the asset KEYS used below (matching the strings exactly):
         logo, youtube, link, file
       Names are CASE-INSENSITIVE and must use only [a-z0-9_-].
    3. Save. The presence will start showing within a few seconds.
"""
from __future__ import annotations
import time
from typing import Optional

try:
    from pypresence import Presence
    HAS_PYPRESENCE = True
except Exception:
    HAS_PYPRESENCE = False

from .config import DISCORD_CLIENT_ID


class DiscordPresence:
    def __init__(self) -> None:
        self._rpc: Optional["Presence"] = None
        self._connected = False
        self._start_time = int(time.time())

    def is_available(self) -> bool:
        return HAS_PYPRESENCE

    def connect(self) -> bool:
        if not HAS_PYPRESENCE:
            return False
        try:
            self._rpc = Presence(DISCORD_CLIENT_ID)
            self._rpc.connect()
            self._connected = True
            self.set_idle()
            return True
        except Exception:
            self._connected = False
            self._rpc = None
            return False

    def disconnect(self) -> None:
        if self._rpc and self._connected:
            try: self._rpc.clear()
            except Exception: pass
            try: self._rpc.close()
            except Exception: pass
        self._connected = False
        self._rpc = None

    def set_idle(self) -> None:
        self._update(
            state="Idle in the lobby",
            details="In NoMansMovies",
            large_image="logo",
            large_text="NoMansMovies",
        )

    def set_source(self, kind: str, label: str = "") -> None:
        """kind: 'youtube' | 'mp4' | 'local' | 'none'. label is an optional title."""
        if kind == "youtube":
            self._update(
                details="Gaming in NoMansMovies with YouTube",
                state=(label or "Watching a YouTube video")[:128],
                large_image="logo", large_text="NoMansMovies",
                small_image="youtube", small_text="YouTube",
            )
        elif kind == "mp4":
            self._update(
                details="Gaming in NoMansMovies",
                state=("Direct stream: " + label)[:128] if label else "Watching a direct stream",
                large_image="logo", large_text="NoMansMovies",
                small_image="link", small_text="Direct link",
            )
        elif kind == "local":
            self._update(
                details="Gaming in NoMansMovies",
                state=("Local file: " + label)[:128] if label else "Watching a local file",
                large_image="logo", large_text="NoMansMovies",
                small_image="file", small_text="Local file",
            )
        else:
            self.set_idle()

    def _update(self, **kwargs) -> None:
        if not self._connected or self._rpc is None:
            return
        try:
            self._rpc.update(start=self._start_time, **kwargs)
        except Exception:
            # Discord disconnected — drop the rpc and try to reconnect later.
            self._connected = False
            self._rpc = None
