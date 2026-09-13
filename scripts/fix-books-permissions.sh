#!/usr/bin/env bash
set -euo pipefail
[[ ${EUID} -eq 0 ]] || { echo "Run with sudo/root: sudo $0" >&2; exit 1; }
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
[[ -f .env ]] || { echo "Missing .env." >&2; exit 1; }
set -a
source .env
set +a

STATE_DIR="${STATE_DIR:-/srv/booklore-reader}"
APP_USER_ID="${APP_USER_ID:-1000}"
APP_GROUP_ID="${APP_GROUP_ID:-1000}"
BOOKS="$STATE_DIR/books"

mkdir -p "$BOOKS"
chown -R "$APP_USER_ID:$APP_GROUP_ID" "$BOOKS"
find "$BOOKS" -type d -exec chmod 775 {} +
find "$BOOKS" -type f -exec chmod 664 {} +

echo "Repaired BookLore books permissions: $BOOKS -> $APP_USER_ID:$APP_GROUP_ID"
