"""api/routes/config.py — konfiguracja systemu."""

from flask import Blueprint, jsonify, request, g
from api.auth import require_auth
import data.database as db

bp = Blueprint("config", __name__)

# Pola które użytkownik może zmieniać przez API
ALLOWED_PATCH = {
    "pv_hysteresis_s",
    "pv_target_temp",
    "pv_min_power_w",
    "pv_window_start",
    "pv_window_stop",
    "pv_power_mode",
    "pv_power_fixed_w",
    "idle_mode",
    "boiler_poll_s",
    "inverter_poll_s",
    "watchdog_timeout_s",
}

# Referencja do aktywnego configu — ustawiana przez app.py
_app_config: dict = {}


def set_config_ref(cfg: dict) -> None:
    global _app_config
    _app_config = cfg


@bp.get("/api/config")
@require_auth
def api_config_get():
    # Zwróć config bez sekretów
    safe = {k: v for k, v in _app_config.items()
            if k not in ("boiler_token", "boiler_pub", "secret_key",
                         "hypon_user", "hypon_pass",
                         "tuya_client_id", "tuya_client_secret",
                         "tauron_username", "tauron_password")}
    return jsonify(safe)


@bp.patch("/api/config")
@require_auth
def api_config_patch():
    d       = request.get_json(silent=True) or {}
    changed = {}

    INT_FIELDS = {
        "pv_hysteresis_s", "pv_target_temp", "pv_min_power_w", "pv_power_fixed_w",
        "boiler_poll_s", "inverter_poll_s", "watchdog_timeout_s",
    }
    STR_FIELDS = {"idle_mode", "pv_window_start", "pv_window_stop", "pv_power_mode"}

    for k, v in d.items():
        if k not in ALLOWED_PATCH:
            continue
        if k in INT_FIELDS:
            try:
                v = int(v)
                if v <= 0:
                    continue
            except (ValueError, TypeError):
                continue
        elif k == "idle_mode" and v not in ("off", "low_20", "low_30"):
            continue
        _app_config[k] = v
        changed[k] = v

    if not changed:
        return jsonify({"error": "Brak prawidłowych pól do zmiany"}), 400

    # Zaktualizuj runtime jeśli histereza się zmieniła
    if "watchdog_timeout_s" in changed:
        from core.watchdog import watchdog
        watchdog.set_timeout(changed["watchdog_timeout_s"])

    if "idle_mode" in changed:
        from service.command_queue import queue, cmd_set_idle_mode
        queue.put(cmd_set_idle_mode(changed["idle_mode"], username=g.username))

    # Zapisz do config.json
    import json, os
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
        import logging
        logging.getLogger("boiler.config").error(f"Błąd zapisu config: {e}")

    db.log_user_action(g.username, "CONFIG_PATCH",
                       payload=str(changed), ip=request.remote_addr)
    return jsonify({"ok": True, "changed": changed})


# ── Ustawienia połączenia (tylko admin) ───────────────────────

ALLOWED_CONNECTION = {
    "boiler_ip", "boiler_port",
    "boiler_poll_s", "inverter_poll_s",
    "hypon_station", "hypon_user",
}

@bp.get("/api/config/connection")
@require_auth
def api_config_connection_get():
    safe_keys = ALLOWED_CONNECTION | {"boiler_token", "boiler_pub"}
    return jsonify({k: _app_config.get(k) for k in safe_keys if k in _app_config})


@bp.patch("/api/config/connection")
@require_auth
def api_config_connection_patch():
    if not g.get("is_admin"):
        return jsonify({"error": "Wymagane uprawnienia administratora"}), 403
    d = request.get_json(silent=True) or {}
    INT_CONN = {"boiler_port", "boiler_poll_s", "inverter_poll_s"}
    changed = {}
    for k, v in d.items():
        if k in ALLOWED_CONNECTION:
            if k in INT_CONN:
                try: v = int(v)
                except: continue
            _app_config[k] = v
            changed[k] = v
    if not changed:
        return jsonify({"error": "Brak prawidłowych pól"}), 400

    # Zapisz do config.json
    import json, os
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

    db.log_user_action(g.username, "CONFIG_CONNECTION",
                       payload=str(changed), ip=request.remote_addr)
    return jsonify({"ok": True, "changed": changed,
                    "note": "Restart serwisu wymagany dla niektórych ustawień"})


# ── Ustawienia Tuya (opcjonalny realny pomiar mocy, tylko admin) ──

ALLOWED_TUYA = {
    "tuya_enabled", "tuya_client_id", "tuya_client_secret",
    "tuya_device_id", "tuya_api_region", "tuya_poll_s",
}

@bp.get("/api/config/tuya")
@require_auth
def api_config_tuya_get():
    safe = {k: _app_config.get(k) for k in ALLOWED_TUYA if k != "tuya_client_secret"}
    safe["tuya_client_secret_set"] = bool(_app_config.get("tuya_client_secret"))
    return jsonify(safe)


