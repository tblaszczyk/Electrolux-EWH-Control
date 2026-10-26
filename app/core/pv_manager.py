"""
core/pv_manager.py
Logika PV z:
- oknem czasowym (PV może grzać tylko między pv_window_start a pv_window_stop)
- progiem minimalnym (pv_min_power_w)
- histerezą (pv_hysteresis_s) — działa przy włączaniu I wyłączaniu
- auto mocą (nadwyżka PV → moc bojlera) lub stałą mocą
- temperaturą docelową (pv_target_temp)

NIE wysyła komend — tylko oblicza i zwraca wynik dla Control Engine.
"""

import logging
import threading
from datetime import datetime, time as dtime
from typing import Optional

log = logging.getLogger("boiler.pv")


def _parse_time(hhmm: str) -> dtime:
    """Parsuje "HH:MM" → time object."""
    try:
        h, m = hhmm.split(":")
        return dtime(int(h), int(m))
    except Exception:
        return dtime(0, 0)


def _auto_power(pv_power: float, pv_min: float) -> int:
    """
    Oblicza moc bojlera na podstawie nadwyżki PV ponad próg rezerwy.
    Moc bojlera zależy od całkowitej produkcji PV.
    pv_min to minimalny próg aktywacji — poniżej brak grzania.
    PV >= 2000W → 2000W
    PV >= 1300W → 1300W
    PV >= 700W  → 700W
    PV < 700W lub PV < pv_min → nie grzej (0W)
    """
    # Moc bojlera bazuje na nadwyżce ponad próg aktywacji
    # PV >= próg          → 700W
    # PV >= próg + 600W   → 1300W
    # PV >= próg + 1300W  → 2000W
    surplus = pv_power - pv_min
    if surplus >= 1300:
        return 2000
    elif surplus >= 600:
        return 1300
    else:
        return 700  # already above pv_min, checked before calling


