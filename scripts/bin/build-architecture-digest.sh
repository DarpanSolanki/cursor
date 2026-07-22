#!/usr/bin/env bash
# Build .cursor/architecture-digest.md from .cursor/architecture.md (≤8KB).
# SoT remains architecture.md — never edit the digest by hand.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SRC="$ROOT/.cursor/architecture.md"
OUT="$ROOT/.cursor/architecture-digest.md"
MAX_BYTES="${ARCH_DIGEST_MAX_BYTES:-8000}"

if [[ ! -f "$SRC" ]]; then
  echo "MISSING: $SRC" >&2
  exit 1
fi

python3 - "$SRC" "$OUT" "$MAX_BYTES" <<'PY'
import re, sys
from pathlib import Path

src_path, out_path, max_bytes = Path(sys.argv[1]), Path(sys.argv[2]), int(sys.argv[3])
lines = src_path.read_text(encoding="utf-8").splitlines()

banner = (
    "GENERATED FILE — edit architecture.md, never this digest.\n\n"
    "# Architecture digest (session bootstrap)\n\n"
    "SoT: `.cursor/architecture.md`. Escalate to full file for deep service maps, "
    "full diagrams, or any section not listed below.\n\n"
)

chunks: list[str] = []
cur: list[str] = []
table_rows = 0

def flush():
    global cur, table_rows
    if cur:
        chunks.append("\n".join(cur))
        cur = []
        table_rows = 0

for line in lines:
    if line.startswith("# ") or line.startswith("## "):
        flush()
    if line.startswith("|"):
        table_rows += 1
        if table_rows > 12:
            if cur and not cur[-1].startswith("…"):
                cur.append("… (table truncated — see full architecture.md) …")
            continue
    cur.append(line)

flush()

body = banner
for ch in chunks:
    trial = body + ch + "\n\n"
    if len(trial.encode("utf-8")) > max_bytes:
        break
    body = trial

body = body.rstrip() + (
    f"\n\n<!-- architecture-digest max={max_bytes} -->\n"
)
if len(body.encode("utf-8")) > max_bytes:
    raw = body.encode("utf-8")[: max_bytes - 60]
    body = raw.decode("utf-8", "ignore") + "\n\n… [truncated — see full architecture.md] …\n"

out_path.write_text(body, encoding="utf-8")
print(f"OK: wrote {out_path} ({len(body.encode())} bytes, cap {max_bytes})")
PY
