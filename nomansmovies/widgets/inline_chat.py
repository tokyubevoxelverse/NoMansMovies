"""Embeddable iMessage-style chat widget.

Used inside the Watch Together panel and anywhere else we need a DM thread.
Reads / writes the same `public.messages` table the old ChatWindow used, and
renders join-room invites as a "Join watch room" button (same scheme).
"""
from __future__ import annotations
from typing import Optional, Callable
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QFrame,
    QScrollArea, QSizePolicy, QMessageBox
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
        radius = "16px"
        # Use a "tail" corner via different radius for iMessage-style.
        tail = "border-bottom-right-radius: 4px;" if mine else "border-bottom-left-radius: 4px;"
        self.setStyleSheet(
            f"QFrame {{ background: {bg}; border: 1px solid {c['border']}; "
            f"border-radius: {radius}; {tail} padding: 8px 12px; }}"
        )
        self.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Preferred)
        lay = QVBoxLayout(self); lay.setContentsMargins(8, 6, 8, 6)
        lbl = QLabel(text); lbl.setWordWrap(True)
        lbl.setMaximumWidth(360)
        lbl.setStyleSheet(f"color: {fg}; background: transparent; border: none; padding: 0;")
        lay.addWidget(lbl)


class InlineChat(QWidget):
    invite_accepted = Signal(str)   # room_id
    back_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._other_id: Optional[str] = None
        self._other_name: str = ""
        self._channel = None

        lay = QVBoxLayout(self); lay.setContentsMargins(8, 8, 8, 8); lay.setSpacing(6)

        # Header: ← Back  @username
        hrow = QHBoxLayout(); hrow.setSpacing(6)
        self.back_btn = QPushButton("←")
        self.back_btn.setFixedWidth(36)
        self.back_btn.setToolTip("Back to friends")
        self.back_btn.clicked.connect(self.back_requested.emit)
        hrow.addWidget(self.back_btn)
        self.title = QLabel("")
        self.title.setStyleSheet("font-size: 12pt; font-weight: 700;")
        hrow.addWidget(self.title, 1)
        lay.addLayout(hrow)

        # Scrollable conversation
        self.scroll = QScrollArea(); self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self._holder = QWidget()
        self._vbox = QVBoxLayout(self._holder)
        self._vbox.setContentsMargins(4, 4, 4, 4); self._vbox.setSpacing(4)
        self._vbox.addStretch(1)
        self.scroll.setWidget(self._holder)
        lay.addWidget(self.scroll, 1)

        # Input row
        irow = QHBoxLayout(); irow.setSpacing(6)
        self.input = QLineEdit()
        self.input.setPlaceholderText("Message…")
        self.input.returnPressed.connect(self._send)
        irow.addWidget(self.input, 1)
        send_btn = QPushButton("Send")
        send_btn.setProperty("accent", True)
        send_btn.clicked.connect(self._send)
        irow.addWidget(send_btn)
        lay.addLayout(irow)

        # Cheap polling refresh as a fallback in case realtime is flaky.
        self._timer = QTimer(self); self._timer.timeout.connect(self._load_history)

    # ============ API ============
    def open_with(self, other_id: str, other_name: str) -> None:
        if self._channel is not None:
            self._unsubscribe()
        self._other_id = other_id
        self._other_name = other_name
        self.title.setText(f"@{other_name}")
        self._clear_bubbles()
        self._load_history()
        self._subscribe()
        if not self._timer.isActive():
            self._timer.start(6000)

    def close_thread(self) -> None:
        self._unsubscribe()
        self._timer.stop()

    def send_invite(self, room_id: str) -> None:
        self._send_text(f"{JOIN_SCHEME}{room_id}")

    # ============ data ============
    def _load_history(self) -> None:
        uid = current_user_id()
        if not uid or not self._other_id:
            return
        try:
            r = (supabase().table("messages").select("*")
                 .or_(f"and(sender.eq.{uid},recipient.eq.{self._other_id}),"
                      f"and(sender.eq.{self._other_id},recipient.eq.{uid})")
                 .order("created_at", desc=False).limit(200).execute())
            rows = r.data or []
        except Exception:
            rows = []
        self._clear_bubbles()
        for row in rows:
            self._append_bubble(row.get("body") or "", row.get("sender") == uid)
        QTimer.singleShot(0, self._scroll_bottom)

    def _clear_bubbles(self) -> None:
        while self._vbox.count() > 1:
            it = self._vbox.takeAt(0)
            w = it.widget()
            if w: w.deleteLater()

    def _append_bubble(self, body: str, mine: bool) -> None:
        wrap = QWidget()
        wlay = QHBoxLayout(wrap); wlay.setContentsMargins(0, 0, 0, 0); wlay.setSpacing(0)
        if mine: wlay.addStretch(1)
        if body.startswith(JOIN_SCHEME):
            room_id = body[len(JOIN_SCHEME):].strip()
            c = current_theme()
            frame = QFrame()
            frame.setStyleSheet(
                f"QFrame {{ background: {c['panel']}; border: 1px solid {c['accent']}; "
                "border-radius: 12px; padding: 8px 12px; }}"
            )
            fl = QVBoxLayout(frame); fl.setContentsMargins(6, 4, 6, 4); fl.setSpacing(4)
            l = QLabel("🎬  Movie invite")
            l.setStyleSheet(f"color: {c['fg']}; background: transparent; border: none; font-weight: 700;")
            fl.addWidget(l)
            btn = QPushButton("Join watch room")
            btn.setProperty("accent", True)
            btn.clicked.connect(lambda: self.invite_accepted.emit(room_id))
            fl.addWidget(btn)
            wlay.addWidget(frame)
        else:
            wlay.addWidget(_Bubble(body, mine))
        if not mine: wlay.addStretch(1)
        self._vbox.insertWidget(self._vbox.count() - 1, wrap)

    def _scroll_bottom(self) -> None:
        sb = self.scroll.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _send(self) -> None:
        text = self.input.text().strip()
        if not text: return
        self.input.clear()
        self._send_text(text)

    def _send_text(self, body: str) -> None:
        uid = current_user_id()
        if not uid or not self._other_id:
            return
        try:
            supabase().table("messages").insert({
                "sender": uid, "recipient": self._other_id, "body": body
            }).execute()
        except Exception as ex:
            QMessageBox.warning(self, "Send failed", str(ex)); return
        self._load_history()

    # ============ realtime ============
    def _subscribe(self) -> None:
        uid = current_user_id()
        if not uid: return
        try:
            ch = supabase().channel(f"inlinechat:{uid}:{self._other_id}")
            cb = lambda *_a, **_kw: QTimer.singleShot(0, self._load_history)
            try:
                ch.on_postgres_changes(event="INSERT", schema="public", table="messages", callback=cb)
            except TypeError:
                ch.on_postgres_changes("INSERT", schema="public", table="messages", callback=cb)
            ch.subscribe()
            self._channel = ch
        except Exception:
            self._channel = None

    def _unsubscribe(self) -> None:
        try:
            if self._channel is not None:
                supabase().remove_channel(self._channel)
        except Exception:
            pass
        self._channel = None
