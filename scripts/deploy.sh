#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

[[ -f .env ]] || ./scripts/init-env.sh "${SITE_ADDRESS:-:80}"
set -a
source .env
set +a

export STATE_DIR="${STATE_DIR:-/srv/booklore-reader}"
STOP_STACK_FOR_BUILD="${STOP_STACK_FOR_BUILD:-1}"

mkdir -p "$STATE_DIR"/{data,books,bookdrop,mariadb,piper-data,caddy-data,caddy-config,backups}

stack_stopped=0
restore_previous_stack() {
  rc=$?
  trap - ERR INT TERM
  if [[ "$stack_stopped" == "1" ]]; then
    echo "==> Build/deploy failed; attempting to restore previous stack" >&2
    docker compose up -d --remove-orphans || true
  fi
  exit "$rc"
}
trap restore_previous_stack ERR INT TERM

if docker compose ps --status running mariadb 2>/dev/null | grep -q booklore-mariadb; then
  echo "==> Pre-deploy DB backup"
  ./scripts/backup.sh || true
fi

./scripts/prepare-source.sh

if [[ "$STOP_STACK_FOR_BUILD" != "0" ]] && docker compose ps --status running --services 2>/dev/null | grep -q .; then
  echo "==> Stopping live stack to free RAM for build"
  docker compose stop
  stack_stopped=1
fi

echo "==> Building BookLore"
docker compose build booklore

echo "==> Building Piper separately"
docker compose build piper

echo "==> Starting stack"
docker compose up -d --remove-orphans
stack_stopped=0
trap - ERR INT TERM

for _ in $(seq 1 60); do
  booklore_health="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' booklore 2>/dev/null || true)"
  mariadb_health="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' booklore-mariadb 2>/dev/null || true)"
  piper_health="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' booklore-piper 2>/dev/null || true)"
  gateway_state="$(docker inspect -f '{{.State.Status}}' booklore-gateway 2>/dev/null || true)"
  if [[ "$booklore_health" == "healthy" && "$mariadb_health" == "healthy" && "$piper_health" == "healthy" && "$gateway_state" == "running" ]]; then
    break
  fi
  sleep 5
done

docker compose ps
printf '\nDeployment complete. Address: %s\n' "$SITE_ADDRESS"
