#!/usr/bin/env bash
# Build .cursor/gaps-and-risks-digest.md from .cursor/gaps-and-risks.md (≤10KB).
# Source of truth remains gaps-and-risks.md — never edit the digest by hand.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SRC="$ROOT/.cursor/gaps-and-risks.md"
OUT="$ROOT/.cursor/gaps-and-risks-digest.md"
MAX_BYTES="${GAPS_DIGEST_MAX_BYTES:-10000}"

if [[ ! -f "$SRC" ]]; then
  echo "MISSING: $SRC" >&2
  exit 1
fi

python3 - "$SRC" "$OUT" "$MAX_BYTES" <<'PY'
import re, sys
from pathlib import Path

src_path, out_path, max_bytes = Path(sys.argv[1]), Path(sys.argv[2]), int(sys.argv[3])
text = src_path.read_text(encoding="utf-8")

m = re.search(
    r"(## Gaps \(evidenced\)\n\n.*?)(?=\n## Notes kept|\n## GAP-\d+|\Z)",
    text,
    re.S,
)
if not m:
    sys.stderr.write("FAIL: could not find Gaps (evidenced) summary table\n")
    sys.exit(2)
section = m.group(1)
lines = section.splitlines()

header: list[str] = []
rows: list[str] = []
in_table = False
for i, line in enumerate(lines):
    if line.startswith("|") and "Gap" in line and "Risk" in line:
        header = [line]
        if i + 1 < len(lines) and re.match(r"\|[\s\-|:]+\|", lines[i + 1]):
            header.append(lines[i + 1])
        in_table = True
        continue
    if in_table:
        if line.startswith("|"):
            rows.append(line)
        elif line.strip():
            break

def classify(row: str) -> str:
    if re.search(r"\*\*Resolved|\*\*FIX VERIFIED|Resolved \(was", row, re.I):
        return "Resolved"
    if "**High**" in row:
        return "High"
    if "**Medium**" in row:
        return "Medium"
    if "**Low**" in row:
        return "Low"
    return "Other"

def cell0(row: str) -> str:
    parts = row.strip("|").split("|")
    return parts[0].strip() if parts else row.strip()

def title_from_cell(cell: str) -> str:
    t = re.sub(r"^\*\*|\*\*$", "", cell.strip())
    return re.sub(r"\s+", " ", t)

def gap_id_from_title(title: str) -> str:
    m = re.search(r"(GAP-\d+)", title)
    if m:
        return m.group(1)
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", title.lower()).strip("-")[:40]
    return f"ROW-{slug}" if slug else "ROW-unknown"

def area_from_row(row: str) -> str:
    parts = row.strip("|").split("|")
    evidence = parts[2].strip() if len(parts) > 2 else row
    pm = re.search(r"`([^`]+)`", evidence)
    if not pm:
        return "platform"
    p = pm.group(1).lower()
    for key in (
        "accounting", "los", "payments", "lib", "batch", "gateway",
        "task", "redis", "kafka", "dms", "notifications", "authorization",
        "masterdata", "approval", "audit",
    ):
        if key in p:
            return key
    return (pm.group(1).split("/")[0])[:28]

high = [r for r in rows if classify(r) == "High"]
medium = [r for r in rows if classify(r) == "Medium"]
low = [r for r in rows if classify(r) == "Low"]

# Narrative GAP-* not already in table titles → Medium/Low index only
table_gap_ids = {
    gap_id_from_title(title_from_cell(cell0(r)))
    for r in rows
    if gap_id_from_title(title_from_cell(cell0(r))).startswith("GAP-")
}
narr_med: list[str] = []
for part in re.split(r"\n(?=## GAP-\d+)", text):
    if not part.startswith("## GAP-"):
        continue
    title_line = part.split("\n", 1)[0]
    gm = re.match(r"## (GAP-\d+):\s*(.*)", title_line)
    if not gm or gm.group(1) in table_gap_ids:
        continue
    gid, gtitle = gm.group(1), gm.group(2).strip()
    head = part[:1000]
    if re.search(r"Risk(?: level)?[:\s|*]*\*?\*?High|\*\*High\*\*", head, re.I):
        # Open High narrative missing from summary: keep as index line (not full body)
        narr_med.append(f"{gid} | [High] {gtitle[:55]} | see-full")
        continue
    narr_med.append(f"{gid} | {gtitle[:60]} | see-full")

