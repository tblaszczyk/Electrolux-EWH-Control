"""
main.py
Entry point — łączy wszystkie moduły i uruchamia system.
Kolejność startu:
  1. Wczytaj config (.env + config.json)
  2. Inicjalizuj DB (tabele + migracje)
  3. Utwórz domyślnego usera (jeśli DB pusta)
  4. Uruchom Control Engine (wątek)
  5. Uruchom Flask API
"""

import os
import sys
import json
import logging
import threading
import time
from pathlib import Path

# ── Logging ───────────────────────────────────────────────────
LOG_DIR = os.environ.get("LOG_DIR", "/var/log/boiler")
Path(LOG_DIR).mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    # Tylko stdout: unit systemd dopisuje go do LOG_DIR/boiler.log (StandardOutput=append:),
    # a rotacje robi logrotate (/etc/logrotate.d/boiler2). Dodatkowy FileHandler dublowal kazdy wpis.
    handlers=[logging.StreamHandler(sys.stdout)]
)
log = logging.getLogger("boiler.main")

# ── Config ────────────────────────────────────────────────────

CFG_FILE = os.environ.get("CFG_FILE", "/var/lib/boiler/config.json")


def load_config() -> dict:
    from config.defaults import get_defaults
    cfg = get_defaults()

    # Nadpisania z pliku config.json
    if Path(CFG_FILE).exists():
        try:
            with open(CFG_FILE, "r") as f:
                overrides = json.load(f)
            cfg.update(overrides)
            log.info(f"Config: wczytano nadpisania z {CFG_FILE}")
        except Exception as e:
            log.error(f"Config: błąd wczytywania {CFG_FILE}: {e}")
    else:
        log.info(f"Config: brak {CFG_FILE} — używam defaults")

    return cfg


# ── Retencja danych — wątek ───────────────────────────────────

def _retention_loop(cfg: dict) -> None:
    """Codziennie o cleanup_hour usuwa stare rekordy."""
    import data.database as db
    from datetime import datetime

    cleanup_hour = cfg.get("cleanup_hour", 3)
    while True:
        now = datetime.now()
        if now.hour == cleanup_hour and now.minute < 1:
            log.info("Retencja: czyszczę stare rekordy...")
            result = db.purge_old_records(
                data_retention_days=cfg.get("data_retention_days", 365),
                log_retention_days= cfg.get("log_retention_days",  30),
            )
            log.info(f"Retencja: {result}")
        time.sleep(60)


# ── Detekcja zużycia wody — wątek (Faza 1, tylko obserwacyjne) ─

def _usage_scan_loop(cfg: dict) -> None:
    """Codziennie o usage_scan_hour skanuje ostatnie usage_scan_lookback_h
    boiler_history w poszukiwaniu zdarzeń poboru wody. Zero wpływu na
    sterowanie — patrz core/usage_detector.py."""
    import data.database as db
    from datetime import datetime, timedelta
    from core.usage_detector import run_scan

    if not cfg.get("usage_enabled", True):
        return
    scan_hour  = cfg.get("usage_scan_hour", 4)
    lookback_h = cfg.get("usage_scan_lookback_h", 48)
    while True:
        now = datetime.now()
        if now.hour == scan_hour and now.minute < 1:
            try:
                since = (now - timedelta(hours=lookback_h)).isoformat()
                result = run_scan(cfg, since_ts=since, until_ts=now.isoformat(), source="daily")
                log.info(f"UsageDetector: {result}")
            except Exception as e:
                log.error(f"UsageDetector: scan failed: {e}")
        time.sleep(60)


# ── Tuya — wątek odpytywania realnej mocy (opcjonalny, przełącznik w UI) ─

def _tuya_poll_loop(cfg: dict) -> None:
    """Co tuya_poll_s (gdy tuya_enabled=True) pobiera realną moc z wtyczki
    Tuya i zapisuje do tuya_readings. Sprawdza flagę co 5s, żeby przełącznik
    w Ustawieniach działał od razu, bez restartu serwisu. Tylko odczyt —
    zero wpływu na sterowanie bojlerem."""
    import data.database as db
    from service.runtime_state import runtime
    from core import tuya_factory

    client = None
    last_poll = 0.0

    while True:
        if cfg.get("tuya_enabled") and tuya_factory.configured(cfg, cfg.get("tuya_device_id")):
            now = time.time()
            poll_s = cfg.get("tuya_poll_s", 60)
            if now - last_poll >= poll_s:
                if client is None:
                    client = tuya_factory.make_client(cfg, cfg["tuya_device_id"])
                try:
                    status = client.get_status()
                    if status:
                        db.insert_tuya_reading(
                            power_w=status["power_w"], voltage_v=status["voltage_v"],
                            current_ma=status["current_ma"], switch=status["switch"],
                        )
                        runtime.update_tuya(status["power_w"], online=True)
                    else:
                        runtime.update_tuya(None, online=False)
                except Exception as e:
                    log.error(f"Tuya: poll failed: {e}")
                    runtime.update_tuya(None, online=False)
                last_poll = now
        else:
            client = None  # reset — dane logowania mogły się zmienić
        time.sleep(5)


