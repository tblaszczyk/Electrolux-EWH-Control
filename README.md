# Boiler Control System v2.1

System sterowania bojlerem elektrycznym Electrolux EWH 100 z integracją
fotowoltaiki (Hypontech HPT-8000) i harmonogramem tygodniowym.
Dostępny przez przeglądarkę z dowolnego miejsca (lokalnie i przez internet).

Od wersji 2.1 dodatkowo:
- **Detekcja zużycia wody** — wykrywa sesje poboru ciepłej wody z przebiegu
  temperatury w historii, bez żadnych dodatkowych czujników (doradcze, nie
  wpływa na sterowanie).
- **Integracja Tuya** (opcjonalna) — realny pomiar mocy z inteligentnej
  wtyczki jako alternatywa dla zadanej mocy bojlera.
- **Sterowanie pompą cyrkulacyjną** (Tuya switch) — tryb ręczny z limitem
  czasu, harmonogram z pracą pulsacyjną, niezależny od logiki bojlera.

---

## Szybki start — zarządzanie serwisem

```bash
# Status
sudo systemctl status boiler2

# Restart
sudo systemctl restart boiler2

# Logi na żywo
tail -f /opt/boiler2/logs/boiler.log

# Test API
curl http://localhost:5000/api/ping

# Ręczny backup
sudo /opt/boiler2/backup.sh

# Wdrożenie aktualizacji (po wrzuceniu ZIP na NAS)
sudo bash /opt/boiler2/update.sh /mnt/nas/NAZWA.zip
```

---

## Środowisko produkcyjne

| Parametr | Wartość |
|---|---|
| Serwer | boiler-server / 192.168.1.10 |
| Port lokalny | 5000 (nginx → Flask 8888) |
| Użytkownik serwisu | www-data |
| Python venv | /opt/boiler/venv/bin/python3 (Python 3.8) |
| Node.js | v20.x |
| NAS backup | //192.168.1.20/backup → /mnt/nas/boiler2-backup/ |
| NAS login | patrz /etc/nas-credentials |

## Urządzenia

| Urządzenie | IP / Host | Port | Protokół |
|---|---|---|---|
| Bojler Electrolux EWH 100 | 192.168.1.50 | 41122/UDP | X25519 + AES-CBC |
| Inwerter PV Hypontech HPT-8000 | api.hypon.cloud | 443/HTTPS | REST API v2 |

---

## Struktura projektu

