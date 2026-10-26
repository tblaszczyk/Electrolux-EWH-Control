# CHANGELOG — Boiler Control System

Format: [YYYY-MM-DD] v X.Y.Z — opis zmian

---

## [2026-10-26] v2.1.2 — Anonimizacja repozytorium przed upublicznieniem

- Usunięto z `app/.env.example` i `README.md` prawdziwy token/klucz bojlera, ID stacji Hypontech
  i e-mail konta — zastąpione wartościami przykładowymi
- Adresy IP, nazwy hostów/udziałów NAS i publiczne IP w dokumentacji zamienione na przykładowe
- Zmiany wyłącznie w dokumentacji i plikach przykładowych — kod bez zmian

## [2026-10-16] v2.1.1 — Szybkie sterowanie pompą z Dashboardu

- Plakietka statusu pompy na głównym ekranie jest teraz przyciskiem: po kliknięciu
  pokazuje menu 5 / 10 / 15 min (oraz „Wyłącz”, gdy pompa pracuje)
- Wybór czasu wywołuje `POST /api/pump/manual` (przełącza pompę w tryb ręczny)

## [2026-09-21] v2.1.0 — Detekcja zużycia wody, integracja Tuya, sterowanie pompą

### Detekcja zużycia wody (doradcza, bez wpływu na sterowanie)
- Nowy moduł `core/usage_detector.py` — wykrywa sesje poboru ciepłej wody z tempa spadku
  temperatury w `boiler_history` (segmentacja odcinków + próg tempa °C/min, nie tylko
  magnitudy — eliminuje fałszywe trafienia z naturalnego stygnięcia zbiornika)
- Backfill na pełnej historii (`scripts/backfill_usage.py`) + codzienny wątek skanujący
- Baseline per dzień tygodnia (mediana trailing 8 tyg.) — sygnał "poniżej typowego/zero"
  bez żadnych ręcznych etykiet
- Nowa zakładka "Detekcja zużycia": podsumowanie, oś czasu (pasy 00–24h), lista zdarzeń
- Nakładka sesji na głównym wykresie (warstwa `draw_events`)

### Integracja Tuya (opcjonalna, przełącznik w Ustawieniach)
- `core/tuya_client.py` — klient Tuya OpenAPI (odczyt mocy z wtyczki pomiarowej + komendy
  sterujące), bez nowych zależności (stdlib `urllib`)
- Realny pomiar mocy jako alternatywne źródło dla Dashboardu i Ekonomii (przełącznik
  "Używaj danych z Tuya") — zweryfikowane na żywym urządzeniu jako dokładniejsze od
  `power_w` (zadana moc ≠ rzeczywisty pobór, różnica potwierdzona pomiarem)
- Nakładka realnej mocy na głównym wykresie (warstwa `tuya_power_w`)

### Sterowanie pompą cyrkulacyjną (Tuya switch)
- Nowa zakładka "Pompa cyrkulacyjna": tryb wyłączony / ręczny (zawsze z limitem czasu,
  5–30 min) / harmonogram (z opcjonalną pracą pulsacyjną w oknie czasowym)
- Niezależna pętla sterująca (`core/pump_logic.py`, `core/pump_scheduler.py`,
  `service/pump_runtime.py`) — zero ingerencji w `decision_logic.py`/`control_engine.py`
  bojlera; pierwsza komenda po restarcie serwisu zawsze wysyłana (synchronizacja stanu)
- Historia uruchomień (kiedy, jak długo, ręcznie/z harmonogramu) + nakładka na wykresie

### Baza danych
- Migracje v2–v5: `draw_events` (przebudowana raz z modelu punktowego na sesyjny),
  `tuya_readings`, `pump_schedule_slots`, `pump_history`

### Poprawki
- Naprawiony błąd podwójnego przesunięcia strefy czasowej w agregacjach SQL
  (`'localtime'` na już-lokalnym `ts` powodował błędne grupowanie po dniu/godzinie)
- `inverter_client.py`: odporność na niedostępność chmury PV (timeout + backoff,
  zamiast blokowania pętli sterującej co cykl)
- `backup.sh`: przepisany na rsync (pełne odzwierciedlenie zamiast tar.gz), nowa
  ścieżka NAS, retencja po liczbie kopii zamiast po wieku

---

