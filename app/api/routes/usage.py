"""api/routes/usage.py — odczyt wykrytych zdarzeń poboru wody (read-only, doradcze)."""

from datetime import datetime, timedelta

from flask import Blueprint, jsonify, request
from api.auth import require_auth
import data.database as db
from core.usage_detector import compute_weekday_baseline, classify_duration_experimental

bp = Blueprint("usage", __name__)


@bp.get("/api/usage/events")
@require_auth
def api_usage_events():
    hours = min(int(request.args.get("hours", 168)), 24 * 180)
    category = request.args.get("category")  # session|subthreshold
    events = db.get_draw_events(hours=hours, category=category)
    return jsonify(classify_duration_experimental(events))


@bp.get("/api/usage/summary")
@require_auth
def api_usage_summary():
    """Dzienne liczby sesji poboru wody wieczorem (17-23h) + łączny czas trwania
    + sygnał baseline (mediana trailing 8 tyg. per dzień tygodnia) — czysto
    doradcze, bez żadnego wpływu na sterowanie."""
    range_param = request.args.get("range", "30d")
    hours_map = {"7d": 168, "30d": 720, "3m": 2160, "12m": 8760}
    hours = hours_map.get(range_param, 720)
    days = hours // 24

    # Baseline potrzebuje historii sprzed okna (do 8 tyg. wstecz) żeby liczyć
    # medianę dla najwcześniejszych dni żądanego zakresu.
    fetch_days = days + 8 * 7
    raw = db.get_draw_events_daily_counts(category="session", days=fetch_days)
    counts_by_day = {r["day"]: r["count"] for r in raw}
    duration_by_day = {r["day"]: r["total_duration_min"] for r in raw}

    # Dopełnij dni bez zdarzeń zerami — inaczej sygnał "zero" nigdy by się nie pojawił.
    today = datetime.now().date()
    all_days = [
        (today - timedelta(days=i)).isoformat()
        for i in range(fetch_days, -1, -1)
    ]
    daily_counts = [{"day": d, "count": counts_by_day.get(d, 0)} for d in all_days]

    with_signal = compute_weekday_baseline(daily_counts, baseline_weeks=8)
    for d in with_signal:
        d["total_duration_min"] = duration_by_day.get(d["day"], 0)

    # Zwróć tylko żądany zakres (fetch_days był tylko dla poprawnej bazy porównawczej)
    cutoff = (today - timedelta(days=days)).isoformat()
    visible = [d for d in with_signal if d["day"] >= cutoff]

    return jsonify({"range": range_param, "daily": visible})
