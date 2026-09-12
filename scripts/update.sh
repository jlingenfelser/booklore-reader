#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"; cd "$ROOT"; BRANCH="${DEPLOY_BRANCH:-main}"
git fetch origin "$BRANCH"; git checkout "$BRANCH"; git pull --ff-only origin "$BRANCH"
exec ./scripts/deploy.sh
