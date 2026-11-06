#!/bin/sh
# Backup service loop (docker-compose.yml, service "backup"): one verified copy of the database per
# ISO week. Checks hourly, so a week missed while the NAS was off is caught up as soon as it is back.
# A failed pass is logged and retried an hour later, never fatal.
set -eu

DB="${BACKUP_DB:-/data/mealplanner.db}"
WEEKLY="${BACKUP_DIR:-/backups}/weekly"
KEEP="${BACKUP_KEEP:-12}"
INTERVAL="${BACKUP_INTERVAL:-3600}"
TZ_NAME="${MEALPLANNER_TIMEZONE:-America/Bogota}"

log() { printf '%s backup-loop: %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*"; }

backup_this_week() {
    week=$(TZ="$TZ_NAME" date +%G-W%V)
    final="$WEEKLY/mealplanner-$week.db"
    [ -e "$final" ] && return 0
    if backup-now.sh "$final"; then
        log "wrote $final"
    else
        log "ERROR: backup for $week failed; will retry on the next pass"
        return 1
    fi
}

prune() {
    # Names sort by week, newest first after sort -r. Runs only after a successful pass.
    ls -1 "$WEEKLY"/mealplanner-????-W??.db | sort -r | tail -n +"$((KEEP + 1))" | while IFS= read -r old; do
        rm -f -- "$old" && log "pruned $old"
    done
}

while :; do
    if [ -f "$DB" ]; then
        mkdir -p "$WEEKLY" || log "ERROR: cannot create $WEEKLY"
        if backup_this_week; then
            prune || log "ERROR: pruning failed"
        fi
    fi
    sleep "$INTERVAL"
done
