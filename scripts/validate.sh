#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

python3 -m py_compile customizations/apply-customizations.py piper/patch-http-server.py
for f in scripts/*.sh linode/*.sh piper/entrypoint.sh; do bash -n "$f"; done

grep -q 'files/upload?libraryId=' customizations/apply-customizations.py
if grep -q "form.append('libraryId'" customizations/apply-customizations.py; then
  echo 'Regression: Paste-to-EPUB is using multipart destination IDs instead of query parameters.' >&2
  exit 1
fi

grep -q 'NG_BUILD_MAX_WORKERS=1' customizations/apply-customizations.py
grep -q -- '--max-workers=1' customizations/apply-customizations.py
grep -q 'ttsTapToStartArmed' customizations/apply-customizations.py
grep -q 'STOP_STACK_FOR_BUILD' scripts/deploy.sh

if grep -R -n --exclude=validate.sh 'DEPLOY_BRANCH:-main' scripts linode .github 2>/dev/null; then
  echo 'Regression: hard-coded main branch default found.' >&2
  exit 1
fi

grep -q 'branches: \[main, master\]' .github/workflows/deploy.yml

if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  docker compose --env-file .env.example config >/dev/null
else
  echo 'docker compose unavailable; skipping Compose render check.'
fi

echo 'Static validation passed.'
