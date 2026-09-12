#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"; cd "$ROOT"
[[ -f .env ]] || { echo "Run ./scripts/init-env.sh first." >&2; exit 1; }
set -a; source .env; set +a
SRC="${1:-}"
[[ -n "$SRC" && -d "$SRC" ]] || { echo "Usage: $0 /path/to/booklore-migration-directory" >&2; exit 2; }
STATE_DIR="${STATE_DIR:-/srv/booklore-reader}"
mkdir -p "$STATE_DIR"/{books,data,bookdrop,backups}

echo "==> Stopping BookLore while copying application files"
docker compose stop booklore 2>/dev/null || true
for d in books data bookdrop; do
  if [[ -d "$SRC/$d" ]]; then
    echo "==> Restoring $d"
    rsync -a "$SRC/$d/" "$STATE_DIR/$d/"
  fi
done

echo "==> Starting MariaDB"
docker compose up -d mariadb
for _ in $(seq 1 60); do
  docker exec booklore-mariadb mariadb-admin ping -h localhost >/dev/null 2>&1 && break
  sleep 2
done

SQL="$SRC/database/booklore.sql.gz"
if [[ -f "$SQL" ]]; then
  echo "==> Restoring database dump"
  gunzip -c "$SQL" | docker exec -i booklore-mariadb sh -lc 'mariadb -u"$MYSQL_USER" -p"$MYSQL_PASSWORD" "$MYSQL_DATABASE"'
else
  echo "No database dump at $SQL; skipping DB restore."
fi

echo "==> Starting full stack"
docker compose up -d

echo "Migration restore complete."
