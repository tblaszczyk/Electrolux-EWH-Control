"""
core/watchdog.py
Pilnuje timeout komunikacji z bojlerem i PV.
Control Engine sprawdza watchdog przed każdą decyzją.
"""

import threading
import logging
from datetime import datetime, timedelta
from typing import Optional

log = logging.getLogger("boiler.watchdog")


class Watchdog:

    def __init__(self, timeout_s: int = 30):
        self._timeout_s = timeout_s
        self._lock      = threading.Lock()

        self._boiler_last_ok: Optional[datetime] = None
        self._pv_last_ok:     Optional[datetime] = None

    # ── Rejestracja sukcesu ───────────────────────────────────

    def boiler_ok(self) -> None:
        """Wywołaj po każdej udanej komunikacji z bojlerem."""
        with self._lock:
            self._boiler_last_ok = datetime.now()

    def pv_ok(self) -> None:
        """Wywołaj po każdym udanym odczycie z PV."""
        with self._lock:
            self._pv_last_ok = datetime.now()

    # ── Sprawdzenia ───────────────────────────────────────────

    def boiler_alive(self) -> bool:
        """True jeśli ostatnia komunikacja z bojlerem była < timeout_s temu."""
        with self._lock:
            if self._boiler_last_ok is None:
                return False
            return (datetime.now() - self._boiler_last_ok).total_seconds() < self._timeout_s

    def pv_alive(self) -> bool:
        """True jeśli ostatnia komunikacja z PV była < timeout_s temu."""
        with self._lock:
            if self._pv_last_ok is None:
                return False
            return (datetime.now() - self._pv_last_ok).total_seconds() < self._timeout_s

    def boiler_seconds_since(self) -> Optional[float]:
        with self._lock:
            if self._boiler_last_ok is None:
                return None
            return (datetime.now() - self._boiler_last_ok).total_seconds()

    def pv_seconds_since(self) -> Optional[float]:
        with self._lock:
            if self._pv_last_ok is None:
                return None
            return (datetime.now() - self._pv_last_ok).total_seconds()

    def set_timeout(self, timeout_s: int) -> None:
        with self._lock:
            self._timeout_s = timeout_s
            log.info(f"Watchdog: timeout ustawiony na {timeout_s}s")

    def status(self) -> dict:
        return {
            "boiler_alive":        self.boiler_alive(),
            "boiler_seconds_since": self.boiler_seconds_since(),
            "pv_alive":            self.pv_alive(),
            "pv_seconds_since":    self.pv_seconds_since(),
            "timeout_s":           self._timeout_s,
        }


# Singleton
watchdog = Watchdog()
