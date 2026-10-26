"""
config/defaults.py
Wszystkie wartości domyślne systemu — podzielone na sekcje.
Nadpisania użytkownika trafiają do config.json (wczytywane przy starcie).
NIE TRZYMAJ TU SEKRETÓW — używaj zmiennych środowiskowych / .env
"""

import os

# ══════════════════════════════════════════════════════════════
# SYSTEM
# ══════════════════════════════════════════════════════════════
SYSTEM = {
    "version":              "2.1.0",
    "port":                 8888,
    "control_loop_s":       10,      # pętla Control Engine
    "data_log_interval_s":  60,      # zapis historii do DB
    "boiler_poll_s":        20,      # co ile sekund odpytuj bojler
    "inverter_poll_s":      30,      # co ile sekund odpytuj inwerter
    "watchdog_timeout_s":   30,      # po ilu sekundach uznaj brak komunikacji
    "retry_count":          3,       # ile prób przed oznaczeniem błędu
    "dry_run":              False,   # True = loguj komendy, nie wysyłaj do bojlera
}

# ══════════════════════════════════════════════════════════════
# PV
# ══════════════════════════════════════════════════════════════
PV = {
    # Próg minimalny mocy PV do załączenia grzania [W]
    "pv_min_power_w":     700,

    # Okno czasowe — PV może grzać tylko w tym przedziale
    "pv_window_start":    "00:00",   # HH:MM
    "pv_window_stop":     "23:59",   # HH:MM

    # Histereza — czas stabilności przed zmianą poziomu [s]
    "pv_hysteresis_s":    30,

    # Temperatura docelowa gdy PV grzeje [°C]
    "pv_target_temp":     65,

    # Tryb mocy: "auto" = oblicz z nadwyżki PV, lub 700/1300/2000 = stała wartość
    "pv_power_mode":      "auto",

    # Stała moc (używana gdy pv_power_mode != "auto") [W]
    "pv_power_fixed_w":   2000,
}

# ══════════════════════════════════════════════════════════════
# SAFETY  (hard limits — nie zmieniaj bez powodu)
# ══════════════════════════════════════════════════════════════
SAFETY = {
    "max_temp_c":       75,   # bezwzględny limit — przekroczenie → ERROR
    "min_temp_manual_c": 20,  # minimalna nastawa manualna
    "max_temp_manual_c": 70,  # maksymalna nastawa manualna
    "temp_step_c":       5,   # krok nastawy temperatury
}

# ══════════════════════════════════════════════════════════════
# IDLE BEHAVIOR
# ══════════════════════════════════════════════════════════════
IDLE = {
    # "off"    = wyłącz grzanie (nastawa 0°C lub no_heat)
    # "low_20" = 20°C + limit 700W
    # "low_30" = 30°C + limit 700W
    "idle_mode":       "off",
    "idle_temp_low":   20,
    "idle_temp_mid":   30,
    "idle_power_w":    700,
}

# ══════════════════════════════════════════════════════════════
# USAGE DETECTION (Bojler Rev 2 — detekcja poboru wody, tylko doradcze)
# ══════════════════════════════════════════════════════════════
USAGE = {
    "usage_enabled":                 True,
    "usage_scan_hour":               4,     # godzina uruchomienia dziennego skanu
    "usage_scan_lookback_h":         48,    # okno re-skanowane każdego dnia
    "usage_active_rate_c_per_min":   0.3,   # próg tempa spadku uznawanego za "aktywny pobór"
                                             # (naturalne stygnięcie ~0.07°C/min — dużo wolniej)
    "usage_merge_gap_min":           15,    # przerwa łącząca sąsiednie "aktywne" odcinki w jedną sesję
    "usage_min_drop_c":              2.0,   # próg magnitudy dla "realnej" sesji poboru
    "usage_subthreshold_min_drop_c": 0.5,   # dolna granica logowania podprogowych sesji
    "usage_run_gap_max_min":         5,     # przerwa łamiąca ciągły odcinek "bez grzania"
    "usage_baseline_weeks":          8,     # okno trailing-median per dzień tygodnia
    "usage_evening_hour_start":      17,
    "usage_evening_hour_end":        23,
}

# ══════════════════════════════════════════════════════════════
# LOGGING & RETENTION
# ══════════════════════════════════════════════════════════════
LOGGING = {
    "data_retention_days":  365,  # boiler_history
    "log_retention_days":   30,   # system_events, user_actions, auth_log
    "cleanup_hour":         3,    # o której godzinie czyść stare rekordy
    "log_level":            "INFO",
}

