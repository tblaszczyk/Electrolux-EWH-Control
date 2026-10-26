"""
core/state_machine.py
Przejścia stanów systemu na podstawie obiektu Decision.
NIE wysyła komend — zwraca nowy stan jako string.
"""

import logging
from core.decision_logic import Decision

log = logging.getLogger("boiler.statemachine")

# Wszystkie dozwolone stany
STATES = frozenset({
    "OFF",
    "STARTING",
    "HEATING_MANUAL",
    "HEATING_SCHEDULE",
    "HEATING_PV",
    "IDLE",
    "COOLING",
    "ERROR",
    "NO_COMMUNICATION",
})

# Mapowanie Decision.mode → stan docelowy
_MODE_TO_STATE = {
    "MANUAL":   "HEATING_MANUAL",
    "SCHEDULE": "HEATING_SCHEDULE",
    "PV":       "HEATING_PV",
    "IDLE":     "IDLE",
    "ERROR":    "ERROR",
    "NO_COMM":  "NO_COMMUNICATION",
}


def transition(
    current_state: str,
    decision: Decision,
    boiler_temp: float,
    boiler_target: float,
) -> str:
    """
    Oblicza nowy stan systemu na podstawie decyzji i aktualnej temperatury.

    Obsługuje stan COOLING: jeśli bojler jest powyżej nastawy,
    nie wchodzi od razu w HEATING — czeka aż wystygnie.

    Zwraca string z nowym stanem.
    """

    # Stany krytyczne — nadpisują wszystko
    if decision.mode == "ERROR":
        _log_transition(current_state, "ERROR", decision.reason)
        return "ERROR"

    if decision.mode == "NO_COMM":
        _log_transition(current_state, "NO_COMMUNICATION", decision.reason)
        return "NO_COMMUNICATION"

    # Wyjście z OFF/STARTING → IDLE lub grzanie
    if current_state in ("OFF", "STARTING"):
        new_state = _MODE_TO_STATE.get(decision.mode, "IDLE")
        _log_transition(current_state, new_state, decision.reason)
        return new_state

    # Wyjście z ERROR/NO_COMMUNICATION — tylko jeśli decyzja jest OK
    if current_state in ("ERROR", "NO_COMMUNICATION"):
        if decision.mode in ("MANUAL", "SCHEDULE", "PV", "IDLE"):
            new_state = _MODE_TO_STATE.get(decision.mode, "IDLE")
            _log_transition(current_state, new_state, "Odzyskano komunikację / reset błędu")
            return new_state
        return current_state   # zostań w stanie błędu

    # COOLING: bojler powyżej nastawy → jeszcze nie grzej
    if decision.target_temp > 0 and boiler_temp > decision.target_temp:
        if current_state != "COOLING":
            _log_transition(current_state, "COOLING",
                            f"temp {boiler_temp:.1f}°C > target {decision.target_temp}°C")
        return "COOLING"

    # Normalne przejście
    # PV z power=0 → czekanie, traktuj jak IDLE
    if decision.mode == "PV" and decision.power_limit == 0:
        if current_state != "IDLE":
            _log_transition(current_state, "IDLE", f"PV nieaktywne (0W) — czekanie")
        return "IDLE"

    new_state = _MODE_TO_STATE.get(decision.mode, "IDLE")
    if new_state != current_state:
        _log_transition(current_state, new_state, decision.reason)
    return new_state


def _log_transition(from_s: str, to_s: str, reason: str) -> None:
    if from_s != to_s:
        log.info(f"State: {from_s} → {to_s} | {reason}")
