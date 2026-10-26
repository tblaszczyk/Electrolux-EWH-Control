from typing import Optional
"""
service/boiler_service.py
Warstwa serwisowa — walidacja danych wejściowych z API.
Tłumaczy request → Command, wrzuca do kolejki.
"""

from config.defaults import SAFETY

VALID_POWERS = {0, 700, 1300, 2000}
VALID_IDLES  = {"off", "low_20", "low_30"}


def validate_manual(temp: int, power_limit: int) -> Optional[str]:
    """Zwraca opis błędu lub None jeśli dane są poprawne."""
    mn   = SAFETY["min_temp_manual_c"]
    mx   = SAFETY["max_temp_manual_c"]
    step = SAFETY["temp_step_c"]

    if not (mn <= temp <= mx):
        return f"Temperatura {temp}°C poza zakresem {mn}–{mx}°C"
    if temp % step != 0:
        return f"Temperatura musi być wielokrotnością {step}°C"
    if power_limit not in VALID_POWERS:
        return f"Limit mocy {power_limit}W musi być jednym z {sorted(VALID_POWERS)}"
    return None


def validate_idle_mode(mode: str) -> Optional[str]:
    if mode not in VALID_IDLES:
        return f"idle_mode musi być jednym z {sorted(VALID_IDLES)}"
    return None