class PVManager:
    """
    Zarządza logiką PV — okno czasowe, próg, histereza, moc.

    update(pv_power, cfg) → dict z decyzją dla Control Engine.
    """

    def __init__(self):
        self._lock          = threading.Lock()

        # Stan histerezy
        self._active        = False    # czy PV aktualnie grzeje
        self._pending_on:   Optional[datetime] = None   # kiedy zaczął spełniać warunek włączenia
        self._pending_off:  Optional[datetime] = None   # kiedy zaczął nie spełniać warunku

    def update(self, pv_power: float, cfg: dict) -> dict:
        """
        Zaktualizuj stan PV.

        Parametry cfg:
          pv_min_power_w   — minimalny próg mocy PV
          pv_window_start  — "HH:MM" od kiedy PV może grzać
          pv_window_stop   — "HH:MM" do kiedy PV może grzać
          pv_hysteresis_s  — histereza [s]
          pv_target_temp   — temperatura docelowa [°C]
          pv_power_mode    — "auto" | 700 | 1300 | 2000
          pv_power_fixed_w — stała moc [W] gdy pv_power_mode != "auto"

        Zwraca:
          {
            "active":        bool,   # czy PV powinno grzać
            "power_w":       int,    # moc do ustawienia [W]
            "target_temp":   int,    # temperatura docelowa [°C]
            "in_window":     bool,   # czy w oknie czasowym
            "above_min":     bool,   # czy powyżej progu
            "pending_on_s":  float,  # sekund do włączenia (histereza)
            "pending_off_s": float,  # sekund do wyłączenia (histereza)
            "reason":        str,    # opis decyzji
          }
        """
        with self._lock:
            now          = datetime.now()
            now_time     = now.time().replace(second=0, microsecond=0)
            hysteresis_s = int(cfg.get("pv_hysteresis_s", 30))
            pv_min       = float(cfg.get("pv_min_power_w", 700))
            win_start    = _parse_time(cfg.get("pv_window_start", "00:00"))
            win_stop     = _parse_time(cfg.get("pv_window_stop",  "23:59"))
            target_temp  = int(cfg.get("pv_target_temp", 65))
            power_mode   = cfg.get("pv_power_mode", "auto")
            power_fixed  = int(cfg.get("pv_power_fixed_w", 2000))

            # Sprawdź warunki
            in_window  = win_start <= now_time <= win_stop
            above_min  = pv_power >= pv_min
            conditions = in_window and above_min

            pending_on_s  = None
            pending_off_s = None

            if conditions:
                # Warunki spełnione — resetuj timer wyłączenia
                self._pending_off = None

                if self._active:
                    # Już aktywne — zostań
                    pass
                else:
                    # Czekaj na histerezę włączenia
                    if self._pending_on is None:
                        self._pending_on = now
                        log.debug(f"PV: warunki spełnione, czekam {hysteresis_s}s na włączenie")

                    elapsed = (now - self._pending_on).total_seconds()
                    pending_on_s = max(0.0, hysteresis_s - elapsed)

                    if elapsed >= hysteresis_s:
                        self._active     = True
                        self._pending_on = None
                        log.info(
                            f"PV: WŁĄCZONO grzanie po {elapsed:.0f}s "
                            f"(PV={pv_power:.0f}W, okno={cfg.get('pv_window_start')}-{cfg.get('pv_window_stop')})"
                        )
            else:
                # Warunki niespełnione — resetuj timer włączenia
                self._pending_on = None

                if self._active:
                    # Czekaj na histerezę wyłączenia
                    if self._pending_off is None:
                        self._pending_off = now
                        reason_why = []
                        if not in_window: reason_why.append("poza oknem czasowym")
                        if not above_min: reason_why.append(f"PV={pv_power:.0f}W < {pv_min:.0f}W")
                        log.debug(f"PV: warunki nie spełnione ({', '.join(reason_why)}), czekam {hysteresis_s}s")

                    elapsed = (now - self._pending_off).total_seconds()
                    pending_off_s = max(0.0, hysteresis_s - elapsed)

                    if elapsed >= hysteresis_s:
                        self._active      = False
                        self._pending_off = None
                        log.info(
                            f"PV: WYŁĄCZONO grzanie po {elapsed:.0f}s "
                            f"(PV={pv_power:.0f}W, in_window={in_window})"
                        )
                else:
                    # Już nieaktywne
                    self._pending_off = None

            # Oblicz moc
            if self._active:
                if power_mode == "auto":
                    power_w = _auto_power(pv_power, pv_min)
                else:
                    power_w = int(power_mode) if str(power_mode).isdigit() else power_fixed
            else:
                power_w = 0

            # Buduj reason
            if self._active:
                reason = (
                    f"PV={pv_power:.0f}W, moc={power_w}W, temp={target_temp}°C"
                    f", okno={cfg.get('pv_window_start')}-{cfg.get('pv_window_stop')}"
                )
            elif not in_window:
                reason = f"Poza oknem czasowym ({cfg.get('pv_window_start')}-{cfg.get('pv_window_stop')})"
            elif not above_min:
                reason = f"PV={pv_power:.0f}W poniżej progu {pv_min:.0f}W"
            elif pending_on_s is not None:
                reason = f"Oczekiwanie na histerezę włączenia ({pending_on_s:.0f}s)"
            elif pending_off_s is not None:
                reason = f"Oczekiwanie na histerezę wyłączenia ({pending_off_s:.0f}s)"
            else:
                reason = "PV nieaktywne"

            return {
                "active":        self._active,
                "power_w":       power_w,
                "target_temp":   target_temp,
                "in_window":     in_window,
                "above_min":     above_min,
                "pending_on_s":  pending_on_s,
                "pending_off_s": pending_off_s,
                "reason":        reason,
            }

    def reset(self) -> None:
        """Reset stanu (np. przy przełączeniu w tryb manual)."""
        with self._lock:
            self._active      = False
            self._pending_on  = None
            self._pending_off = None
        log.info("PV: reset stanu")

    @property
    def is_active(self) -> bool:
        with self._lock:
            return self._active


# Singleton
pv_manager = PVManager()