## [2026-04-19] v2.0.0 — Premiera produkcyjna

### Architektura
- Pełna migracja z jednoplikowego skryptu `/opt/boiler/app.py` do modularnej aplikacji
- Backend: Python 3.8 / Flask, uruchamiany jako serwis `boiler2.service` (www-data)
- Frontend: React 18 + Recharts, serwowany przez nginx (port 5000)
- Baza danych: SQLite z migracjami wersji schematu
- Projekt przeniesiony z katalogu domowego do `/opt/boiler2/`

### Backend — Control Engine
- Pętla sterowania co 3s (wcześniej brak pętli)
- Priorytet decyzji: Safety → NO_COMM → OFF → MANUAL → SCHEDULE → PV → IDLE
- Thread-safe command queue (last-write-wins dla SET_*, queue-all dla RELOAD_*)
- State machine z pełną historią przejść stanów
- Watchdog timeout dla bojlera i inwertera PV

### Protokół bojlera
- Zdebugowany pełny protokół UDP X25519 + AES-CBC
- Mapowanie mocy: 700W→pwr_byte=1, 1300W→2, 2000W→3
- Status grzania: bojler nie raportuje bitu grzania — logika: power=True AND temp_current < temp_target
- Auto-refresh klucza publicznego przez mDNS

### Logika PV (pv_manager.py)
- Okno czasowe (pv_window_start / pv_window_stop)
- Próg minimalny mocy (pv_min_power_w)
- Histereza przy włączaniu I wyłączaniu (pv_hysteresis_s)
- Auto moc: nadwyżka PV → moc bojlera (nadwyżka<300W→700W, <700W→1300W, ≥700W→2000W)
- Temperatura docelowa konfigurowana osobno (pv_target_temp)
- Tryb mocy: auto lub stała wartość (700/1300/2000W)

### Harmonogram (scheduler.py)
- Sloty z wyborem dni tygodnia, godzin, temperatury i mocy
- Tryb IDLE: off / low_20 (20°C + 700W) / low_30 (30°C + 700W)
- IDLE=off: CE działa, harmonogram/PV mogą włączyć bojler

### Przycisk ON/OFF systemu
- OFF: zawiesza CE całkowicie, bojler wyłączony, harmonogram i PV ignorowane
- ON: wznawia CE z ostatnim aktywnym trybem
- Różnica od IDLE=off: IDLE nie zawiesza CE

### Frontend — zakładki
- **Dashboard**: gauge temperatury, PowerBar, StatChips PV, przycisk ON/OFF obok karty trybu
- **Sterowanie**: przełącznik AUTO/MANUAL, suwak temp z kolorem, wybór mocy, przycisk Edytuj (timeout 3s)
- **Harmonogram**: styl Home Assistant, IDLE selector, sloty z toggle i modalem
- **Ustawienia PV**: próg, okno, histereza, temperatura, tryb mocy z wyjaśnieniem nadwyżki
- **Wykresy**: Recharts ComposedChart, selektor zakresu (6h/24h/3d/7d + custom), warstwy, kolorowe tło trybów
- **Konfiguracja**: zakładki Użytkownicy (CRUD, zmiana hasła, role admin), Połączenie, System, Logi

### Infrastruktura
- Nginx jako reverse proxy (port 5000 → 8888)
- Systemd autostart (www-data)
- Automatyczny backup co 3h na NAS (/mnt/nas_backup/backup_boiler2/), retencja 3 dni
- Meta tagi PWA dla trybu fullscreen na telefonie

### Poprawki błędów
- Mapowanie mocy bojlera naprawione (stara apka: max pwr_byte=3, nowa błędnie wysyłała 4)
- Config.json: pola numeryczne konwertowane na int w endpointach
- Python 3.8: usunięto list[dict], str|None → Optional[X] z typing
- boiler_heating=False gdy stan IN (IDLE, OFF, COOLING, NO_COMM, ERROR)
- Temperatura docelowa w gauge: last_decision_temp zamiast boiler_temp_target
- Podwójne logi przy starcie — artefakt restartu, niegroźne
- Control Engine: usunięto lock z get_status() i set_target()

---

## Szablon dla przyszłych wpisów

```
## [YYYY-MM-DD] vX.Y.Z — krótki opis

### Co zostało zmienione
-

### Poprawki błędów
-

### Znane problemy
-
```