```
/opt/boiler2/
├── app/                           # Backend Python/Flask
│   ├── main.py                    # Entry point
│   ├── .env                       # Sekrety (NIGDY nie commitować!)
│   ├── config/
│   │   └── defaults.py            # Wartości domyślne wszystkich parametrów
│   ├── core/
│   │   ├── boiler_client.py       # Komunikacja UDP z bojlerem (X25519+AES)
│   │   ├── inverter_client.py     # Hypontech Cloud API
│   │   ├── control_engine.py      # ★ Serce systemu — pętla bojlera
│   │   ├── decision_logic.py      # Logika decyzji → Decision(mode,temp,power)
│   │   ├── state_machine.py       # Przejścia stanów
│   │   ├── pv_manager.py          # PV: okno, próg, histereza, auto moc
│   │   ├── scheduler.py           # Harmonogram tygodniowy (bojler)
│   │   ├── watchdog.py            # Timeout komunikacji
│   │   ├── usage_detector.py      # Detekcja sesji poboru wody (doradcze)
│   │   ├── tuya_client.py         # Klient Tuya OpenAPI / IoT Core (odczyt + komendy)
│   │   ├── tuya_sharing_client.py # Klient Tuya Device Sharing (konto Smart Life, bez IoT Core)
│   │   ├── tuya_factory.py        # Wybór backendu wg tuya_backend
│   │   ├── pump_logic.py          # Logika decyzji pompy (manual/schedule)
│   │   └── pump_scheduler.py      # Harmonogram pompy (z pulsacją)
│   ├── service/
│   │   ├── command_queue.py       # Thread-safe kolejka komend API→CE
│   │   ├── runtime_state.py       # Stan runtime bojlera (singleton)
│   │   ├── pump_runtime.py        # Stan runtime pompy (singleton, niezależny)
│   │   └── boiler_service.py      # Walidacja danych API
│   ├── data/
│   │   ├── database.py            # SQLite — wszystkie operacje
│   │   ├── migrations.py          # Wersjonowanie schematu DB
│   │   └── models.py              # Definicje tabel SQL
│   ├── scripts/
│   │   └── backfill_usage.py      # Jednorazowy backfill detekcji na historii
│   └── api/
│       ├── app.py                 # Flask factory + rejestracja blueprintów
│       ├── auth.py                # Sesje tokenowe (Bearer token)
│       └── routes/
│           ├── status.py          # GET /api/status, /api/history, /api/tuya/history
│           ├── control.py         # POST /api/control/*
│           ├── schedule.py        # CRUD /api/schedule (bojler)
│           ├── config.py          # GET/PATCH /api/config + /connection + /tuya
│           ├── usage.py           # GET /api/usage/events, /summary
│           ├── pump.py            # Status/tryb/manual/harmonogram/historia pompy
│           ├── users.py           # CRUD /api/users (admin)
│           └── auth_routes.py     # POST /api/login, /api/logout
├── ui/                            # Frontend React 18
│   ├── src/
│   │   ├── App.js                 # Routing zakładek
│   │   ├── index.css              # CSS variables, dark/light theme
│   │   ├── api/client.js          # Komunikacja z API
│   │   ├── context/               # AuthContext, ThemeContext
│   │   ├── hooks/useStatus.js     # Polling /api/status co 8s
│   │   ├── components/Layout.js   # Header + nawigacja
│   │   └── pages/
│   │       ├── Login.js           # Strona logowania
│   │       ├── Dashboard.js       # Stan, temp, PV, pompa, przycisk ON/OFF
│   │       ├── Control.js         # AUTO/MANUAL, suwak, moc
│   │       ├── Schedule.js        # Harmonogram bojlera (styl Home Assistant)
│   │       ├── PVSettings.js      # Ustawienia PV
│   │       ├── Charts.js          # Wykresy historyczne (Recharts, warstwy)
│   │       ├── Economy.js         # Bilans PV/sieć, autokonsumpcja
│   │       ├── UsageDetection.js  # Detekcja zużycia wody (sesje, oś czasu)
│   │       ├── Pump.js            # Sterowanie pompą cyrkulacyjną
│   │       └── Settings.js        # Użytkownicy, połączenie, Tuya, logi
│   ├── build/                     # Produkcja — nginx root
│   └── package.json
├── data/
│   ├── boiler.db                  # Baza danych SQLite
│   └── config.json                # Nadpisania konfiguracji
├── logs/
│   ├── boiler.log                 # Logi aplikacji
│   ├── backup.log                 # Logi automatycznych backupów
│   └── update.log                 # Logi wdrożeń
├── backup.sh                      # Skrypt backup (cron co 3h)
├── update.sh                      # Skrypt wdrożenia aktualizacji
├── README.md                      # Ten plik
└── CHANGELOG.md                   # Historia wersji
```

---

## Konfiguracja

### /opt/boiler2/data/config.json

Nadpisuje domyślne wartości z `config/defaults.py`. Edytowalny przez UI
(Konfiguracja → Połączenie / PV) lub ręcznie. **Pola numeryczne muszą być
liczbami — nie stringami.**