# ── Pompa cyrkulacyjna — niezależna pętla sterująca ─────────────

def _pump_control_loop(cfg: dict) -> None:
    """Sterowanie pompą cyrkulacyjną (Tuya switch) — całkowicie niezależne
    od core/decision_logic.py i control_engine.py bojlera. Priorytet:
    manual (z limitem czasu) > harmonogram (opcjonalna pulsacja) > off.
    Pierwsza iteracja po starcie ZAWSZE wysyła komendę (synchronizacja
    stanu realnego urządzenia po restarcie serwisu, na wypadek gdyby
    zostało włączone przed nieplanowanym zatrzymaniem)."""
    import data.database as db
    from datetime import datetime
    from core import tuya_factory
    from core.pump_logic import compute_pump_state
    from core.pump_scheduler import pump_scheduler
    from service.pump_runtime import pump_runtime
    from core.notifier import notifier

    pump_scheduler.reload()
    client = None
    first_tick = True
    poll_s = cfg.get("pump_poll_s", 10)

    while True:
        try:
            device_id = cfg.get("pump_device_id")
            if not device_id:
                time.sleep(poll_s)
                continue

            if client is None:
                client = tuya_factory.make_client(cfg, device_id)

            mode = cfg.get("pump_mode", "off")

            # Koniec jednorazowego trybu ręcznego → automatyczny powrót do
            # harmonogramu (żeby nie zostawać w "Tryb ręczny — czas minął"
            # bez ponownej ingerencji użytkownika).
            if mode == "manual" and pump_runtime.manual_until and datetime.now() >= pump_runtime.manual_until:
                from api.routes.pump import _save_pump_mode
                _save_pump_mode("schedule")
                pump_runtime.clear_manual()
                mode = "schedule"
                log.info("Pump: koniec trybu ręcznego — automatyczny powrót do harmonogramu")

            active_slot = pump_scheduler.get_active_slot() if mode == "schedule" else None
            should_be_on, reason = compute_pump_state(
                mode=mode,
                manual_until=pump_runtime.manual_until,
                manual_target=pump_runtime.manual_target,
                active_slot=active_slot,
            )

            if should_be_on != pump_runtime.current_on or first_tick:
                ok = client.set_switch(should_be_on, dp_code=cfg.get("pump_switch_dp", "switch_1"))
                if ok:
                    if should_be_on and pump_runtime.open_history_id is None:
                        source = active_slot.get("label") if mode == "schedule" and active_slot else "ręcznie"
                        hid = db.insert_pump_event_start(trigger=mode, source_label=source or "")
                        pump_runtime.set_open_history_id(hid)
                    elif not should_be_on and pump_runtime.open_history_id is not None:
                        db.close_pump_event(pump_runtime.open_history_id)
                        pump_runtime.set_open_history_id(None)
                    pump_runtime.update_state(should_be_on, reason)
                    log.info(f"Pump: {'WŁĄCZONA' if should_be_on else 'WYŁĄCZONA'} — {reason}")
                else:
                    log.error(f"Pump: komenda set_switch({should_be_on}) nieudana")
                notifier.track(
                    "pump_cmd", bad=not ok, after_s=60,
                    title="Bojler2: pompa nie reaguje",
                    msg=(f"Komenda {'włącz' if should_be_on else 'wyłącz'} pompę nie przechodzi od ponad minuty. "
                         f"{getattr(client, 'auth_error', None) or 'Sprawdź połączenie z Tuya (logi boiler2).'}"),
                    ok_title="Bojler2: pompa znów reaguje", ok_msg="Komendy do pompy przechodzą.")
                first_tick = False
            else:
                pump_runtime.update_state(should_be_on, reason)  # odśwież powód/licznik czasu

            auth_err = getattr(client, "auth_error", None)
            notifier.track(
                "tuya_session", bad=bool(auth_err), after_s=0,
                title="Bojler2: sesja Tuya wygasła",
                msg=f"{auth_err} Pompa nie będzie sterowana, dopóki nie zalogujesz się ponownie kodem QR.",
                ok_title="Bojler2: sesja Tuya odnowiona", ok_msg="Sesja Tuya działa.")
            notifier.track("pump_loop", bad=False, after_s=60, title="", msg="",
                           ok_title="Bojler2: pętla pompy działa", ok_msg="Pętla sterowania pompą działa poprawnie.")

        except Exception as e:
            log.error(f"Pump: control loop error: {e}")
            notifier.track("pump_loop", bad=True, after_s=60,
                           title="Bojler2: błąd pętli pompy", msg=f"Powtarzający się błąd: {e}")

        time.sleep(poll_s)


