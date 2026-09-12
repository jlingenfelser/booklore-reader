#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"; cd "$ROOT"
REF="${1:-}"; [[ -n "$REF" ]] || { echo "Usage: $0 <BookLore tag/branch/SHA>" >&2; exit 2; }
python3 - "$REF" <<'PYREF'
from pathlib import Path
import sys,re
p=Path('config/upstream.env'); s=p.read_text(); s=re.sub(r'^BOOKLORE_UPSTREAM_REF=.*$', f'BOOKLORE_UPSTREAM_REF={sys.argv[1]}', s, flags=re.M); p.write_text(s)
PYREF
echo "Pinned upstream ref to $REF. Run ./scripts/deploy.sh to test, then commit config/upstream.env."
