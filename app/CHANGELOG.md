# CHANGELOG

## [2.0.0] — 2025-01

### Nowa architektura
- Control Engine jako jedyne źródło decyzji sterujących
- State machine (OFF, HEATING_MANUAL, HEATING_SCHEDULE, HEATING_PV, IDLE, COOLING, ERROR, NO_COMMUNICATION)
- Command Queue (thread-safe) — API wrzuca komendy, CE wykonuje
- Decision Logic — zawsze zwraca Decision(mode, temp, power, reason)
- Runtime State — separacja od config
- Warstwa Service między API a Core
- Migracje schematu DB (versioned)
- Retencja danych: 365 dni historia, 30 dni logi
- dry_run mode w BoilerClient
- Port: 8888
