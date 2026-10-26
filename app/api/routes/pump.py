"""api/routes/pump.py — sterowanie i harmonogram pompy cyrkulacyjnej (Tuya)."""

import json
import os
from typing import Optional

from flask import Blueprint, jsonify, request, g
from api.auth import require_auth
from api.routes import config as config_routes
import data.database as db

bp = Blueprint("pump", __name__)

VALID_DAYS = {"mon", "tue", "wed", "thu", "fri", "sat", "sun"}
VALID_MODES = {"off", "manual", "schedule"}
VALID_MANUAL_MINUTES = {5, 10, 15, 30}


def _save_pump_mode(mode: str) -> None:
    config_routes._app_config["pump_mode"] = mode
    cfg_file = os.environ.get("CFG_FILE", "/var/lib/boiler/config.json")
    try:
        existing = {}
        if os.path.exists(cfg_file):
            with open(cfg_file) as f:
                existing = json.load(f)
        existing["pump_mode"] = mode
        os.makedirs(os.path.dirname(cfg_file), exist_ok=True)
        with open(cfg_file, "w") as f:
            json.dump(existing, f, indent=2, ensure_ascii=False)
    except Exception as e:
        import logging
        logging.getLogger("boiler.pump").error(f"Błąd zapisu pump_mode: {e}")


def _validate_slot(d: dict) -> Optional[str]:
    required = ["days", "time_start", "time_stop"]
    for f in required:
        if f not in d:
            return f"Brak pola: {f}"

    if not isinstance(d["days"], list) or not d["days"]:
        return "days musi być niepustą listą"
    invalid_days = set(d["days"]) - VALID_DAYS
    if invalid_days:
        return f"Nieprawidłowe dni: {invalid_days}"

    for t_field in ("time_start", "time_stop"):
        t = d.get(t_field, "")
        parts = t.split(":")
        if len(parts) != 2 or not parts[0].isdigit() or not parts[1].isdigit():
            return f"{t_field} musi być w formacie HH:MM"

    if d["time_start"] >= d["time_stop"]:
        return "time_start musi być przed time_stop"

    cycle_on = d.get("cycle_on_min")
    cycle_off = d.get("cycle_off_min")
    if cycle_on is not None:
        if not (isinstance(cycle_on, int) and cycle_on > 0):
            return "cycle_on_min musi być dodatnią liczbą minut"
        if cycle_off is not None and not (isinstance(cycle_off, int) and cycle_off >= 0):
            return "cycle_off_min musi być nieujemną liczbą minut"

    return None


@bp.get("/api/pump/config")
@require_auth
def api_pump_config_get():
    return jsonify({
        "pump_device_id": config_routes._app_config.get("pump_device_id", ""),
        "pump_switch_dp": config_routes._app_config.get("pump_switch_dp", "switch_1"),
    })


@bp.patch("/api/pump/config")
@require_auth
def api_pump_config_patch():
    if not g.get("is_admin"):
        return jsonify({"error": "Wymagane uprawnienia administratora"}), 403
    d = request.get_json(silent=True) or {}
    changed = {}
    for k in ("pump_device_id", "pump_switch_dp"):
        if k in d and d[k]:
            config_routes._app_config[k] = d[k]
            changed[k] = d[k]
    if not changed:
        return jsonify({"error": "Brak prawidłowych pól"}), 400

    cfg_file = os.environ.get("CFG_FILE", "/var/lib/boiler/config.json")
    try:
        existing = {}
        if os.path.exists(cfg_file):
            with open(cfg_file) as f:
                existing = json.load(f)
        existing.update(changed)
        os.makedirs(os.path.dirname(cfg_file), exist_ok=True)
        with open(cfg_file, "w") as f:
            json.dump(existing, f, indent=2, ensure_ascii=False)
    except Exception as e:
        return jsonify({"error": f"Błąd zapisu: {e}"}), 500

    db.log_user_action(g.username, "PUMP_CONFIG", payload=str(changed), ip=request.remote_addr)
    return jsonify({"ok": True, "changed": changed})