| Klucz | Typ | Domyślnie | Opis |
|---|---|---|---|
| port | int | 8888 | Port Flask |
| control_loop_s | int | 10 | Pętla Control Engine [s] |
| boiler_poll_s | int | 20 | Polling bojlera [s] |
| inverter_poll_s | int | 30 | Polling inwertera [s] |
| watchdog_timeout_s | int | 30 | Timeout komunikacji [s] |
| pv_min_power_w | int | 700 | Próg minimalny PV [W] |
| pv_window_start | str | 00:00 | Okno PV od [HH:MM] |
| pv_window_stop | str | 23:59 | Okno PV do [HH:MM] |
| pv_hysteresis_s | int | 30 | Histereza PV [s] |
| pv_target_temp | int | 65 | Temperatura docelowa PV [°C] |
| pv_power_mode | str | auto | auto / 700 / 1300 / 2000 |
| pv_power_fixed_w | int | 2000 | Stała moc gdy tryb≠auto [W] |
| idle_mode | str | off | off / low_20 / low_30 |
| boiler_pub | str | — | Klucz publiczny bojlera (64 hex) |
| usage_enabled | bool | true | Włącz detekcję zużycia wody |
| usage_scan_hour | int | 4 | Godzina codziennego skanu |
| usage_min_drop_c | float | 2.0 | Próg magnitudy sesji poboru [°C] |
| tuya_enabled | bool | false | Używaj realnego pomiaru mocy Tuya zamiast power_w |
| tuya_client_id / tuya_client_secret | str | — | Dane projektu Tuya IoT Platform (wspólne dla wtyczki i pompy) |
| tuya_device_id | str | — | Device ID wtyczki pomiarowej bojlera |
| tuya_api_region | str | eu | Region Data Center Tuya (eu/weu/us/cn/in) |
| tuya_backend | str | auto | `auto` = `sharing`, gdy istnieje plik sesji, inaczej `cloud`; `cloud` = IoT Core (projekt deweloperski); `sharing` = Device Sharing przez konto Smart Life (bez IoT Core, bez kwoty) |
| tuya_session_file | str | `<katalog config.json>/tuya_session.json` | Sesja logowania QR dla backendu `sharing` (0600) |
| pump_device_id | str | — | Device ID przełącznika Tuya pompy cyrkulacyjnej |
| pump_switch_dp | str | switch_1 | Kod DP przełącznika (zależny od modelu urządzenia) |
| pump_mode | str | off | off / manual / schedule |

Uwaga: `tuya_client_secret` i `pump_device_id`/`tuya_device_id` można też
wpisać bezpośrednio w UI (Ustawienia → Tuya, Pompa → Urządzenie Tuya) —
zapisują się do `config.json` bez potrzeby edycji pliku ręcznie.

### /opt/boiler2/app/.env (sekrety)

```
BOILER_IP=192.168.1.50
BOILER_PORT=41122
BOILER_TOKEN=<token-z-parowania>
BOILER_PUB=<aktualny klucz z config.json>
HYPON_USER=twoj@email.com
HYPON_PASS=<haslo>
HYPON_STATION=<id-stacji-z-hypon-cloud>
SECRET_KEY=<losowy min 32 znaki>
DEFAULT_USER=admin
DEFAULT_PASS=<haslo>
DB_PATH=/opt/boiler2/data/boiler.db
CFG_FILE=/opt/boiler2/data/config.json
LOG_DIR=/opt/boiler2/logs
```

---

## Logika sterowania

### Priorytet decyzji (od najwyższego)

```
1. Safety:       temp >= 75°C             → ERROR
2. Brak komun.:  bojler nie odpowiada     → NO_COMMUNICATION
3. System OFF:   przycisk OFF w UI        → OFF (CE zawieszony)
4. Manual:       tryb ręczny aktywny      → HEATING_MANUAL
5. Harmonogram:  aktywny slot             → HEATING_SCHEDULE
6. PV:           warunki spełnione        → HEATING_PV
7. Reszta:                                → IDLE
```

### Stany systemu

| Stan | Kolor UI | Opis |
|---|---|---|
| HEATING_MANUAL | fiolet | Grzanie ręczne |
| HEATING_SCHEDULE | niebieski | Grzanie z harmonogramu |
| HEATING_PV | zielony | Grzanie z nadwyżki PV |
| IDLE | szary | Czuwanie |
| COOLING | pomarańczowy | Stygnięcie (temp > nastawa) |
| ERROR | czerwony | Temperatura >= 75°C |
| NO_COMMUNICATION | czerwony | Brak odpowiedzi bojlera |
| OFF | ciemny | System wyłączony przyciskiem |

