"""
service/pump_runtime.py
Stan RUNTIME pompy cyrkulacyjnej — żyje tylko w pamięci (reset przy
restarcie = powrót do stanu z configu, tryb ręczny NIE jest odtwarzany —
bezpieczny domyślny fallback, zgodnie z filozofią service/runtime_state.py).
Thread-safe dzięki RLock.
"""

import threading
from datetime import datetime
from typing import Optional


class PumpRuntimeState:

    def __init__(self):
        self._lock = threading.RLock()

        self.current_on: bool = False
        self.last_reason: str = ""
        self.last_update_ts: Optional[datetime] = None

        # ── Tryb ręczny (nigdy nie przetrwa restartu) ───────────
        self.manual_until: Optional[datetime] = None
        self.manual_target: bool = False

        # ── Otwarty wpis w pump_history (do zamknięcia przy OFF) ─
        self.open_history_id: Optional[int] = None

    def set_manual(self, on: bool, minutes: int) -> None:
        with self._lock:
            self.manual_target = on
            self.manual_until  = datetime.now().replace(microsecond=0)
            from datetime import timedelta
            self.manual_until += timedelta(minutes=minutes)

    def clear_manual(self) -> None:
        with self._lock:
            self.manual_until = None

    def update_state(self, on: bool, reason: str) -> None:
        with self._lock:
            self.current_on    = on
            self.last_reason   = reason
            self.last_update_ts = datetime.now()

    def set_open_history_id(self, hid: Optional[int]) -> None:
        with self._lock:
            self.open_history_id = hid

    def snapshot(self) -> dict:
        with self._lock:
            manual_remaining_s = None
            if self.manual_until:
                manual_remaining_s = max(0, int((self.manual_until - datetime.now()).total_seconds()))
            return {
                "current_on":          self.current_on,
                "reason":              self.last_reason,
                "last_update":         self.last_update_ts.isoformat() if self.last_update_ts else None,
                "manual_remaining_s":  manual_remaining_s,
            }


# Singleton
pump_runtime = PumpRuntimeState()
