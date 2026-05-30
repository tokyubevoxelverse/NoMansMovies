"""Static configuration for NoMansMovies."""
from __future__ import annotations
import os
import sys
from pathlib import Path

# ====== Supabase ======
# REPLACE with your Supabase project URL (e.g. https://abcd1234.supabase.co).
# Find it under Project Settings -> API in the Supabase dashboard.
SUPABASE_URL = "https://uhhyurupeapjpjseoffl.supabase.co"
SUPABASE_PUBLISHABLE_KEY = "sb_publishable_ghWEVDYjfexgOokhwXebLA_BH6iHkUW"

# ====== Paths ======
def _app_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent

APP_ROOT: Path = _app_root()
YTDLP_DIR: Path = APP_ROOT / "ytdlp"
YTDLP_EXE: Path = YTDLP_DIR / "yt-dlp.exe"
YTDLP_DIR.mkdir(parents=True, exist_ok=True)

ASSETS_DIR: Path = APP_ROOT / "assets"

# ====== App ======
APP_NAME = "NoMansMovies"
ORG_NAME = "NoMansMovies"

# Default color scheme — applied app-wide via theme.apply_theme().
# Keys:
#   bg      = main window background
#   fg      = primary text color (used EVERYWHERE text appears)
#   accent  = primary action color (buttons, sliders, selection)
#   border  = panel & input borders
#   panel   = card / panel / input background (sits on top of bg)
#   muted   = secondary / placeholder / hint text color
DEFAULT_COLORS = {
    "bg":     "#0f0f14",
    "fg":     "#f0f0f5",
    "accent": "#e50914",
    "border": "#2a2a35",
    "panel":  "#16161d",
    "muted":  "#8a8a95",
}

PRESET_THEMES = {
    "Theater":  {"bg": "#0f0f14", "fg": "#f0f0f5", "accent": "#e50914", "border": "#2a2a35", "panel": "#16161d", "muted": "#8a8a95"},
    "Neon":     {"bg": "#10001a", "fg": "#f8f0ff", "accent": "#00ffd5", "border": "#3a1a50", "panel": "#1a0428", "muted": "#9a82b0"},
    "Sepia":    {"bg": "#241a10", "fg": "#f4e8d0", "accent": "#c98a3c", "border": "#4a3520", "panel": "#2e2418", "muted": "#a08868"},
    "Midnight": {"bg": "#05070d", "fg": "#cdd5e0", "accent": "#4a8cff", "border": "#1a2438", "panel": "#0a0f1a", "muted": "#5a6478"},
    "Daylight": {"bg": "#f4f4f8", "fg": "#1a1a22", "accent": "#0b66ff", "border": "#d8d8e0", "panel": "#ffffff", "muted": "#6a6a78"},
}

COLOR_KEYS = ["bg", "fg", "accent", "border", "panel", "muted"]
COLOR_LABELS = {
    "bg":     "Background",
    "fg":     "Text",
    "accent": "Accent",
    "border": "Border",
    "panel":  "Panel / Card",
    "muted":  "Muted Text",
}

# Quality selectors — ALL single-stream (one URL with merged audio+video).
# Using "bestvideo+bestaudio" returns TWO URLs which QtMediaPlayer can't combine,
# so it'd play video-only with no audio and choppily. Always pick a single muxed file.
# YouTube only serves single-file streams up to ~1080p; above 1080p we fall back.
QUALITY_FORMATS = {
    "Low":           "worst[ext=mp4]/worst",
    "480p":          "best[height<=480][ext=mp4]/best[height<=480]",
    "720p":          "best[height<=720][ext=mp4]/best[height<=720]",
    "1080p":         "best[height<=1080][ext=mp4]/best[height<=1080]/best",
    "1440p (2K)":    "best[height<=1440][ext=mp4]/best[height<=1080][ext=mp4]/best[height<=1080]",
    "2160p (4K)":    "best[height<=2160][ext=mp4]/best[height<=1080][ext=mp4]/best[height<=1080]",
    "4320p (8K)":    "best[height<=4320][ext=mp4]/best[height<=1080][ext=mp4]/best[height<=1080]",
    "Best available":"best[ext=mp4]/best",
}

ASPECT_RATIOS = ["Native", "16:9", "21:9", "4:3", "1:1", "Stretch"]

MAX_INVITES = 3

# ====== Discord OAuth (PKCE — NO client secret used in this client) ======
# Discord app: https://discord.com/developers/applications/<DISCORD_CLIENT_ID>/oauth2
# In the OAuth2 → Redirects section, add:
#   http://localhost:53682/discord-callback
#
# Scope notes:
#   identify          — always granted, gives us your Discord user id + username + avatar.
#   relationships.read — RESTRICTED. Discord rejects this scope for most apps
#                        with "requested scope is unknown, invalid, or malformed".
#                        Only enable if your app has the scope whitelisted.
DISCORD_CLIENT_ID = "1509779937404653649"
DISCORD_REDIRECT_PORT = 53682
DISCORD_REDIRECT_URI = f"http://localhost:{DISCORD_REDIRECT_PORT}/discord-callback"
DISCORD_SCOPES = "identify"
# Set this to True ONLY if your Discord app has been granted relationships.read.
DISCORD_TRY_RELATIONSHIPS = False
