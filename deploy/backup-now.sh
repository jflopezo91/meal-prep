#!/bin/sh
# One verified copy of the live database: backup-now.sh <destination>
# Writes to a temporary name, checks integrity, then renames, so a destination file is always good.
# Used by the weekly loop (backup-loop.sh) and by scripts/release.sh before every deploy.
set -eu

DB="${BACKUP_DB:-/data/mealplanner.db}"
dest="$1"
tmp="$(dirname "$dest")/.$(basename "$dest").tmp"
trap 'rm -f "$tmp" "$tmp-wal" "$tmp-shm"' EXIT
rm -f "$tmp" "$tmp-wal" "$tmp-shm"  # db_cli refuses to overwrite a leftover from an interrupted run

python -m mealplanner.entrypoints.db_cli backup --db "$DB" --dest "$tmp"
python -c '
import sqlite3, sys
con = sqlite3.connect("file:" + sys.argv[1] + "?mode=ro&immutable=1", uri=True)
result = con.execute("PRAGMA integrity_check").fetchone()[0]
sys.exit(0 if result == "ok" else "integrity_check: " + str(result))
' "$tmp"
mv "$tmp" "$dest"