@bp.patch("/api/config/tuya")
@require_auth
def api_config_tuya_patch():
    if not g.get("is_admin"):
        return jsonify({"error": "Wymagane uprawnienia administratora"}), 403
    d = request.get_json(silent=True) or {}
    changed = {}
    for k, v in d.items():
        if k not in ALLOWED_TUYA:
            continue
        if k == "tuya_enabled":
            v = bool(v)
        elif k == "tuya_poll_s":
            try:
                v = int(v)
                if v < 10:
                    continue
            except (ValueError, TypeError):
                continue
        elif k == "tuya_client_secret" and not v:
            continue  # puste pole = nie nadpisuj istniejącego sekretu
        _app_config[k] = v
        changed[k] = v if k != "tuya_client_secret" else "***"
    if not changed:
        return jsonify({"error": "Brak prawidłowych pól"}), 400

    # Zapisz do config.json (ten sam wzorzec co reszta sekcji)
    import json, os
    cfg_file = os.environ.get("CFG_FILE", "/var/lib/boiler/config.json")
    try:
        existing = {}
        if os.path.exists(cfg_file):
            with open(cfg_file) as f:
                existing = json.load(f)
        existing.update({k: _app_config[k] for k in changed if k in ALLOWED_TUYA})
        os.makedirs(os.path.dirname(cfg_file), exist_ok=True)
        with open(cfg_file, "w") as f:
            json.dump(existing, f, indent=2, ensure_ascii=False)
    except Exception as e:
        return jsonify({"error": f"Błąd zapisu: {e}"}), 500

    db.log_user_action(g.username, "CONFIG_TUYA",
                       payload=str(changed), ip=request.remote_addr)
    return jsonify({"ok": True, "changed": changed,
                    "note": "Zmiany działają od razu, bez restartu serwisu"})


# ── Ustawienia Tauron eLicznik (opcjonalne dane z sieci, tylko admin) ──

ALLOWED_TAURON = {
    "tauron_enabled", "tauron_username", "tauron_password",
    "tauron_meter_id", "net_metering_rate", "energy_price_pln_kwh",
    "tauron_sync_hours",
}

@bp.get("/api/config/tauron")
@require_auth
def api_config_tauron_get():
    safe = {k: _app_config.get(k) for k in ALLOWED_TAURON if k != "tauron_password"}
    safe["tauron_password_set"] = bool(_app_config.get("tauron_password"))
    return jsonify(safe)


@bp.patch("/api/config/tauron")
@require_auth
def api_config_tauron_patch():
    if not g.get("is_admin"):
        return jsonify({"error": "Wymagane uprawnienia administratora"}), 403
    d = request.get_json(silent=True) or {}
    changed = {}
    for k, v in d.items():
        if k not in ALLOWED_TAURON:
            continue
        if k == "tauron_enabled":
            v = bool(v)
        elif k == "tauron_sync_hours":
            try:
                v = int(v)
                if v < 1:
                    continue
            except (ValueError, TypeError):
                continue
        elif k == "net_metering_rate":
            try:
                v = float(v)
                if not (0 < v <= 1):
                    continue
            except (ValueError, TypeError):
                continue
        elif k == "energy_price_pln_kwh":
            if v in (None, ""):
                v = None
            else:
                try:
                    v = float(v)
                except (ValueError, TypeError):
                    continue
        elif k == "tauron_password" and not v:
            continue  # puste pole = nie nadpisuj istniejącego hasła
        _app_config[k] = v
        changed[k] = v if k != "tauron_password" else "***"
    if not changed:
        return jsonify({"error": "Brak prawidłowych pól"}), 400

    # Zmiana danych logowania/licznika — wymuś ponowne logowanie przy kolejnej sync
    if any(k in changed for k in ("tauron_username", "tauron_password", "tauron_meter_id")):
        import core.tauron_sync as tauron_sync
        tauron_sync.reset_client()

    import json, os
    cfg_file = os.environ.get("CFG_FILE", "/var/lib/boiler/config.json")
    try:
        existing = {}
        if os.path.exists(cfg_file):
            with open(cfg_file) as f:
                existing = json.load(f)
        existing.update({k: _app_config[k] for k in changed if k in ALLOWED_TAURON})
        os.makedirs(os.path.dirname(cfg_file), exist_ok=True)
        with open(cfg_file, "w") as f:
            json.dump(existing, f, indent=2, ensure_ascii=False)
    except Exception as e:
        return jsonify({"error": f"Błąd zapisu: {e}"}), 500

    db.log_user_action(g.username, "CONFIG_TAURON",
                       payload=str(changed), ip=request.remote_addr)
    return jsonify({"ok": True, "changed": changed,
                    "note": "Zmiany działają od razu, bez restartu serwisu"})


@bp.get("/api/events/recent")
@require_auth
def api_events_recent():
    """Ostatnie zdarzenia do wyświetlenia w konfiguracji."""
    limit = min(int(request.args.get("limit", 50)), 200)
    try:
        with db._get_con() as con:
            rows = con.execute(
                "SELECT * FROM system_events ORDER BY ts DESC LIMIT ?",
                (limit,)
            ).fetchall()
        return jsonify([dict(r) for r in rows])
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.get("/api/system/info")
@require_auth
def api_system_info():
    """Informacje o systemie."""
    import os
    from datetime import datetime
    from service.runtime_state import runtime
    return jsonify({
        "version":     _app_config.get("version", "2.0.0"),
        "server_time": datetime.now().isoformat(),
        "uptime_state": runtime.current_state,
        "db_path":     _app_config.get("db_path", ""),
        "dry_run":     _app_config.get("dry_run", False),
    })
