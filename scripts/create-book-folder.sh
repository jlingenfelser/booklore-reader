#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
[[ -f .env ]] || { echo "Missing .env; run this on an initialized deployment." >&2; exit 1; }
set -a
source .env
set +a

STATE_DIR="${STATE_DIR:-/srv/booklore-reader}"
APP_USER_ID="${APP_USER_ID:-1000}"
APP_GROUP_ID="${APP_GROUP_ID:-1000}"
REL="${1:-}"
[[ -n "$REL" ]] || { echo "Usage: $0 RELATIVE/FOLDER" >&2; exit 2; }
[[ "$REL" != /* && "$REL" != *".."* ]] || { echo "Folder must be a safe relative path under books/." >&2; exit 2; }

TARGET="$STATE_DIR/books/$REL"
mkdir -p "$TARGET"

if [[ $(id -u) -eq 0 ]]; then
  chown -R "$APP_USER_ID:$APP_GROUP_ID" "$TARGET"
elif [[ $(id -u) -ne "$APP_USER_ID" ]]; then
  echo "Created $TARGET, but current UID $(id -u) is not APP_USER_ID=$APP_USER_ID." >&2
  echo "Run: sudo chown -R $APP_USER_ID:$APP_GROUP_ID '$TARGET'" >&2
  exit 1
fi

find "$TARGET" -type d -exec chmod 775 {} +
find "$TARGET" -type f -exec chmod 664 {} +
echo "Created writable BookLore folder: $TARGET"