### Logika PV

```
Warunki załączenia:
  pv_power >= pv_min_power_w  AND  godzina IN [window_start, window_stop]

Auto moc (nadwyżka = pv_power - pv_min_power_w):
  nadwyżka < 300W   → bojler 700W
  nadwyżka < 700W   → bojler 1300W
  nadwyżka >= 700W  → bojler 2000W

Histereza działa przy włączaniu I wyłączaniu:
  warunki muszą być stabilne przez pv_hysteresis_s sekund
```

### Detekcja zużycia wody (doradcza — zero wpływu na sterowanie)

`core/usage_detector.py` wykrywa **sesje** poboru wody z tempa spadku
temperatury w `boiler_history` (nie tylko magnitudy — kryterium tempa
°C/min eliminuje fałszywe trafienia z naturalnego stygnięcia zbiornika,
zwalidowane na realnej historii produkcyjnej). Sąsiadujące "aktywne"
odcinki są łączone w jedną sesję (z liczbą "faz" `n_bursts` jako
przybliżeniem liczby osób), żeby jedna wieczorna seria pryszniców nie
rozpadała się na osobne, częściowo odrzucane fragmenty.

```
Segmentacja: odcinki heating=0 (gap > 5 min przerywa odcinek)
Aktywność:   tempo spadku >= usage_active_rate_c_per_min (0.3°C/min)
Sesja:       złączenie aktywnych odcinków z przerwą <= usage_merge_gap_min (15 min)
Kategoria:   'session' (drop >= 2.0°C) | 'subthreshold' (0.5–2.0°C, możliwa pompa cyrkulacyjna)
Baseline:    mediana trailing 8 tyg. per dzień tygodnia → sygnał zero/poniżej typowej/normalnie
```

Backfill na pełnej historii: `scripts/backfill_usage.py` (uruchom po
migracji/reset danych — patrz sekcja *Baza danych*). Codzienny skan
(ostatnie 48h) działa automatycznie w tle.

### Integracja Tuya (opcjonalna)

`core/tuya_client.py` — klient Tuya OpenAPI (stdlib `urllib`, zero nowych
zależności), podpisywanie żądań wg spec Tuya Cloud API (HMAC-SHA256).
Gdy `tuya_enabled=true`, realny pomiar mocy z wtyczki zastępuje zadaną
`power_w` na Dashboardzie i w Ekonomii (zweryfikowane na żywym urządzeniu
jako znacząco dokładniejsze — zadana moc ≠ rzeczywisty pobór, różnica
potwierdzona pomiarem podczas wdrożenia). Wątek odpytujący co
`tuya_poll_s` (60s domyślnie) zapisuje odczyty do `tuya_readings`.

#### Backend `sharing` (Device Sharing) — gdy kończy się trial IoT Core

Objaw wyczerpania IoT Core: w `logs/boiler.log` powtarza się
`Tuya: błąd odczytu statusu: IoT Core trial quota is exhausted.`, pompa nie
reaguje (`Pump: komenda set_switch(True) nieudana`), a `tuya_online=false`.
Backend `sharing` (`core/tuya_sharing_client.py`) używa tego samego API co
integracja Home Assistant: loguje się kontem aplikacji Smart Life przez kod QR,
nie potrzebuje projektu deweloperskiego ani `tuya_client_id/secret`.
Interfejs jest ten sam co `TuyaClient` (`get_status`, `set_switch`), więc pętla
pompy i odczyt mocy wtyczki działają bez zmian; wybór robi `core/tuya_factory.py`.

Włączenie (jednorazowo):

