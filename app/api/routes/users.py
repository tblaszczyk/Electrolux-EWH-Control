"""api/routes/users.py — zarządzanie użytkownikami."""

from flask import Blueprint, jsonify, request, g
from api.auth import require_auth
import data.database as db

bp = Blueprint("users", __name__)


def require_admin_role(f):
    """Decorator — tylko admin może wykonać akcję."""
    from functools import wraps
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not g.get("is_admin"):
            return jsonify({"error": "Wymagane uprawnienia administratora"}), 403
        return f(*args, **kwargs)
    return wrapper


@bp.get("/api/users")
@require_auth
@require_admin_role
def api_users_list():
    try:
        with db._get_con() as con:
            rows = con.execute(
                "SELECT id, username, is_admin, created_at FROM users ORDER BY id"
            ).fetchall()
        return jsonify([dict(r) for r in rows])
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.post("/api/users")
@require_auth
@require_admin_role
def api_users_add():
    d = request.get_json(silent=True) or {}
    username = d.get("username", "").strip()
    password = d.get("password", "")
    is_admin = bool(d.get("is_admin", False))

    if not username or not password:
        return jsonify({"error": "Wymagane: username, password"}), 400
    if len(username) < 3:
        return jsonify({"error": "Nazwa użytkownika min. 3 znaki"}), 400
    if len(password) < 4:
        return jsonify({"error": "Hasło min. 4 znaki"}), 400

    ok = db.create_user(username, password, is_admin=is_admin)
    if not ok:
        return jsonify({"error": f"Użytkownik '{username}' już istnieje"}), 409

    db.log_user_action(g.username, "ADD_USER",
                       payload=f"username={username} admin={is_admin}",
                       ip=request.remote_addr)
    return jsonify({"ok": True}), 201


@bp.delete("/api/users/<int:uid>")
@require_auth
@require_admin_role
def api_users_delete(uid):
    # Nie pozwól usunąć samego siebie
    me = db.get_user(g.username)
    if me and me["id"] == uid:
        return jsonify({"error": "Nie możesz usunąć własnego konta"}), 400

    try:
        with db._get_con() as con:
            con.execute("DELETE FROM users WHERE id=?", (uid,))
        db.log_user_action(g.username, "DELETE_USER",
                           payload=f"uid={uid}", ip=request.remote_addr)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.post("/api/users/<int:uid>/password")
@require_auth
def api_users_change_password(uid):
    d = request.get_json(silent=True) or {}
    new_password = d.get("password", "")

    if len(new_password) < 4:
        return jsonify({"error": "Hasło min. 4 znaki"}), 400

    # Zwykły user może zmieniać tylko swoje hasło
    me = db.get_user(g.username)
    if not g.get("is_admin") and (not me or me["id"] != uid):
        return jsonify({"error": "Brak uprawnień"}), 403

    try:
        with db._get_con() as con:
            from data.database import _hash_password
            con.execute(
                "UPDATE users SET password_hash=? WHERE id=?",
                (_hash_password(new_password), uid)
            )
        db.log_user_action(g.username, "CHANGE_PASSWORD",
                           payload=f"uid={uid}", ip=request.remote_addr)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.patch("/api/users/<int:uid>")
@require_auth
@require_admin_role
def api_users_update(uid):
    d = request.get_json(silent=True) or {}
    # Tylko is_admin można zmieniać (nie username)
    if "is_admin" not in d:
        return jsonify({"error": "Brak pól do zmiany"}), 400

    # Nie możesz odebrać sobie admina
    me = db.get_user(g.username)
    if me and me["id"] == uid and not d["is_admin"]:
        return jsonify({"error": "Nie możesz odebrać sobie uprawnień admina"}), 400

    try:
        with db._get_con() as con:
            con.execute("UPDATE users SET is_admin=? WHERE id=?",
                        (int(bool(d["is_admin"])), uid))
        db.log_user_action(g.username, "UPDATE_USER",
                           payload=f"uid={uid} is_admin={d['is_admin']}",
                           ip=request.remote_addr)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
