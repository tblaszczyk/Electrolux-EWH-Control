#!/bin/bash
DEST="/mnt/nas/boiler2-backup/$(date +%Y-%m-%d_%H-%M)"
mkdir -p "$DEST"
rsync -a --exclude='logs' --exclude='ui/node_modules' --exclude='ui/build' /opt/boiler2/ "$DEST/"
echo "Backup OK: $DEST"
# Zachowaj tylko 30 ostatnich backupów
ls -dt /mnt/nas/boiler2-backup/*/ | tail -n +31 | xargs rm -rf