1. Doinstaluj SDK: `/opt/boiler/venv/bin/pip install --target /opt/boiler2/app/vendor tuya-device-sharing-sdk qrcode` (katalog `app/vendor` jest w `.gitignore`; klient sam dodaje go do `sys.path`, więc nie trzeba roota ani zmian w venv).
2. Zaloguj się kodem QR (kod użytkownika: Smart Life → Ja → Ustawienia → Konto i bezpieczeństwo → Kod użytkownika):
   `/opt/boiler/venv/bin/python /opt/boiler2/app/tools/tuya_login.py <KOD_UŻYTKOWNIKA>` (plik sesji dostaje grupę `www-data` i tryb 0660)
   i zeskanuj QR w aplikacji (Smart Life → Ja → ikona skanera). Powstaje `data/tuya_session.json`.
3. Zrestartuj `boiler2` (`tuya_backend` domyślnie `auto` wybiera `sharing`, gdy plik sesji istnieje; można wymusić `"tuya_backend": "sharing"` w `data/config.json`).
4. Sprawdź `GET /api/pump/status` i log (`Pump: WŁĄCZONA`); komenda trafia do chmury, a stan gniazda można zweryfikować w Smart Life.

Podtrzymanie sesji: token dostępu ważny jest 2 h, a SDK odświeża go dopiero w ostatniej
minucie (po wygaśnięciu odświeżenie jest odrzucane: `token is expired` → `sign invalid`).
Pompa komunikuje się z Tuya rzadko, więc `TuyaSharingClient` ma wątek `tuya_keepalive`, który co 60 s
odświeża token, gdy zostało mniej niż 30 min. Jeśli sesja mimo to umrze (np. VM wyłączona >2 h),
w logu pojawi się `wymagane ponowne logowanie QR` — wtedy uruchom `tools/tuya_login.py` ponownie
i zrestartuj usługę.

Uwagi: ta sama sesja Smart Life nie powinna być współdzielona z innym
programem (np. tv-display) — każdy konsument ma własne logowanie QR, bo
odświeżenie tokenu przez jednego może unieważnić drugi. Wycofanie: `"tuya_backend": "cloud"`
(lub usunięcie pliku sesji) i restart. Sterowanie jest nadal chmurowe (nie lokalne LAN); lokalne
sterowanie (tinytuya + `local_key`) to osobna, możliwa przyszła zmiana.

### Powiadomienia o awariach (ntfy)

`core/notifier.py` wysyła powiadomienia ntfy, gdy coś przestaje działać (powtórzenie co 6 h, a po powrocie
do normy komunikat „znów działa”). Adres tematu: zmienna `NTFY_URL` albo plik `data/ntfy.url`
(np. `https://ntfy.sh/moj-temat`; plik jest w `.gitignore`). Brak adresu = tylko wpis w logu.

| Zdarzenie | Próg | Gdzie |
|---|---|---|
| Komenda do pompy nie przechodzi (np. Tuya) | > 1 min | pętla pompy (`main.py`) |
| Sesja Tuya wygasła (wymagane QR) | od razu | `TuyaSharingClient.auth_error` |
| Błąd pętli pompy (wyjątek) | > 1 min | `main.py` |
| Brak łączności ze sterownikiem bojlera | > 5 min | `control_engine._poll_boiler` |
| Start usługi (priorytet min) | — | `main.py` |

Gdy sam Bojler2 padnie, powiadomi o tym tv-display (`boiler_alert.py`): brak odpowiedzi API > 5 min lub
`last_update` pętli pompy starszy niż 5 min.

### Sterowanie pompą cyrkulacyjną (Tuya switch)

Całkowicie niezależna pętla (`core/pump_logic.py` + `core/pump_scheduler.py`
+ `service/pump_runtime.py`), zero ingerencji w `decision_logic.py`/
`control_engine.py` bojlera. Priorytet: **manual** (zawsze z limitem
czasu 5–30 min) > **schedule** (opcjonalna praca pulsacyjna w oknie
czasowym, np. "5 min włączona / 15 min przerwy") > **off**.

