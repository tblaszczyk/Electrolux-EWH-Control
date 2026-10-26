"""
service/runtime_state.py
Stan RUNTIME systemu — żyje tylko w pamięci (reset przy restarcie = powrót do AUTO).
Thread-safe dzięki RLock.
NIE TRZYMAJ TU CONFIGU ani STAŁYCH.
"""

import threading
from datetime import datetime
from typing import Optional


class RuntimeState:
    """
    Jedyne źródło prawdy o aktualnym stanie systemu w czasie rzeczywistym.
    Control Engine aktualizuje, API tylko odczytuje.
    """

    def __init__(self):
        self._lock = threading.RLock()

        # ── Tryb i stan ────────────────────────────────────────
        self.current_mode: str = "AUTO"          # "MANUAL" | "AUTO"
        self.current_state: str = "STARTING"     # stany z state_machine

        # ── Nastawa manualna ───────────────────────────────────
        self.manual_temp: int = 55
        self.manual_power_limit: int = 2000

        # ── IDLE ───────────────────────────────────────────────
        self.idle_mode: str = "off"              # "off" | "low_20" | "low_30"

        # ── PV ────────────────────────────────────────────────
        self.pv_last_power: float = 0.0          # [W]
        self.pv_last_power_level: int = 0        # 0–3
        self.pv_last_update_ts: Optional[datetime] = None
        self.pv_online: bool = False
        self.pv_today_kwh: float = 0.0

        # ── Bojler ─────────────────────────────────────────────
        self.boiler_last_temp: float = 0.0       # [°C]
        self.boiler_last_target: float = 0.0     # [°C]
        self.boiler_last_power_w: int = 0        # [W]
        self.boiler_last_update_ts: Optional[datetime] = None
        self.boiler_online: bool = False
        self.boiler_heating: bool = False

        # ── Tuya (opcjonalny realny pomiar mocy) ────────────────
        self.tuya_last_power_w: Optional[float] = None
        self.tuya_online: bool = False
        self.tuya_last_update_ts: Optional[datetime] = None

        # ── Ostatnia decyzja (debug) ───────────────────────────
        self.last_decision_mode: str = ""
        self.last_decision_temp: int = 0
        self.last_decision_power: int = 0
        self.last_decision_reason: str = ""
        self.last_decision_ts: Optional[datetime] = None

        # ── Ostatnia komenda do bojlera ────────────────────────
        self.last_command_sent: Optional[dict] = None
        self.last_command_ts: Optional[datetime] = None

        # ── Zmiany stanu ───────────────────────────────────────
        self.last_state_change_ts: Optional[datetime] = datetime.now()

        # ── Histereza PV (runtime kopia z configu) ─────────────
        self.pv_hysteresis_s: int = 30

        # ── Błędy ─────────────────────────────────────────────
        self.error_message: Optional[str] = None

    # ── Thread-safe gettery / settery ─────────────────────────

    def update_boiler(
        self,
        temp_current: float,
        temp_target: float,
        power_w: int,
        heating: bool,
        online: bool
    ) -> None:
        with self._lock:
            self.boiler_last_temp      = temp_current
            self.boiler_last_target    = temp_target
            self.boiler_last_power_w   = power_w
            self.boiler_heating        = heating
            self.boiler_online         = online
            self.boiler_last_update_ts = datetime.now()

    def update_pv(
        self,
        pv_power: float,
        power_level: int,
        today_kwh: float,
        online: bool
    ) -> None:
        with self._lock:
            self.pv_last_power       = pv_power
            self.pv_last_power_level = power_level
            self.pv_today_kwh        = today_kwh
            self.pv_online           = online
            self.pv_last_update_ts   = datetime.now()

    def update_tuya(self, power_w: Optional[float], online: bool) -> None:
        with self._lock:
            self.tuya_last_power_w   = power_w
            self.tuya_online         = online
            self.tuya_last_update_ts = datetime.now()

    def set_state(self, new_state: str) -> None:
        with self._lock:
            if self.current_state != new_state:
                self.current_state      = new_state
                self.last_state_change_ts = datetime.now()

    def set_mode(self, mode: str) -> None:
        """mode: 'MANUAL' | 'AUTO'"""
        with self._lock:
            self.current_mode = mode

    def set_manual(self, temp: int, power_limit: int) -> None:
        with self._lock:
            self.manual_temp        = temp
            self.manual_power_limit = power_limit
            self.current_mode       = "MANUAL"

    def set_auto(self) -> None:
        with self._lock:
            self.current_mode = "AUTO"

    def set_idle_mode(self, mode: str) -> None:
        """mode: 'off' | 'low_20' | 'low_30'"""
        with self._lock:
            self.idle_mode = mode

    def record_decision(
        self, mode: str, temp: int, power: int, reason: str
    ) -> None:
        with self._lock:
            self.last_decision_mode   = mode
            self.last_decision_temp   = temp
            self.last_decision_power  = power
            self.last_decision_reason = reason
            self.last_decision_ts     = datetime.now()

    def record_command(self, temp: int, power_w: int) -> None:
        with self._lock:
            self.last_command_sent = {"temp": temp, "power_w": power_w}
            self.last_command_ts   = datetime.now()

    def set_error(self, message: str) -> None:
        with self._lock:
            self.error_message  = message
            self.current_state  = "ERROR"
            self.last_state_change_ts = datetime.now()

    def clear_error(self) -> None:
        with self._lock:
            self.error_message = None

    def snapshot(self) -> dict:
        """Zwraca bezpieczną kopię całego stanu (do API)."""
        if True:  # lock usunięty - snapshot tylko odczytuje
            return {
                "mode":                   self.current_mode,
                "state":                  self.current_state,
                "manual_temp":            self.manual_temp,
                "manual_power_limit":     self.manual_power_limit,
                "idle_mode":              self.idle_mode,
                "pv_power_w":             self.pv_last_power,
                "pv_power_level":         self.pv_last_power_level,
                "pv_today_kwh":           self.pv_today_kwh,
                "pv_online":              self.pv_online,
                "pv_last_update":         self.pv_last_update_ts.isoformat()
                                          if self.pv_last_update_ts else None,
                "boiler_temp_current":    self.boiler_last_temp,
                "boiler_temp_target":     self.boiler_last_target,
                "boiler_power_w":         self.boiler_last_power_w,
                "boiler_heating":         self.boiler_heating and self.current_state not in ("IDLE", "OFF", "COOLING", "NO_COMMUNICATION", "ERROR"),
                "boiler_online":          self.boiler_online,
                "boiler_last_update":     self.boiler_last_update_ts.isoformat()
                                          if self.boiler_last_update_ts else None,
                "tuya_power_w":           self.tuya_last_power_w,
                "tuya_online":            self.tuya_online,
                "tuya_last_update":       self.tuya_last_update_ts.isoformat()
                                          if self.tuya_last_update_ts else None,
                "last_decision_mode":     self.last_decision_mode,
                "last_decision_temp":     self.last_decision_temp,
                "last_decision_power":    self.last_decision_power,
                "reason":                 self.last_decision_reason,
                "last_decision_ts":       self.last_decision_ts.isoformat()
                                          if self.last_decision_ts else None,
                "last_command_sent":      self.last_command_sent,
                "last_command_ts":        self.last_command_ts.isoformat()
                                          if self.last_command_ts else None,
                "last_state_change":      self.last_state_change_ts.isoformat()
                                          if self.last_state_change_ts else None,
                "error_message":          self.error_message,
                "pv_hysteresis_s":        self.pv_hysteresis_s,
                "system_enabled":         getattr(self, "system_enabled", True),
            }


# Singleton — jeden egzemplarz dla całej aplikacji
runtime = RuntimeState()

# Patch: dodaj pv_info jako atrybut instancji (używany przez control_engine)
RuntimeState.pv_info = {"active": False, "power_w": 0, "target_temp": 65, "reason": ""}


# ── System ON/OFF (patch na istniejący singleton) ─────────────
# Dodajemy do klasy przez monkey-patch żeby nie przepisywać całego pliku

def _set_system_enabled(self, enabled: bool) -> None:
    with self._lock:
        if enabled and not self.system_enabled:
            # Wznowienie — przywróć ostatni aktywny tryb
            if self._state_before_disable:
                self.current_mode  = self._mode_before_disable or "AUTO"
                self.current_state = "STARTING"
        elif not enabled and self.system_enabled:
            # Wyłączenie — zapamiętaj stan
            self._state_before_disable = self.current_state
            self._mode_before_disable  = self.current_mode
            self.current_state = "OFF"
        self.system_enabled = enabled

RuntimeState.system_enabled          = True
RuntimeState._state_before_disable   = None
RuntimeState._mode_before_disable    = None
RuntimeState.set_system_enabled      = _set_system_enabled