# ── Tauron eLicznik — wątek synchronizacji (opcjonalny, przełącznik w UI) ─

def _tauron_sync_loop(cfg: dict) -> None:
    """Co tauron_sync_hours (gdy tauron_enabled=True) synchronizuje dane
    z eLicznika Taurona (pobór/oddanie z sieci — net-metering). Sprawdza
    flagę co 5s, żeby przełącznik w Ustawieniach działał od razu, bez
    restartu serwisu. Pierwsza synchronizacja po włączeniu robi pełny
    backfill (ostatnie ~14 miesięcy + historia roczna), kolejne są
    przyrostowe. Tylko odczyt — zero wpływu na sterowanie bojlerem."""
    from core.tauron_sync import run_sync_once

    last_sync = 0.0
    while True:
        if cfg.get("tauron_enabled") and cfg.get("tauron_username") and cfg.get("tauron_password"):
            now = time.time()
            interval_s = cfg.get("tauron_sync_hours", 6) * 3600
            if now - last_sync >= interval_s:
                try:
                    run_sync_once(cfg)
                except Exception as e:
                    log.error(f"Tauron: synchronizacja nieudana: {e}")
                last_sync = now
        else:
            last_sync = 0.0  # gdy wyłączone, wymuś pełny cykl zaraz po włączeniu
        time.sleep(5)


# ══════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════

def main():
    log.info("=" * 60)
    log.info("Boiler Control System v2.0 — start")
    log.info("=" * 60)

    # 1. Config
    cfg = load_config()
    log.info(f"Port: {cfg['port']} | dry_run: {cfg['dry_run']}")

    # 2. DB
    import data.database as db
    db.configure(cfg["db_path"])
    db.init_db()

    # 3. Domyślny user
    default_user = os.environ.get("DEFAULT_USER", "admin")
    default_pass = os.environ.get("DEFAULT_PASS", "admin")
    db.ensure_default_user(default_user, default_pass)

    # 4. Klienty sprzętowe
    from core.boiler_client   import BoilerClient
    from core.inverter_client import InverterClient

    boiler_client = BoilerClient(
        ip=         cfg["boiler_ip"],
        port=       cfg["boiler_port"],
        token=      cfg["boiler_token"],
        pub_key=    cfg["boiler_pub"],
        retry_count=cfg["retry_count"],
        dry_run=    cfg["dry_run"],
    )
    inverter_client = InverterClient(
        username=   cfg["hypon_user"],
        password=   cfg["hypon_pass"],
        station_id= str(cfg["hypon_station"]),
    )

    # 5. Control Engine
    from core.control_engine import ControlEngine
    engine = ControlEngine(cfg, boiler_client, inverter_client)
    engine.start()

    # 6. Wątek retencji danych
    t_retention = threading.Thread(
        target=_retention_loop, args=(cfg,),
        name="retention", daemon=True
    )
    t_retention.start()

    # 6b. Wątek detekcji zużycia wody (Faza 1 — obserwacyjny)
    t_usage = threading.Thread(
        target=_usage_scan_loop, args=(cfg,),
        name="usage_detector", daemon=True
    )
    t_usage.start()

    # 6c. Wątek odczytu Tuya (opcjonalny, sterowany przełącznikiem w UI)
    t_tuya = threading.Thread(
        target=_tuya_poll_loop, args=(cfg,),
        name="tuya_poll", daemon=True
    )
    t_tuya.start()

    # 6d. Wątek sterowania pompą cyrkulacyjną (niezależny od bojlera)
    t_pump = threading.Thread(
        target=_pump_control_loop, args=(cfg,),
        name="pump_control", daemon=True
    )
    t_pump.start()

    # 6e. Wątek synchronizacji eLicznika Tauron (opcjonalny, przełącznik w UI)
    t_tauron = threading.Thread(
        target=_tauron_sync_loop, args=(cfg,),
        name="tauron_sync", daemon=True
    )
    t_tauron.start()

    from core.notifier import send as _ntfy_send
    threading.Thread(target=_ntfy_send, daemon=True, args=(
        "Bojler2 uruchomiony", "Usługa boiler2 wystartowała (restart lub wdrożenie).", "min", "information_source")).start()

    # 7. Flask API
    from api.app import create_app
    app = create_app(cfg)

    log.info(f"API dostępne na http://0.0.0.0:{cfg['port']}")
    log.info("=" * 60)

    app.run(
        host="0.0.0.0",
        port=cfg["port"],
        debug=False,
        threaded=True,
        use_reloader=False,
    )


if __name__ == "__main__":
    main()