```
Priorytet:  manual (z wygasającym limitem) > schedule (z pulsacją) > off
Pulsacja:   pozycja w cyklu = (teraz - start_slotu) mod (cycle_on+cycle_off) — bezstanowe
Sync:       pierwsza komenda po restarcie serwisu ZAWSZE wysyłana
            (synchronizacja realnego stanu, gdyby serwis padł z pompą włączoną)
```

Historia uruchomień (kiedy, jak długo, ręcznie czy z harmonogramu) w
tabeli `pump_history`, widoczna w zakładce Pompa i jako warstwa na
głównym wykresie.

### Przycisk ON/OFF vs IDLE=off

| | Przycisk OFF | IDLE=off |
|---|---|---|
| Bojler | wyłączony | wyłączony |
| CE działa | NIE | TAK |
| Harmonogram | ignorowany | może włączyć |
| PV | ignorowane | może włączyć |
| Wznowienie | tylko przycisk ON | automatyczne |

---

## Protokół bojlera (UDP)

### Format ramki
```
struct.pack('>BHH', type, seq, len(payload)) + payload
```

### Handshake (2 etapy)
```
1. HELLO     (0x01): wysyłamy my_pub(32B klucz X25519)
   HELLO_RESP(0x02): odbieramy dev_pub(32B) → oblicz klucz sesji
2. AUTH      (0x03): wysyłamy my_pub + AES_enc(token padded 32B)
   AUTH_RESP (0x04): payload[0]==0x01 = OK
```

### Klucz sesji AES-CBC
```python
secret = priv.exchange(X25519PublicKey.from_public_bytes(dev_pub))
key16  = SHA256(secret)[:16]
iv     = os.urandom(16)           # losowy IV
cipher = iv + AES_CBC_PKCS7(key16, iv, plaintext)
```

### Komendy
```
cmd=0x02 payload[0]: temperatura nastawa [°C]
cmd=0x14 payload[0]: temperatura aktualna [°C]
cmd=0x01 payload[0]: moc (val=1/2/3 → 700/1300/2000W)
cmd=0x91 payload[1]: bit0=power ON/OFF
```

### Mapowanie mocy
```
700W  → POWER_W_TO_LEVEL=1 → pwr_byte=1
1300W → POWER_W_TO_LEVEL=2 → pwr_byte=2
2000W → POWER_W_TO_LEVEL=3 → pwr_byte=3
OFF   → pwr_byte=0
```

### Status grzania
Bojler **nie raportuje** statusu grzania w żadnym bicie. Logika:
```python
heating = power == True AND temp_current < temp_target
```

### Klucz publiczny (BOILER_PUB)
Zmienia się po hard resecie urządzenia. Aktualny klucz zawsze
w `/opt/boiler2/data/config.json` (pole `boiler_pub`).

---

## Baza danych

| Tabela | Zawartość | Retencja |
|---|---|---|
| boiler_history | temp, moc, PV, stan — co 60s | 365 dni |
| system_events | zmiany stanów, decyzje CE | 30 dni |
| user_actions | akcje użytkownika + IP | 30 dni |
| auth_log | logowania: user + IP + wynik | 30 dni |
| users | login, hash SHA256+salt, is_admin | bez limitu |
| schedule_slots | definicje harmonogramu bojlera | bez limitu |
| draw_events | wykryte sesje poboru wody (start/koniec, spadek, n_bursts, kategoria) | 365 dni |
| tuya_readings | realne odczyty mocy z wtyczki Tuya | 365 dni |
| pump_schedule_slots | definicje harmonogramu pompy (z pulsacją) | bez limitu |
| pump_history | uruchomienia pompy: start/koniec/czas/źródło | brak automatycznej (kolumna `start_ts`, poza generyczną retencją) |
| schema_version | wersja schematu (migracje, aktualnie v5) | — |

Migracja schematu jest idempotentna (`init_db()` przy każdym starcie) —
`draw_events` była raz przebudowana (v3, model punktowy → sesyjny); po
takiej zmianie modelu danych trzeba ręcznie ponowić
`scripts/backfill_usage.py`, żeby odtworzyć historię w nowym formacie.

