"""api/routes/auth_routes.py — logowanie i wylogowanie."""

from flask import Blueprint, jsonify, request, make_response
import data.database as db
from api import auth

bp = Blueprint("auth_routes", __name__)


@bp.post("/api/login")
def api_login():
    d        = request.get_json(silent=True) or {}
    username = d.get("username", "")
    password = d.get("password", "")
    ip       = request.remote_addr

    user = db.verify_user(username, password)
    db.log_auth(username, success=bool(user), ip=ip)

    if not user:
        return jsonify({"ok": False, "error": "Nieprawidłowe dane logowania"}), 401

    token = auth.create_session(username, is_admin=user.get("is_admin", False))
    db.log_user_action(username, "LOGIN", ip=ip)

    resp = make_response(jsonify({"ok": True, "token": token}))
    resp.set_cookie(
        "session_token", token,
        httponly=True, samesite="Strict", max_age=30 * 24 * 3600
    )
    return resp


@bp.post("/api/logout")
def api_logout():
    token = request.cookies.get("session_token") or \
            request.headers.get("Authorization", "").replace("Bearer ", "")
    if token:
        auth.revoke_token(token)
    resp = make_response(jsonify({"ok": True}))
    resp.delete_cookie("session_token")
    return resp
