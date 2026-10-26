from typing import Optional
"""
api/auth.py
Autentykacja — sesje tokenowe, require_auth decorator.
Każde logowanie logowane do DB.
"""

import secrets
import logging
from datetime import datetime, timedelta
from functools import wraps
from flask import request, jsonify, g

import data.database as db

log = logging.getLogger("boiler.auth")

# Token store: {token: {username, expires_at, is_admin}}
_sessions: dict = {}
_session_days: int = 30


def configure(session_days: int = 30) -> None:
    global _session_days
    _session_days = session_days


def create_session(username: str, is_admin: bool = False) -> str:
    token = secrets.token_hex(32)
    _sessions[token] = {
        "username":   username,
        "is_admin":   is_admin,
        "created_at": datetime.now().isoformat(),
        "expires_at": (datetime.now() + timedelta(days=_session_days)).isoformat(),
    }
    return token


def validate_token(token: str) -> Optional[dict]:
    session = _sessions.get(token)
    if not session:
        return None
    if datetime.now().isoformat() > session["expires_at"]:
        _sessions.pop(token, None)
        return None
    return session


def revoke_token(token: str) -> None:
    _sessions.pop(token, None)


def _get_token() -> Optional[str]:
    # 1. Header Authorization: Bearer <token>
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:]
    # 2. Cookie
    return request.cookies.get("session_token")


def require_auth(f):
    """Decorator — wymaga ważnego tokenu sesji."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        token   = _get_token()
        session = validate_token(token) if token else None
        if not session:
            return jsonify({"error": "Unauthorized"}), 401
        g.username = session["username"]
        g.is_admin = session["is_admin"]
        return f(*args, **kwargs)
    return wrapper


def require_admin(f):
    """Decorator — wymaga uprawnień admina."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        token   = _get_token()
        session = validate_token(token) if token else None
        if not session:
            return jsonify({"error": "Unauthorized"}), 401
        if not session.get("is_admin"):
            return jsonify({"error": "Admin required"}), 403
        g.username = session["username"]
        g.is_admin = True
        return f(*args, **kwargs)
    return wrapper