---

## API — endpointy

Autoryzacja: `Authorization: Bearer <token>` lub cookie `session_token`.
Wyjątki bez autoryzacji: `/api/ping`, `/api/login`.

| Metoda | Endpoint | Opis | Admin |
|---|---|---|---|
| POST | /api/login | Logowanie → token | — |
| POST | /api/logout | Wylogowanie | — |
| GET | /api/ping | Health check | — |
| GET | /api/status | Pełny stan runtime | — |
| GET | /api/history?hours=N | Historia z DB | — |
| GET | /api/events/recent | Ostatnie 100 zdarzeń | — |
| POST | /api/control/manual | Tryb manual {temp, power_limit} | — |
| POST | /api/control/auto | Tryb automatyczny | — |
| POST | /api/control/power | ON/OFF systemu {enabled} | — |
| POST | /api/control/idle_mode | Zmień IDLE {mode} | — |
| GET | /api/schedule | Lista slotów | — |
| POST | /api/schedule | Dodaj slot | — |
| PUT | /api/schedule/<id> | Edytuj slot | — |
| DELETE | /api/schedule/<id> | Usuń slot | — |
| GET | /api/config | Konfiguracja PV/system | — |
| PATCH | /api/config | Zmień parametry PV/system | — |
| GET | /api/config/connection | Ustawienia połączenia | — |
| PATCH | /api/config/connection | Zmień IP/porty | ✓ |
| GET | /api/config/tuya | Ustawienia Tuya (bez sekretu) | — |
| PATCH | /api/config/tuya | Zmień dane Tuya / włącz-wyłącz | ✓ |
| GET | /api/system/info | Wersja, stan, dry_run | — |
| GET | /api/users | Lista użytkowników | ✓ |
| POST | /api/users | Dodaj użytkownika | ✓ |
| DELETE | /api/users/<id> | Usuń użytkownika | ✓ |
| POST | /api/users/<id>/password | Zmień hasło | własne/✓ |
| GET | /api/usage/events?hours=N | Wykryte sesje poboru wody | — |
| GET | /api/usage/summary?range= | Podsumowanie dzienne + sygnał baseline | — |
| GET | /api/tuya/history?hours=N | Surowe odczyty mocy Tuya (do wykresu) | — |
| GET | /api/pump/status | Stan pompy, tryb, licznik ręcznego trybu | — |
| POST | /api/pump/mode | Zmień tryb {mode} | — |
| POST | /api/pump/manual | Włącz na czas {on, minutes} | — |
| GET/POST | /api/pump/schedule | Lista / dodaj slot pompy | — |
| PUT/DELETE | /api/pump/schedule/<id> | Edytuj / usuń slot pompy | — |
| GET | /api/pump/config | Device ID / kod DP pompy | — |
| PATCH | /api/pump/config | Zmień Device ID / kod DP | ✓ |
| GET | /api/pump/history?hours=N | Historia uruchomień pompy | — |

---

## Backup i restore

### Automatyczny / ręczny backup
`backup.sh` robi pełne lustro `rsync` (nie archiwum tar.gz) na NAS,
pomijając `logs/`, `ui/node_modules/`, `ui/build/`:

```
Cel:      /mnt/nas/boiler2-backup/YYYY-MM-DD_HH-MM/
Retencja: 30 ostatnich kopii (po liczbie, nie po wieku)
```

```bash
sudo /opt/boiler2/backup.sh
```

### Restore z backupu
```bash
sudo systemctl stop boiler2
sudo rsync -a --delete /mnt/nas/boiler2-backup/YYYY-MM-DD_HH-MM/ /opt/boiler2/
sudo chown -R www-data:www-data /opt/boiler2/data /opt/boiler2/logs /opt/boiler2/app /opt/boiler2/ui
sudo systemctl daemon-reload && sudo systemctl start boiler2
sudo systemctl reload nginx
curl http://localhost:5000/api/ping
```

