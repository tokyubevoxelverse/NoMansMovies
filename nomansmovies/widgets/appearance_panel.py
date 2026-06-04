"""Combined Profile + Appearance editor — side by side inside a FloatingPanel.

Left:   Profile  — avatar, username, bio, Discord link, Logout.
Right:  Appearance — colors, fonts (family/size/bold/letter-spacing), video
                     border (on/off/color/width/rounded), default layout.
"""
from __future__ import annotations
import os
import time
from PySide6.QtCore import Qt, Signal, QObject, QThread
from PySide6.QtGui import QColor, QFont, QFontDatabase
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton,
    QComboBox, QColorDialog, QSpinBox, QFrame, QMessageBox, QFileDialog,
    QLineEdit, QTextEdit, QCheckBox, QSplitter, QScrollArea, QSizePolicy,
)

from ..config import (
    PRESET_THEMES, DEFAULT_COLORS, COLOR_KEYS, COLOR_LABELS,
    DEFAULT_FONT_FAMILY, DEFAULT_FONT_SIZE, FONT_SIZE_RANGE,
    DEFAULT_FONT_WEIGHT, DEFAULT_LETTER_SPACING_PX, LETTER_SPACING_RANGE,
    DEFAULT_VIDEO_BORDER, DEFAULT_VIDEO_BORDER_COLOR, DEFAULT_VIDEO_BORDER_WIDTH,
    DEFAULT_VIDEO_BORDER_WIDTH_RANGE, DEFAULT_VIDEO_ROUNDED,
    DEFAULT_VIDEO_CORNER_RADIUS, DEFAULT_VIDEO_CORNER_RADIUS_RANGE,
    LAYOUTS, LAYOUT_LABELS, LAYOUT_DEFAULT,
)
from ..supabase_client import supabase, current_user_id, clear_session
from ..theme import apply_theme
from .animated_avatar import AnimatedAvatar
from ..discord_oauth import link_discord, DiscordLinkResult


# ============ SUPABASE WORKERS ============
class _SaveAppearanceWorker(QObject):
    done = Signal(object)
    def __init__(self, payload: dict, uid: str):
        super().__init__(); self._payload = payload; self._uid = uid
    def run(self) -> None:
        try:
            supabase().table("profiles").update(
                {"color_scheme": self._payload}).eq("id", self._uid).execute()
            self.done.emit(None)
        except Exception as ex: self.done.emit(ex)


class _SaveProfileWorker(QObject):
    done = Signal(object)
    def __init__(self, payload: dict, uid: str):
        super().__init__(); self._payload = payload; self._uid = uid
    def run(self) -> None:
        try:
            supabase().table("profiles").update(self._payload).eq("id", self._uid).execute()
            self.done.emit(None)
        except Exception as ex: self.done.emit(ex)


class _DiscordLinkWorker(QObject):
    done = Signal(object)
    def run(self) -> None:
        try: self.done.emit(link_discord())
        except Exception as ex: self.done.emit(ex)


# ============ helpers ============
class _Swatch(QPushButton):
    def __init__(self, label: str, parent=None):
        super().__init__(parent)
        self._label = label
        self.setMinimumHeight(32)
        self.setCursor(Qt.PointingHandCursor)
    def set_color(self, hex_: str) -> None:
        c = QColor(hex_)
        lum = (0.299 * c.red() + 0.587 * c.green() + 0.114 * c.blue())
        text = "#000000" if lum > 160 else "#ffffff"
        self.setStyleSheet(
            f"QPushButton {{ background: {hex_}; color: {text}; "
            "border: 1px solid rgba(0,0,0,0.25); border-radius: 6px; "
            "padding: 6px 8px; font-weight: 600; }}"
        )
        self.setText(f"{self._label}  {hex_}")


def _wrap_scroll(w: QWidget) -> QScrollArea:
    sa = QScrollArea()
    sa.setWidgetResizable(True)
    sa.setWidget(w)
    sa.setFrameShape(QFrame.NoFrame)
    return sa


