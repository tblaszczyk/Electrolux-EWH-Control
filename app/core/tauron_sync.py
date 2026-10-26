"""
core/tauron_sync.py
Synchronizacja danych z eLicznika Tauron do lokalnej bazy (energy_daily /
energy_monthly; wartości po bilansowaniu godzinowym + surowe odczyty). Wywoływane cyklicznie z main.py (wątek _tauron_sync_loop)
oraz ręcznie z api/routes/energy.py (przycisk "Synchronizuj teraz").
"""

import time
import logging
from calendar import monthrange
from datetime import datetime, timedelta

import data.database as db
from core.tauron_client import TauronClient
from core.net_metering import balance_hourly, aggregate_months

log = logging.getLogger("boiler.tauron_sync")

REQUEST_DELAY_S  = 0.3

_client: TauronClient = None


def _get_client(cfg: dict) -> TauronClient:
    global _client
    if _client is None:
        _client = TauronClient(
            username=cfg.get("tauron_username", ""),
            password=cfg.get("tauron_password", ""),
            meter_id=cfg.get("tauron_meter_id") or None,
        )
    return _client


def reset_client() -> None:
    """Wymusza ponowne logowanie przy kolejnej synchronizacji (np. po zmianie hasła)."""
    global _client
    _client = None


def _ensure_logged_in(cfg: dict) -> TauronClient:
    client = _get_client(cfg)
    if not client.logged_in:
        if not client.login():
            raise RuntimeError("Logowanie do eLicznika nieudane — sprawdź login/hasło w Ustawieniach")
    return client


def _sync_month(client: TauronClient, year: int, month: int) -> None:
    """Pobiera odczyty godzinowe miesiąca, bilansuje je godzinowo (art. 4 ust. 2b
    ustawy o OZE) i zapisuje sumy dzienne oraz miesięczne."""
    first = datetime(year, month, 1)
    to = min(datetime(year, month, monthrange(year, month)[1]), datetime.now())
    if first > to:
        return

    imp = client.get_hourly(first, to, "import")
    time.sleep(REQUEST_DELAY_S)
    exp = client.get_hourly(first, to, "export")
    time.sleep(REQUEST_DELAY_S)
    if not imp and not exp:
        return

    daily = balance_hourly(imp, exp)
    period = f"{year}-{month:02d}"
    month_days = {d: v for d, v in daily.items() if d.startswith(period)}
    for d, v in month_days.items():
        db.upsert_energy_daily(d, v["imported_kwh"], v["exported_kwh"],
                               v["raw_imported_kwh"], v["raw_exported_kwh"])
    m = aggregate_months(month_days).get(period)
    if m:
        db.upsert_energy_monthly(period, m["imported_kwh"], m["exported_kwh"],
                                 m["raw_imported_kwh"], m["raw_exported_kwh"])


def run_backfill(cfg: dict) -> None:
    client = _ensure_logged_in(cfg)
    now = datetime.now()

    # Od stycznia (rok−3): historia do prognozy + rozgrzanie depozytu (stan jest
    # wiarygodny dopiero 12 miesięcy po pierwszym wczytanym miesiącu).
    y, m = now.year - 3, 1
    while (y, m) <= (now.year, now.month):
        _sync_month(client, y, m)
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)

    selected = next((mm for mm in client.meters if mm["meter_id"] == client.meter_id), None)
    db.set_energy_meta("backfill_done", "1")
    db.set_energy_meta("tariff", client.tariff or "unknown")
    db.set_energy_meta("meter_id", client.meter_id or "")
    db.set_energy_meta("meter_label", selected["meter_name"] if selected else "")
    db.set_energy_meta("last_full_sync_at", datetime.now().isoformat())
    log.info(f"Tauron: backfill zakończony (licznik={client.meter_id})")


def run_incremental(cfg: dict) -> None:
    client = _ensure_logged_in(cfg)
    now = datetime.now()
    prev = now.replace(day=1) - timedelta(days=1)
    _sync_month(client, prev.year, prev.month)
    _sync_month(client, now.year, now.month)
    db.set_energy_meta("last_incremental_sync_at", datetime.now().isoformat())
    log.info("Tauron: synchronizacja przyrostowa zakończona")


def run_sync_once(cfg: dict) -> None:
    try:
        if db.get_energy_meta("backfill_done") != "1":
            run_backfill(cfg)
        else:
            run_incremental(cfg)
    except Exception:
        reset_client()
        raise
