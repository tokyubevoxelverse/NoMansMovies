# NoMansMovies

A frameless, always-on-top desktop movie player that overlays on top of your game (built originally for No Man's Sky, works over anything in borderless windowed mode). Sign up, build an Instagram-style profile, friend other users, DM them, and watch movies together with up to three friends — synchronized over Supabase Realtime, no media relay server required.

- **Sources** — paste any direct video link (mp4 / mkv / webm), search YouTube, or open a local file.
- **Watch together** — invite up to three friends; play / pause / seek mirrors instantly. Resync button snaps everyone to the host's position.
- **Floating overlay** — every panel (movie, sources, friends, playback bar, controls) is its own frameless always-on-top window. Drag from any edge to resize, drag the title bar to move, minimize each independently. Customize the layout and save your own presets ("Custom 1", "Custom 2", …) into the cycle button.
- **Profile + Appearance** — animated GIF avatars, bio, color scheme (background, foreground, accent, border, panel, muted), font family + size + bold + letter spacing, video player border (color, width, rounded corners), default layout. Linked Discord shows Rich Presence (`Gaming in NoMansMovies with YouTube / Direct link / Local file`).
- **Friends** — search by username, send requests, accept / decline, online status (green dot via Supabase Realtime presence), iMessage-style inline DMs inside the Watch panel.
- **Movie invite toasts** — frameless top-right notification when a friend invites you to a watch room.

## Tech

- Python 3.11+
- PySide6 (Qt 6) — `QMediaPlayer` + `QVideoWidget`, frameless `QWindow`s, `QGraphicsOpacityEffect`, native `startSystemMove` / `startSystemResize`
- supabase-py — auth, Postgres, Storage, Realtime broadcast + postgres_changes + presence
- yt-dlp (bundled exe, auto-installed + auto-updated on first launch)
- pypresence — Discord Rich Presence over local IPC (no client secret in the EXE)
- PyInstaller — single-file Windows EXE

## Setup

```powershell
py -m pip install -r requirements.txt
```

### 1. Configure credentials

Open `nomansmovies/config.py` and fill in the three placeholders:

```python
SUPABASE_URL = "https://<your-project-ref>.supabase.co"
SUPABASE_PUBLISHABLE_KEY = "<your-publishable-anon-key>"
DISCORD_CLIENT_ID = "<your-discord-application-id>"  # optional, for Rich Presence
```

The publishable / anon key is safe to ship in clients — Row-Level Security policies enforce access (see `sql/schema.sql`).

### 2. Apply the Supabase schema

In your Supabase dashboard's SQL editor, run in order:

1. `sql/schema.sql` — `profiles`, `friendships`, `messages` tables, `avatars` storage bucket, all RLS policies.
2. `sql/002_discord.sql` — adds `discord_id`, `discord_username`, `discord_avatar` columns.

Also make sure Realtime is enabled for `public.messages` and `public.friendships` (the schema already does this).

### 3. (Optional) Discord OAuth + Rich Presence

In the Discord developer portal (`https://discord.com/developers/applications`):

- **OAuth2 → Redirects** — add `http://localhost:53682/discord-callback`. This client uses the **PKCE flow**, no client secret is used or embedded.
- **Rich Presence → Art Assets** — upload images keyed `logo`, `youtube`, `link`, `file` to make the presence card look nice (the text status works without them).

`relationships.read` scope is restricted by Discord and is left disabled by default. The app falls back to a "Discord" tab in the Friends panel for finding other linked users manually.

### 4. Run

```powershell
python run.py
```

First launch downloads `yt-dlp.exe` into `./ytdlp/` (about 14 MB, one-time).

### 5. Build the EXE

```powershell
.\build.ps1
```

Output: `dist\NoMansMovies.exe` (single file, no Python required to run).

## Using it over a game

Set the game's display mode to **Borderless Windowed** — frameless always-on-top windows can't draw over true fullscreen-exclusive DX games. Once running:

- Press **9 three times** quickly for cinema mode (movie-only). Triple-9 again restores.
- Drag each panel by its title bar; resize from any edge or corner.
- The **NoMansMovies** controls bar has: Profile, Recenter, ⟳ Layout, Save Custom Layout, Show All, Restore All, — Minimize All Tabs (drops the app to the Windows taskbar), Opacity slider, ? Controls (a full plain-English how-to).
- ✕ on the NoMansMovies controls panel quits the app.

## Layout

```
MoviePlugin/
├── nomansmovies/
│   ├── main.py                — entry, MainWindow, overlay mode, layouts
│   ├── config.py              — credentials, color/font/border/layout defaults
│   ├── supabase_client.py     — singleton + session persistence
│   ├── ytdlp_manager.py       — install / update / search / extract
│   ├── theme.py               — palette + QSS, font + spacing + weight
│   ├── discord_oauth.py       — PKCE link flow
│   ├── discord_presence.py    — Rich Presence over IPC
│   ├── presence.py            — Supabase Realtime online tracker
│   ├── auth/                  — login + signup
│   ├── profile/               — profile_view, friends_panel
│   ├── messaging/             — chat_window (full-window dialog)
│   ├── player/                — video_panel, controls_overlay, playback_bar,
│   │                           source_panel, watch_panel, settings_dialog
│   ├── sync/                  — Realtime broadcast room
│   └── widgets/               — floating_panel, overlay_controls, inline_chat,
│                                appearance_panel, invite_toast, controls_help,
│                                splash, bottom_bar, collapsible_dock,
│                                animated_avatar
├── assets/icons/              — app.png + app.ico
├── sql/                       — schema + Discord migration
├── ytdlp/                     — runtime-managed yt-dlp.exe (gitignored)
├── requirements.txt
├── build.spec
├── build.ps1
└── run.py
```

## Architecture notes

- **Watch-together sync**: per-room Supabase Realtime **broadcast** channel `watch:<uuid>`. Host publishes `source`, `state`, `seek`, and 1 Hz `heartbeat`. Guests apply state changes and correct drift > 1.5 s automatically. Video bytes are fetched by each peer independently from the same origin (YouTube CDN or direct link) — so the only cross-peer traffic is tiny JSON control messages. Local files cannot be shared (no URL the guest can reach); the Invite button greys out for local sources.
- **Frameless windows + native resize**: every floating panel uses `Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint` and delegates moves/resizes to `QWindow.startSystemMove()` / `startSystemResize()` for fully OS-native behaviour.
- **Hover controls**: `QVideoWidget` uses a native Win32 surface that swallows Enter events, so the hover overlay is driven by an 80 ms `QCursor.pos()` poll instead of Qt event filters.
- **Theme as a single source of truth**: `theme.py` keeps the current color / font / border dict and emits `theme_signal.changed`; widgets with custom QSS re-skin on every save.

## License

MIT.
