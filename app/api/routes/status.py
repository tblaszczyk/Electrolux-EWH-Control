"""api/routes/status.py — odczyt stanu i historii."""

from flask import Blueprint, jsonify, request
from api.auth import require_auth
from api.routes import config as config_routes
from service.runtime_state import runtime
from core.watchdog import watchdog
from core.scheduler import scheduler
import data.database as db

bp = Blueprint("status", __name__)


@bp.get("/api/status")
@require_auth
def api_status():
    snap = runtime.snapshot()
    snap["watchdog"] = watchdog.status()
    snap["scheduler"] = scheduler.status()

    if config_routes._app_config.get("tuya_enabled"):
        snap["energy_today_kwh"] = db.get_tuya_energy_today()
        snap["energy_source"] = "tuya"
    else:
        try:
            with db._get_con() as con:
                rows = con.execute(
                    "SELECT power_w FROM boiler_history WHERE ts >= date('now','localtime') AND power_w > 0"
                ).fetchall()
            snap["energy_today_kwh"] = round(sum(r["power_w"] for r in rows) / 60 / 1000, 3)
        except Exception:
            snap["energy_today_kwh"] = None
        snap["energy_source"] = "power_w"

    return jsonify(snap)


@bp.get("/api/history")
@require_auth
def api_history():
    hours = min(int(request.args.get("hours", 24)), 168)  # max 7 dni
    return jsonify(db.get_boiler_history(hours=hours))


@bp.get("/api/tuya/history")
@require_auth
def api_tuya_history():
    """Surowe odczyty mocy z wtyczki Tuya — do nałożenia na wykres."""
    hours = min(int(request.args.get("hours", 24)), 168)
    return jsonify(db.get_tuya_readings(hours=hours))


@bp.get("/api/events")
@require_auth
def api_events():
    hours    = min(int(request.args.get("hours", 24)), 168)
    category = request.args.get("category")
    return jsonify(db.get_events(hours=hours, category=category))


@bp.get("/api/ping")
def api_ping():
    from datetime import datetime
    return jsonify({"ok": True, "ts": datetime.now().isoformat()})


@bp.get("/api/energy")
@require_auth
def api_energy():
    # Konwertuj days= na range= dla kompatybilności
    days = request.args.get('days', 14, type=int)
    if days <= 7:
        range_p = '7d'
    elif days <= 30:
        range_p = '30d'
    elif days <= 90:
        range_p = '3m'
    else:
        range_p = '12m'
    from flask import request as req
    # Podmień parametr i wywołaj api_economy
    with req.environ['werkzeug.request'].environ as env:
        pass
    return api_economy()

@bp.get("/api/economy")
@require_auth
def api_economy():
    """
    Statystyki ekonomiczne z DB.
    ?range=7d|30d|3m|12m
    Zwraca: daily[] i monthly[] z podziałem na PV vs sieć [kWh]
    """
    range_param = request.args.get("range", "30d")

    # Przelicz zakres na godziny
    hours_map = {"7d": 168, "30d": 720, "3m": 2160, "12m": 8760}
    hours = hours_map.get(range_param, 720)

    try:
        with db._get_con() as con:
            rows = con.execute("""
                SELECT
                    strftime('%Y-%m-%d', ts) as day,
                    strftime('%Y-%m',    ts) as month,
                    mode,
                    power_w
                FROM boiler_history
                WHERE ts >= datetime('now', ? || ' hours')
                  AND power_w IS NOT NULL
                  AND power_w > 0
                ORDER BY ts ASC
            """, (f"-{hours}",)).fetchall()

        # Grupuj dziennie
        daily = {}
        monthly = {}

        for row in rows:
            day   = row["day"]
            month = row["month"]
            mode  = row["mode"] or ""
            kwh   = (row["power_w"] / 60) / 1000  # próbka co 60s

            # Dzienne
            if day not in daily:
                daily[day] = {"day": day, "pv": 0.0, "grid": 0.0, "total": 0.0}
            if mode == "PV":
                daily[day]["pv"]   += kwh
            else:
                daily[day]["grid"] += kwh
            daily[day]["total"] += kwh

            # Miesięczne
            if month not in monthly:
                monthly[month] = {"month": month, "pv": 0.0, "grid": 0.0, "total": 0.0}
            if mode == "PV":
                monthly[month]["pv"]   += kwh
            else:
                monthly[month]["grid"] += kwh
            monthly[month]["total"] += kwh

        # Zaokrąglij
        daily_list   = []
        for d in daily.values():
            daily_list.append({
                "day":   d["day"],
                "pv":    round(d["pv"],    3),
                "grid":  round(d["grid"],  3),
                "total": round(d["total"], 3),
                "pct_pv": round(d["pv"] / d["total"] * 100, 1) if d["total"] > 0 else 0,
            })

        monthly_list = []
        for m in monthly.values():
            monthly_list.append({
                "month":  m["month"],
                "pv":     round(m["pv"],    3),
                "grid":   round(m["grid"],  3),
                "total":  round(m["total"], 3),
                "pct_pv": round(m["pv"] / m["total"] * 100, 1) if m["total"] > 0 else 0,
            })

        energy_source = "power_w"
        if config_routes._app_config.get("tuya_enabled"):
            # Tuya mierzy tylko sumę (nie rozróżnia PV/sieć) — bierzemy realną,
            # dokładną sumę dzienną z wtyczki i przeskalowujemy nią proporcje
            # PV/sieć wyliczone z mode= w boiler_history (przybliżenie, ale
            # dużo dokładniejsze niż sama metoda power_w).
            tuya_daily = {r["day"]: r["kwh"] for r in db.get_tuya_energy_per_day(days=hours // 24 + 1)}
            for d in daily_list:
                real_kwh = tuya_daily.get(d["day"])
                if real_kwh is not None:
                    ratio = (real_kwh / d["total"]) if d["total"] > 0 else 0
                    d["pv"]    = round(d["pv"] * ratio, 3)
                    d["grid"]  = round(real_kwh - d["pv"], 3)
                    d["total"] = round(real_kwh, 3)
                    d["pct_pv"] = round(d["pv"] / d["total"] * 100, 1) if d["total"] > 0 else 0
            energy_source = "tuya"

            # Miesięczne — przelicz z już skorygowanych danych dziennych,
            # żeby sumy dzienne i miesięczne były spójne.
            monthly_corrected = {}
            for d in daily_list:
                month = d["day"][:7]
                m = monthly_corrected.setdefault(month, {"month": month, "pv": 0.0, "grid": 0.0, "total": 0.0})
                m["pv"] += d["pv"]; m["grid"] += d["grid"]; m["total"] += d["total"]
            monthly_list = [
                {**m, "pv": round(m["pv"], 3), "grid": round(m["grid"], 3), "total": round(m["total"], 3),
                 "pct_pv": round(m["pv"] / m["total"] * 100, 1) if m["total"] > 0 else 0}
                for m in monthly_corrected.values()
            ]

        # Podsumowanie całego okresu
        total_pv    = sum(d["pv"]    for d in daily_list)
        total_grid  = sum(d["grid"]  for d in daily_list)
        total_all   = total_pv + total_grid
        pct_pv      = round(total_pv / total_all * 100, 1) if total_all > 0 else 0

        return jsonify({
            "range":    range_param,
            "energy_source": energy_source,
            "summary":  {
                "total_kwh":  round(total_all,  3),
                "pv_kwh":     round(total_pv,   3),
                "grid_kwh":   round(total_grid, 3),
                "pct_pv":     pct_pv,
            },
            "daily":    daily_list,
            "monthly":  monthly_list,
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500
