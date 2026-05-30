"""Singleton Supabase client + simple session persistence via QSettings."""
from __future__ import annotations
from typing import Optional
from PySide6.QtCore import QSettings
from supabase import create_client, Client

from .config import SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY, ORG_NAME, APP_NAME

_client: Optional[Client] = None


def supabase() -> Client:
    global _client
    if _client is None:
        _client = create_client(SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY)
    return _client


def current_user_id() -> Optional[str]:
    try:
        u = supabase().auth.get_user()
        return u.user.id if u and u.user else None
    except Exception:
        return None


def save_session(access_token: str, refresh_token: str) -> None:
    s = QSettings(ORG_NAME, APP_NAME)
    s.setValue("auth/access_token", access_token)
    s.setValue("auth/refresh_token", refresh_token)


def clear_session() -> None:
    s = QSettings(ORG_NAME, APP_NAME)
    s.remove("auth/access_token")
    s.remove("auth/refresh_token")


def try_restore_session() -> bool:
    s = QSettings(ORG_NAME, APP_NAME)
    at = s.value("auth/access_token")
    rt = s.value("auth/refresh_token")
    if not at or not rt:
        return False
    try:
        supabase().auth.set_session(at, rt)
        return True
    except Exception:
        clear_session()
        return False
