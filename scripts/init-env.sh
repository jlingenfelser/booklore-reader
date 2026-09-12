#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
SITE="${1:-${SITE_ADDRESS:-:80}}"
if [[ -f .env ]]; then echo ".env already exists; leaving it unchanged."; exit 0; fi
cp .env.example .env
DB_PASSWORD="$(openssl rand -hex 24)"
ROOT_PASSWORD="$(openssl rand -hex 24)"
UID_NOW="$(id -u)"
GID_NOW="$(id -g)"
python3 - "$SITE" "$DB_PASSWORD" "$ROOT_PASSWORD" "$UID_NOW" "$GID_NOW" <<'PYENV'
from pathlib import Path
import sys
p=Path('.env'); s=p.read_text()
s=s.replace('SITE_ADDRESS=:80', f'SITE_ADDRESS={sys.argv[1]}')
s=s.replace('DB_PASSWORD=CHANGE_ME', f'DB_PASSWORD={sys.argv[2]}')
s=s.replace('MYSQL_ROOT_PASSWORD=CHANGE_ME', f'MYSQL_ROOT_PASSWORD={sys.argv[3]}')
s=s.replace('APP_USER_ID=1000', f'APP_USER_ID={sys.argv[4]}')
s=s.replace('APP_GROUP_ID=1000', f'APP_GROUP_ID={sys.argv[5]}')
s=s.replace('DB_USER_ID=1000', f'DB_USER_ID={sys.argv[4]}')
s=s.replace('DB_GROUP_ID=1000', f'DB_GROUP_ID={sys.argv[5]}')
p.write_text(s)
PYENV
chmod 600 .env
mkdir -p .state
printf '%s\n' "Created .env. SITE_ADDRESS=$SITE"
