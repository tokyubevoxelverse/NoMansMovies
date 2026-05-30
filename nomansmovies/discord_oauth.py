"""Discord OAuth2 PKCE flow + identity / relationships fetch.

Run link_discord() from a Qt-friendly thread. The flow:
    1. Generate a PKCE verifier + S256 challenge.
    2. Start a one-shot local HTTP server on DISCORD_REDIRECT_PORT.
    3. Open the Discord authorize URL in the user's default browser.
    4. After authorization, Discord redirects to localhost with ?code=…
    5. Exchange the code (with PKCE verifier, NO client secret) for an access token.
    6. Pull identity + relationships and return them.

If the user denies access or the redirect times out, raises DiscordOAuthError.
"""
from __future__ import annotations
import base64
import hashlib
import http.server
import json
import secrets
import socketserver
import threading
import urllib.parse
import webbrowser
from dataclasses import dataclass
from typing import Optional

import requests

from .config import (
    DISCORD_CLIENT_ID, DISCORD_REDIRECT_PORT, DISCORD_REDIRECT_URI, DISCORD_SCOPES,
    DISCORD_TRY_RELATIONSHIPS,
)


class DiscordOAuthError(Exception):
    pass


@dataclass
class DiscordIdentity:
    id: str
    username: str
    global_name: Optional[str]
    avatar_url: Optional[str]


@dataclass
class DiscordLinkResult:
    access_token: str
    identity: DiscordIdentity
    friend_ids: list[str]               # Discord user IDs (type==1 relationships, i.e. confirmed friends)
    relationships_denied: bool          # True if the scope wasn't granted


# ============ PKCE helpers ============
def _pkce_pair() -> tuple[str, str]:
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(64)).decode().rstrip("=")
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()
    ).decode().rstrip("=")
    return verifier, challenge


# ============ local HTTP listener ============
_HTML_OK = b"""<!doctype html><html><head><meta charset=utf-8><title>NoMansMovies</title>
<style>body{font-family:Segoe UI,sans-serif;background:#0f0f14;color:#f0f0f5;
display:flex;align-items:center;justify-content:center;height:100vh;margin:0}
.card{background:#16161d;border:1px solid #2a2a35;border-radius:14px;padding:32px;text-align:center}
h1{margin:0 0 8px;font-size:20pt}</style></head><body>
<div class=card><h1>Discord linked</h1><p>You can close this tab and return to NoMansMovies.</p></div>
</body></html>"""

_HTML_FAIL = b"""<!doctype html><html><head><meta charset=utf-8><title>NoMansMovies</title>
<style>body{font-family:Segoe UI,sans-serif;background:#0f0f14;color:#f0f0f5;
display:flex;align-items:center;justify-content:center;height:100vh;margin:0}
.card{background:#16161d;border:1px solid #e50914;border-radius:14px;padding:32px;text-align:center}</style></head><body>
<div class=card><h1>Link failed</h1><p>Return to NoMansMovies and try again.</p></div>
</body></html>"""


class _CallbackHandler(http.server.BaseHTTPRequestHandler):
    captured_code: Optional[str] = None
    captured_state: Optional[str] = None
    captured_error: Optional[str] = None
    expected_state: str = ""

    def do_GET(self):  # noqa: N802
        if not self.path.startswith("/discord-callback"):
            self.send_response(404); self.end_headers(); return
        parsed = urllib.parse.urlparse(self.path)
        params = dict(urllib.parse.parse_qsl(parsed.query))
        if params.get("error"):
            _CallbackHandler.captured_error = params.get("error_description") or params.get("error")
            self.send_response(200); self.send_header("Content-Type", "text/html"); self.end_headers()
            self.wfile.write(_HTML_FAIL); return
        code = params.get("code"); state = params.get("state")
        if not code or state != _CallbackHandler.expected_state:
            _CallbackHandler.captured_error = "State mismatch or missing code."
            self.send_response(400); self.send_header("Content-Type", "text/html"); self.end_headers()
            self.wfile.write(_HTML_FAIL); return
        _CallbackHandler.captured_code = code
        self.send_response(200); self.send_header("Content-Type", "text/html"); self.end_headers()
        self.wfile.write(_HTML_OK)

    def log_message(self, *_args, **_kwargs):
        return  # silence access logs


