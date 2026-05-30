"""DM chat window with Supabase Realtime postgres-changes subscription.

A message body starting with `nomansmovies://join/<uuid>` is rendered as an
"Accept invite" call-to-action that joins a watch-together room.
"""
from __future__ import annotations
from typing import Optional, Callable
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton, QLabel,
    QScrollArea, QWidget, QFrame, QMessageBox
)

from ..supabase_client import supabase, current_user_id
from ..theme import current as current_theme

JOIN_SCHEME = "nomansmovies://join/"


class _Bubble(QFrame):
    def __init__(self, text: str, mine: bool, parent=None):
        super().__init__(parent)
        c = current_theme()
        bg = c["accent"] if mine else c["panel"]
        fg = "#ffffff" if mine else c["fg"]
        self.setStyleSheet(
            f"QFrame {{ background: {bg}; border: 1px solid {c['border']}; "
            f"border-radius: 12px; padding: 8px 12px; }}"
        )
        lay = QVBoxLayout(self); lay.setContentsMargins(8, 6, 8, 6)
        lbl = QLabel(text); lbl.setWordWrap(True); lbl.setStyleSheet(f"color: {fg}; background: transparent;")
        lay.addWidget(lbl)


class ChatWindow(QDialog):
    """Per-friend DM dialog. join_callback gets called when user accepts an invite."""
    invite_accepted = Signal(str)  # room_id

    def __init__(self, other_id: str, other_name: str, parent=None):
        super().__init__(parent)
        self.other_id = other_id
        self.setWindowTitle(f"Chat with @{other_name}")
        self.resize(440, 560)

        lay = QVBoxLayout(self); lay.setContentsMargins(10, 10, 10, 10); lay.setSpacing(6)

        self.scroll = QScrollArea(); self.scroll.setWidgetResizable(True)
        self._container = QWidget()
        self._vbox = QVBoxLayout(self._container); self._vbox.setSpacing(6); self._vbox.addStretch(1)
        self.scroll.setWidget(self._container)
        lay.addWidget(self.scroll, 1)

        row = QHBoxLayout()
        self.input = QLineEdit(); self.input.setPlaceholderText("Type a message…")
        self.input.returnPressed.connect(self._send)
        send_btn = QPushButton("Send"); send_btn.setProperty("accent", True); send_btn.clicked.connect(self._send)
        row.addWidget(self.input, 1); row.addWidget(send_btn)
        lay.addLayout(row)

        self._channel = None
        self._load_history()
        self._subscribe()

        # Periodically refresh as a fallback (in case realtime is flaky).
        self._timer = QTimer(self); self._timer.timeout.connect(self._refresh); self._timer.start(5000)

    def _load_history(self) -> None:
        uid = current_user_id()
        if not uid:
            return
        try:
            r = (supabase().table("messages").select("*")
                 .or_(f"and(sender.eq.{uid},recipient.eq.{self.other_id}),"
                      f"and(sender.eq.{self.other_id},recipient.eq.{uid})")
                 .order("created_at", desc=False).limit(200).execute())
            rows = r.data or []
        except Exception:
            rows = []
        # clear bubbles (skip stretch)
        while self._vbox.count() > 1:
            it = self._vbox.takeAt(0)
            w = it.widget()
            if w: w.deleteLater()
        for row in rows:
            self._append_bubble(row["body"], row["sender"] == uid)
        QTimer.singleShot(0, self._scroll_bottom)

    def _refresh(self) -> None:
        # cheap re-read; realtime should usually keep us in sync
        self._load_history()

    def _append_bubble(self, body: str, mine: bool) -> None:
        wrap = QHBoxLayout()
        if mine:
            wrap.addStretch(1)
        if body.startswith(JOIN_SCHEME):
            room_id = body[len(JOIN_SCHEME):].strip()
            ct = current_theme()
            frame = QFrame()
            frame.setStyleSheet(
                f"QFrame {{ background: {ct['panel']}; border: 1px solid {ct['accent']}; "
                "border-radius: 12px; padding: 8px 12px; }}"
            )
            fl = QVBoxLayout(frame); fl.setContentsMargins(8, 6, 8, 6); fl.setSpacing(4)
            fl.addWidget(QLabel("🎬  Invitation to watch a movie together"))
            btn = QPushButton("Join watch room")
            btn.setProperty("accent", True)
            btn.clicked.connect(lambda: self.invite_accepted.emit(room_id))
            fl.addWidget(btn)
            wrap.addWidget(frame, 0, Qt.AlignLeft if not mine else Qt.AlignRight)
        else:
            wrap.addWidget(_Bubble(body, mine), 0, Qt.AlignLeft if not mine else Qt.AlignRight)
        if not mine:
            wrap.addStretch(1)
        container = QWidget(); container.setLayout(wrap)
        self._vbox.insertWidget(self._vbox.count() - 1, container)

    def _scroll_bottom(self) -> None:
        sb = self.scroll.verticalScrollBar(); sb.setValue(sb.maximum())

    def _send(self, body: str | None = None) -> None:
        text = body if body is not None else self.input.text().strip()
        if not text:
            return
        uid = current_user_id()
        if not uid:
            return
        try:
            supabase().table("messages").insert({
                "sender": uid, "recipient": self.other_id, "body": text
            }).execute()
        except Exception as ex:
            QMessageBox.warning(self, "Send failed", str(ex)); return
        if body is None:
            self.input.clear()
        self._load_history()

    def send_invite(self, room_id: str) -> None:
        self._send(f"{JOIN_SCHEME}{room_id}")

    def _subscribe(self) -> None:
        uid = current_user_id()
        if not uid:
            return
        try:
            ch = supabase().channel(f"dm:{uid}:{self.other_id}")
            ch.on_postgres_changes(
                event="INSERT", schema="public", table="messages",
                callback=lambda payload: QTimer.singleShot(0, self._load_history),
            )
            ch.subscribe()
            self._channel = ch
        except Exception:
            self._channel = None

    def closeEvent(self, e):
        try:
            if self._channel is not None:
                supabase().remove_channel(self._channel)
        except Exception:
            pass
        super().closeEvent(e)
