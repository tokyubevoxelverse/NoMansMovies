"""Manage the bundled yt-dlp.exe: install on first run, update once per day."""
from __future__ import annotations
import json
import subprocess
import time
from pathlib import Path
from typing import List, Optional

import requests
from PySide6.QtCore import QObject, QThread, Signal, QSettings

from .config import YTDLP_DIR, YTDLP_EXE, ORG_NAME, APP_NAME, QUALITY_FORMATS

YTDLP_URL = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe"
UPDATE_INTERVAL_SECONDS = 24 * 60 * 60

# Hide console windows when calling subprocess on Windows (frozen / no-console).
_CREATE_NO_WINDOW = 0x08000000


def _run(args: List[str], timeout: int = 60) -> subprocess.CompletedProcess:
    return subprocess.run(
        args,
        capture_output=True,
        text=True,
        timeout=timeout,
        creationflags=_CREATE_NO_WINDOW,
    )


def is_installed() -> bool:
    return YTDLP_EXE.exists() and YTDLP_EXE.stat().st_size > 0


def install() -> None:
    YTDLP_DIR.mkdir(parents=True, exist_ok=True)
    tmp = YTDLP_EXE.with_suffix(".exe.tmp")
    with requests.get(YTDLP_URL, stream=True, timeout=60) as r:
        r.raise_for_status()
        with open(tmp, "wb") as f:
            for chunk in r.iter_content(chunk_size=64 * 1024):
                if chunk:
                    f.write(chunk)
    tmp.replace(YTDLP_EXE)


def update() -> None:
    if not is_installed():
        install()
        return
    try:
        _run([str(YTDLP_EXE), "-U"], timeout=120)
    except Exception:
        pass


def maybe_update_async() -> None:
    """Kick off install-or-update in a background thread, non-blocking."""
    s = QSettings(ORG_NAME, APP_NAME)
    last = float(s.value("ytdlp/last_check", 0) or 0)
    now = time.time()
    needs = (not is_installed()) or (now - last > UPDATE_INTERVAL_SECONDS)
    if not needs:
        return

    worker = _Worker()
    thread = QThread()
    worker.moveToThread(thread)
    thread.started.connect(worker.run)
    worker.done.connect(thread.quit)
    worker.done.connect(lambda: s.setValue("ytdlp/last_check", time.time()))
    worker.done.connect(worker.deleteLater)
    thread.finished.connect(thread.deleteLater)
    # keep refs alive
    _live_threads.append((thread, worker))
    thread.start()


_live_threads: list = []


class _Worker(QObject):
    done = Signal()

    def run(self) -> None:
        try:
            if not is_installed():
                install()
            else:
                update()
        except Exception:
            pass
        self.done.emit()


# ====== Search & stream extraction ======

def search_youtube(query: str, n: int = 5) -> List[dict]:
    """Return up to n search results as dicts: {title, channel, duration, thumbnail, id, url}."""
    if not is_installed() or not query.strip():
        return []
    try:
        cp = _run(
            [
                str(YTDLP_EXE),
                f"ytsearch{n}:{query}",
                "--dump-json",
                "--skip-download",
                "--no-warnings",
                "--flat-playlist",
            ],
            timeout=30,
        )
    except Exception:
        return []
    results: List[dict] = []
    for line in cp.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            j = json.loads(line)
        except Exception:
            continue
        vid = j.get("id") or ""
        results.append({
            "title": j.get("title") or "(untitled)",
            "channel": j.get("uploader") or j.get("channel") or "",
            "duration": j.get("duration"),
            "thumbnail": j.get("thumbnail") or (f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg" if vid else ""),
            "id": vid,
            "url": j.get("url") or (f"https://www.youtube.com/watch?v={vid}" if vid else ""),
            "description": j.get("description") or "",
        })
        if len(results) >= n:
            break
    return results


def extract_stream_url(source_url: str, quality_label: str = "Best available") -> Optional[str]:
    """Return a direct playable URL for the given YouTube/page URL via yt-dlp -g."""
    if not is_installed() or not source_url:
        return None
    fmt = QUALITY_FORMATS.get(quality_label, QUALITY_FORMATS["Best available"])
    try:
        cp = _run(
            [str(YTDLP_EXE), "-f", fmt, "-g", "--no-warnings", source_url],
            timeout=45,
        )
    except Exception:
        return None
    for line in cp.stdout.splitlines():
        line = line.strip()
        if line.startswith("http"):
            return line
    return None
