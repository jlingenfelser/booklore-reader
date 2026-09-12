#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"; cd "$ROOT"
[[ -f .env ]] && set -a && source .env && set +a
STATE_DIR="${STATE_DIR:-/srv/booklore-reader}"; BACKUP_DIR="${BACKUP_DIR:-$STATE_DIR/backups}"
mkdir -p "$BACKUP_DIR"; OUT="$BACKUP_DIR/booklore-$(date +%Y%m%d-%H%M%S).sql.gz"
if docker compose ps --status running mariadb 2>/dev/null | grep -q booklore-mariadb; then
  docker exec booklore-mariadb sh -lc 'mariadb-dump --single-transaction --quick -u"$MYSQL_USER" -p"$MYSQL_PASSWORD" "$MYSQL_DATABASE"' | gzip -9 > "$OUT"
  echo "$OUT"
else
  echo "MariaDB is not running; no database backup created." >&2
fi
