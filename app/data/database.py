"""
data/database.py
Warstwa danych SQLite — init, zapis, odczyt, retencja.
Jedyne miejsce w systemie które dotyka pliku DB.
"""

import sqlite3
import os
import logging
import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional

from data.models import ALL_TABLES, SQL_INDEXES
from data.migrations import check_and_migrate

log = logging.getLogger("boiler.db")

_db_path: str = "/var/lib/boiler/boiler.db"


def configure(db_path: str) -> None:
    """Ustaw ścieżkę do pliku DB (wywołaj przed init_db)."""
    global _db_path
    _db_path = db_path


def _get_con() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(_db_path), exist_ok=True)
    con = sqlite3.connect(_db_path, check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA foreign_keys=ON")
    return con


# ══════════════════════════════════════════════════════════════
# INIT
# ══════════════════════════════════════════════════════════════

def init_db() -> None:
    """Utwórz tabele i zastosuj migracje. Wywołaj raz przy starcie."""
    with _get_con() as con:
        for sql in ALL_TABLES:
            con.executescript(sql)
        con.executescript(SQL_INDEXES)
        con.commit()
        check_and_migrate(con)
    log.info(f"DB zainicjalizowana: {_db_path}")


# ══════════════════════════════════════════════════════════════
# BOILER HISTORY
# ══════════════════════════════════════════════════════════════

def insert_boiler_history(
    temp_current: float,
    temp_target: float,
    power_w: int,
    state: str,
    mode: str,
    pv_power_w: float,
    heating: bool = False,
    source: str = "poll"
) -> None:
    try:
        with _get_con() as con:
            con.execute(
                """INSERT INTO boiler_history
                   (ts, temp_current, temp_target, power_w, state, mode, pv_power_w, heating, source)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (datetime.now().isoformat(),
                 temp_current, temp_target, power_w,
                 state, mode, pv_power_w, 1 if heating else 0, source)
            )
    except Exception as e:
        log.error(f"DB insert_boiler_history: {e}")


def get_boiler_history(hours: int = 24) -> list:
    try:
        since = (datetime.now() - timedelta(hours=hours)).isoformat()
        with _get_con() as con:
            rows = con.execute(
                "SELECT * FROM boiler_history WHERE ts >= ? ORDER BY ts DESC",
                (since,)
            ).fetchall()
        return [dict(r) for r in rows]
    except Exception as e:
        log.error(f"DB get_boiler_history: {e}")
        return []


def iter_boiler_history_for_scan(since_ts: Optional[str] = None, until_ts: Optional[str] = None):
    """
    Generator (ts: datetime, temp_current: float|None, heating: bool) dla
    core/usage_detector.py — czyta w porcjach (fetchmany), żeby nie
    materializować całej historii (backfill = ~163 dni / 246k+ wierszy)
    naraz w pamięci, w przeciwieństwie do get_boiler_history().
    """
    con = _get_con()
    try:
        where, params = [], []
        if since_ts:
            where.append("ts >= ?"); params.append(since_ts)
        if until_ts:
            where.append("ts <= ?"); params.append(until_ts)
        clause = f"WHERE {' AND '.join(where)}" if where else ""
        cur = con.execute(
            f"SELECT ts, temp_current, heating FROM boiler_history {clause} ORDER BY ts ASC",
            params
        )
        while True:
            batch = cur.fetchmany(5000)
            if not batch:
                break
            for row in batch:
                try:
                    ts = datetime.fromisoformat(row["ts"])
                except Exception:
                    continue
                yield ts, row["temp_current"], bool(row["heating"])
    except Exception as e:
        log.error(f"DB iter_boiler_history_for_scan: {e}")
    finally:
        con.close()


# ══════════════════════════════════════════════════════════════
# SYSTEM EVENTS
# ══════════════════════════════════════════════════════════════

def log_event(
    category: str,
    message: str,
    state_from: str = None,
    state_to: str = None,
    mode: str = None,
    reason: str = None
) -> None:
    """Zapisz zdarzenie systemowe (zmiana stanu, decyzja CE, błąd)."""
    try:
        with _get_con() as con:
            con.execute(
                """INSERT INTO system_events
                   (ts, category, state_from, state_to, mode, reason, message)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (datetime.now().isoformat(),
                 category, state_from, state_to, mode, reason, message)
            )
    except Exception as e:
        log.error(f"DB log_event: {e}")


def get_events(hours: int = 24, category: str = None) -> list:
    try:
        since = (datetime.now() - timedelta(hours=hours)).isoformat()
        with _get_con() as con:
            if category:
                rows = con.execute(
                    "SELECT * FROM system_events WHERE ts >= ? AND category = ? ORDER BY ts DESC",
                    (since, category)
                ).fetchall()
            else:
                rows = con.execute(
                    "SELECT * FROM system_events WHERE ts >= ? ORDER BY ts DESC",
                    (since,)
                ).fetchall()
        return [dict(r) for r in rows]
    except Exception as e:
        log.error(f"DB get_events: {e}")
        return []


# ══════════════════════════════════════════════════════════════
# USER ACTIONS
# ══════════════════════════════════════════════════════════════

def log_user_action(
    username: str,
    action: str,
    payload: str = None,
    ip: str = None
) -> None:
    try:
        with _get_con() as con:
            con.execute(
                """INSERT INTO user_actions (ts, username, action, payload, ip)
                   VALUES (?, ?, ?, ?, ?)""",
                (datetime.now().isoformat(), username, action, payload, ip)
            )
    except Exception as e:
        log.error(f"DB log_user_action: {e}")


# ══════════════════════════════════════════════════════════════
# AUTH LOG
# ══════════════════════════════════════════════════════════════

def log_auth(username: str, success: bool, ip: str = None) -> None:
    try:
        with _get_con() as con:
            con.execute(
                "INSERT INTO auth_log (ts, username, success, ip) VALUES (?, ?, ?, ?)",
                (datetime.now().isoformat(), username, int(success), ip)
            )
    except Exception as e:
        log.error(f"DB log_auth: {e}")


# ══════════════════════════════════════════════════════════════
# USERS
# ══════════════════════════════════════════════════════════════

def _hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    h = hashlib.sha256(f"{salt}{password}".encode()).hexdigest()
    return f"{salt}:{h}"


def _verify_password(password: str, stored: str) -> bool:
    try:
        salt, h = stored.split(":", 1)
        return hashlib.sha256(f"{salt}{password}".encode()).hexdigest() == h
    except Exception:
        return False


def create_user(username: str, password: str, is_admin: bool = False) -> bool:
    try:
        with _get_con() as con:
            con.execute(
                """INSERT INTO users (username, password_hash, created_at, is_admin)
                   VALUES (?, ?, ?, ?)""",
                (username, _hash_password(password),
                 datetime.now().isoformat(), int(is_admin))
            )
        log.info(f"Użytkownik '{username}' utworzony")
        return True
    except sqlite3.IntegrityError:
        log.warning(f"Użytkownik '{username}' już istnieje")
        return False
    except Exception as e:
        log.error(f"DB create_user: {e}")
        return False


def verify_user(username: str, password: str) -> Optional[dict]:
    """Zwraca dict usera jeśli dane poprawne, None jeśli błędne."""
    try:
        with _get_con() as con:
            row = con.execute(
                "SELECT * FROM users WHERE username = ?", (username,)
            ).fetchone()
        if row and _verify_password(password, row["password_hash"]):
            return {"id": row["id"], "username": row["username"],
                    "is_admin": bool(row["is_admin"])}
        return None
    except Exception as e:
        log.error(f"DB verify_user: {e}")
        return None


def get_user(username: str) -> Optional[dict]:
    try:
        with _get_con() as con:
            row = con.execute(
                "SELECT id, username, is_admin, created_at FROM users WHERE username = ?",
                (username,)
            ).fetchone()
        return dict(row) if row else None
    except Exception as e:
        log.error(f"DB get_user: {e}")
        return None


def ensure_default_user(username: str, password: str) -> None:
    """Utwórz domyślnego usera jeśli tabela jest pusta."""
    try:
        with _get_con() as con:
            count = con.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        if count == 0:
            create_user(username, password, is_admin=True)
            log.info(f"Domyślny użytkownik '{username}' utworzony")
    except Exception as e:
        log.error(f"DB ensure_default_user: {e}")


# ══════════════════════════════════════════════════════════════
# SCHEDULE SLOTS
# ══════════════════════════════════════════════════════════════

def get_schedule_slots(enabled_only: bool = False) -> list:
    try:
        with _get_con() as con:
            if enabled_only:
                rows = con.execute(
                    "SELECT * FROM schedule_slots WHERE enabled=1 ORDER BY time_start"
                ).fetchall()
            else:
                rows = con.execute(
                    "SELECT * FROM schedule_slots ORDER BY time_start"
                ).fetchall()
        return [dict(r) for r in rows]
    except Exception as e:
        log.error(f"DB get_schedule_slots: {e}")
        return []


def add_schedule_slot(
    days: list,
    time_start: str,
    time_stop: str,
    temp_c: int,
    power_w: int,
    label: str = ""
) -> Optional[int]:
    try:
        import json
        with _get_con() as con:
            cur = con.execute(
                """INSERT INTO schedule_slots
                   (label, days, time_start, time_stop, temp_c, power_w, enabled, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, 1, ?)""",
                (label, json.dumps(days), time_start, time_stop,
                 temp_c, power_w, datetime.now().isoformat())
            )
            return cur.lastrowid
    except Exception as e:
        log.error(f"DB add_schedule_slot: {e}")
        return None


def update_schedule_slot(slot_id: int, fields: dict) -> bool:
    allowed = {"label", "days", "time_start", "time_stop",
               "temp_c", "power_w", "enabled"}
    import json
    updates, vals = [], []
    for k, v in fields.items():
        if k in allowed:
            updates.append(f"{k}=?")
            vals.append(json.dumps(v) if k == "days" else v)
    if not updates:
        return False
    vals.append(slot_id)
    try:
        with _get_con() as con:
            con.execute(
                f"UPDATE schedule_slots SET {','.join(updates)} WHERE id=?", vals
            )
        return True
    except Exception as e:
        log.error(f"DB update_schedule_slot: {e}")
        return False


def delete_schedule_slot(slot_id: int) -> bool:
    try:
        with _get_con() as con:
            con.execute("DELETE FROM schedule_slots WHERE id=?", (slot_id,))
        return True
    except Exception as e:
        log.error(f"DB delete_schedule_slot: {e}")
        return False


# ══════════════════════════════════════════════════════════════
# DRAW EVENTS — wykryte zdarzenia poboru wody (usage_detector)
# ══════════════════════════════════════════════════════════════

def insert_draw_events_bulk(events: list) -> int:
    """INSERT OR IGNORE (idempotentne dzięki UNIQUE(start_ts, end_ts))."""
    if not events:
        return 0
    try:
        with _get_con() as con:
            cur = con.executemany(
                """INSERT OR IGNORE INTO draw_events
                   (start_ts, end_ts, temp_before, temp_after, drop_c,
                    duration_min, n_bursts, category, source)
                   VALUES (:start_ts, :end_ts, :temp_before, :temp_after, :drop_c,
                           :duration_min, :n_bursts, :category, :source)""",
                events
            )
        return cur.rowcount
    except Exception as e:
        log.error(f"DB insert_draw_events_bulk: {e}")
        return 0


def get_draw_events(hours: int = 168, category: Optional[str] = None) -> list:
    try:
        since = (datetime.now() - timedelta(hours=hours)).isoformat()
        with _get_con() as con:
            if category:
                rows = con.execute(
                    "SELECT * FROM draw_events WHERE start_ts >= ? AND category = ? ORDER BY start_ts DESC",
                    (since, category)
                ).fetchall()
            else:
                rows = con.execute(
                    "SELECT * FROM draw_events WHERE start_ts >= ? ORDER BY start_ts DESC",
                    (since,)
                ).fetchall()
        return [dict(r) for r in rows]
    except Exception as e:
        log.error(f"DB get_draw_events: {e}")
        return []


def get_draw_events_daily_counts(category: str = "session", hour_start: int = 17,
                                  hour_end: int = 23, days: int = 180) -> list:
    """Dzienne liczby zdarzeń danej kategorii w oknie godzinowym [hour_start, hour_end].

    start_ts jest zapisywany jako naiwny czas lokalny (datetime.now().isoformat(),
    bez strefy) — tak samo jak boiler_history.ts. NIE używamy tu modyfikatora
    SQLite 'localtime' (on zakłada, że przechowywany czas to UTC i przesuwa go
    o offset strefy — dla już-lokalnego ts dałoby to podwójne przesunięcie,
    np. zdarzenie 22:30 wyliczone jako "00:30"). Cutoff liczony w Pythonie,
    tak samo jak get_boiler_history/get_events.
    """
    try:
        since = (datetime.now() - timedelta(days=days)).isoformat()
        with _get_con() as con:
            rows = con.execute("""
                SELECT date(start_ts) as day, COUNT(*) as count,
                       SUM(duration_min) as total_duration_min
                FROM draw_events
                WHERE category = ?
                  AND start_ts >= ?
                  AND CAST(strftime('%H', start_ts) AS INTEGER) BETWEEN ? AND ?
                GROUP BY day
                ORDER BY day ASC
            """, (category, since, hour_start, hour_end)).fetchall()
        return [{"day": r["day"], "count": r["count"],
                 "total_duration_min": round(r["total_duration_min"] or 0, 1)} for r in rows]
    except Exception as e:
        log.error(f"DB get_draw_events_daily_counts: {e}")
        return []


# ══════════════════════════════════════════════════════════════
# TUYA — realne odczyty mocy z inteligentnej wtyczki
# ══════════════════════════════════════════════════════════════

def insert_tuya_reading(power_w: Optional[float], voltage_v: Optional[float],
                         current_ma: Optional[float], switch: Optional[bool]) -> None:
    try:
        with _get_con() as con:
            con.execute(
                """INSERT INTO tuya_readings (ts, power_w, voltage_v, current_ma, switch)
                   VALUES (?, ?, ?, ?, ?)""",
                (datetime.now().isoformat(), power_w, voltage_v, current_ma,
                 1 if switch else 0 if switch is not None else None)
            )
    except Exception as e:
        log.error(f"DB insert_tuya_reading: {e}")


def get_tuya_readings(hours: int = 24) -> list:
    """Surowe odczyty (ts, power_w, voltage_v, current_ma, switch) — do wykresów."""
    try:
        since = (datetime.now() - timedelta(hours=hours)).isoformat()
        with _get_con() as con:
            rows = con.execute(
                "SELECT * FROM tuya_readings WHERE ts >= ? ORDER BY ts ASC",
                (since,)
            ).fetchall()
        return [dict(r) for r in rows]
    except Exception as e:
        log.error(f"DB get_tuya_readings: {e}")
        return []


def get_tuya_energy_today() -> float:
    """kWh od 00:00 lokalnego czasu do teraz, liczone z realnych odczytów mocy."""
    try:
        since = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        with _get_con() as con:
            row = con.execute(
                "SELECT SUM(power_w) * (1.0/60) / 1000 FROM tuya_readings WHERE ts >= ? AND power_w IS NOT NULL",
                (since,)
            ).fetchone()
        return round(row[0] or 0.0, 3)
    except Exception as e:
        log.error(f"DB get_tuya_energy_today: {e}")
        return 0.0


def get_tuya_energy_per_day(days: int = 30) -> list:
    """kWh per dzień z realnych odczytów mocy (Tuya) — do zakładki Ekonomia."""
    try:
        since = (datetime.now() - timedelta(days=days)).isoformat()
        with _get_con() as con:
            rows = con.execute("""
                SELECT date(ts) as day, SUM(power_w) * (1.0/60) / 1000 as kwh
                FROM tuya_readings
                WHERE ts >= ? AND power_w IS NOT NULL
                GROUP BY day
                ORDER BY day ASC
            """, (since,)).fetchall()
        return [{"day": r["day"], "kwh": round(r["kwh"] or 0.0, 3)} for r in rows]
    except Exception as e:
        log.error(f"DB get_tuya_energy_per_day: {e}")
        return []


# ══════════════════════════════════════════════════════════════
# POMPA CYRKULACYJNA — harmonogram + historia pracy
# ══════════════════════════════════════════════════════════════

def get_pump_schedule_slots(enabled_only: bool = False) -> list:
    try:
        with _get_con() as con:
            if enabled_only:
                rows = con.execute(
                    "SELECT * FROM pump_schedule_slots WHERE enabled=1 ORDER BY time_start"
                ).fetchall()
            else:
                rows = con.execute(
                    "SELECT * FROM pump_schedule_slots ORDER BY time_start"
                ).fetchall()
        return [dict(r) for r in rows]
    except Exception as e:
        log.error(f"DB get_pump_schedule_slots: {e}")
        return []


def add_pump_schedule_slot(
    days: list,
    time_start: str,
    time_stop: str,
    cycle_on_min: Optional[int] = None,
    cycle_off_min: Optional[int] = None,
    label: str = ""
) -> Optional[int]:
    try:
        import json
        with _get_con() as con:
            cur = con.execute(
                """INSERT INTO pump_schedule_slots
                   (label, days, time_start, time_stop, cycle_on_min, cycle_off_min, enabled, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, 1, ?)""",
                (label, json.dumps(days), time_start, time_stop,
                 cycle_on_min, cycle_off_min, datetime.now().isoformat())
            )
            return cur.lastrowid
    except Exception as e:
        log.error(f"DB add_pump_schedule_slot: {e}")
        return None


def update_pump_schedule_slot(slot_id: int, fields: dict) -> bool:
    allowed = {"label", "days", "time_start", "time_stop",
               "cycle_on_min", "cycle_off_min", "enabled"}
    import json
    updates, vals = [], []
    for k, v in fields.items():
        if k in allowed:
            updates.append(f"{k}=?")
            vals.append(json.dumps(v) if k == "days" else v)
    if not updates:
        return False
    vals.append(slot_id)
    try:
        with _get_con() as con:
            con.execute(
                f"UPDATE pump_schedule_slots SET {','.join(updates)} WHERE id=?", vals
            )
        return True
    except Exception as e:
        log.error(f"DB update_pump_schedule_slot: {e}")
        return False


def delete_pump_schedule_slot(slot_id: int) -> bool:
    try:
        with _get_con() as con:
            con.execute("DELETE FROM pump_schedule_slots WHERE id=?", (slot_id,))
        return True
    except Exception as e:
        log.error(f"DB delete_pump_schedule_slot: {e}")
        return False


def insert_pump_event_start(trigger: str, source_label: str = "") -> Optional[int]:
    try:
        with _get_con() as con:
            cur = con.execute(
                """INSERT INTO pump_history (start_ts, trigger, source_label)
                   VALUES (?, ?, ?)""",
                (datetime.now().isoformat(), trigger, source_label)
            )
            return cur.lastrowid
    except Exception as e:
        log.error(f"DB insert_pump_event_start: {e}")
        return None


def close_pump_event(event_id: int) -> None:
    try:
        with _get_con() as con:
            row = con.execute(
                "SELECT start_ts FROM pump_history WHERE id=?", (event_id,)
            ).fetchone()
            if not row:
                return
            start = datetime.fromisoformat(row["start_ts"])
            end = datetime.now()
            duration_min = round((end - start).total_seconds() / 60, 1)
            con.execute(
                "UPDATE pump_history SET end_ts=?, duration_min=? WHERE id=?",
                (end.isoformat(), duration_min, event_id)
            )
    except Exception as e:
        log.error(f"DB close_pump_event: {e}")


def get_pump_history(hours: int = 168) -> list:
    try:
        since = (datetime.now() - timedelta(hours=hours)).isoformat()
        with _get_con() as con:
            rows = con.execute(
                "SELECT * FROM pump_history WHERE start_ts >= ? ORDER BY start_ts DESC",
                (since,)
            ).fetchall()
        return [dict(r) for r in rows]
    except Exception as e:
        log.error(f"DB get_pump_history: {e}")
        return []


def get_pump_today_minutes() -> float:
    """Suma minut pracy dziś, licząc otwarty (trwający) wpis do 'teraz'."""
    try:
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        with _get_con() as con:
            rows = con.execute(
                "SELECT start_ts, end_ts, duration_min FROM pump_history WHERE start_ts >= ?",
                (today_start,)
            ).fetchall()
        total = 0.0
        for r in rows:
            if r["end_ts"] is not None:
                total += r["duration_min"] or 0.0
            else:
                start = datetime.fromisoformat(r["start_ts"])
                total += (datetime.now() - start).total_seconds() / 60
        return round(total, 1)
    except Exception as e:
        log.error(f"DB get_pump_today_minutes: {e}")
        return 0.0


# ══════════════════════════════════════════════════════════════
# ENERGIA (eLicznik Tauron) — pobór/oddanie z sieci, dziennie i miesięcznie
# ══════════════════════════════════════════════════════════════

def upsert_energy_daily(date: str, imported_kwh: float, exported_kwh: float,
                         raw_imported_kwh: float = None, raw_exported_kwh: float = None) -> None:
    try:
        with _get_con() as con:
            con.execute(
                """INSERT INTO energy_daily (date, imported_kwh, exported_kwh,
                                             raw_imported_kwh, raw_exported_kwh, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?)
                   ON CONFLICT(date) DO UPDATE SET
                     imported_kwh=excluded.imported_kwh,
                     exported_kwh=excluded.exported_kwh,
                     raw_imported_kwh=excluded.raw_imported_kwh,
                     raw_exported_kwh=excluded.raw_exported_kwh,
                     updated_at=excluded.updated_at""",
                (date, imported_kwh, exported_kwh, raw_imported_kwh, raw_exported_kwh,
                 datetime.now().isoformat())
            )
    except Exception as e:
        log.error(f"DB upsert_energy_daily: {e}")


def upsert_energy_monthly(period: str, imported_kwh: float, exported_kwh: float,
                         raw_imported_kwh: float = None, raw_exported_kwh: float = None) -> None:
    try:
        with _get_con() as con:
            con.execute(
                """INSERT INTO energy_monthly (period, imported_kwh, exported_kwh,
                                             raw_imported_kwh, raw_exported_kwh, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?)
                   ON CONFLICT(period) DO UPDATE SET
                     imported_kwh=excluded.imported_kwh,
                     exported_kwh=excluded.exported_kwh,
                     raw_imported_kwh=excluded.raw_imported_kwh,
                     raw_exported_kwh=excluded.raw_exported_kwh,
                     updated_at=excluded.updated_at""",
                (period, imported_kwh, exported_kwh, raw_imported_kwh, raw_exported_kwh,
                 datetime.now().isoformat())
            )
    except Exception as e:
        log.error(f"DB upsert_energy_monthly: {e}")


def get_energy_daily_from(from_date: str) -> list:
    try:
        with _get_con() as con:
            rows = con.execute(
                "SELECT * FROM energy_daily WHERE date >= ? ORDER BY date ASC", (from_date,)
            ).fetchall()
        return [dict(r) for r in rows]
    except Exception as e:
        log.error(f"DB get_energy_daily_from: {e}")
        return []


def get_energy_monthly_range(from_period: str, to_period: str) -> list:
    try:
        with _get_con() as con:
            rows = con.execute(
                "SELECT * FROM energy_monthly WHERE period >= ? AND period <= ? ORDER BY period ASC",
                (from_period, to_period)
            ).fetchall()
        return [dict(r) for r in rows]
    except Exception as e:
        log.error(f"DB get_energy_monthly_range: {e}")
        return []


def get_energy_meta(key: str) -> Optional[str]:
    try:
        with _get_con() as con:
            row = con.execute("SELECT value FROM energy_meta WHERE key=?", (key,)).fetchone()
        return row["value"] if row else None
    except Exception as e:
        log.error(f"DB get_energy_meta: {e}")
        return None


def set_energy_meta(key: str, value: str) -> None:
    try:
        with _get_con() as con:
            con.execute(
                """INSERT INTO energy_meta (key, value) VALUES (?, ?)
                   ON CONFLICT(key) DO UPDATE SET value=excluded.value""",
                (key, str(value))
            )
    except Exception as e:
        log.error(f"DB set_energy_meta: {e}")


# ══════════════════════════════════════════════════════════════
# RETENCJA — czyszczenie starych rekordów
# ══════════════════════════════════════════════════════════════

def purge_old_records(
    data_retention_days: int = 365,
    log_retention_days: int = 30
) -> dict:
    """
    Usuń rekordy starsze niż limit.
    Zwraca dict z liczbą usuniętych wierszy per tabela.
    """
    now = datetime.now()
    data_cutoff = (now - timedelta(days=data_retention_days)).isoformat()
    log_cutoff  = (now - timedelta(days=log_retention_days)).isoformat()

    deleted = {}
    tables = [
        ("boiler_history", data_cutoff),
        ("system_events",  log_cutoff),
        ("user_actions",   log_cutoff),
        ("auth_log",       log_cutoff),
        ("tuya_readings",  data_cutoff),
    ]
    try:
        with _get_con() as con:
            for table, cutoff in tables:
                cur = con.execute(
                    f"DELETE FROM {table} WHERE ts < ?", (cutoff,)
                )
                deleted[table] = cur.rowcount
        log.info(f"Retencja: usunięto {deleted}")
        return deleted
    except Exception as e:
        log.error(f"DB purge_old_records: {e}")
        return {}


def get_energy_per_day(days: int = 30) -> list:
    """Zwraca zużycie energii w kWh per dzień (pełne doby)."""
    con = _get_con()
    with con:
        rows = con.execute("""
            SELECT
                date(ts, 'localtime') as day,
                SUM(power_w) * (1.0/60) / 1000 as kwh,
                COUNT(*) as samples
            FROM boiler_history
            WHERE ts >= datetime('now', '-' || ? || ' days')
              AND power_w > 0
              AND heating = 1
            GROUP BY date(ts, 'localtime')
            ORDER BY day ASC
        """, (days,)).fetchall()
    return [{"day": r[0], "kwh": round(r[1], 3), "samples": r[2]} for r in rows]


def get_energy_today() -> float:
    """Zwraca zużycie energii w kWh od 00:00 do teraz (czas lokalny)."""
    con = _get_con()
    with con:
        row = con.execute("""
            SELECT SUM(power_w) * (1.0/60) / 1000
            FROM boiler_history
            WHERE date(ts, 'localtime') = date('now', 'localtime')
              AND power_w > 0
              AND heating = 1
        """).fetchone()
    return round(row[0] or 0.0, 3)
