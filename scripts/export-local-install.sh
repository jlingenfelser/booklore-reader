#!/usr/bin/env bash
set -euo pipefail
SRC="${BOOKLORE_TTS_DIR:-$HOME/booklore-tts}"; OUT="${1:-$HOME/booklore-migration-$(date +%Y%m%d-%H%M%S)}"; mkdir -p "$OUT"
[[ -d "$SRC/books" ]] && rsync -a "$SRC/books/" "$OUT/books/" || true
[[ -d "$SRC/data" ]] && rsync -a "$SRC/data/" "$OUT/data/" || true
[[ -d "$SRC/bookdrop" ]] && rsync -a "$SRC/bookdrop/" "$OUT/bookdrop/" || true
mkdir -p "$OUT/database"
if docker ps --format '{{.Names}}' | grep -qx booklore-mariadb; then docker exec booklore-mariadb sh -lc 'mariadb-dump --single-transaction --quick -u"$MYSQL_USER" -p"$MYSQL_PASSWORD" "$MYSQL_DATABASE"' | gzip -9 > "$OUT/database/booklore.sql.gz"; fi
echo "$OUT"
