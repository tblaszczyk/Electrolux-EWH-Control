"""
core/pump_scheduler.py
Sprawdza harmonogram pompy cyrkulacyjnej i zwraca aktywny slot (jeśli jest).
NIE steruje pompą — tylko informuje pętlę sterującą (main.py:_pump_control_loop).

Świadomy duplikat core/scheduler.py (osobna tabela, dodatkowe pola cyklu
pulsacyjnego) — mniejsze ryzyko niż współdzielenie z działającym kodem
harmonogramu bojlera.
"""

import json
import logging
import threading
from datetime import datetime
from typing import Optional

import data.database as db

log = logging.getLogger("boiler.pump_scheduler")

DAY_NAMES = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


def _now_matches_slot(slot: dict) -> bool:
    """True jeśli teraz (dzień + godzina) pasuje do slotu."""
    now      = datetime.now()
    weekday  = now.weekday()
    day_name = DAY_NAMES[weekday]

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

    now_hhmm = now.strftime("%H:%M")
    t_start  = slot.get("time_start", "00:00")
    t_stop   = slot.get("time_stop",  "00:00")

    return t_start <= now_hhmm < t_stop


class PumpScheduler:

    def __init__(self):
        self._lock  = threading.Lock()
        self._slots: list = []
        self._loaded_at: Optional[datetime] = None

    def reload(self) -> None:
        """Wczytaj sloty z bazy danych (wywołaj przy starcie i po zmianie CRUD)."""
        with self._lock:
            self._slots = db.get_pump_schedule_slots(enabled_only=True)
            self._loaded_at = datetime.now()
        log.info(f"PumpScheduler: wczytano {len(self._slots)} aktywnych slotów")

    def get_active_slot(self) -> Optional[dict]:
        """Zwraca aktywny slot harmonogramu pompy lub None."""
        with self._lock:
            for slot in self._slots:
                if _now_matches_slot(slot):
                    return slot
        return None

    def status(self) -> dict:
        with self._lock:
            active_slot = None
            for s in self._slots:
                if _now_matches_slot(s):
                    active_slot = s
                    break
            return {
                "slots_count": len(self._slots),
                "loaded_at":   self._loaded_at.isoformat() if self._loaded_at else None,
                "active_slot": active_slot,
            }


# Singleton
pump_scheduler = PumpScheduler()
