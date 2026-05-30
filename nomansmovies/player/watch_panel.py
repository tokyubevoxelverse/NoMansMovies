"""Right dock: friends list with invite buttons + active room participants.

Host invites up to 3 friends to the current movie. Each invite is a DM
containing `nomansmovies://join/<room_id>` — the friend's chat window
renders that as a "Join watch room" CTA.
"""
from __future__ import annotations
from typing import List, Optional
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QListWidget,
    QListWidgetItem, QMessageBox
)

from ..supabase_client import supabase, current_user_id
from ..config import MAX_INVITES


class WatchPanel(QWidget):
    invite_clicked = Signal(str, str)   # (friend_id, friend_username)
    leave_room = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self); lay.setContentsMargins(10, 10, 10, 10); lay.setSpacing(8)

        title = QLabel("Watch together"); title.setStyleSheet("font-size: 14pt; font-weight: 700;")
        lay.addWidget(title)

        self.room_lbl = QLabel("No active room")
        self.room_lbl.setProperty("muted", True)
        lay.addWidget(self.room_lbl)

        self.invited_lbl = QLabel(f"Invited: 0 / {MAX_INVITES}")
        lay.addWidget(self.invited_lbl)

        self.friends = QListWidget()
        lay.addWidget(self.friends, 1)

        leave = QPushButton("Leave room"); leave.clicked.connect(self.leave_room.emit)
        lay.addWidget(leave)

        self._invited_ids: List[str] = []
        self._enabled = True  # only valid for streaming sources
        self.refresh()

    def set_room(self, room_id: Optional[str]) -> None:
        if room_id:
            self.room_lbl.setText(f"Room: {room_id[:8]}…")
        else:
            self.room_lbl.setText("No active room")
            self._invited_ids.clear()
            self._update_counter()
            self.refresh()

    def set_invite_enabled(self, enabled: bool) -> None:
        """Disable invites for local-file sources (friends can't reach the path)."""
        self._enabled = enabled
        self.refresh()

    def refresh(self) -> None:
        uid = current_user_id()
        if not uid:
            return
        try:
            r = supabase().table("friendships").select("requester, addressee").eq("status", "accepted").execute()
            rows = r.data or []
        except Exception:
            rows = []
        ids = []
        for row in rows:
            ids.append(row["addressee"] if row["requester"] == uid else row["requester"])
        try:
            r = supabase().table("profiles").select("id, username").in_("id", ids).execute() if ids else None
            profiles = (r.data if r else []) or []
        except Exception:
            profiles = []

        self.friends.clear()
        for p in profiles:
            it = QListWidgetItem(); it.setSizeHint(QSize(0, 40))
            self.friends.addItem(it)
            w = QWidget(); h = QHBoxLayout(w); h.setContentsMargins(6, 4, 6, 4)
            h.addWidget(QLabel(f"@{p['username']}"), 1)
            btn = QPushButton("Invite" if p["id"] not in self._invited_ids else "Invited ✓")
            btn.setProperty("accent", True)
            already = p["id"] in self._invited_ids
            at_cap = len(self._invited_ids) >= MAX_INVITES
            btn.setEnabled(self._enabled and not already and not at_cap)
            if not self._enabled:
                btn.setToolTip("Local files can't be shared (your friends can't reach the path).")
            elif at_cap and not already:
                btn.setToolTip(f"Max {MAX_INVITES} invitees.")
            btn.clicked.connect(lambda _, oid=p["id"], un=p["username"]: self._invite(oid, un))
            h.addWidget(btn)
            self.friends.setItemWidget(it, w)

    def _invite(self, friend_id: str, username: str) -> None:
        if len(self._invited_ids) >= MAX_INVITES:
            QMessageBox.information(self, "Limit reached", f"Max {MAX_INVITES} invitees per room."); return
        if friend_id in self._invited_ids:
            return
        self._invited_ids.append(friend_id)
        self._update_counter()
        self.refresh()
        self.invite_clicked.emit(friend_id, username)

    def _update_counter(self) -> None:
        self.invited_lbl.setText(f"Invited: {len(self._invited_ids)} / {MAX_INVITES}")
