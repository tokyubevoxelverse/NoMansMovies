# NoMansMovies

Desktop movie-theater app with Instagram-style social profiles, friends, DMs, and watch-together sync. Built with PySide6 + Supabase + yt-dlp.

## Setup

1. **Install Python 3.11+**.
2. From this folder:
   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```
3. **Set your Supabase project URL** — open `nomansmovies/config.py` and replace `SUPABASE_URL` with your project URL (e.g. `https://abcd1234.supabase.co`). The publishable key is already filled in.
4. **Apply the schema** — open the Supabase dashboard's SQL editor and run, in order:
   - `sql/schema.sql` — tables, RLS, avatars bucket.
   - `sql/002_discord.sql` — adds Discord columns to `profiles`.
   ### Discord linking (optional)
   - Go to https://discord.com/developers/applications → your app → **OAuth2 → Redirects** and add
     `http://localhost:53682/discord-callback`.
   - Save. **The Discord client secret is NOT used and should NOT be put in the app** — this client
     uses the PKCE flow (only the public client ID, which is already in `config.py`).
   - For automatic mutual-friend matching, your app needs Discord's `relationships.read` scope.
     That scope is restricted; Discord usually denies it. If it's denied, linking still works —
     the friends panel just gains a "Discord" tab listing other linked users to add manually.
5. **Run the app**:
   ```powershell
   python -m nomansmovies.main
   ```
   First launch downloads `yt-dlp.exe` to `./ytdlp/` automatically.

## Build the EXE

```powershell
.\build.ps1
```

The single-file EXE lands in `dist\NoMansMovies.exe`. Keep the `ytdlp\` folder next to it (yt-dlp downloads / updates itself on launch).

## Architecture

See the docstrings in each module.

- `nomansmovies/main.py` — entry point, QMainWindow, mode switching, dock layout.
- `nomansmovies/auth/` — login + signup windows.
- `nomansmovies/profile/` — profile view, edit, friends panel.
- `nomansmovies/messaging/` — DM chat.
- `nomansmovies/player/` — video panel, hover controls, source/watch sidebars, settings dialog.
- `nomansmovies/sync/` — Supabase Realtime broadcast room for watch-together.
- `nomansmovies/widgets/` — bottom bar, animated avatar (QMovie), collapsible dock.
- `nomansmovies/ytdlp_manager.py` — auto-installs and auto-updates yt-dlp.exe in `./ytdlp/`.
