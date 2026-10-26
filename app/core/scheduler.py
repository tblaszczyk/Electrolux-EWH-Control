"""
core/scheduler.py
Sprawdza harmonogram i zwraca aktywny slot (jeśli jest).
NIE steruje bojlerem — tylko informuje Control Engine.
"""

import json
import logging
import threading
from datetime import datetime
from typing import Optional

import data.database as db

log = logging.getLogger("boiler.scheduler")

DAY_NAMES = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


def _now_matches_slot(slot: dict) -> bool:
    """True jeśli teraz (dzień + godzina) pasuje do slotu."""
    now      = datetime.now()
    weekday  = now.weekday()           # 0=pon, 6=nie
    day_name = DAY_NAMES[weekday]

    # Parsuj dni (JSON array: ["mon","tue"] lub "mon,tue")
    try:
        days_raw = slot.get("days", "[]")
        if isinstance(days_raw, str):
            try:
                days = json.loads(days_raw)
            except Exception:
                days = [d.strip() for d in days_raw.split(",")]
        else:
            days = days_raw
    except Exception:
        days = []

    if day_name not in days:
        return False

    # Porównaj godziny HH:MM
    now_hhmm = now.strftime("%H:%M")
    t_start  = slot.get("time_start", "00:00")
    t_stop   = slot.get("time_stop",  "00:00")

    return t_start <= now_hhmm < t_stop


class Scheduler:

    def __init__(self):
        self._lock  = threading.Lock()
        self._slots: list = []
        self._loaded_at: Optional[datetime] = None

    def reload(self) -> None:
        """Wczytaj sloty z bazy danych (wywołaj przy starcie i po RELOAD_SCHEDULE)."""
        with self._lock:
            self._slots = db.get_schedule_slots(enabled_only=True)
            self._loaded_at = datetime.now()
        log.info(f"Scheduler: wczytano {len(self._slots)} aktywnych slotów")

    def get_active_slot(self) -> Optional[dict]:
        """
        Zwraca aktywny slot harmonogramu lub None.
        Jeśli pasuje kilka slotów — zwraca pierwszy (priorytet wg kolejności w DB).
        """
        with self._lock:
            for slot in self._slots:
                if _now_matches_slot(slot):
                    return slot
        return None

    def status(self) -> dict:
        with self._lock:
            active_slot = None
            now = datetime.now()
            for s in self._slots:
                if s.get("enabled") and _now_matches_slot(s):
                    active_slot = s
                    break
            return {
                "slots_count": len(self._slots),
                "loaded_at":   self._loaded_at.isoformat() if self._loaded_at else None,
                "active_slot": active_slot,
            }


# Singleton
scheduler = Scheduler()
