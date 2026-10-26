"""
scripts/backfill_usage.py
Jednorazowy backfill detekcji zużycia wody na pełnej historii boiler_history
(Faza 0 — nie trzeba czekać tygodniami na nowe dane, są już w bazie).

Użycie:
  sudo -u www-data DB_PATH=/opt/boiler2/data/boiler.db \
    CFG_FILE=/opt/boiler2/data/config.json \
    /opt/boiler/venv/bin/python3 /opt/boiler2/app/scripts/backfill_usage.py
"""

import sys
import os
import json
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

import data.database as db
from config.defaults import get_defaults
from core.usage_detector import run_scan


def main():
    cfg = get_defaults()
    cfg_file = os.environ.get("CFG_FILE", "/var/lib/boiler/config.json")
    if os.path.exists(cfg_file):
        with open(cfg_file) as f:
            cfg.update(json.load(f))

    db.configure(cfg["db_path"])
    db.init_db()  # idempotentne — tworzy draw_events jeśli brakuje

    print("Backfill: skanuję całą historię boiler_history...")
    result = run_scan(cfg, since_ts=None, until_ts=None, source="backfill")
    print(f"Backfill zakończony: {result}")


if __name__ == "__main__":
    main()