# ══════════════════════════════════════════════════════════════
# HARDWARE (wartości domyślne — nadpisywane przez .env)
# ══════════════════════════════════════════════════════════════
HARDWARE = {
    "boiler_ip":        os.environ.get("BOILER_IP",     "192.168.20.21"),
    "boiler_port":      int(os.environ.get("BOILER_PORT",   "41122")),
    "boiler_token":     os.environ.get("BOILER_TOKEN",  ""),
    "boiler_pub":       os.environ.get("BOILER_PUB",    ""),

    "hypon_user":       os.environ.get("HYPON_USER",    ""),
    "hypon_pass":       os.environ.get("HYPON_PASS",    ""),
    "hypon_station":    os.environ.get("HYPON_STATION", ""),
}

# ══════════════════════════════════════════════════════════════
# TUYA (opcjonalne, realny pomiar mocy z inteligentnej wtyczki)
# ══════════════════════════════════════════════════════════════
TUYA = {
    "tuya_enabled":       False,   # przełącznik w Ustawieniach — domyślnie wyłączone
    "tuya_client_id":     os.environ.get("TUYA_CLIENT_ID",     ""),
    "tuya_client_secret": os.environ.get("TUYA_CLIENT_SECRET", ""),
    "tuya_device_id":     os.environ.get("TUYA_DEVICE_ID",     ""),
    "tuya_api_region":    os.environ.get("TUYA_API_REGION",    "eu"),
    "tuya_poll_s":        60,
    # "auto" = sharing gdy jest plik sesji, inaczej cloud; "cloud" = Tuya IoT Core (projekt deweloperski, kwota trial), "sharing" = Device Sharing
    # przez konto Smart Life (QR, bez IoT Core). Logowanie: python tools/tuya_login.py
    "tuya_backend":       os.environ.get("TUYA_BACKEND", "auto"),
    "tuya_session_file":  os.environ.get(
        "TUYA_SESSION_FILE",
        os.path.join(os.path.dirname(os.environ.get("CFG_FILE", "/var/lib/boiler/config.json")),
                     "tuya_session.json")),
}

# ══════════════════════════════════════════════════════════════
# POMPA CYRKULACYJNA (Tuya switch — osobne urządzenie od wtyczki bojlera)
# ══════════════════════════════════════════════════════════════
PUMP = {
    "pump_device_id": os.environ.get("PUMP_DEVICE_ID", ""),
    "pump_switch_dp": "switch_1",   # kod DP w Tuya — do zweryfikowania po podaniu urządzenia
    "pump_mode":      "off",        # "off" | "manual" | "schedule"
    "pump_poll_s":    10,
}

# ══════════════════════════════════════════════════════════════
# TAURON eLICZNIK (opcjonalne — dane z sieci: pobór/oddanie, net-metering)
# ══════════════════════════════════════════════════════════════
TAURON = {
    "tauron_enabled":       False,   # przełącznik w Ustawieniach — domyślnie wyłączone
    "tauron_username":      os.environ.get("TAURON_USERNAME", ""),
    "tauron_password":      os.environ.get("TAURON_PASSWORD", ""),
    "tauron_meter_id":      os.environ.get("TAURON_METER_ID", ""),  # puste = auto-detekcja
    "net_metering_rate":    0.8,     # 0.8 dla instalacji <=10kWp, 0.7 dla >10kWp
    "energy_price_pln_kwh": None,    # opcjonalnie, do szacowania oszczędności w zł
    "tauron_sync_hours":    6,       # co ile godzin synchronizować dane
}

# ══════════════════════════════════════════════════════════════
# AUTH
# ══════════════════════════════════════════════════════════════
AUTH = {
    "secret_key":   os.environ.get("SECRET_KEY",  "ZMIEN_TO_NA_SILNY_KLUCZ"),
    "session_days": 30,
}

# ══════════════════════════════════════════════════════════════
# DATABASE
# ══════════════════════════════════════════════════════════════
DATABASE = {
    "db_path": os.environ.get("DB_PATH", "/var/lib/boiler/boiler.db"),
}

# ══════════════════════════════════════════════════════════════
# MERGED CONFIG — jeden słownik do użycia w aplikacji
# ══════════════════════════════════════════════════════════════
def get_defaults() -> dict:
    """Zwraca płaski słownik wszystkich wartości domyślnych."""
    merged = {}
    for section in (SYSTEM, PV, SAFETY, IDLE, USAGE, LOGGING, HARDWARE, TUYA, PUMP, TAURON, AUTH, DATABASE):
        merged.update(section)
    return merged