def index_lines(title_max: int) -> list[str]:
    out: list[str] = []
    for r in medium + low:
        title = title_from_cell(cell0(r))
        gid = gap_id_from_title(title)
        area = area_from_row(r)
        if len(title) > title_max:
            title = title[: title_max - 1] + "…"
        out.append(f"{gid} | {title} | {area}")
    for line in narr_med:
        segs = line.split(" | ", 2)
        if len(segs) == 3 and len(segs[1]) > title_max:
            segs[1] = segs[1][: title_max - 1] + "…"
            line = " | ".join(segs)
        out.append(line)
    return sorted(set(out))

banner = (
    "GENERATED FILE — edit gaps-and-risks.md, never this digest.\n"
    "\n"
    "# Gaps digest (session bootstrap)\n"
    "\n"
    "SoT: `.cursor/gaps-and-risks.md`. Escalate to full file when task touches a GAP-id/area "
    "below, needs Medium/Low narrative, or digest missing/stale.\n"
    "\n"
    "## Open High (verbatim summary-table rows)\n"
    "\n"
)

high_block = "\n".join(header + high) + "\n"

def assemble(idx: list[str], stub: str | None = None) -> str:
    parts = [banner, high_block]
    if idx:
        parts.append("\n## Medium/Low index\n\n")
        parts.append("\n".join(idx))
        parts.append("\n")
    elif stub:
        parts.append("\n")
        parts.append(stub)
        parts.append("\n")
    parts.append(
        f"\n<!-- digest high={len(high)} medium={len(medium)} low={len(low)} "
        f"idx={len(idx)} max={max_bytes} -->\n"
    )
    return "".join(parts)

body = None
# Prefer: all High + as much Medium/Low index as fits (tighten title_max)
for tmax in (60, 45, 32, 24, 18):
    idx = index_lines(tmax)
    while True:
        candidate = assemble(idx)
        if len(candidate.encode("utf-8")) <= max_bytes:
            body = candidate
            break
        if not idx:
            break
        idx = idx[:-1]  # drop last (sorted) line to shrink
    if body is not None:
        break

# If High-only fits with room, attach a one-line Medium/Low pointer (cap-tightened index)
if body is not None and "## Medium/Low" not in body:
    stub = (
        f"## Medium/Low index\n\n"
        f"(cap) {len(medium)} Medium / {len(low)} Low — see full gaps-and-risks.md\n"
    )
    trial = body.replace(
        f"\n<!-- digest high={len(high)}",
        stub + f"\n<!-- digest high={len(high)}",
        1,
    )
    if len(trial.encode("utf-8")) <= max_bytes:
        body = trial

if body is None:
    stub = (
        f"## Medium/Low index\n\n"
        f"(omitted for digest cap — {len(medium)} Medium / {len(low)} Low in SoT table; "
        f"read full gaps-and-risks.md)\n"
    )
    candidate = assemble([], stub=stub)
    if len(candidate.encode("utf-8")) <= max_bytes:
        body = candidate
    else:
        # Shorten banner only; never drop High rows if possible
        short_banner = (
            "GENERATED FILE — edit gaps-and-risks.md, never this digest.\n\n"
            "# Gaps digest\n\n"
            "Escalate to full `.cursor/gaps-and-risks.md` when GAP-id/area applies "
            "or digest stale.\n\n"
            "## Open High (verbatim)\n\n"
        )
        body = short_banner + high_block + (
            f"\n<!-- digest high={len(high)} medium={len(medium)} max={max_bytes} -->\n"
        )
        if len(body.encode("utf-8")) > max_bytes:
            sys.stderr.write(
                f"FAIL: open-High alone ({len(body.encode())} B) exceeds hard cap {max_bytes}\n"
            )
            sys.exit(3)

data = body.encode("utf-8")
out_path.write_text(body, encoding="utf-8")
print(f"OK: wrote {out_path} ({len(data)} bytes, cap {max_bytes})")
PY
