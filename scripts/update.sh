#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

BRANCH="${DEPLOY_BRANCH:-}"
if [[ -z "$BRANCH" ]]; then
  BRANCH="$(git branch --show-current)"
fi
if [[ -z "$BRANCH" ]]; then
  git remote set-head origin -a >/dev/null 2>&1 || true
  BRANCH="$(git symbolic-ref --quiet --short refs/remotes/origin/HEAD 2>/dev/null | sed 's#^origin/##' || true)"
fi
if [[ -z "$BRANCH" ]]; then
  BRANCH="$(git remote show origin | sed -n '/HEAD branch/s/.*: //p' | head -n1)"
fi
[[ -n "$BRANCH" ]] || { echo "Could not determine deploy branch; set DEPLOY_BRANCH explicitly." >&2; exit 1; }

echo "==> Updating branch: $BRANCH"
git fetch origin "$BRANCH"
git checkout "$BRANCH"
git pull --ff-only origin "$BRANCH"
exec ./scripts/deploy.sh
