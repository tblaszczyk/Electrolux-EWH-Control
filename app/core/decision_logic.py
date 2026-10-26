"""
core/decision_logic.py
Czysta logika decyzji — CO system chce zrobić.
Zawsze zwraca kompletny obiekt Decision.
"""

import logging
from dataclasses import dataclass
from typing import Optional

log = logging.getLogger("boiler.decision")

IDLE_SETTINGS = {
    "off":    (0,  0),
    "low_20": (20, 700),
    "low_30": (30, 700),
}


@dataclass
class Decision:
    mode:        str
    target_temp: int
    power_limit: int
    reason:      str

    def __repr__(self):
        return (
            f"Decision(mode={self.mode}, temp={self.target_temp}C, "
            f"power={self.power_limit}W, reason='{self.reason}')"
        )


def compute(
    boiler_temp:    float,
    boiler_online:  bool,
    manual_mode:    bool,
    manual_temp:    int,
    manual_power:   int,
    schedule_slot:  Optional[dict],
    pv_active:      bool,
    pv_power_w:     int,
    pv_target_temp: int,
    pv_reason:      str = "",
    idle_mode:      str = "off",
    max_temp:       int = 75,
) -> Decision:
    """
    Priorytet:
    1. Safety: temp >= max_temp
    2. Brak komunikacji
    3. Manual
    4. Harmonogram
    5. PV (tylko gdy pv_active=True)
    6. IDLE
    """

    # 1. SAFETY
    if boiler_temp >= max_temp:
        return Decision(
            mode="ERROR", target_temp=0, power_limit=0,
            reason=f"SAFETY: temperatura {boiler_temp:.1f}C >= limit {max_temp}C"
        )

    # 2. BRAK KOMUNIKACJI
    if not boiler_online:
        return Decision(
            mode="NO_COMM", target_temp=0, power_limit=0,
            reason="Brak komunikacji z bojlerem"
        )

    # 3. MANUAL
    if manual_mode:
        return Decision(
            mode="MANUAL",
            target_temp=manual_temp,
            power_limit=manual_power,
            reason=f"Tryb manualny: {manual_temp}C, {manual_power}W"
        )

    # 4. HARMONOGRAM
    if schedule_slot:
        slot_temp  = int(schedule_slot.get("temp_c",  55))
        slot_power = int(schedule_slot.get("power_w", 2000))
        label      = schedule_slot.get("label", f"id={schedule_slot.get('id','?')}")
        return Decision(
            mode="SCHEDULE",
            target_temp=slot_temp,
            power_limit=slot_power,
            reason=f"Harmonogram '{label}': {slot_temp}C, {slot_power}W"
        )

    # 5. PV
    if pv_active:
        return Decision(
            mode="PV",
            target_temp=pv_target_temp,
            power_limit=pv_power_w,
            reason=f"PV aktywne: {pv_power_w}W -> {pv_target_temp}C | {pv_reason}"
        )

    # 6. IDLE
    idle_temp, idle_power = IDLE_SETTINGS.get(idle_mode, (0, 0))
    return Decision(
        mode="IDLE",
        target_temp=idle_temp,
        power_limit=idle_power,
        reason=f"IDLE ({idle_mode}): {pv_reason or 'brak aktywnych warunkow'}"
    )
