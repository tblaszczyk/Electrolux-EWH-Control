from typing import Optional
"""api/routes/schedule.py — CRUD harmonogramu."""

from flask import Blueprint, jsonify, request, g
from api.auth import require_auth
from service.command_queue import queue, cmd_reload_schedule
import data.database as db

bp = Blueprint("schedule", __name__)

VALID_DAYS   = {"mon", "tue", "wed", "thu", "fri", "sat", "sun"}
VALID_POWERS = {700, 1300, 2000}


def _validate_slot(d: dict) -> Optional[str]:
    """Zwraca opis błędu lub None jeśli OK."""
    required = ["days", "time_start", "time_stop", "temp_c", "power_w"]
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

    temp = int(d.get("temp_c", 0))
    if not (20 <= temp <= 70):
        return "temp_c musi być 20–70°C"

    if int(d.get("power_w", 0)) not in VALID_POWERS:
        return f"power_w musi być jednym z {sorted(VALID_POWERS)}"

    return None


@bp.get("/api/schedule")
@require_auth
def api_schedule_list():
    slots = db.get_schedule_slots()
    return jsonify(slots)


@bp.post("/api/schedule")
@require_auth
def api_schedule_add():
    d = request.get_json(silent=True) or {}
    err = _validate_slot(d)
    if err:
        return jsonify({"error": err}), 400

    slot_id = db.add_schedule_slot(
        days=       d["days"],
        time_start= d["time_start"],
        time_stop=  d["time_stop"],
        temp_c=     int(d["temp_c"]),
        power_w=    int(d["power_w"]),
        label=      d.get("label", ""),
    )
    if slot_id is None:
        return jsonify({"error": "Błąd zapisu do DB"}), 500

    queue.put(cmd_reload_schedule(username=g.username))
    db.log_user_action(g.username, "ADD_SCHEDULE_SLOT",
                       payload=str(d), ip=request.remote_addr)
    return jsonify({"ok": True, "id": slot_id}), 201


@bp.put("/api/schedule/<int:sid>")
@require_auth
def api_schedule_update(sid: int):
    d   = request.get_json(silent=True) or {}
    ok  = db.update_schedule_slot(sid, d)
    if not ok:
        return jsonify({"error": "Nie znaleziono slotu lub brak pól"}), 400

    queue.put(cmd_reload_schedule(username=g.username))
    db.log_user_action(g.username, "UPDATE_SCHEDULE_SLOT",
                       payload=f"id={sid} {d}", ip=request.remote_addr)
    return jsonify({"ok": True})


@bp.delete("/api/schedule/<int:sid>")
@require_auth
def api_schedule_delete(sid: int):
    db.delete_schedule_slot(sid)
    queue.put(cmd_reload_schedule(username=g.username))
    db.log_user_action(g.username, "DELETE_SCHEDULE_SLOT",
                       payload=f"id={sid}", ip=request.remote_addr)
    return jsonify({"ok": True})
