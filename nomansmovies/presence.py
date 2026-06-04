"""Supabase Realtime presence tracker.

Each signed-in app instance joins the global channel `nomansmovies:online` and
tracks `{uid: <auth.uid()>}`. Any subscriber to the channel can read the
current presence state to know who else is online.
"""
from __future__ import annotations
from typing import Set
from PySide6.QtCore import QObject, Signal

from .supabase_client import supabase


class PresenceTracker(QObject):
    online_changed = Signal(set)  # set[str] of online uids

    def __init__(self):
        super().__init__()
        self._channel = None
        self._uid: str | None = None
        self._online: Set[str] = set()

    def connect(self, my_uid: str) -> None:
        if not my_uid:
            return
        self._uid = my_uid
        try:
            ch = supabase().channel(
                "nomansmovies:online",
                {"config": {"presence": {"key": my_uid}}},
            )
        except TypeError:
            # Older supabase-py: channel() takes only a name.
            ch = supabase().channel("nomansmovies:online")

        def on_sync(*_args, **_kwargs):
            try:
                state = ch.presence_state() if hasattr(ch, "presence_state") else {}
                online = set()
                for key, entries in (state or {}).items():
                    # entries is a list of meta-dicts; key is the presence key (we use uid).
                    for entry in entries or []:
                        u = entry.get("uid") if isinstance(entry, dict) else None
                        if u: online.add(u)
                    online.add(key)
                self._online = online
                self.online_changed.emit(set(self._online))
            except Exception:
                pass

        try:
            ch.on_presence_sync(on_sync)
        except Exception:
            pass

        def on_subscribe(status, *_a, **_kw):
            if status == "SUBSCRIBED":
                try: ch.track({"uid": my_uid})
                except Exception: pass

        try:
            ch.subscribe(on_subscribe)
        except Exception:
            try: ch.subscribe()
            except Exception: pass

        self._channel = ch

    def disconnect(self) -> None:
        if self._channel is None:
            return
        try:
            self._channel.untrack()
        except Exception:
            pass
        try:
            supabase().remove_channel(self._channel)
        except Exception:
            pass
        self._channel = None
        self._online = set()

    def online_ids(self) -> Set[str]:
        return set(self._online)
