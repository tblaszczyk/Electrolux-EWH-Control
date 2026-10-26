"""
data/models.py
Definicje tabel SQLite jako stałe SQL.
Używane przez migrations.py i database.py.
"""

# ── Wersja schematu ────────────────────────────────────────────
SCHEMA_VERSION = 7

# ══════════════════════════════════════════════════════════════
# CREATE TABLE statements
# ══════════════════════════════════════════════════════════════

SQL_CREATE_SCHEMA_VERSION = """
CREATE TABLE IF NOT EXISTS schema_version (
    version     INTEGER NOT NULL,
    applied_at  TEXT    NOT NULL
);
"""

SQL_CREATE_BOILER_HISTORY = """
CREATE TABLE IF NOT EXISTS boiler_history (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    ts              TEXT    NOT NULL,
    temp_current    REAL,
    temp_target     REAL,
    power_w         INTEGER,
    state           TEXT,
    mode            TEXT,
    pv_power_w      REAL,
    source          TEXT    DEFAULT 'poll'
);
"""

SQL_CREATE_SYSTEM_EVENTS = """
CREATE TABLE IF NOT EXISTS system_events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          TEXT    NOT NULL,
    category    TEXT    NOT NULL,
    state_from  TEXT,
    state_to    TEXT,
    mode        TEXT,
    reason      TEXT,
    message     TEXT
);
"""

SQL_CREATE_USER_ACTIONS = """
CREATE TABLE IF NOT EXISTS user_actions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          TEXT    NOT NULL,
    username    TEXT    NOT NULL,
    action      TEXT    NOT NULL,
    payload     TEXT,
    ip          TEXT
);
"""

SQL_CREATE_AUTH_LOG = """
CREATE TABLE IF NOT EXISTS auth_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          TEXT    NOT NULL,
    username    TEXT    NOT NULL,
    success     INTEGER NOT NULL,
    ip          TEXT
);
"""

SQL_CREATE_USERS = """
CREATE TABLE IF NOT EXISTS users (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    username        TEXT    NOT NULL UNIQUE,
    password_hash   TEXT    NOT NULL,
    created_at      TEXT    NOT NULL,
    is_admin        INTEGER DEFAULT 0
);
"""

SQL_CREATE_SCHEDULE_SLOTS = """
CREATE TABLE IF NOT EXISTS schedule_slots (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    label       TEXT,
    days        TEXT    NOT NULL,
    time_start  TEXT    NOT NULL,
    time_stop   TEXT    NOT NULL,
    temp_c      INTEGER NOT NULL,
    power_w     INTEGER NOT NULL DEFAULT 2000,
    enabled     INTEGER NOT NULL DEFAULT 1,
    created_at  TEXT    NOT NULL
);
"""

SQL_CREATE_DRAW_EVENTS = """
CREATE TABLE IF NOT EXISTS draw_events (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    start_ts        TEXT    NOT NULL,
    end_ts          TEXT    NOT NULL,
    temp_before     REAL,
    temp_after      REAL,
    drop_c          REAL    NOT NULL,
    duration_min    REAL,
    n_bursts        INTEGER,
    category        TEXT    NOT NULL,
    source          TEXT    DEFAULT 'daily'
);
"""

SQL_CREATE_TUYA_READINGS = """
CREATE TABLE IF NOT EXISTS tuya_readings (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    ts              TEXT    NOT NULL,
    power_w         REAL,
    voltage_v       REAL,
    current_ma      REAL,
    switch          INTEGER
);
"""

SQL_CREATE_PUMP_SCHEDULE_SLOTS = """
CREATE TABLE IF NOT EXISTS pump_schedule_slots (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    label           TEXT,
    days            TEXT    NOT NULL,
    time_start      TEXT    NOT NULL,
    time_stop       TEXT    NOT NULL,
    cycle_on_min    INTEGER,
    cycle_off_min   INTEGER,
    enabled         INTEGER NOT NULL DEFAULT 1,
    created_at      TEXT    NOT NULL
);
"""

SQL_CREATE_PUMP_HISTORY = """
CREATE TABLE IF NOT EXISTS pump_history (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    start_ts        TEXT    NOT NULL,
    end_ts          TEXT,
    duration_min    REAL,
    trigger         TEXT    NOT NULL,
    source_label    TEXT
);
"""

SQL_CREATE_ENERGY_DAILY = """
CREATE TABLE IF NOT EXISTS energy_daily (
    date            TEXT PRIMARY KEY,
    imported_kwh    REAL,
    exported_kwh    REAL,
    raw_imported_kwh REAL,
    raw_exported_kwh REAL,
    updated_at      TEXT NOT NULL
);
"""

SQL_CREATE_ENERGY_MONTHLY = """
CREATE TABLE IF NOT EXISTS energy_monthly (
    period          TEXT PRIMARY KEY,
    imported_kwh    REAL,
    exported_kwh    REAL,
    raw_imported_kwh REAL,
    raw_exported_kwh REAL,
    updated_at      TEXT NOT NULL
);
"""

SQL_CREATE_ENERGY_META = """
CREATE TABLE IF NOT EXISTS energy_meta (
    key     TEXT PRIMARY KEY,
    value   TEXT
);
"""

# ══════════════════════════════════════════════════════════════
# INDEXES
# ══════════════════════════════════════════════════════════════

SQL_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_bh_ts  ON boiler_history(ts);
CREATE INDEX IF NOT EXISTS idx_se_ts  ON system_events(ts);
CREATE INDEX IF NOT EXISTS idx_ua_ts  ON user_actions(ts);
CREATE INDEX IF NOT EXISTS idx_al_ts  ON auth_log(ts);
CREATE UNIQUE INDEX IF NOT EXISTS idx_de_unique ON draw_events(start_ts, end_ts);
CREATE INDEX IF NOT EXISTS idx_de_start_ts       ON draw_events(start_ts);
CREATE INDEX IF NOT EXISTS idx_de_category       ON draw_events(category);
CREATE INDEX IF NOT EXISTS idx_tuya_ts           ON tuya_readings(ts);
CREATE INDEX IF NOT EXISTS idx_ph_start_ts       ON pump_history(start_ts);
"""

# ══════════════════════════════════════════════════════════════
# ALL TABLES — kolejność ważna (schema_version pierwsza)
# ══════════════════════════════════════════════════════════════

ALL_TABLES = [
    SQL_CREATE_SCHEMA_VERSION,
    SQL_CREATE_BOILER_HISTORY,
    SQL_CREATE_SYSTEM_EVENTS,
    SQL_CREATE_USER_ACTIONS,
    SQL_CREATE_AUTH_LOG,
    SQL_CREATE_USERS,
    SQL_CREATE_SCHEDULE_SLOTS,
    SQL_CREATE_DRAW_EVENTS,
    SQL_CREATE_TUYA_READINGS,
    SQL_CREATE_PUMP_SCHEDULE_SLOTS,
    SQL_CREATE_PUMP_HISTORY,
    SQL_CREATE_ENERGY_DAILY,
    SQL_CREATE_ENERGY_MONTHLY,
    SQL_CREATE_ENERGY_META,
]
