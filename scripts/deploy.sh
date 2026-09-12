#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"; cd "$ROOT"
[[ -f .env ]] || ./scripts/init-env.sh "${SITE_ADDRESS:-:80}"
set -a; source .env; set +a
export STATE_DIR="${STATE_DIR:-/srv/booklore-reader}"
mkdir -p "$STATE_DIR"/{data,books,bookdrop,mariadb,piper-data,caddy-data,caddy-config,backups}
if docker compose ps --status running mariadb 2>/dev/null | grep -q booklore-mariadb; then echo "==> Pre-deploy DB backup"; ./scripts/backup.sh || true; fi
./scripts/prepare-source.sh
echo "==> Building custom images"; docker compose build booklore piper
echo "==> Starting stack"; docker compose up -d --remove-orphans
for i in $(seq 1 60); do
  if docker compose ps --format json 2>/dev/null | grep -q '"Health":"healthy"'; then break; fi
  sleep 5
done
docker compose ps
printf '\nDeployment complete. Address: %s\n' "$SITE_ADDRESS"
