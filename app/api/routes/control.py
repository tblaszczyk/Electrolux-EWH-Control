"""api/routes/control.py — sterowanie przez kolejkę komend."""

from flask import Blueprint, jsonify, request, g
from api.auth import require_auth
from service.command_queue import queue, cmd_set_manual, cmd_set_auto, cmd_set_idle_mode
import data.database as db
from config.defaults import SAFETY, IDLE

bp = Blueprint("control", __name__)

VALID_POWERS = {0, 700, 1300, 2000}
VALID_IDLES  = {"off", "low_20", "low_30"}


@bp.post("/api/control/manual")
@require_auth
def api_control_manual():
    d = request.get_json(silent=True) or {}

    temp  = d.get("temp")
    power = d.get("power_limit")

    if temp is None or power is None:
        return jsonify({"error": "Wymagane: temp, power_limit"}), 400

    temp  = int(temp)
    power = int(power)

    # Walidacja
    mn = SAFETY["min_temp_manual_c"]
    mx = SAFETY["max_temp_manual_c"]
    step = SAFETY["temp_step_c"]

    if not (mn <= temp <= mx):
        return jsonify({"error": f"temp musi być {mn}–{mx}°C"}), 400
    if temp % step != 0:
        return jsonify({"error": f"temp musi być wielokrotnością {step}°C"}), 400
    if power not in VALID_POWERS:
        return jsonify({"error": f"power_limit musi być jednym z {sorted(VALID_POWERS)}"}), 400

    queue.put(cmd_set_manual(temp, power, username=g.username))
    db.log_user_action(
        username=g.username,
        action="SET_MANUAL",
        payload=f"temp={temp}, power={power}",
        ip=request.remote_addr,
    )
    return jsonify({"ok": True, "queued": "SET_MANUAL", "temp": temp, "power_limit": power})


@bp.post("/api/control/auto")
@require_auth
def api_control_auto():
    queue.put(cmd_set_auto(username=g.username))
    db.log_user_action(
        username=g.username, action="SET_AUTO", ip=request.remote_addr
    )
    return jsonify({"ok": True, "queued": "SET_AUTO"})


@bp.post("/api/control/idle_mode")
@require_auth
def api_control_idle():
    d    = request.get_json(silent=True) or {}
    mode = d.get("mode")
    if mode not in VALID_IDLES:
        return jsonify({"error": f"mode musi być jednym z {sorted(VALID_IDLES)}"}), 400

    queue.put(cmd_set_idle_mode(mode, username=g.username))
    db.log_user_action(
        username=g.username, action="SET_IDLE_MODE",
        payload=f"mode={mode}", ip=request.remote_addr,
    )
    return jsonify({"ok": True, "queued": "SET_IDLE_MODE", "mode": mode})


@bp.post("/api/control/power")
@require_auth
def api_control_power():
    d       = request.get_json(silent=True) or {}
    enabled = d.get("enabled")
    if enabled is None:
        return jsonify({"error": "Wymagane: enabled (true/false)"}), 400

    from service.command_queue import cmd_set_system_enabled
    queue.put(cmd_set_system_enabled(bool(enabled), username=g.username))
    db.log_user_action(
        username=g.username,
        action="SET_POWER",
        payload=f"enabled={enabled}",
        ip=request.remote_addr,
    )
    return jsonify({"ok": True, "queued": "SET_SYSTEM_ENABLED", "enabled": bool(enabled)})
