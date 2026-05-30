"""View one user's profile (own or a friend's). Read-only summary card."""
from __future__ import annotations
from typing import Optional
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame, QSizePolicy
)

from ..supabase_client import supabase, current_user_id
from ..widgets.animated_avatar import AnimatedAvatar


class ProfileView(QWidget):
    edit_requested = Signal()
    message_requested = Signal(str)         # other user id
    remove_friend_requested = Signal(str)   # other user id

    def __init__(self, parent=None):
        super().__init__(parent)
        self._user_id: Optional[str] = None
        self._is_self: bool = False

        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 24, 24, 24)
        outer.setSpacing(14)

        card = QFrame()
        card.setObjectName("profileCard")
        # styled via theme.py
        clay = QHBoxLayout(card); clay.setSpacing(20)

        self.avatar = AnimatedAvatar(size=140)
        clay.addWidget(self.avatar, 0, Qt.AlignTop)

        right = QVBoxLayout(); right.setSpacing(6)
        self.username_lbl = QLabel("…"); self.username_lbl.setStyleSheet("font-size: 22pt; font-weight: 700;")
        self.discord_lbl = QLabel("")
        self.discord_lbl.setProperty("muted", True)
        self.bio_lbl = QLabel(""); self.bio_lbl.setWordWrap(True)
        self.bio_lbl.setProperty("muted", True)
        right.addWidget(self.username_lbl)
        right.addWidget(self.discord_lbl)
        right.addWidget(self.bio_lbl)
        right.addStretch(1)

        actions = QHBoxLayout(); actions.setSpacing(8)
        self.edit_btn = QPushButton("Edit profile")
        self.edit_btn.setProperty("accent", True)
        self.edit_btn.clicked.connect(self.edit_requested.emit)
        self.msg_btn = QPushButton("Message")
        self.msg_btn.clicked.connect(self._on_msg)
        self.remove_btn = QPushButton("Remove friend")
        self.remove_btn.clicked.connect(self._on_remove)
        actions.addWidget(self.edit_btn)
        actions.addWidget(self.msg_btn)
        actions.addWidget(self.remove_btn)
        actions.addStretch(1)
        right.addLayout(actions)

        clay.addLayout(right, 1)
        outer.addWidget(card)
        outer.addStretch(1)

    def load(self, user_id: str) -> None:
        self._user_id = user_id
        self._is_self = (user_id == current_user_id())
        try:
            r = supabase().table("profiles").select("*").eq("id", user_id).single().execute()
            data = r.data or {}
        except Exception:
            data = {}
        self.username_lbl.setText(data.get("username") or "(no username)")
        if data.get("discord_id"):
            self.discord_lbl.setText(f"🎮 Discord: {data.get('discord_username') or 'linked'}")
            self.discord_lbl.show()
        else:
            self.discord_lbl.hide()
        self.bio_lbl.setText(data.get("bio") or ("Hi, I'm new here." if self._is_self else ""))
        self.avatar.set_url(data.get("avatar_url") or "")

        self.edit_btn.setVisible(self._is_self)
        self.msg_btn.setVisible(not self._is_self)
        self.remove_btn.setVisible(not self._is_self)

    def _on_msg(self) -> None:
        if self._user_id:
            self.message_requested.emit(self._user_id)

    def _on_remove(self) -> None:
        if self._user_id:
            self.remove_friend_requested.emit(self._user_id)
