# Boiler Control System v2.0 — Backup

## Data backupu
Wygenerowany: automatycznie przez skrypt backup.sh

## Zawartość archiwum

```
boiler_backup_YYYYMMDD_HHMM.tar.gz
├── home/<user>/boiler-system/     # Kod backendu (Python/Flask)
├── home/<user>/boiler-ui/         # Kod frontendu (React) + build/
├── var/lib/boiler/                # Baza danych SQLite + config.json
├── var/log/boiler/                # Logi aplikacji
├── etc/nginx/sites-available/boiler  # Konfiguracja nginx
├── etc/systemd/system/boiler2.service # Serwis systemd
└── README.md                      # Ten plik
```

## Serwer produkcyjny

| Parametr | Wartość |
|---|---|
| IP | 192.168.1.10 |
| Port publiczny | 5000 (nginx) |
| Port backendu | 8888 (Flask) |
| Użytkownik serwisu | www-data |
| Python venv | /opt/boiler/venv |
| Node.js | v20.x |

## Urządzenia

| Urządzenie | IP | Port |
|---|---|---|
| Bojler Electrolux EWH 100 | 192.168.1.50 | 41122/UDP |
| Inwerter PV Hypontech | api.hypon.cloud | 443/HTTPS |

## Przywracanie z backupu

```bash
# 1. Zatrzymaj serwis
sudo systemctl stop boiler2

# 2. Rozpakuj backup
sudo tar -xzf boiler_backup_YYYYMMDD_HHMM.tar.gz -C /

# 3. Przywróć uprawnienia
sudo chown -R www-data:www-data /var/lib/boiler /var/log/boiler

# 4. Przeładuj i uruchom
sudo systemctl daemon-reload
sudo systemctl start boiler2
sudo systemctl reload nginx

# 5. Sprawdź
curl http://localhost:5000/api/ping
```

## Wdrożenie na nowym serwerze

```bash
# 1. Zainstaluj zależności
sudo apt install -y nginx nodejs
python3 -m venv /opt/boiler/venv
/opt/boiler/venv/bin/pip install flask flask-cors cryptography

# 2. Utwórz katalogi
sudo mkdir -p /var/lib/boiler /var/log/boiler
sudo chown www-data:www-data /var/lib/boiler /var/log/boiler

# 3. Rozpakuj backup i uzupełnij .env
cd ~/boiler-system
cp .env.example .env
nano .env  # uzupełnij BOILER_TOKEN, HYPON_PASS, SECRET_KEY

# 4. Zbuduj UI
cd ~/boiler-ui
npm install
npm run build

# 5. Aktywuj serwisy
sudo systemctl daemon-reload
sudo systemctl enable --now boiler2
sudo ln -sf /etc/nginx/sites-available/boiler /etc/nginx/sites-enabled/
sudo systemctl enable --now nginx
```

## Ważne uwagi

- **BOILER_PUB** — klucz publiczny bojlera zmienia się po hard resecie.
  Aktualny klucz zawsze jest w `/var/lib/boiler/config.json` (pole `boiler_pub`).

- **Typy w config.json** — pola numeryczne (port, poll_s itp.) muszą być
  zapisane jako liczby, nie stringi.

- **Stare aplikacje** — `/opt/electrolux-ctrl` i `/opt/boiler` są wyłączone.
  Nie uruchamiaj ich — zajmą port bojlera i uniemożliwią komunikację.

- **Hypontech** — po 5 błędnych próbach logowania konto blokuje się na 15 min.

## Kontakt / dokumentacja

Pełna dokumentacja: `boiler_dokumentacja_kompletna.pdf`
