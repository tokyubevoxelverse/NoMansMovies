"""Edit dialog for the current user's profile."""
from __future__ import annotations
import os
import time
from PySide6.QtCore import Qt, Signal, QThread, QObject
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QLineEdit, QTextEdit,
    QPushButton, QComboBox, QColorDialog, QFileDialog, QMessageBox, QFrame, QWidget
)

from ..supabase_client import supabase, current_user_id
from ..config import PRESET_THEMES, DEFAULT_COLORS, COLOR_KEYS, COLOR_LABELS
from ..theme import apply_theme
from ..widgets.animated_avatar import AnimatedAvatar
from ..discord_oauth import link_discord, DiscordLinkResult, DiscordOAuthError


class _DiscordLinkWorker(QObject):
    done = Signal(object)   # DiscordLinkResult or Exception

    def run(self) -> None:
        try:
            self.done.emit(link_discord())
        except Exception as ex:
            self.done.emit(ex)


class _SwatchButton(QPushButton):
    def __init__(self, label: str, key: str, parent=None):
        super().__init__(parent)
        self._label = label
        self._key = key
        self.setMinimumHeight(34)
        self.setCursor(Qt.PointingHandCursor)

    def set_color(self, hex_: str) -> None:
        c = QColor(hex_)
        # high-contrast text color for swatch (white over dark, black over light)
        lum = (0.299*c.red() + 0.587*c.green() + 0.114*c.blue())
        text = "#000000" if lum > 160 else "#ffffff"
        self.setStyleSheet(
            f"QPushButton {{ background: {hex_}; color: {text}; border: 1px solid rgba(0,0,0,0.2); "
            f"border-radius: 6px; padding: 6px 10px; font-weight: 600; }}"
        )
        self.setText(f"{self._label}\n{hex_}")


