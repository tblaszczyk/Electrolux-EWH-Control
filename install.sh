#!/bin/bash
# install.sh — Fresh installation of Boiler Control System v2
# Usage: sudo bash install.sh
# Run from the cloned repo root: /opt/boiler2/

set -e

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
INSTALL_DIR="/opt/boiler2"
VENV_DIR="/opt/boiler/venv"
LOG_DIR="$INSTALL_DIR/logs"
DATA_DIR="$INSTALL_DIR/data"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
log()  { echo -e "${GREEN}[+]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
err()  { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

# ── 0. Root check ──────────────────────────────────────────────────────────────
[ "$(id -u)" -eq 0 ] || err "Run as root: sudo bash install.sh"

# ── 1. System packages ─────────────────────────────────────────────────────────
log "Installing system packages..."
apt-get update -qq
apt-get install -y --no-install-recommends \
    python3 python3-pip python3-venv \
    nodejs npm \
    nginx curl \
    > /dev/null
log "System packages OK"

# ── 2. Directory structure ─────────────────────────────────────────────────────
log "Creating directories..."
mkdir -p "$LOG_DIR" "$DATA_DIR" "$VENV_DIR"
touch "$LOG_DIR/boiler.log" "$LOG_DIR/backup.log" "$LOG_DIR/update.log"

# If installed from a different path, copy to /opt/boiler2
if [ "$REPO_DIR" != "$INSTALL_DIR" ]; then
    log "Copying files to $INSTALL_DIR..."
    rsync -a --exclude='.git' --exclude='data/config.json' --exclude='data/boiler.db' \
        --exclude='app/.env' --exclude='app/data_storage' --exclude='logs' \
        --exclude='ui/node_modules' --exclude='ui/build' \
        "$REPO_DIR/" "$INSTALL_DIR/"
fi

# ── 3. Python virtual environment ─────────────────────────────────────────────
log "Setting up Python venv at $VENV_DIR..."
python3 -m venv "$VENV_DIR"
"$VENV_DIR/bin/pip" install --quiet --upgrade pip
"$VENV_DIR/bin/pip" install --quiet -r "$INSTALL_DIR/app/requirements.txt"
log "Python dependencies installed"

# ── 4. Build React UI ─────────────────────────────────────────────────────────
log "Building React UI..."
cd "$INSTALL_DIR/ui"
npm install --silent
npm run build --silent
log "UI build OK"

# ── 5. Configure the application ──────────────────────────────────────────────
if [ ! -f "$DATA_DIR/config.json" ]; then
    warn "No config.json found. Copying example — EDIT IT before starting the service."
    cp "$INSTALL_DIR/data/config.example.json" "$DATA_DIR/config.json"
    echo ""
    echo "  Edit: $DATA_DIR/config.json"
    echo "  Required fields: boiler_ip, boiler_token, boiler_pub,"
    echo "                   hypon_user, hypon_pass, hypon_station,"
    echo "                   web_user, web_pass, admin_pass"
    echo ""
fi

if [ ! -f "$INSTALL_DIR/app/.env" ]; then
    warn "No app/.env found. Copying example — EDIT IT before starting the service."
    cp "$INSTALL_DIR/app/.env.example" "$INSTALL_DIR/app/.env"
fi

# ── 6. Nginx ──────────────────────────────────────────────────────────────────
log "Configuring nginx..."
SERVER_IP=$(hostname -I | awk '{print $1}')
sed "s/SERVER_IP/$SERVER_IP/" "$INSTALL_DIR/install/nginx.conf" \
    > /etc/nginx/sites-available/boiler
ln -sf /etc/nginx/sites-available/boiler /etc/nginx/sites-enabled/boiler
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx
log "Nginx OK (serving on $SERVER_IP:5000)"

# ── 7. Systemd service ────────────────────────────────────────────────────────
log "Installing systemd service..."
cp "$INSTALL_DIR/install/boiler2.service" /etc/systemd/system/boiler2.service
systemctl daemon-reload
systemctl enable boiler2
log "Service enabled (not started yet — configure config.json first)"

# ── 8. Permissions ────────────────────────────────────────────────────────────
log "Setting permissions..."
chown -R www-data:www-data "$INSTALL_DIR/app" "$DATA_DIR" "$LOG_DIR"
chown -R "$SUDO_USER:$SUDO_USER" "$INSTALL_DIR/ui" 2>/dev/null || true
chmod 600 "$DATA_DIR/config.json" "$INSTALL_DIR/app/.env" 2>/dev/null || true

# ── 9. Done ───────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}Installation complete.${NC}"
echo ""
echo "Next steps:"
echo "  1. Edit $DATA_DIR/config.json  (credentials, IPs, tokens)"
echo "  2. Edit $INSTALL_DIR/app/.env  (HYPON_USER, HYPON_PASS, SECRET_KEY)"
echo "  3. sudo systemctl start boiler2"
echo "  4. sudo systemctl status boiler2"
echo "  5. Open http://$SERVER_IP:5000"
echo ""