### Montowanie NAS (gdy odmontowany)
Udział to `//192.168.1.20/backup`,
dane logowania w `/etc/nas-credentials` (root-only, nie w repo):
```bash
sudo mount -t cifs //192.168.1.20/backup /mnt/nas \
  -o credentials=/etc/nas-credentials,iocharset=utf8,uid=root,gid=root,_netdev
```

---

## Wdrożenie aktualizacji

### Workflow (przez NAS)
```
1. Pobierz ZIP z Claude na komputer
2. Wrzuć ZIP przez Sambę do \\192.168.1.20\backup\
3. Na serwerze:
   sudo bash /opt/boiler2/update.sh /mnt/nas/NAZWA.zip
```

### Ręczne wdrożenie
```bash
unzip -o /mnt/nas/NAZWA.zip -d ~/
cd /opt/boiler2/ui && npm run build
sudo systemctl restart boiler2
```

### Znane problemy Python 3.8 (naprawiane automatycznie przez update.sh)
```bash
# list[Command] → list
sed -i 's/def drain(self) -> list\[Command\]:/def drain(self) -> list:/' \
  /opt/boiler2/app/service/command_queue.py

# set_hysteresis usunięte
sed -i 's/pv_manager.set_hysteresis(config.get("pv_hysteresis_s", 30))/# przez cfg/' \
  /opt/boiler2/app/core/control_engine.py
```

---

## Znane problemy i rozwiązania

| Problem | Rozwiązanie |
|---|---|
| Klucz bojlera po resecie | Sprawdź aktualny w config.json (boiler_pub) |
| Typy numeryczne jako string | Zawsze używaj liczb bez cudzysłowów w config.json |
| Konto Hypontech zablokowane | Odczekaj 15 min, nie restartuj zbyt często |
| Python 3.8 type hints | Używaj Optional[X] z typing zamiast X\|None i list[X] |
| NAS odmontowany | sudo mount -t cifs //192.168.1.20/backup /mnt/nas -o credentials=/etc/nas-credentials,uid=root,gid=root |
| Stare apki zajmują bojler | ps aux \| grep python — sprawdź /opt/boiler i /opt/electrolux-ctrl |
| Port 5000 zajęty | Nginx używa 5000, Flask 8888 — nie zmieniaj portu w config.json |
| boiler_heating pokazuje błędnie | Logika: power=True AND temp_current < temp_target AND state NOT IN (IDLE,OFF,COOLING) |
| Warstwa draw_events/pump_events niewidoczna na wykresie | Oś X jest kategoryczna — zdarzenia z innych tabel muszą być dopasowane do najbliższego istniejącego `ts` (patrz `snapToNearestTs` w Charts.js), inaczej Recharts nie renderuje |
| Kod DP przełącznika Tuya inny niż switch_1 | Różni się między modelami — sprawdź `get_raw_status()` w `tuya_client.py` przed pierwszym użyciem nowego urządzenia |
| Wtyczka Tuya bez pomiaru mocy (cur_power zawsze 0) | Niektóre modele przełączników nie mają czujnika — normalne, funkcja pompy nie zależy od pomiaru mocy, tylko od stanu przełącznika |
| Konto deweloperskie Tuya "nie istnieje" przy odzyskiwaniu hasła | iot.tuya.com to osobna baza kont od apki Tuya Smart/Smart Life — trzeba założyć nowe konto (Sign Up), nie odzyskiwać hasło do nieistniejącego |

---

## Optymalne ustawienia PV (rekomendacja)

```
pv_window_start:  09:00
pv_window_stop:   16:00
pv_target_temp:   65°C
pv_power_mode:    auto
pv_min_power_w:   700
pv_hysteresis_s:  30

Harmonogram — slot wieczorny (zabezpieczenie):
  Pon–Nd, 20:00–21:30, 55°C, 2000W
  (nie włączy się jeśli PV już nagrzało do 65°C)

idle_mode: off
```
