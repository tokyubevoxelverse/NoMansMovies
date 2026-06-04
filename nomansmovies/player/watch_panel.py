"""Right dock / floating panel: friends list with Invite / DM / Unfriend actions,
inline iMessage-style chat, and search-to-add-friends bar.

Click DM on a friend → the panel swaps to an embedded chat view with a Back
button. Add-friends search lives at the top.
"""
from __future__ import annotations
from typing import List, Optional
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QListWidget,
    QListWidgetItem, QMessageBox, QStackedWidget
)

from ..supabase_client import supabase, current_user_id
from ..config import MAX_INVITES
from ..widgets.inline_chat import InlineChat


class WatchPanel(QWidget):
    invite_clicked = Signal(str, str)   # (friend_id, friend_username)
    leave_room = Signal()
    invite_via_chat = Signal(str, str)   # (friend_id, friend_username) — DM-based invite from chat view

    def __init__(self, parent=None):
        super().__init__(parent)
        outer = QVBoxLayout(self); outer.setContentsMargins(10, 10, 10, 10); outer.setSpacing(8)

        title = QLabel("Watch together"); title.setStyleSheet("font-size: 14pt; font-weight: 700;")
        outer.addWidget(title)

        self.room_lbl = QLabel("No active room")
        self.room_lbl.setProperty("muted", True)
        outer.addWidget(self.room_lbl)
        self.invited_lbl = QLabel(f"Invited: 0 / {MAX_INVITES}")
        outer.addWidget(self.invited_lbl)

        # ---- search row (add friend by username) ----
        srow = QHBoxLayout(); srow.setSpacing(4)
        self.search = QLineEdit(); self.search.setPlaceholderText("Find by username — add friend")
        self.search.returnPressed.connect(self._do_search)
        srow.addWidget(self.search, 1)
        sbtn = QPushButton("Search"); sbtn.clicked.connect(self._do_search)
        srow.addWidget(sbtn)
        outer.addLayout(srow)

        # ---- two pages: friends list, inline chat ----
        self.stack = QStackedWidget()
        outer.addWidget(self.stack, 1)

        self._friends_page = QWidget()
        fl = QVBoxLayout(self._friends_page); fl.setContentsMargins(0, 0, 0, 0); fl.setSpacing(4)
        self.list = QListWidget()
        self.list.setStyleSheet("QListWidget { border: 1px solid rgba(255,255,255,0.10); border-radius: 6px; }")
        fl.addWidget(self.list, 1)
        self.search_results = QListWidget()
        self.search_results.setVisible(False)
        self.search_results.setStyleSheet("QListWidget { border: 1px solid rgba(255,255,255,0.10); border-radius: 6px; }")
        fl.addWidget(self.search_results)
        self.stack.addWidget(self._friends_page)

        self.chat = InlineChat()
        self.chat.back_requested.connect(self._show_friends)
        self.chat.invite_accepted.connect(lambda rid: self.invite_via_chat.emit("__join__", rid))
        self.stack.addWidget(self.chat)

        # ---- leave room ----
        leave = QPushButton("Leave room"); leave.clicked.connect(self.leave_room.emit)
        outer.addWidget(leave)

        self._invited_ids: List[str] = []
        self._enabled = True
        self._online_ids: set = set()
        self.refresh()

    # ============ API ============
    def set_room(self, room_id: Optional[str]) -> None:
        if room_id:
            self.room_lbl.setText(f"Room: {room_id[:8]}…")
        else:
            self.room_lbl.setText("No active room")
            self._invited_ids.clear()
            self._update_counter()
            self.refresh()

    def set_invite_enabled(self, enabled: bool) -> None:
        self._enabled = enabled
        self.refresh()

    def set_online_ids(self, ids) -> None:
        self._online_ids = set(ids or [])
        self.refresh()

    def refresh(self) -> None:
        uid = current_user_id()
        if not uid:
            return
        try:
            r = supabase().table("friendships").select("requester, addressee, status").eq("status", "accepted").execute()
            rows = r.data or []
        except Exception:
            rows = []
        ids = []
        for row in rows:
            ids.append(row["addressee"] if row["requester"] == uid else row["requester"])
        if ids:
            try:
                pr = supabase().table("profiles").select("id, username, discord_username").in_("id", ids).execute()
                profiles = pr.data or []
            except Exception:
                profiles = []
        else:
            profiles = []

        self.list.clear()
        for p in profiles:
            it = QListWidgetItem(); it.setSizeHint(QSize(0, 44))
            self.list.addItem(it)
            self.list.setItemWidget(it, self._friend_row(p))

    # ============ rows ============
    def _friend_row(self, p: dict) -> QWidget:
        w = QWidget(); h = QHBoxLayout(w); h.setContentsMargins(6, 4, 6, 4); h.setSpacing(4)
        online = p["id"] in self._online_ids
        dot = QLabel("●")
        dot.setStyleSheet(
            f"color: {'#22c55e' if online else '#5a5a65'}; "
            "background: transparent; font-size: 14pt;"
        )
        dot.setToolTip("Online" if online else "Offline")
        h.addWidget(dot)

        h.addWidget(QLabel(f"@{p['username']}"), 1)

        invite = QPushButton("Invite"); invite.setProperty("accent", True)
        invite.setEnabled(self._enabled and p["id"] not in self._invited_ids
                          and len(self._invited_ids) < MAX_INVITES)
        if not self._enabled:
            invite.setToolTip("Local files can't be shared with friends.")
        invite.clicked.connect(lambda _, oid=p["id"], un=p["username"]: self._invite(oid, un))
        h.addWidget(invite)

        dm = QPushButton("DM"); dm.setToolTip("Open chat with this friend")
        dm.clicked.connect(lambda _, oid=p["id"], un=p["username"]: self._open_chat(oid, un))
        h.addWidget(dm)

        rm = QPushButton("Unfriend")
        rm.clicked.connect(lambda _, oid=p["id"]: self._unfriend(oid))
        h.addWidget(rm)
        return w

    # ============ actions ============
    def _invite(self, friend_id: str, username: str) -> None:
        if len(self._invited_ids) >= MAX_INVITES:
            QMessageBox.information(self, "Limit reached", f"Max {MAX_INVITES} invitees per room."); return
        if friend_id in self._invited_ids:
            return
        self._invited_ids.append(friend_id)
        self._update_counter()
        self.refresh()
        self.invite_clicked.emit(friend_id, username)

    def _open_chat(self, friend_id: str, username: str) -> None:
        self.chat.open_with(friend_id, username)
        self.stack.setCurrentWidget(self.chat)

    def _show_friends(self) -> None:
        self.chat.close_thread()
        self.stack.setCurrentWidget(self._friends_page)

    def _unfriend(self, other_id: str) -> None:
        uid = current_user_id()
        if not uid:
            return
        try:
            supabase().table("friendships").delete().or_(
                f"and(requester.eq.{uid},addressee.eq.{other_id}),"
                f"and(requester.eq.{other_id},addressee.eq.{uid})"
            ).execute()
        except Exception as ex:
            QMessageBox.warning(self, "Could not unfriend", str(ex)); return
        self.refresh()

    def _do_search(self) -> None:
        q = self.search.text().strip()
        if not q:
            self.search_results.clear(); self.search_results.setVisible(False); return
        uid = current_user_id()
        try:
            r = supabase().table("profiles").select("id, username").ilike("username", f"%{q}%").limit(20).execute()
            rows = [p for p in (r.data or []) if p["id"] != uid]
        except Exception as ex:
            QMessageBox.critical(self, "Search failed", str(ex)); return
        self.search_results.clear()
        self.search_results.setVisible(True)
        if not rows:
            self.search_results.addItem("No matches."); return
        for p in rows:
            it = QListWidgetItem(); it.setSizeHint(QSize(0, 36))
            self.search_results.addItem(it)
            sw = QWidget(); sh = QHBoxLayout(sw); sh.setContentsMargins(6, 4, 6, 4)
            sh.addWidget(QLabel(f"@{p['username']}"), 1)
            add = QPushButton("Add"); add.setProperty("accent", True)
            add.clicked.connect(lambda _, oid=p["id"]: self._send_request(oid))
            sh.addWidget(add)
            self.search_results.setItemWidget(it, sw)

    def _send_request(self, other_id: str) -> None:
        uid = current_user_id()
        if not uid: return
        try:
            supabase().table("friendships").insert({
                "requester": uid, "addressee": other_id, "status": "pending"
            }).execute()
            QMessageBox.information(self, "Sent", "Friend request sent.")
        except Exception as ex:
            QMessageBox.warning(self, "Could not send", str(ex))

    def _update_counter(self) -> None:
        self.invited_lbl.setText(f"Invited: {len(self._invited_ids)} / {MAX_INVITES}")
