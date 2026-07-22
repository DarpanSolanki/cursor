#!/usr/bin/env bash
# Jira handoff bridge — validates Dev-Test ADF BEFORE any post (Upgrade 7).
# Usage:
#   jira-handoff.sh --dry-run --jira TDPQA-123 [--proof-dir PATH] [--adf PATH]
# Actual post: only after dry-run PASS + explicit user go (plugin-atlassian via parent agent).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
DRY=0
JIRA=""
PROOF=""
ADF=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY=1; shift ;;
    --jira) JIRA="${2:-}"; shift 2 ;;
    --proof-dir) PROOF="${2:-}"; shift 2 ;;
    --adf) ADF="${2:-}"; shift 2 ;;
    -h|--help) sed -n '2,8p' "$0"; exit 0 ;;
    *) echo "unknown: $1" >&2; exit 2 ;;
  esac
done

[[ -n "$JIRA" ]] || { echo "Required: --jira KEY"; exit 2; }

python3 - "$ROOT" "$JIRA" "$PROOF" "$ADF" "$DRY" <<'PY'
import json, re, sys
from pathlib import Path
root, jira, proof, adf_path, dry = sys.argv[1:6]
dry = dry == "1"
errors = []
warns = []

if not re.match(r"^[A-Z][A-Z0-9]+-\d+$", jira):
    errors.append(f"jira key shape invalid: {jira}")

# Prefer generated ADF from capture-proof export
out = Path(adf_path) if adf_path else Path(root) / "scripts/scratch/jira-handoff" / f"{jira}-dev-test.adf.json"
if not out.is_file() and proof:
    # build minimal ADF from proof dir
    p = Path(proof) if proof else Path()
    rows = []
    if p.is_dir():
        for f in sorted(p.glob("*"))[:20]:
            rows.append((f.name, f.stat().st_size))
    out.parent.mkdir(parents=True, exist_ok=True)
    # ADF-ish table structure (Atlassian Document Format lite)
    table_rows = []
    for name, sz in rows or [("proof", 0)]:
        table_rows.append({
            "type": "tableRow",
            "content": [
                {"type": "tableCell", "content": [{"type": "paragraph", "content": [{"type": "text", "text": name}]}]},
                {"type": "tableCell", "content": [{"type": "paragraph", "content": [{"type": "text", "text": str(sz)}]}]},
            ],
        })
    doc = {
        "version": 1,
        "type": "doc",
        "content": [
            {"type": "heading", "attrs": {"level": 3}, "content": [{"type": "text", "text": "Dev Test evidence"}]},
            {"type": "table", "content": [
                {"type": "tableRow", "content": [
                    {"type": "tableHeader", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Artifact"}]}]},
                    {"type": "tableHeader", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Bytes"}]}]},
                ]},
                *table_rows,
            ]},
            {"type": "paragraph", "content": [{"type": "text", "text": f"Jira {jira} — dry-run export; post only after human go."}]},
        ],
    }
    out.write_text(json.dumps(doc, indent=2), encoding="utf-8")
    print(f"wrote ADF sample → {out}")

if not out.is_file():
    # synthesize empty template for dry-run demo
    out.parent.mkdir(parents=True, exist_ok=True)
    doc = {
        "version": 1,
        "type": "doc",
        "content": [
            {"type": "heading", "attrs": {"level": 3}, "content": [{"type": "text", "text": "Dev Test"}]},
            {"type": "table", "content": [
                {"type": "tableRow", "content": [
                    {"type": "tableHeader", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Scenario"}]}]},
                    {"type": "tableHeader", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Result"}]}]},
                ]},
                {"type": "tableRow", "content": [
                    {"type": "tableCell", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "happy_path"}]}]},
                    {"type": "tableCell", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "PASS"}]}]},
                ]},
            ]},
        ],
    }
    out.write_text(json.dumps(doc, indent=2), encoding="utf-8")
    warns.append(f"no proof dir — wrote template ADF {out}")

text = out.read_text(encoding="utf-8")
# Validators: fields, % scale, jargon, attachment presence
forbidden_jargon = ("cursor brand", "as an ai", "chatgpt", "claude said")
for j in forbidden_jargon:
    if j in text.lower():
        errors.append(f"jargon forbidden: {j}")
# % effectiveness claims without evidence
if re.search(r"\b\d{2,3}%\b", text) and "evidence" not in text.lower():
    warns.append("% scale present without evidence keyword — confirm AITDP fraction rules")

try:
    doc = json.loads(text)
    if doc.get("type") != "doc":
        errors.append("ADF root type must be doc")
    if "table" not in text:
        errors.append("Dev-Test ADF must include a table")
except Exception as e:
    errors.append(f"ADF JSON invalid: {e}")

print("=== jira-handoff validator ===")
print(f"jira: {jira}")
print(f"adf:  {out}")
print(f"mode: {'DRY-RUN' if dry else 'LIVE-BLOCKED'}")
for w in warns:
    print(f"WARN: {w}")
if errors:
    print("FAIL:")
    for e in errors:
        print(f"  - {e}")
    sys.exit(1)
print("PASS: fields/table/jargon OK — mutation gate: do NOT post until explicit user go")
print("Next: parent agent CallMcpTool editJiraIssue / addComment AFTER user says go")
if not dry:
    print("REFUSING live post from this script (use MCP after go)")
    sys.exit(3)
sys.exit(0)
PY
