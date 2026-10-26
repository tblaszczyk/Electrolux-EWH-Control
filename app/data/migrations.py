"""
data/migrations.py
Wersjonowanie schematu SQLite — bez zewnętrznych bibliotek.
Przy starcie: check_and_migrate() stosuje wszystkie brakujące migracje.
"""

import sqlite3
import logging
from datetime import datetime
from data.models import SCHEMA_VERSION

log = logging.getLogger("boiler.migrations")

# ══════════════════════════════════════════════════════════════
# MIGRACJE — dodawaj kolejne jako funkcje _migrate_vN
# ══════════════════════════════════════════════════════════════

def _migrate_v1(con: sqlite3.Connection):
    """v1 → tabele bazowe (patrz models.py — tworzone przez init_db)."""
    # Tabele tworzy init_db() przed migracjami.
    # Tu możemy dodać dane startowe (np. domyślny user).
    log.info("Migration v1: schema bazowy OK")


def _migrate_v2(con: sqlite3.Connection):
    """v2 → draw_events (tabelę tworzy init_db()/ALL_TABLES — wpis czysto ewidencyjny)."""
    log.info("Migration v2: draw_events OK")


def _migrate_v3(con: sqlite3.Connection):
    """v3 → przebudowa draw_events: z pojedynczych punktów (trough) na sesje
    (start_ts..end_ts, n_bursts) — wykrywanie oknowe zamiast punktowego.
    Stare dane doradcze/eksperymentalne, bezpieczne do odtworzenia backfillem."""
    from data.models import SQL_CREATE_DRAW_EVENTS
    con.execute("DROP TABLE IF EXISTS draw_events")
    con.executescript(SQL_CREATE_DRAW_EVENTS)
    con.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_de_unique ON draw_events(start_ts, end_ts)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_de_start_ts ON draw_events(start_ts)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_de_category ON draw_events(category)")
    log.info("Migration v3: draw_events przebudowane na model sesji (uruchom ponownie backfill_usage.py)")


def _migrate_v4(con: sqlite3.Connection):
    """v4 → tuya_readings (tabelę tworzy ALL_TABLES — wpis czysto ewidencyjny)."""
    log.info("Migration v4: tuya_readings OK")


def _migrate_v5(con: sqlite3.Connection):
    """v5 → pump_schedule_slots + pump_history (tabelę tworzy ALL_TABLES — wpis czysto ewidencyjny)."""
    log.info("Migration v5: pump_schedule_slots + pump_history OK")


def _migrate_v6(con: sqlite3.Connection):
    """v6 → energy_daily + energy_monthly + energy_meta (eLicznik Tauron;
    tabele tworzy ALL_TABLES — wpis czysto ewidencyjny)."""
    log.info("Migration v6: energy_daily/energy_monthly/energy_meta OK")


def _migrate_v7(con: sqlite3.Connection):
    """v7 → energy_daily/energy_monthly: imported/exported = po bilansowaniu godzinowym,
    raw_* = surowe odczyty licznika. Stare wiersze (surowe) zostaną nadpisane backfillem."""
    for table in ("energy_daily", "energy_monthly"):
        cols = {r[1] for r in con.execute(f"PRAGMA table_info({table})").fetchall()}
        for col in ("raw_imported_kwh", "raw_exported_kwh"):
            if col not in cols:
                con.execute(f"ALTER TABLE {table} ADD COLUMN {col} REAL")
    con.execute("DELETE FROM energy_meta WHERE key='backfill_done'")
    log.info("Migration v7: energy_* raw columns OK (backfill eLicznika zostanie powtórzony)")


# Rejestr migracji: {numer_wersji: funkcja}
MIGRATIONS: dict = {
    1: _migrate_v1,
    2: _migrate_v2,
    3: _migrate_v3,
    4: _migrate_v4,
    5: _migrate_v5,
    6: _migrate_v6,
    7: _migrate_v7,
}


# ══════════════════════════════════════════════════════════════
# PUBLIC API
# ══════════════════════════════════════════════════════════════

def get_current_version(con: sqlite3.Connection) -> int:
    """Zwraca aktualną wersję schematu z DB (0 jeśli brak)."""
    try:
        row = con.execute(
            "SELECT version FROM schema_version ORDER BY version DESC LIMIT 1"
        ).fetchone()
        return row[0] if row else 0
    except sqlite3.OperationalError:
        return 0


def check_and_migrate(con: sqlite3.Connection) -> None:
    """
    Sprawdza wersję schematu i aplikuje wszystkie brakujące migracje
    w kolejności rosnącej. Bezpieczne do wywołania przy każdym starcie.
    """
    current = get_current_version(con)
    target  = SCHEMA_VERSION

    if current >= target:
        log.info(f"Migrations: schema aktualne (v{current})")
        return

    log.info(f"Migrations: aktualizacja v{current} → v{target}")

    for version in sorted(MIGRATIONS.keys()):
        if version <= current:
            continue
        log.info(f"Migrations: aplikuję v{version}...")
        try:
            MIGRATIONS[version](con)
            con.execute(
                "INSERT INTO schema_version (version, applied_at) VALUES (?, ?)",
                (version, datetime.now().isoformat())
            )
            con.commit()
            log.info(f"Migrations: v{version} zastosowana")
        except Exception as e:
            log.error(f"Migrations: błąd w v{version}: {e}")
            con.rollback()
            raise RuntimeError(f"Migration v{version} failed: {e}") from e

    log.info(f"Migrations: gotowe — schema v{target}")