# ============ Profile section ============
class _ProfileSection(QWidget):
    saved = Signal()
    logout_requested = Signal()
    border_settings_changed = Signal()   # bubble up to whole panel

    def __init__(self, parent=None):
        super().__init__(parent)
        self._avatar_url: str | None = None
        self._discord_id: str | None = None
        self._discord_username: str | None = None
        self._email: str = ""

        lay = QVBoxLayout(self); lay.setContentsMargins(14, 14, 14, 14); lay.setSpacing(10)

        title = QLabel("Profile"); title.setStyleSheet("font-size: 16pt; font-weight: 700;")
        lay.addWidget(title)

        # Avatar + email
        row = QHBoxLayout(); row.setSpacing(12)
        self.avatar = AnimatedAvatar(size=96)
        row.addWidget(self.avatar, 0, Qt.AlignTop)
        col = QVBoxLayout(); col.setSpacing(4)
        self.upload_btn = QPushButton("Upload avatar")
        self.upload_btn.clicked.connect(self._upload_avatar)
        col.addWidget(self.upload_btn)
        self.email_lbl = QLabel(""); self.email_lbl.setProperty("muted", True)
        col.addWidget(self.email_lbl)
        col.addStretch(1)
        row.addLayout(col, 1)
        lay.addLayout(row)

        # Username
        lay.addWidget(QLabel("Username"))
        self.username = QLineEdit()
        lay.addWidget(self.username)

        # Bio
        lay.addWidget(QLabel("Bio"))
        self.bio = QTextEdit(); self.bio.setFixedHeight(70)
        lay.addWidget(self.bio)

        # Discord
        lay.addWidget(QLabel("Discord"))
        drow = QHBoxLayout(); drow.setSpacing(6)
        self.discord_status = QLabel("Not linked"); self.discord_status.setProperty("muted", True)
        drow.addWidget(self.discord_status, 1)
        self.discord_btn = QPushButton("Link Discord")
        self.discord_btn.clicked.connect(self._link_discord)
        drow.addWidget(self.discord_btn)
        lay.addLayout(drow)

        lay.addStretch(1)

        # Save + Logout
        brow = QHBoxLayout(); brow.setSpacing(6)
        self.logout_btn = QPushButton("Logout")
        self.logout_btn.setToolTip("Sign out of your Supabase account and return to the login screen")
        self.logout_btn.clicked.connect(self.logout_requested.emit)
        brow.addWidget(self.logout_btn)
        brow.addStretch(1)
        self.save_btn = QPushButton("Save profile")
        self.save_btn.setProperty("accent", True)
        self.save_btn.clicked.connect(self._save)
        brow.addWidget(self.save_btn)
        lay.addLayout(brow)

        self._load()

    # ---- data ----
    def _load(self) -> None:
        uid = current_user_id()
        if not uid:
            return
        # Email is in auth.user, not profiles
        try:
            u = supabase().auth.get_user()
            if u and u.user:
                self._email = u.user.email or ""
                self.email_lbl.setText(self._email)
        except Exception:
            pass
        try:
            r = supabase().table("profiles").select("*").eq("id", uid).single().execute()
            data = r.data or {}
        except Exception:
            data = {}
        self.username.setText(data.get("username") or "")
        self.bio.setPlainText(data.get("bio") or "")
        self._avatar_url = data.get("avatar_url")
        if self._avatar_url:
            self.avatar.set_url(self._avatar_url)
        self._discord_id = data.get("discord_id")
        self._discord_username = data.get("discord_username")
        if self._discord_id:
            self.discord_status.setText(f"@{self._discord_username or self._discord_id} ✓")
            self.discord_btn.setText("Re-link Discord")

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
                    path=key, file=f.read(),
                    file_options={"content-type": f"image/{ext}", "upsert": "true"})
            url = supabase().storage.from_("avatars").get_public_url(key)
        except Exception as ex:
            QMessageBox.critical(self, "Upload failed", str(ex)); return
        self._avatar_url = url
        self.avatar.set_url(url)

    def _link_discord(self) -> None:
        self.discord_btn.setEnabled(False)
        self.discord_status.setText("Opening browser…")
        self._dthread = QThread(self)
        self._dworker = _DiscordLinkWorker()
        self._dworker.moveToThread(self._dthread)
        self._dthread.started.connect(self._dworker.run)
        self._dworker.done.connect(self._on_discord_done)
        self._dworker.done.connect(self._dthread.quit)
        self._dworker.done.connect(self._dworker.deleteLater)
        self._dthread.finished.connect(self._dthread.deleteLater)
        self._dthread.start()

    def _on_discord_done(self, result) -> None:
        self.discord_btn.setEnabled(True)
        if isinstance(result, Exception):
            self.discord_status.setText("Link failed")
            QMessageBox.warning(self, "Discord link failed", str(result)); return
        assert isinstance(result, DiscordLinkResult)
        uid = current_user_id()
        if not uid: return
        try:
            supabase().table("profiles").update({
                "discord_id":       result.identity.id,
                "discord_username": result.identity.global_name or result.identity.username,
                "discord_avatar":   result.identity.avatar_url,
            }).eq("id", uid).execute()
        except Exception as ex:
            QMessageBox.critical(self, "Save failed", f"Linked but couldn't save: {ex}"); return
        self._discord_id = result.identity.id
        self._discord_username = result.identity.username
        self.discord_status.setText(f"@{result.identity.username} ✓")
        self.discord_btn.setText("Re-link Discord")

        # Auto-friend any NoMansMovies user whose discord_id is a Discord friend of
        # ours. Only works if Discord granted the `relationships.read` scope.
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
                    # already friends or RLS rejected — skip silently
                    pass

        if result.relationships_denied:
            QMessageBox.information(
                self, "Discord linked",
                "Discord linked.\n\nDiscord did not grant the friends-list scope, so we "
                "couldn't auto-add your Discord friends. Use the Friends panel's "
                "“Discord” tab to find other linked users.")
        elif added:
            QMessageBox.information(
                self, "Discord linked",
                f"Discord linked.\nAuto-added {added} mutual Discord friend(s) on NoMansMovies.")
        else:
            QMessageBox.information(self, "Discord linked",
                "Discord linked. None of your Discord friends have a NoMansMovies account yet.")

    def _save(self) -> None:
        uid = current_user_id()
        if not uid:
            QMessageBox.warning(self, "Not signed in", "Sign in first."); return
        payload = {
            "username": self.username.text().strip(),
            "bio":      self.bio.toPlainText().strip(),
        }
        if self._avatar_url:
            payload["avatar_url"] = self._avatar_url
        self.save_btn.setEnabled(False); self.save_btn.setText("Saving…")
        self._sthread = QThread(self)
        self._sworker = _SaveProfileWorker(payload, uid)
        self._sworker.moveToThread(self._sthread)
        self._sthread.started.connect(self._sworker.run)
        self._sworker.done.connect(self._on_save_done)
        self._sworker.done.connect(self._sthread.quit)
        self._sworker.done.connect(self._sworker.deleteLater)
        self._sthread.finished.connect(self._sthread.deleteLater)
        self._sthread.start()

    def _on_save_done(self, error) -> None:
        self.save_btn.setEnabled(True); self.save_btn.setText("Save profile")
        if error is None:
            self.saved.emit()
        else:
            QMessageBox.warning(self, "Save failed", str(error))