@bp.get("/api/pump/status")
@require_auth
def api_pump_status():
    from service.pump_runtime import pump_runtime
    from core.pump_scheduler import pump_scheduler
    snap = pump_runtime.snapshot()
    snap["mode"] = config_routes._app_config.get("pump_mode", "off")
    snap["today_minutes"] = db.get_pump_today_minutes()
    snap["scheduler"] = pump_scheduler.status()
    snap["device_configured"] = bool(config_routes._app_config.get("pump_device_id"))
    return jsonify(snap)


@bp.post("/api/pump/mode")
@require_auth
def api_pump_mode():
    d = request.get_json(silent=True) or {}
    mode = d.get("mode")
    if mode not in VALID_MODES:
        return jsonify({"error": f"mode musi być jednym z {sorted(VALID_MODES)}"}), 400
    _save_pump_mode(mode)
    db.log_user_action(g.username, "PUMP_SET_MODE", payload=mode, ip=request.remote_addr)
    return jsonify({"ok": True, "mode": mode})


@bp.post("/api/pump/manual")
@require_auth
def api_pump_manual():
    from service.pump_runtime import pump_runtime
    d = request.get_json(silent=True) or {}
    on = bool(d.get("on", True))
    minutes = d.get("minutes")
    try:
        minutes = int(minutes)
    except (TypeError, ValueError):
        return jsonify({"error": "minutes wymagane"}), 400
    if minutes not in VALID_MANUAL_MINUTES:
        return jsonify({"error": f"minutes musi być jednym z {sorted(VALID_MANUAL_MINUTES)}"}), 400

    _save_pump_mode("manual")
    pump_runtime.set_manual(on, minutes)
    db.log_user_action(g.username, "PUMP_MANUAL",
                       payload=f"on={on} minutes={minutes}", ip=request.remote_addr)
    return jsonify({"ok": True, "on": on, "minutes": minutes})


@bp.get("/api/pump/schedule")
@require_auth
def api_pump_schedule_list():
    return jsonify(db.get_pump_schedule_slots())


@bp.post("/api/pump/schedule")
@require_auth
def api_pump_schedule_add():
    from core.pump_scheduler import pump_scheduler
    d = request.get_json(silent=True) or {}
    err = _validate_slot(d)
    if err:
        return jsonify({"error": err}), 400

    slot_id = db.add_pump_schedule_slot(
        days=          d["days"],
        time_start=    d["time_start"],
        time_stop=     d["time_stop"],
        cycle_on_min=  d.get("cycle_on_min"),
        cycle_off_min= d.get("cycle_off_min"),
        label=         d.get("label", ""),
    )
    if slot_id is None:
        return jsonify({"error": "Błąd zapisu do DB"}), 500

    pump_scheduler.reload()
    db.log_user_action(g.username, "PUMP_ADD_SLOT", payload=str(d), ip=request.remote_addr)
    return jsonify({"ok": True, "id": slot_id}), 201


@bp.put("/api/pump/schedule/<int:sid>")
@require_auth
def api_pump_schedule_update(sid: int):
    from core.pump_scheduler import pump_scheduler
    d = request.get_json(silent=True) or {}
    ok = db.update_pump_schedule_slot(sid, d)
    if not ok:
        return jsonify({"error": "Nie znaleziono slotu lub brak pól"}), 400

    pump_scheduler.reload()
    db.log_user_action(g.username, "PUMP_UPDATE_SLOT",
                       payload=f"id={sid} {d}", ip=request.remote_addr)
    return jsonify({"ok": True})


@bp.delete("/api/pump/schedule/<int:sid>")
@require_auth
def api_pump_schedule_delete(sid: int):
    from core.pump_scheduler import pump_scheduler
    db.delete_pump_schedule_slot(sid)
    pump_scheduler.reload()
    db.log_user_action(g.username, "PUMP_DELETE_SLOT", payload=f"id={sid}", ip=request.remote_addr)
    return jsonify({"ok": True})


@bp.get("/api/pump/history")
@require_auth
def api_pump_history():
    hours = min(int(request.args.get("hours", 168)), 24 * 180)
    return jsonify(db.get_pump_history(hours=hours))
