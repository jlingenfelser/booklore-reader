#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"; cd "$ROOT"; source config/upstream.env
BUILD="$ROOT/.build/booklore-src"; rm -rf "$BUILD"; mkdir -p "$ROOT/.build"
echo "==> Fetching BookLore upstream: $BOOKLORE_UPSTREAM_REF"
git clone --filter=blob:none --no-checkout "$BOOKLORE_UPSTREAM_REPO" "$BUILD"
git -C "$BUILD" fetch --depth 1 origin "$BOOKLORE_UPSTREAM_REF"
git -C "$BUILD" checkout --detach FETCH_HEAD
mkdir -p .state; git -C "$BUILD" rev-parse HEAD > .state/upstream-sha

echo "==> Applying customizations"
python3 customizations/apply-customizations.py "$BUILD"

UID_NOW="$(id -u)"; GID_NOW="$(id -g)"
echo "==> Updating frontend lockfile"
docker run --rm --user "$UID_NOW:$GID_NOW" -e HOME=/tmp -v "$BUILD/booklore-ui:/app" -w /app node:24-alpine \
  sh -lc 'npm install --package-lock-only --ignore-scripts --force jszip@3.10.2 piper-tts-web@1.1.2'

echo "==> Installing piper-tts-web runtime assets"
TMP="$ROOT/.build/piper-web-package"; rm -rf "$TMP"; mkdir -p "$TMP"
docker run --rm --user "$UID_NOW:$GID_NOW" -e HOME=/tmp -v "$TMP:/work" -w /work node:24-alpine sh -lc \
  'npm pack piper-tts-web@1.1.2 >/tmp/pkg && PKG=$(tail -n1 /tmp/pkg) && tar -xzf "$PKG"'
mkdir -p "$BUILD/booklore-ui/public"
for d in onnx piper worker; do
  if [[ -d "$TMP/package/dist/$d" ]]; then rm -rf "$BUILD/booklore-ui/public/$d"; cp -a "$TMP/package/dist/$d" "$BUILD/booklore-ui/public/$d"; fi
done
rm -rf "$TMP"

echo "Prepared source: $BUILD"