class ProfileEditDialog(QDialog):
    saved = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit profile")
        self.setMinimumSize(560, 680)
        self._colors = dict(DEFAULT_COLORS)
        self._avatar_url: str | None = None

        lay = QVBoxLayout(self); lay.setSpacing(12); lay.setContentsMargins(24, 24, 24, 24)

        title = QLabel("Edit profile"); title.setStyleSheet("font-size: 18pt; font-weight: 700;")
        lay.addWidget(title)

        row = QHBoxLayout()
        self.avatar = AnimatedAvatar(size=120)
        row.addWidget(self.avatar)
        col = QVBoxLayout()
        self.upload_btn = QPushButton("Upload avatar (GIF / PNG / JPG)")
        self.upload_btn.clicked.connect(self._upload_avatar)
        col.addWidget(self.upload_btn)
        hint = QLabel("Max 5 MB. Animated GIFs supported.")
        hint.setProperty("muted", True)
        col.addWidget(hint)
        col.addStretch(1)
        row.addLayout(col, 1)
        lay.addLayout(row)

        lay.addWidget(QLabel("Username"))
        self.username = QLineEdit()
        lay.addWidget(self.username)

        lay.addWidget(QLabel("Bio"))
        self.bio = QTextEdit(); self.bio.setFixedHeight(70)
        lay.addWidget(self.bio)

        # Discord link row
        drow = QHBoxLayout(); drow.setSpacing(8)
        self.discord_status = QLabel("Discord: not linked")
        self.discord_status.setProperty("muted", True)
        drow.addWidget(self.discord_status, 1)
        self.discord_btn = QPushButton("Link Discord")
        self.discord_btn.clicked.connect(self._start_discord_link)
        drow.addWidget(self.discord_btn)
        lay.addLayout(drow)
        self._discord_thread = None
        self._discord_worker = None

        lay.addWidget(QLabel("Color scheme"))
        self.preset = QComboBox()
        self.preset.addItems(list(PRESET_THEMES.keys()) + ["Custom"])
        self.preset.currentTextChanged.connect(self._preset_changed)
        lay.addWidget(self.preset)

        # Grid of swatch buttons — 3 cols × 2 rows for the 6 color keys
        grid = QGridLayout(); grid.setSpacing(8)
        self._swatches: dict[str, _SwatchButton] = {}
        for i, key in enumerate(COLOR_KEYS):
            btn = _SwatchButton(COLOR_LABELS[key], key)
            btn.clicked.connect(lambda _, k=key: self._pick(k))
            self._swatches[key] = btn
            grid.addWidget(btn, i // 3, i % 3)
        lay.addLayout(grid)

        # Live preview block
        self.preview = QFrame(); self.preview.setObjectName("colorPreview")
        self.preview.setFixedHeight(56)
        pv = QHBoxLayout(self.preview); pv.setContentsMargins(12, 8, 12, 8)
        self.preview_text = QLabel("Aa  text on the panel  ✓")
        pv.addWidget(self.preview_text, 1)
        self.preview_btn = QPushButton("Accent button")
        self.preview_btn.setProperty("accent", True)
        pv.addWidget(self.preview_btn)
        lay.addWidget(self.preview)

        lay.addStretch(1)

        btns = QHBoxLayout()
        cancel = QPushButton("Cancel"); cancel.clicked.connect(self.reject)
        save = QPushButton("Save"); save.setProperty("accent", True); save.clicked.connect(self._save)
        btns.addStretch(1); btns.addWidget(cancel); btns.addWidget(save)
        lay.addLayout(btns)

        self._load()
        self._refresh_swatches()
        self._refresh_preview()

    def _load(self) -> None:
        uid = current_user_id()
        if not uid:
            return
        try:
            r = supabase().table("profiles").select("*").eq("id", uid).single().execute()
            data = r.data or {}
        except Exception:
            data = {}
        self.username.setText(data.get("username") or "")
        self.bio.setPlainText(data.get("bio") or "")
        cs = data.get("color_scheme") or DEFAULT_COLORS
        self._colors = {**DEFAULT_COLORS, **(cs if isinstance(cs, dict) else {})}
        self._avatar_url = data.get("avatar_url")
        if self._avatar_url:
            self.avatar.set_url(self._avatar_url)
        if data.get("discord_id"):
            uname = data.get("discord_username") or "linked"
            self.discord_status.setText(f"Discord: @{uname} ✓")
            self.discord_btn.setText("Re-sync Discord")

    def _preset_changed(self, name: str) -> None:
        if name in PRESET_THEMES:
            self._colors = dict(PRESET_THEMES[name])
            self._refresh_swatches()
            self._refresh_preview()

    def _pick(self, key: str) -> None:
        col = QColorDialog.getColor(QColor(self._colors[key]), self, f"Pick {COLOR_LABELS[key]}")
        if col.isValid():
            self._colors[key] = col.name()
            self.preset.blockSignals(True)
            self.preset.setCurrentText("Custom")
            self.preset.blockSignals(False)
            self._refresh_swatches()
            self._refresh_preview()

    def _refresh_swatches(self) -> None:
        for key, btn in self._swatches.items():
            btn.set_color(self._colors[key])

    def _refresh_preview(self) -> None:
        c = self._colors
        self.preview.setStyleSheet(
            f"QFrame#colorPreview {{ background: {c['panel']}; border: 1px solid {c['border']}; border-radius: 6px; }}"
        )
        self.preview_text.setStyleSheet(f"color: {c['fg']}; background: transparent;")

    def _upload_avatar(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Choose avatar", "", "Images (*.gif *.png *.jpg *.jpeg *.webp)")
        if not path:
            return
        if os.path.getsize(path) > 5 * 1024 * 1024:
            QMessageBox.warning(self, "Too large", "Max 5 MB."); return
        uid = current_user_id()
        if not uid:
            return
        ext = os.path.splitext(path)[1].lower().lstrip(".") or "png"
        key = f"{uid}/{int(time.time())}.{ext}"
        try:
            with open(path, "rb") as f:
                supabase().storage.from_("avatars").upload(
                    path=key,
                    file=f.read(),
                    file_options={"content-type": f"image/{ext}", "upsert": "true"},
                )
            url = supabase().storage.from_("avatars").get_public_url(key)
        except Exception as ex:
            QMessageBox.critical(self, "Upload failed", str(ex)); return
        self._avatar_url = url
        self.avatar.set_url(url)

    def _save(self) -> None:
        uid = current_user_id()
        if not uid:
            return
        payload = {
            "username": self.username.text().strip(),
            "bio": self.bio.toPlainText().strip(),
            "color_scheme": self._colors,
        }
        if self._avatar_url:
            payload["avatar_url"] = self._avatar_url
        try:
            supabase().table("profiles").update(payload).eq("id", uid).execute()
        except Exception as ex:
            QMessageBox.critical(self, "Save failed", str(ex)); return
        apply_theme(self._colors)
        self.saved.emit()
        self.accept()

    # ============ Discord link ============
    def _start_discord_link(self) -> None:
        self.discord_btn.setEnabled(False)
        self.discord_status.setText("Discord: opening browser…")
        self._discord_thread = QThread(self)
        self._discord_worker = _DiscordLinkWorker()
        self._discord_worker.moveToThread(self._discord_thread)
        self._discord_thread.started.connect(self._discord_worker.run)
        self._discord_worker.done.connect(self._on_discord_done)
        self._discord_worker.done.connect(self._discord_thread.quit)
        self._discord_worker.done.connect(self._discord_worker.deleteLater)
        self._discord_thread.finished.connect(self._discord_thread.deleteLater)
        self._discord_thread.start()

    def _on_discord_done(self, result) -> None:
        self.discord_btn.setEnabled(True)
        if isinstance(result, Exception):
            self.discord_status.setText("Discord: link failed")
            QMessageBox.warning(self, "Discord link failed", str(result))
            return
        assert isinstance(result, DiscordLinkResult)
        uid = current_user_id()
        if not uid:
            return

        # 1. Save Discord identity to my profile.
        try:
            supabase().table("profiles").update({
                "discord_id":       result.identity.id,
                "discord_username": result.identity.global_name or result.identity.username,
                "discord_avatar":   result.identity.avatar_url,
            }).eq("id", uid).execute()
        except Exception as ex:
            QMessageBox.critical(self, "Save failed", f"Linked but could not save: {ex}"); return

        self.discord_status.setText(f"Discord: @{result.identity.username} ✓")
        self.discord_btn.setText("Re-sync Discord")

        # 2. Auto-friend any NoMansMovies users whose discord_id is among my Discord friends.
        added = 0
        if result.friend_ids:
            try:
                r = (supabase().table("profiles").select("id, discord_id")
                     .in_("discord_id", result.friend_ids).execute())
                rows = r.data or []
            except Exception:
                rows = []
            for row in rows:
                other = row.get("id")
                if not other or other == uid:
                    continue
                try:
                    supabase().table("friendships").insert({
                        "requester": uid, "addressee": other, "status": "accepted",
                    }).execute()
                    added += 1
                except Exception:
                    # already exists or RLS rejected — skip
                    pass

        if result.relationships_denied:
            QMessageBox.information(self, "Discord linked",
                "Discord linked.\n\nDiscord didn't grant the relationships scope, so your friend "
                "list wasn't pulled. You can still discover Discord-linked users from the Friends panel.")
        else:
            QMessageBox.information(self, "Discord linked",
                f"Discord linked.\nAuto-friended {added} mutual Discord user(s) on NoMansMovies.")