def _await_callback(state: str, timeout_s: int = 180) -> str:
    _CallbackHandler.captured_code = None
    _CallbackHandler.captured_error = None
    _CallbackHandler.expected_state = state

    server = socketserver.TCPServer(("127.0.0.1", DISCORD_REDIRECT_PORT), _CallbackHandler)
    server.timeout = 1
    done = threading.Event()

    def serve():
        while not done.is_set():
            server.handle_request()
            if _CallbackHandler.captured_code or _CallbackHandler.captured_error:
                done.set()

    t = threading.Thread(target=serve, daemon=True); t.start()
    done.wait(timeout=timeout_s)
    try: server.server_close()
    except Exception: pass

    if _CallbackHandler.captured_error:
        raise DiscordOAuthError(_CallbackHandler.captured_error)
    if not _CallbackHandler.captured_code:
        raise DiscordOAuthError("Timed out waiting for Discord authorization.")
    return _CallbackHandler.captured_code


# ============ main entry ============
def link_discord() -> DiscordLinkResult:
    """Blocking — runs the full Discord OAuth PKCE flow. Call off the UI thread."""
    verifier, challenge = _pkce_pair()
    state = secrets.token_urlsafe(24)

    auth_url = "https://discord.com/oauth2/authorize?" + urllib.parse.urlencode({
        "client_id":             DISCORD_CLIENT_ID,
        "response_type":         "code",
        "redirect_uri":          DISCORD_REDIRECT_URI,
        "scope":                 DISCORD_SCOPES,
        "state":                 state,
        "code_challenge":        challenge,
        "code_challenge_method": "S256",
        "prompt":                "consent",
    })
    if not webbrowser.open(auth_url):
        raise DiscordOAuthError("Could not open the system browser.")

    code = _await_callback(state)

    # Exchange code for token — PKCE, no client_secret.
    tr = requests.post(
        "https://discord.com/api/oauth2/token",
        data={
            "client_id":     DISCORD_CLIENT_ID,
            "grant_type":    "authorization_code",
            "code":          code,
            "redirect_uri":  DISCORD_REDIRECT_URI,
            "code_verifier": verifier,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=20,
    )
    if not tr.ok:
        raise DiscordOAuthError(f"Token exchange failed: {tr.status_code} {tr.text[:200]}")
    token = tr.json().get("access_token")
    if not token:
        raise DiscordOAuthError("No access token returned.")

    auth = {"Authorization": f"Bearer {token}"}

    me = requests.get("https://discord.com/api/v10/users/@me", headers=auth, timeout=20)
    if not me.ok:
        raise DiscordOAuthError(f"/users/@me failed: {me.status_code}")
    mej = me.json()
    avatar_url = None
    if mej.get("avatar"):
        ext = "gif" if str(mej["avatar"]).startswith("a_") else "png"
        avatar_url = f"https://cdn.discordapp.com/avatars/{mej['id']}/{mej['avatar']}.{ext}?size=256"

    identity = DiscordIdentity(
        id=mej["id"],
        username=mej.get("username") or "",
        global_name=mej.get("global_name"),
        avatar_url=avatar_url,
    )

    # Relationships — only attempt when the restricted scope is enabled in config.
    friend_ids: list[str] = []
    relationships_denied = not DISCORD_TRY_RELATIONSHIPS
    if DISCORD_TRY_RELATIONSHIPS:
        rel = requests.get("https://discord.com/api/v10/users/@me/relationships", headers=auth, timeout=20)
        if rel.status_code in (401, 403):
            relationships_denied = True
        elif rel.ok:
            try:
                for r in rel.json() or []:
                    # type 1 == friend (2 = blocked, 3 = incoming, 4 = outgoing)
                    if r.get("type") == 1 and r.get("id"):
                        friend_ids.append(str(r["id"]))
            except Exception:
                relationships_denied = True

    return DiscordLinkResult(
        access_token=token,
        identity=identity,
        friend_ids=friend_ids,
        relationships_denied=relationships_denied,
    )
