"""Friends panel: search, requests, friend list, view profile, message, remove."""
from __future__ import annotations
from typing import Callable, List, Optional
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QListWidget, QListWidgetItem, QMessageBox, QTabWidget
)

from ..supabase_client import supabase, current_user_id


class FriendsPanel(QWidget):
    view_profile = Signal(str)   # user id
    message = Signal(str)        # user id

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self); lay.setContentsMargins(10, 10, 10, 10); lay.setSpacing(8)

        title = QLabel("Friends"); title.setStyleSheet("font-size: 14pt; font-weight: 700;")
        lay.addWidget(title)

        search_row = QHBoxLayout()
        self.search = QLineEdit(); self.search.setPlaceholderText("Find by username")
        self.search.returnPressed.connect(self._do_search)
        go = QPushButton("Search"); go.clicked.connect(self._do_search)
        search_row.addWidget(self.search, 1); search_row.addWidget(go)
        lay.addLayout(search_row)

        self.tabs = QTabWidget()
        self.results_list = QListWidget()
        self.results_list.itemDoubleClicked.connect(self._open_search_profile)
        self.requests_list = QListWidget()
        self.friends_list = QListWidget()
        self.friends_list.itemDoubleClicked.connect(self._open_friend_profile)
        self.discord_list = QListWidget()
        self.tabs.addTab(self.friends_list, "Friends")
        self.tabs.addTab(self.requests_list, "Requests")
        self.tabs.addTab(self.discord_list, "Discord")
        self.tabs.addTab(self.results_list, "Search")
        self.tabs.currentChanged.connect(self._on_tab_changed)
        lay.addWidget(self.tabs, 1)

        self.refresh()

    # ============ data ============
    def refresh(self) -> None:
        self._load_friends()
        self._load_requests()
        if self.tabs.currentWidget() is self.discord_list:
            self._load_discord_users()

    def _on_tab_changed(self, idx: int) -> None:
        if self.tabs.widget(idx) is self.discord_list:
            self._load_discord_users()

    def _load_friends(self) -> None:
        uid = current_user_id()
        if not uid:
            return
        try:
            r = supabase().table("friendships").select("*").eq("status", "accepted").execute()
            rows = r.data or []
        except Exception:
            rows = []
        ids = [self._other(row, uid) for row in rows if self._other(row, uid)]
        profiles = self._fetch_profiles(ids)
        self.friends_list.clear()
        for p in profiles:
            it = QListWidgetItem(f"@{p['username']}")
            it.setData(Qt.UserRole, p["id"])
            it.setSizeHint(QSize(0, 36))
            self.friends_list.addItem(it)
            row = self._friend_row_widget(p)
            self.friends_list.setItemWidget(it, row)

    def _load_requests(self) -> None:
        uid = current_user_id()
        if not uid:
            return
        try:
            r = supabase().table("friendships").select("*").eq("addressee", uid).eq("status", "pending").execute()
            rows = r.data or []
        except Exception:
            rows = []
        ids = [row["requester"] for row in rows]
        profiles = {p["id"]: p for p in self._fetch_profiles(ids)}
        self.requests_list.clear()
        for row in rows:
            p = profiles.get(row["requester"]) or {"username": "(unknown)", "id": row["requester"]}
            it = QListWidgetItem(); it.setSizeHint(QSize(0, 40))
            self.requests_list.addItem(it)
            w = QWidget(); h = QHBoxLayout(w); h.setContentsMargins(6, 4, 6, 4)
            h.addWidget(QLabel(f"@{p['username']} wants to be your friend"), 1)
            acc = QPushButton("Accept"); acc.setProperty("accent", True)
            acc.clicked.connect(lambda _, rid=row["id"]: self._accept(rid))
            dec = QPushButton("Decline")
            dec.clicked.connect(lambda _, rid=row["id"]: self._decline(rid))
            h.addWidget(acc); h.addWidget(dec)
            self.requests_list.setItemWidget(it, w)

    def _load_discord_users(self) -> None:
        """List NoMansMovies users with linked Discord — excluding self and existing friends/requests."""
        uid = current_user_id()
        if not uid:
            return
        try:
            r = (supabase().table("profiles")
                 .select("id, username, discord_username, discord_avatar")
                 .not_.is_("discord_id", "null")
                 .neq("id", uid).limit(100).execute())
            rows = r.data or []
        except Exception:
            rows = []
        try:
            fr = supabase().table("friendships").select("requester, addressee, status").execute()
            existing = set()
            for row in fr.data or []:
                existing.add(row["addressee"] if row["requester"] == uid else row["requester"])
        except Exception:
            existing = set()
        rows = [p for p in rows if p["id"] not in existing]
        self.discord_list.clear()
        if not rows:
            self.discord_list.addItem("No Discord-linked users to discover."); return
        for p in rows:
            it = QListWidgetItem(); it.setSizeHint(QSize(0, 40)); it.setData(Qt.UserRole, p["id"])
            self.discord_list.addItem(it)
            w = QWidget(); h = QHBoxLayout(w); h.setContentsMargins(6, 4, 6, 4); h.setSpacing(6)
            label = f"@{p['username']}"
            if p.get("discord_username"):
                label += f"   ·   discord: {p['discord_username']}"
            h.addWidget(QLabel(label), 1)
            add = QPushButton("Add friend"); add.setProperty("accent", True)
            add.clicked.connect(lambda _, oid=p["id"]: self._send_request(oid))
            view = QPushButton("View"); view.clicked.connect(lambda _, oid=p["id"]: self.view_profile.emit(oid))
            h.addWidget(view); h.addWidget(add)
            self.discord_list.setItemWidget(it, w)

    def _fetch_profiles(self, ids: List[str]) -> List[dict]:
        ids = [i for i in ids if i]
        if not ids:
            return []
        try:
            r = supabase().table("profiles").select("id, username, avatar_url").in_("id", ids).execute()
            return r.data or []
        except Exception:
            return []

    def _other(self, row: dict, me: str) -> Optional[str]:
        return row["addressee"] if row["requester"] == me else row["requester"]

    # ============ actions ============
    def _do_search(self) -> None:
        q = self.search.text().strip()
        if not q:
            return
        uid = current_user_id()
        try:
            r = supabase().table("profiles").select("id, username, avatar_url").ilike("username", f"%{q}%").limit(20).execute()
            rows = [p for p in (r.data or []) if p["id"] != uid]
        except Exception as ex:
            QMessageBox.critical(self, "Search failed", str(ex)); return
        self.results_list.clear()
        self.tabs.setCurrentIndex(2)
        for p in rows:
            it = QListWidgetItem(); it.setSizeHint(QSize(0, 40)); it.setData(Qt.UserRole, p["id"])
            self.results_list.addItem(it)
            w = QWidget(); h = QHBoxLayout(w); h.setContentsMargins(6, 4, 6, 4)
            h.addWidget(QLabel(f"@{p['username']}"), 1)
            add = QPushButton("Add friend"); add.setProperty("accent", True)
            add.clicked.connect(lambda _, oid=p["id"]: self._send_request(oid))
            h.addWidget(add)
            self.results_list.setItemWidget(it, w)

    def _send_request(self, other_id: str) -> None:
        uid = current_user_id()
        if not uid:
            return
        try:
            supabase().table("friendships").insert({
                "requester": uid, "addressee": other_id, "status": "pending"
            }).execute()
            QMessageBox.information(self, "Sent", "Friend request sent.")
        except Exception as ex:
            QMessageBox.warning(self, "Could not send", str(ex))

    def _accept(self, fid: str) -> None:
        try:
            supabase().table("friendships").update({"status": "accepted"}).eq("id", fid).execute()
        except Exception as ex:
            QMessageBox.warning(self, "Could not accept", str(ex)); return
        self.refresh()

    def _decline(self, fid: str) -> None:
        try:
            supabase().table("friendships").delete().eq("id", fid).execute()
        except Exception as ex:
            QMessageBox.warning(self, "Could not decline", str(ex)); return
        self.refresh()

    def _remove(self, other_id: str) -> None:
        uid = current_user_id()
        if not uid:
            return
        try:
            supabase().table("friendships").delete().or_(
                f"and(requester.eq.{uid},addressee.eq.{other_id}),"
                f"and(requester.eq.{other_id},addressee.eq.{uid})"
            ).execute()
        except Exception as ex:
            QMessageBox.warning(self, "Could not remove", str(ex)); return
        self.refresh()

    def _friend_row_widget(self, p: dict) -> QWidget:
        w = QWidget(); h = QHBoxLayout(w); h.setContentsMargins(6, 4, 6, 4); h.setSpacing(6)
        h.addWidget(QLabel(f"@{p['username']}"), 1)
        view = QPushButton("View"); view.clicked.connect(lambda: self.view_profile.emit(p["id"]))
        msg = QPushButton("Message"); msg.clicked.connect(lambda: self.message.emit(p["id"]))
        rm = QPushButton("Remove"); rm.clicked.connect(lambda: self._remove(p["id"]))
        h.addWidget(view); h.addWidget(msg); h.addWidget(rm)
        return w

    def _open_friend_profile(self, item: QListWidgetItem) -> None:
        uid = item.data(Qt.UserRole)
        if uid:
            self.view_profile.emit(uid)

    def _open_search_profile(self, item: QListWidgetItem) -> None:
        uid = item.data(Qt.UserRole)
        if uid:
            self.view_profile.emit(uid)

    def accepted_friend_ids(self) -> List[str]:
        uid = current_user_id()
        if not uid:
            return []
        try:
            r = supabase().table("friendships").select("requester, addressee").eq("status", "accepted").execute()
            ids = []
            for row in r.data or []:
                ids.append(row["addressee"] if row["requester"] == uid else row["requester"])
            return ids
        except Exception:
            return []
