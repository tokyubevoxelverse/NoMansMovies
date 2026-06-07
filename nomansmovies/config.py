"""Static configuration for NoMansMovies."""
from __future__ import annotations
import os
import sys
from pathlib import Path

# ====== Supabase ======
# Fill these in with your own Supabase project credentials before running.
#   SUPABASE_URL                e.g. "https://<your-project-ref>.supabase.co"
#   SUPABASE_PUBLISHABLE_KEY    the "publishable" / anon key from Project Settings → API
# Publishable keys are designed to ship in clients; safety comes from Row-Level
# Security policies on the tables (see sql/schema.sql).
SUPABASE_URL = "https://YOUR-PROJECT-REF.supabase.co"
SUPABASE_PUBLISHABLE_KEY = "YOUR_SUPABASE_PUBLISHABLE_KEY"

# ====== Paths ======
def _app_root() -> Path:
    """Writable app dir (next to the exe when frozen). Used for ytdlp/, which the
    app downloads/updates at runtime and so must be a real on-disk location."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


def _resource_root() -> Path:
    """Read-only bundled-resource dir. For a PyInstaller one-file build this is
    the temp extraction dir (sys._MEIPASS); otherwise it's the app root. Bundled
    data (e.g. assets/splash.gif) lives here, NOT next to the exe."""
    mp = getattr(sys, "_MEIPASS", None)
    if mp:
        return Path(mp)
    return _app_root()


APP_ROOT: Path = _app_root()
RESOURCE_ROOT: Path = _resource_root()
YTDLP_DIR: Path = APP_ROOT / "ytdlp"
YTDLP_EXE: Path = YTDLP_DIR / "yt-dlp.exe"
YTDLP_DIR.mkdir(parents=True, exist_ok=True)

# Assets are bundled read-only resources → resolve from RESOURCE_ROOT so the
# splash GIF and icons are found inside the frozen exe (sys._MEIPASS), with a
# fallback to a sibling assets/ folder for dev / loose-file runs.
ASSETS_DIR: Path = RESOURCE_ROOT / "assets"
if not ASSETS_DIR.exists() and (APP_ROOT / "assets").exists():
    ASSETS_DIR = APP_ROOT / "assets"

# ====== App ======
APP_NAME = "NoMansMovies"
ORG_NAME = "NoMansMovies"
VERSION = "0.2.5"

# 2–3 short bullets shown on the splash under the version.
CHANGELOG_BULLETS = [
    "Layout system rework: 3 custom slots, Save now overrides the active slot",
    "New title-bar buttons on the Movie panel: Minimize all + bring back NoMansMovies controls",
    "New preset layout: Movie + Playback",
]

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

# ---- Font defaults (applied app-wide via theme.py) ----
DEFAULT_FONT_FAMILY = "Segoe UI"
DEFAULT_FONT_SIZE = 10
FONT_SIZE_RANGE = (8, 18)
DEFAULT_FONT_WEIGHT = "normal"   # "normal" | "bold"
DEFAULT_LETTER_SPACING_PX = 0     # int px (negative tightens)
LETTER_SPACING_RANGE = (-2, 8)

# ---- Video player border defaults ----
DEFAULT_VIDEO_BORDER = False
DEFAULT_VIDEO_BORDER_COLOR = "#e50914"
DEFAULT_VIDEO_BORDER_WIDTH = 4
DEFAULT_VIDEO_BORDER_WIDTH_RANGE = (1, 20)
DEFAULT_VIDEO_ROUNDED = False
DEFAULT_VIDEO_CORNER_RADIUS = 12
DEFAULT_VIDEO_CORNER_RADIUS_RANGE = (0, 40)

# ---- Layout presets (used by overlay Cycle Layouts + Movie-only cinema mode) ----
LAYOUT_DEFAULT            = "default"
LAYOUT_MOVIE_SOURCES      = "movie_sources"
LAYOUT_MOVIE_ONLY         = "movie_only"
LAYOUT_MOVIE_PLAYBACK     = "movie_playback"
LAYOUT_MOVIE_PLAYER_ONLY  = "movie_player_only"   # video panel ONLY — everything
                                                  # else (including NoMansMovies
                                                  # controls) is hidden
# Built-ins that appear BEFORE the user's custom slots in the cycler.
LAYOUTS = [LAYOUT_DEFAULT, LAYOUT_MOVIE_SOURCES, LAYOUT_MOVIE_ONLY, LAYOUT_MOVIE_PLAYBACK]
# Built-ins that appear AFTER all custom slots in the cycler (so once you
# cycle into Movie-player-only — which hides the controls bar — the wrap-
# around takes you back to Default rather than skipping past your customs).
LAYOUTS_AFTER_CUSTOMS = [LAYOUT_MOVIE_PLAYER_ONLY]
# Every built-in (used for validation).
ALL_BUILTIN_LAYOUTS = LAYOUTS + LAYOUTS_AFTER_CUSTOMS
LAYOUT_LABELS = {
    LAYOUT_DEFAULT:           "Default",
    LAYOUT_MOVIE_SOURCES:     "Movie + Sources",
    LAYOUT_MOVIE_ONLY:        "Movie only",
    LAYOUT_MOVIE_PLAYBACK:    "Movie + Playback",
    LAYOUT_MOVIE_PLAYER_ONLY: "Movie player only",
}
# Custom user-saved layouts are stored separately and referenced as
# "custom:1", "custom:2", "custom:3" — they don't appear in LAYOUTS but DO
# appear in the cycler (see main.py: _all_layouts / _cycle_layout).
CUSTOM_LAYOUT_PREFIX = "custom:"
MAX_CUSTOM_LAYOUTS = 3

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
DISCORD_CLIENT_ID = "YOUR_DISCORD_CLIENT_ID"
DISCORD_REDIRECT_PORT = 53682
DISCORD_REDIRECT_URI = f"http://localhost:{DISCORD_REDIRECT_PORT}/discord-callback"
DISCORD_SCOPES = "identify"
# Discord rejects relationships.read for this app, so we cannot auto-pull the
# user's Discord friends list. The "Discord" tab in the Friends panel still
# lets users find each other manually after both link Discord.
DISCORD_TRY_RELATIONSHIPS = False


# ============ LOCAL OVERRIDES ============
# Drop a `config_local.py` next to this file with your real Supabase / Discord
# credentials. It's gitignored, so the public config.py stays sanitized while
# your local build picks up the real values.
#
# Example config_local.py:
#     SUPABASE_URL = "https://<your-ref>.supabase.co"
#     SUPABASE_PUBLISHABLE_KEY = "sb_publishable_..."
#     DISCORD_CLIENT_ID = "1234567890"
try:
    from .config_local import *  # noqa: F401, F403
except ImportError:
    pass
