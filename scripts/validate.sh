#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"; cd "$ROOT"
python3 -m py_compile customizations/apply-customizations.py piper/patch-http-server.py
for f in scripts/*.sh linode/*.sh piper/entrypoint.sh; do bash -n "$f"; done
grep -q 'files/upload?libraryId=' customizations/apply-customizations.py
if grep -q "form.append('libraryId'" customizations/apply-customizations.py; then
  echo 'Regression: Paste-to-EPUB is using multipart destination IDs instead of query parameters.' >&2
  exit 1
fi
if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  docker compose --env-file .env.example config >/dev/null
else
  echo 'docker compose unavailable; skipping Compose render check.'
fi
echo 'Static validation passed.'