# ============ Appearance section ============
class _AppearanceSection(QWidget):
    saved = Signal()
    border_changed = Signal(dict)   # {enabled, color, width, rounded, radius}

    def __init__(self, parent=None):
        super().__init__(parent)
        self._colors: dict = dict(DEFAULT_COLORS)
        self._font_family = DEFAULT_FONT_FAMILY
        self._font_size = DEFAULT_FONT_SIZE
        self._font_weight = DEFAULT_FONT_WEIGHT
        self._letter_spacing = DEFAULT_LETTER_SPACING_PX
        self._video_border = DEFAULT_VIDEO_BORDER
        self._video_border_color = DEFAULT_VIDEO_BORDER_COLOR
        self._video_border_width = DEFAULT_VIDEO_BORDER_WIDTH
        self._video_rounded = DEFAULT_VIDEO_ROUNDED
        self._video_corner_radius = DEFAULT_VIDEO_CORNER_RADIUS
        self._default_layout = LAYOUT_DEFAULT

        lay = QVBoxLayout(self); lay.setContentsMargins(14, 14, 14, 14); lay.setSpacing(10)

        title = QLabel("Appearance"); title.setStyleSheet("font-size: 16pt; font-weight: 700;")
        lay.addWidget(title)

        # Theme preset
        lay.addWidget(QLabel("Color preset"))
        self.preset = QComboBox()
        self.preset.addItems(list(PRESET_THEMES.keys()) + ["Custom"])
        self.preset.currentTextChanged.connect(self._preset_changed)
        lay.addWidget(self.preset)

        # Swatches
        grid = QGridLayout(); grid.setSpacing(6)
        self._swatches: dict[str, _Swatch] = {}
        for i, key in enumerate(COLOR_KEYS):
            sw = _Swatch(COLOR_LABELS[key])
            sw.clicked.connect(lambda _, k=key: self._pick(k))
            self._swatches[key] = sw
            grid.addWidget(sw, i // 3, i % 3)
        lay.addLayout(grid)

        # Font row
        lay.addWidget(QLabel("Text font"))
        frow = QHBoxLayout(); frow.setSpacing(6)
        self.font_combo = QComboBox(); self.font_combo.setEditable(True)
        self.font_combo.addItems(QFontDatabase.families())
        self.font_combo.currentTextChanged.connect(self._font_text_changed)
        frow.addWidget(self.font_combo, 1)
        self.size_spin = QSpinBox()
        self.size_spin.setRange(*FONT_SIZE_RANGE); self.size_spin.setSuffix(" pt")
        self.size_spin.valueChanged.connect(self._size_changed)
        frow.addWidget(self.size_spin)
        lay.addLayout(frow)

        # Bold + letter spacing row
        srow = QHBoxLayout(); srow.setSpacing(10)
        self.bold_chk = QCheckBox("Bold text")
        self.bold_chk.toggled.connect(self._bold_changed)
        srow.addWidget(self.bold_chk)
        srow.addWidget(QLabel("Letter spacing"))
        self.spacing_spin = QSpinBox()
        self.spacing_spin.setRange(*LETTER_SPACING_RANGE); self.spacing_spin.setSuffix(" px")
        self.spacing_spin.valueChanged.connect(self._spacing_changed)
        srow.addWidget(self.spacing_spin)
        srow.addStretch(1)
        lay.addLayout(srow)

        # ---- Video border ----
        bgrp = QFrame(); bgrp.setObjectName("apGroup")
        bgrp.setStyleSheet("QFrame#apGroup { border: 1px solid rgba(255,255,255,0.10); border-radius: 8px; padding: 8px; }")
        bg_lay = QVBoxLayout(bgrp); bg_lay.setSpacing(6)
        bg_lay.addWidget(QLabel("Video player border"))

        brow1 = QHBoxLayout(); brow1.setSpacing(6)
        self.border_chk = QCheckBox("Show border")
        self.border_chk.toggled.connect(self._border_toggle_changed)
        brow1.addWidget(self.border_chk)
        self.rounded_chk = QCheckBox("Rounded corners")
        self.rounded_chk.toggled.connect(self._rounded_changed)
        brow1.addWidget(self.rounded_chk)
        brow1.addStretch(1)
        bg_lay.addLayout(brow1)

        brow2 = QHBoxLayout(); brow2.setSpacing(6)
        self.border_swatch = _Swatch("Border color")
        self.border_swatch.clicked.connect(self._pick_border_color)
        brow2.addWidget(self.border_swatch, 1)
        brow2.addWidget(QLabel("Width"))
        self.width_spin = QSpinBox()
        self.width_spin.setRange(*DEFAULT_VIDEO_BORDER_WIDTH_RANGE); self.width_spin.setSuffix(" px")
        self.width_spin.valueChanged.connect(self._width_changed)
        brow2.addWidget(self.width_spin)
        brow2.addWidget(QLabel("Radius"))
        self.radius_spin = QSpinBox()
        self.radius_spin.setRange(*DEFAULT_VIDEO_CORNER_RADIUS_RANGE); self.radius_spin.setSuffix(" px")
        self.radius_spin.valueChanged.connect(self._radius_changed)
        brow2.addWidget(self.radius_spin)
        bg_lay.addLayout(brow2)
        lay.addWidget(bgrp)

        # Default layout
        lay.addWidget(QLabel("Default layout when overlay opens"))
        self.layout_combo = QComboBox()
        for k in LAYOUTS:
            self.layout_combo.addItem(LAYOUT_LABELS[k], userData=k)
        self.layout_combo.currentIndexChanged.connect(self._layout_combo_changed)
        lay.addWidget(self.layout_combo)

        # Preview
        self.preview = QFrame(); self.preview.setObjectName("apPreview")
        self.preview.setFixedHeight(56)
        pv = QHBoxLayout(self.preview); pv.setContentsMargins(12, 8, 12, 8)
        self.preview_text = QLabel("Aa  Sample text  ✓")
        pv.addWidget(self.preview_text, 1)
        lay.addWidget(self.preview)

        lay.addStretch(1)

        # Buttons
        brow = QHBoxLayout()
        self.preview_btn = QPushButton("Preview (no save)")
        self.preview_btn.clicked.connect(self._apply_preview_theme)
        brow.addWidget(self.preview_btn)
        brow.addStretch(1)
        self.save_btn = QPushButton("Save appearance")
        self.save_btn.setProperty("accent", True)
        self.save_btn.clicked.connect(self._save)
        brow.addWidget(self.save_btn)
        lay.addLayout(brow)

        self._load()
        self._refresh_swatches()
        self._refresh_border_swatch()
        self._refresh_preview()

    # ---- data ----
    def _load(self) -> None:
        uid = current_user_id()
        if not uid:
            return
        try:
            r = supabase().table("profiles").select("color_scheme").eq("id", uid).single().execute()
            data = (r.data or {}).get("color_scheme") or {}
        except Exception:
            data = {}
        self._colors = {**DEFAULT_COLORS, **{k: v for k, v in data.items() if k in COLOR_KEYS}}
        self._font_family = str(data.get("font_family") or DEFAULT_FONT_FAMILY)
        try: self._font_size = int(data.get("font_size") or DEFAULT_FONT_SIZE)
        except (TypeError, ValueError): self._font_size = DEFAULT_FONT_SIZE
        self._font_weight = str(data.get("font_weight") or DEFAULT_FONT_WEIGHT)
        try: self._letter_spacing = int(data.get("letter_spacing") or DEFAULT_LETTER_SPACING_PX)
        except (TypeError, ValueError): self._letter_spacing = DEFAULT_LETTER_SPACING_PX
        self._video_border = bool(data.get("video_border", DEFAULT_VIDEO_BORDER))
        self._video_border_color = str(data.get("video_border_color") or DEFAULT_VIDEO_BORDER_COLOR)
        try: self._video_border_width = int(data.get("video_border_width") or DEFAULT_VIDEO_BORDER_WIDTH)
        except (TypeError, ValueError): self._video_border_width = DEFAULT_VIDEO_BORDER_WIDTH
        self._video_rounded = bool(data.get("video_rounded", DEFAULT_VIDEO_ROUNDED))
        try: self._video_corner_radius = int(data.get("video_corner_radius") or DEFAULT_VIDEO_CORNER_RADIUS)
        except (TypeError, ValueError): self._video_corner_radius = DEFAULT_VIDEO_CORNER_RADIUS
        self._default_layout = str(data.get("default_layout") or LAYOUT_DEFAULT)
        if self._default_layout not in LAYOUTS:
            self._default_layout = LAYOUT_DEFAULT

        # widgets
        self.font_combo.blockSignals(True); self.font_combo.setCurrentText(self._font_family); self.font_combo.blockSignals(False)
        self.size_spin.blockSignals(True); self.size_spin.setValue(self._font_size); self.size_spin.blockSignals(False)
        self.bold_chk.blockSignals(True); self.bold_chk.setChecked(self._font_weight == "bold"); self.bold_chk.blockSignals(False)
        self.spacing_spin.blockSignals(True); self.spacing_spin.setValue(self._letter_spacing); self.spacing_spin.blockSignals(False)
        self.border_chk.blockSignals(True); self.border_chk.setChecked(self._video_border); self.border_chk.blockSignals(False)
        self.rounded_chk.blockSignals(True); self.rounded_chk.setChecked(self._video_rounded); self.rounded_chk.blockSignals(False)
        self.width_spin.blockSignals(True); self.width_spin.setValue(self._video_border_width); self.width_spin.blockSignals(False)
        self.radius_spin.blockSignals(True); self.radius_spin.setValue(self._video_corner_radius); self.radius_spin.blockSignals(False)
        idx = LAYOUTS.index(self._default_layout)
        self.layout_combo.blockSignals(True); self.layout_combo.setCurrentIndex(idx); self.layout_combo.blockSignals(False)

    # ---- event handlers ----
    def _preset_changed(self, name: str) -> None:
        if name in PRESET_THEMES:
            self._colors = dict(PRESET_THEMES[name])
            self._refresh_swatches(); self._refresh_preview()

    def _pick(self, key: str) -> None:
        col = QColorDialog.getColor(QColor(self._colors[key]), self, f"Pick {COLOR_LABELS[key]}")
        if col.isValid():
            self._colors[key] = col.name()
            self.preset.blockSignals(True); self.preset.setCurrentText("Custom"); self.preset.blockSignals(False)
            self._refresh_swatches(); self._refresh_preview()

    def _font_text_changed(self, name: str) -> None:
        self._font_family = name.strip() or DEFAULT_FONT_FAMILY; self._refresh_preview()

    def _size_changed(self, n: int) -> None:
        self._font_size = int(n); self._refresh_preview()

    def _bold_changed(self, on: bool) -> None:
        self._font_weight = "bold" if on else "normal"; self._refresh_preview()

    def _spacing_changed(self, n: int) -> None:
        self._letter_spacing = int(n); self._refresh_preview()

    def _border_toggle_changed(self, on: bool) -> None:
        self._video_border = bool(on); self._emit_border()

    def _rounded_changed(self, on: bool) -> None:
        self._video_rounded = bool(on); self._emit_border()

    def _width_changed(self, n: int) -> None:
        self._video_border_width = int(n); self._emit_border()

    def _radius_changed(self, n: int) -> None:
        self._video_corner_radius = int(n); self._emit_border()

    def _pick_border_color(self) -> None:
        col = QColorDialog.getColor(QColor(self._video_border_color), self, "Pick border color")
        if col.isValid():
            self._video_border_color = col.name()
            self._refresh_border_swatch()
            self._emit_border()

    def _emit_border(self) -> None:
        self.border_changed.emit({
            "enabled": self._video_border,
            "color":   self._video_border_color,
            "width":   self._video_border_width,
            "rounded": self._video_rounded,
            "radius":  self._video_corner_radius,
        })

    def _layout_combo_changed(self, idx: int) -> None:
        key = self.layout_combo.itemData(idx)
        if isinstance(key, str) and key in LAYOUTS:
            self._default_layout = key

    def _refresh_swatches(self) -> None:
        for key, sw in self._swatches.items():
            sw.set_color(self._colors[key])

    def _refresh_border_swatch(self) -> None:
        self.border_swatch.set_color(self._video_border_color)

    def _refresh_preview(self) -> None:
        c = self._colors
        self.preview.setStyleSheet(
            f"QFrame#apPreview {{ background: {c['panel']}; border: 1px solid {c['border']}; border-radius: 6px; }}"
        )
        weight = "700" if self._font_weight == "bold" else "600"
        self.preview_text.setStyleSheet(
            f"color: {c['fg']}; background: transparent; "
            f"font-family: '{self._font_family}'; font-size: {self._font_size}pt; "
            f"font-weight: {weight}; letter-spacing: {self._letter_spacing}px;"
        )

    def _build_payload(self) -> dict:
        return {
            **self._colors,
            "font_family":         self._font_family,
            "font_size":           self._font_size,
            "font_weight":         self._font_weight,
            "letter_spacing":      self._letter_spacing,
            "video_border":        self._video_border,
            "video_border_color":  self._video_border_color,
            "video_border_width":  self._video_border_width,
            "video_rounded":       self._video_rounded,
            "video_corner_radius": self._video_corner_radius,
            "default_layout":      self._default_layout,
        }

    def _apply_preview_theme(self) -> None:
        apply_theme(self._build_payload())
        self._emit_border()

    def _save(self) -> None:
        uid = current_user_id()
        if not uid:
            QMessageBox.warning(self, "Not signed in", "Sign in first."); return
        payload = self._build_payload()
        apply_theme(payload)
        self._emit_border()
        self.save_btn.setEnabled(False); self.save_btn.setText("Saving…")
        self._sthread = QThread(self)
        self._sworker = _SaveAppearanceWorker(payload, uid)
        self._sworker.moveToThread(self._sthread)
        self._sthread.started.connect(self._sworker.run)
        self._sworker.done.connect(self._on_save_done)
        self._sworker.done.connect(self._sthread.quit)
        self._sworker.done.connect(self._sworker.deleteLater)
        self._sthread.finished.connect(self._sthread.deleteLater)
        self._sthread.start()

    def _on_save_done(self, error) -> None:
        self.save_btn.setEnabled(True); self.save_btn.setText("Save appearance")
        if error is None:
            self.saved.emit()
        else:
            QMessageBox.warning(self, "Save failed",
                f"Theme applied locally; Supabase save failed:\n{error}")


# ============ Combined panel (this is what the FloatingPanel hosts) ============
class AppearancePanel(QWidget):
    saved = Signal()
    logout_requested = Signal()
    border_changed = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        outer = QHBoxLayout(self); outer.setContentsMargins(0, 0, 0, 0)

        self.profile = _ProfileSection()
        self.appearance = _AppearanceSection()
        self.profile.logout_requested.connect(self.logout_requested.emit)
        self.profile.saved.connect(self.saved.emit)
        self.appearance.saved.connect(self.saved.emit)
        self.appearance.border_changed.connect(self.border_changed.emit)

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(_wrap_scroll(self.profile))
        splitter.addWidget(_wrap_scroll(self.appearance))
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([380, 520])
        outer.addWidget(splitter)
