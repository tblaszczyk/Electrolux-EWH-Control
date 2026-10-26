"""api/routes/energy.py — eLicznik Tauron: pobór/oddanie z sieci, depozyt
net-meteringowy (opust), prognoza do końca roku. Dane tylko z sieci (grid
import/export) — prawdziwa produkcja PV jest w api/routes/status.py /
core/inverter_client.py."""

import threading
import logging
from datetime import datetime, timedelta

from flask import Blueprint, jsonify, request, g
from api.auth import require_auth
from api.routes import config as config_routes
import data.database as db
from core.net_metering import compute_deposit, compute_projection

log = logging.getLogger("boiler.api.energy")

bp = Blueprint("energy", __name__)

_syncing = False
_sync_lock = threading.Lock()


def _is_configured() -> bool:
    cfg = config_routes._app_config
    return bool(cfg.get("tauron_enabled") and cfg.get("tauron_username") and cfg.get("tauron_password"))


@bp.get("/api/energy/configured")
@require_auth
def api_energy_configured():
    return jsonify({"configured": _is_configured()})


@bp.get("/api/energy/summary")
@require_auth
def api_energy_summary():
    if not _is_configured():
        return jsonify({"error": "Integracja eLicznika nie jest skonfigurowana"}), 503

    cfg = config_routes._app_config
    rate = cfg.get("net_metering_rate", 0.8)
    price = cfg.get("energy_price_pln_kwh")

    now = datetime.now()
    monthly_rows = db.get_energy_monthly_range(f"{now.year - 3}-01", f"{now.year}-12")
    deposit = compute_deposit(monthly_rows, rate=rate)
    projection = compute_projection(monthly_rows, rate=rate, year=now.year)

    savings = round(deposit["covered_by_deposit_kwh"] * price, 3) if price else None

    return jsonify({
        "tariff":                    db.get_energy_meta("tariff"),
        "meter_id":                  db.get_energy_meta("meter_id"),
        "meter_label":               db.get_energy_meta("meter_label"),
        "backfill_done":             db.get_energy_meta("backfill_done") == "1",
        "last_full_sync_at":         db.get_energy_meta("last_full_sync_at"),
        "last_incremental_sync_at":  db.get_energy_meta("last_incremental_sync_at"),
        "price_pln_kwh":             price,
        "savings_from_deposit_pln":  savings,
        "history_from":              monthly_rows[0]["period"] if monthly_rows else None,
        "deposit":                   deposit,
        "projection":                projection,
    })


@bp.get("/api/energy/daily")
@require_auth
def api_energy_daily():
    if not _is_configured():
        return jsonify({"error": "Integracja eLicznika nie jest skonfigurowana"}), 503
    days = min(int(request.args.get("days", 90)), 500)
    since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    return jsonify(db.get_energy_daily_from(since))


@bp.get("/api/energy/monthly")
@require_auth
def api_energy_monthly():
    if not _is_configured():
        return jsonify({"error": "Integracja eLicznika nie jest skonfigurowana"}), 503
    now = datetime.now()
    from_year = int(request.args.get("fromYear", now.year - 2))
    return jsonify(db.get_energy_monthly_range(f"{from_year}-01", f"{now.year}-12"))


@bp.post("/api/energy/sync")
@require_auth
def api_energy_sync():
    if not _is_configured():
        return jsonify({"error": "Integracja eLicznika nie jest skonfigurowana"}), 503

    global _syncing
    if _syncing:
        return jsonify({"ok": False, "error": "Synchronizacja już trwa"}), 409

    from core.tauron_sync import run_sync_once
    cfg = dict(config_routes._app_config)
    username = g.username

    def _bg():
        global _syncing
        with _sync_lock:
            _syncing = True
            try:
                run_sync_once(cfg)
            except Exception as e:
                log.error(f"Ręczna synchronizacja eLicznika nieudana: {e}")
            finally:
                _syncing = False

    threading.Thread(target=_bg, name="tauron_manual_sync", daemon=True).start()
    db.log_user_action(username, "ENERGY_SYNC", ip=request.remote_addr)
    return jsonify({"ok": True, "started": True})
