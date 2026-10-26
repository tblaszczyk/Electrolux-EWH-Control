#!/bin/bash
# update.sh — Wdrożenie nowej wersji Boiler Control System
# Użycie: sudo bash /opt/boiler2/update.sh [ZIP_FILE]
# Przykład: sudo bash /opt/boiler2/update.sh /mnt/nas_backup/boiler-update.zip

set -e

ZIP_FILE="${1:-}"
APP_DIR="/opt/boiler2/app"
UI_DIR="/opt/boiler2/ui"
LOG="/opt/boiler2/logs/update.log"
DATE=$(date '+%Y-%m-%d %H:%M:%S')

log() { echo "[$DATE] $1" | tee -a "$LOG"; }

log "=== START AKTUALIZACJI ==="

# 1. Sprawdź ZIP
if [ -n "$ZIP_FILE" ]; then
    if [ ! -f "$ZIP_FILE" ]; then
        log "BŁĄD: Nie znaleziono pliku $ZIP_FILE"
        exit 1
    fi
    log "Rozpakowuję: $ZIP_FILE"
    unzip -o "$ZIP_FILE" -d /home/tomasz/ && cp -r /home/tomasz/boiler-system/. "$APP_DIR/" 2>/dev/null || true && cp -r /home/tomasz/boiler-ui/. "$UI_DIR/" 2>/dev/null || true
    log "Rozpakowano OK"
fi

# 2. Kopiuj backend jeśli istnieje
if [ -d "/home/tomasz/boiler-system" ]; then
    log "Kopiuję backend..."
    cp -r /home/tomasz/boiler-system/. "$APP_DIR/"
    chown -R www-data:www-data "$APP_DIR/"
    log "Backend OK"
fi

# 3. Kopiuj UI jeśli istnieje
if [ -d "/home/tomasz/boiler-ui" ]; then
    log "Kopiuję UI..."
    cp -r /home/tomasz/boiler-ui/. "$UI_DIR/"
    chown -R tomasz:tomasz "$UI_DIR/"
    log "UI OK"
fi

# 4. Napraw znane problemy Python 3.8
log "Naprawiam kompatybilność Python 3.8..."
sed -i 's/def drain(self) -> list\[Command\]:/def drain(self) -> list:/' \
    "$APP_DIR/service/command_queue.py" 2>/dev/null || true
sed -i 's/pv_manager.set_hysteresis(config.get("pv_hysteresis_s", 30))/# histereza przez cfg/' \
    "$APP_DIR/core/control_engine.py" 2>/dev/null || true

# 5. Build UI
log "Buduję UI..."
cd "$UI_DIR"
npm run build >> "$LOG" 2>&1
log "Build OK"

# 6. Restart serwisu
log "Restartuję serwis..."
systemctl restart boiler2
sleep 5

# 7. Sprawdź czy działa
if curl -s http://localhost:5000/api/ping | grep -q "ok"; then
    log "=== AKTUALIZACJA ZAKOŃCZONA SUKCESEM ==="
else
    log "BŁĄD: API nie odpowiada po aktualizacji!"
    exit 1
fi

# 8. Backup po aktualizacji
log "Tworzę backup po aktualizacji..."
/opt/boiler2/backup.sh >> "$LOG" 2>&1 || true

log "=== KONIEC ==="
