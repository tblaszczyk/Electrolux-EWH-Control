"""
core/pump_logic.py
Czysta logika decyzji dla pompy cyrkulacyjnej — CO pompa powinna robić.
Wzorem core/decision_logic.py: brak dostępu do DB/sieci, tylko obliczenia.

Priorytet: manual (z limitem czasu) > schedule (z opcjonalną pulsacją) > off.
Zero powiązania z core/decision_logic.py bojlera — całkowicie niezależne.
"""

from datetime import datetime, timedelta
from typing import Optional


def _in_cycle_on_phase(slot: dict, now: datetime) -> bool:
    """
    Sprawdza, czy `now` przypada na fazę "włącz" cyklu pulsacyjnego slotu.
    Brak cycle_on_min = slot pracuje ciągle w oknie czasowym (bez pulsacji).
    Pozycja w cyklu liczona jest od godziny startu slotu danego dnia,
    deterministycznie (bez trzymania stanu) — modulo (on+off).
    """
    on_min = slot.get("cycle_on_min")
    if not on_min:
        return True

    off_min = slot.get("cycle_off_min") or 0
    period = on_min + off_min
    if period <= 0:
        return True

    try:
        h, m = slot["time_start"].split(":")
        slot_start_today = now.replace(hour=int(h), minute=int(m), second=0, microsecond=0)
    except Exception:
        return True

    elapsed_min = (now - slot_start_today).total_seconds() / 60
    if elapsed_min < 0:
        elapsed_min += 24 * 60

    phase = elapsed_min % period
    return phase < on_min


def compute_pump_state(
    mode: str,
    manual_until: Optional[datetime],
    manual_target: bool,
    active_slot: Optional[dict],
    now: Optional[datetime] = None,
) -> tuple:
    """
    Zwraca (should_be_on: bool, reason: str).

    mode:          "off" | "manual" | "schedule"
    manual_until:  koniec ważności trybu ręcznego (None = brak aktywnego override)
    manual_target: pożądany stan (on/off) w trybie ręcznym
    active_slot:   aktywny slot harmonogramu z pump_scheduler.get_active_slot() lub None
    """
    now = now or datetime.now()

    if mode == "manual":
        if manual_until and now < manual_until:
            remaining_min = int((manual_until - now).total_seconds() / 60) + 1
            return manual_target, f"Ręcznie ({remaining_min} min pozostało)"
        return False, "Tryb ręczny — czas minął"

    if mode == "schedule":
        if not active_slot:
            return False, "Poza oknem harmonogramu"
        if _in_cycle_on_phase(active_slot, now):
            label = active_slot.get("label") or "harmonogram"
            if active_slot.get("cycle_on_min"):
                return True, f"Slot: {label} (pulsacja {active_slot['cycle_on_min']}/{active_slot.get('cycle_off_min') or 0} min)"
            return True, f"Slot: {label}"
        return False, f"Slot: {active_slot.get('label') or 'harmonogram'} (przerwa w pulsacji)"

    return False, "Wyłączona"
