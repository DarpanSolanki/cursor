#!/usr/bin/env python3
"""Local-parity gate — local PASS must be reproducible via migrations (Upgrade 8 TASK E).

Fail-closed when a pending ship touches schema/masterdata/Flyway OR a DDL hand-patch
hit a money table without a matching migration/initial-setup entry.

Does NOT fail fixture row UPDATEs (purge/seed) — only DDL / schema-shaped SQL.
Duplicate Flyway versions (GAP-077 class) always fail when schema paths are in scope.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PENDING = ROOT / ".cursor" / ".pending-ship-work.json"
HAND_PATCH_LOG = ROOT / ".cursor" / ".local-hand-patch-log.jsonl"
PARITY_RESULT = ROOT / ".cursor" / ".local-parity-result.json"
MANIFEST = ROOT / "scripts" / "lib" / "acceptance_coverage_manifest.json"
INITIAL_SETUP = ROOT / "trustt-platform-initial-setup"

SCHEMA_PATH_RE = re.compile(
    r"(?ix)"
    r"(?:^|/)"
    r"(?:"
    r"trustt-platform-initial-setup/"
    r"|flyway/"
    r"|deploy/.*/db/migration/"
    r"|db/migration/"
    r"|scripts/sql/setup/"
    r"|scripts/sql/deploy/"
    r")"
)
FLYWAY_FILE_RE = re.compile(r"(?i)V\d+__.*\.sql$")
LOCAL_ONLY_SETUP_RE = re.compile(r"(?i)scripts/sql/setup/local_setup_.*\.sql$")
DDL_RE = re.compile(
    r"(?is)\b(ALTER\s+TABLE|CREATE\s+TABLE|DROP\s+TABLE|ADD\s+COLUMN|DROP\s+COLUMN|"
    r"CREATE\s+(UNIQUE\s+)?INDEX|ALTER\s+COLUMN)\b"
)
TABLE_RE = re.compile(
    r"(?is)\b(?:ALTER\s+TABLE|CREATE\s+TABLE|DROP\s+TABLE|ADD\s+COLUMN|DROP\s+COLUMN|"
    r"CREATE\s+(?:UNIQUE\s+)?INDEX\s+\w+\s+ON|ALTER\s+COLUMN)\s+"
    r"(?:IF\s+(?:NOT\s+)?EXISTS\s+)?(?:\w+\.)?(\w+)",
)
COLUMN_HINT_RE = re.compile(r"(?i)\bADD\s+COLUMN\s+(?:IF\s+NOT\s+EXISTS\s+)?(\w+)")
VERSION_RE = re.compile(r"^(V\d+)__", re.I)


def _utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load_json(path: Path, default):
    if not path.is_file():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def money_tables() -> set[str]:
    man = _load_json(MANIFEST, {})
    out: set[str] = set()
    for tables in (man.get("domain_money_tables") or {}).values():
        out.update(tables or [])
    return out


def pending_files(pending: dict | None = None) -> list[str]:
    p = pending if pending is not None else _load_json(PENDING, {})
    return [str(f).replace("\\", "/") for f in (p.get("files") or [])]


def schema_or_masterdata_touched(pending: dict | None = None) -> bool:
    """True when process matrix / gate should run (selection principle)."""
    files = pending_files(pending)
    if any(SCHEMA_PATH_RE.search(f) or FLYWAY_FILE_RE.search(Path(f).name) for f in files):
        return True
    if any("masterdata" in f.lower() and f.endswith(".sql") for f in files):
        return True
    # DDL hand-patches since pending opened also force the gate
    if _ddl_hand_patches_since(pending):
        return True
    return False


def _parse_ts(ts: str) -> float:
    try:
        return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp()
    except Exception:
        return 0.0


def _read_hand_patch_rows() -> list[dict]:
    if not HAND_PATCH_LOG.is_file():
        return []
    rows = []
    for line in HAND_PATCH_LOG.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    return rows


def _ddl_hand_patches_since(pending: dict | None = None) -> list[dict]:
    p = pending if pending is not None else _load_json(PENDING, {})
    since = _parse_ts(str(p.get("updated_at") or "")) or 0.0
    # If no pending stamp, only look at last 6h
    if not since:
        since = datetime.now(timezone.utc).timestamp() - 6 * 3600
    money = money_tables()
    out = []
    for row in _read_hand_patch_rows():
        if not row.get("ddl"):
            continue
        ts = _parse_ts(str(row.get("ts") or ""))
        if ts and ts < since - 60:  # small skew
            continue
        tables = {t.lower() for t in (row.get("tables") or [])}
        if tables & {m.lower() for m in money}:
            out.append(row)
    return out


def log_hand_patch(*, sql: str, source: str, path: str | None = None) -> dict | None:
    """Called by db-local-write.sh — append DDL money-table events only."""
    if not DDL_RE.search(sql or ""):
        return None
    tables = [m.group(1).lower() for m in TABLE_RE.finditer(sql or "")]
    money = {t.lower() for t in money_tables()}
    hit = sorted({t for t in tables if t in money})
    if not hit:
        return None
    cols = COLUMN_HINT_RE.findall(sql or "")
    row = {
        "ts": _utc(),
        "ddl": True,
        "tables": hit,
        "columns": cols,
        "source": source,
        "path": path,
        "preview": (sql or "").strip()[:240],
    }
    HAND_PATCH_LOG.parent.mkdir(parents=True, exist_ok=True)
    with HAND_PATCH_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    # keep log lean
    rows = _read_hand_patch_rows()
    if len(rows) > 200:
        HAND_PATCH_LOG.write_text(
            "\n".join(json.dumps(r, ensure_ascii=False) for r in rows[-200:]) + "\n",
            encoding="utf-8",
        )
    return row


def find_duplicate_versions(sql_roots: list[Path]) -> list[str]:
    """GAP-077 class: two VNNNN__*.sql share a version under one service tree."""
    errors = []
    for root in sql_roots:
        if not root.is_dir():
            continue
        by_ver: dict[str, list[str]] = defaultdict(list)
        for f in root.rglob("V*__*.sql"):
            m = VERSION_RE.match(f.name)
            if not m:
                continue
            by_ver[m.group(1).upper()].append(_rel(f))
        for ver, paths in sorted(by_ver.items()):
            if len(paths) > 1:
                errors.append(f"duplicate Flyway version {ver}: {', '.join(paths)}")
    return errors


def _rel(f: Path) -> str:
    try:
        return str(f.relative_to(ROOT))
    except ValueError:
        return str(f)


def _migration_corpus(pending: dict | None = None) -> str:
    """Concat text of pending Flyway/initial-setup + on-disk initial-setup for touched services."""
    chunks: list[str] = []
    files = pending_files(pending)
    services: set[str] = set()
    for f in files:
        p = ROOT / f
        if p.is_file() and (FLYWAY_FILE_RE.search(p.name) or "flyway/" in f or "db/migration" in f):
            try:
                chunks.append(p.read_text(encoding="utf-8", errors="ignore"))
            except OSError:
                pass
        m = re.search(r"flyway/sli/([a-z0-9_]+)/", f, re.I)
        if m:
            services.add(m.group(1).lower())
        if "accounting" in f.lower():
            services.add("accounting")
        if "masterdata" in f.lower():
            services.add("masterdata")
        if "notifications" in f.lower():
            services.add("notifications")
    # Always scan duplicate versions for services in play; include full migration text for token search
    for svc in services or set():
        svc_root = INITIAL_SETUP / "flyway" / "sli" / svc / "sql"
        if svc_root.is_dir():
            for f in svc_root.rglob("V*__*.sql"):
                try:
                    chunks.append(f.read_text(encoding="utf-8", errors="ignore"))
                except OSError:
                    pass
    return "\n".join(chunks).lower()


def _token_in_migrations(token: str, corpus: str) -> bool:
    t = (token or "").lower().strip()
    if not t or len(t) < 3:
        return False
    return t in corpus


def check_parity(pending: dict | None = None) -> dict:
    """Return {ok, errors, summary, migrations_ok, seeds_ok, train}."""
    p = pending if pending is not None else _load_json(PENDING, {})
    if not schema_or_masterdata_touched(p):
        return {
            "ok": True,
            "skipped": True,
            "summary": "LOCAL PASS — parity: n/a (no schema/masterdata touch)",
            "migrations_ok": True,
            "seeds_ok": True,
            "errors": [],
        }

    errors: list[str] = []
    files = pending_files(p)
    train = _infer_train(p)

    # --- duplicate versions for touched initial-setup services ---
    svc_roots: list[Path] = []
    for f in files:
        m = re.search(r"flyway/sli/([a-z0-9_]+)/", f, re.I)
        if m:
            svc_roots.append(INITIAL_SETUP / "flyway" / "sli" / m.group(1) / "sql")
        if re.search(r"masterdata", f, re.I):
            svc_roots.append(INITIAL_SETUP / "flyway" / "sli" / "masterdata" / "sql")
        if re.search(r"notification", f, re.I):
            svc_roots.append(INITIAL_SETUP / "flyway" / "sli" / "notifications" / "sql")
        if re.search(r"accounting", f, re.I) and ("flyway" in f or "Entity" in f or "setup" in f):
            svc_roots.append(INITIAL_SETUP / "flyway" / "sli" / "accounting" / "sql")
    # Dedup roots
    uniq_roots = []
    seen = set()
    for r in svc_roots:
        key = str(r)
        if key not in seen:
            seen.add(key)
            uniq_roots.append(r)
    # If only local_setup / deploy scripts, still scan accounting for dups when money schema
    if not uniq_roots and any(LOCAL_ONLY_SETUP_RE.search(f) for f in files):
        uniq_roots.append(INITIAL_SETUP / "flyway" / "sli" / "accounting" / "sql")

    errors.extend(find_duplicate_versions(uniq_roots))

    corpus = _migration_corpus(p)
    has_migration_file = any(
        FLYWAY_FILE_RE.search(Path(f).name) or "/flyway/" in f or "/db/migration/" in f for f in files
    )
    local_only = [f for f in files if LOCAL_ONLY_SETUP_RE.search(f)]
    if local_only and not has_migration_file:
        # GAP-076 class: local_setup alone does not predict QA/prod
        for f in local_only:
            text = ""
            try:
                text = (ROOT / f).read_text(encoding="utf-8", errors="ignore")
            except OSError:
                pass
            cols = COLUMN_HINT_RE.findall(text) or re.findall(
                r"(?i)\b(\w*(?:amount|status|column|dpi|suspense)\w*)\b", text
            )
            missing = [c for c in cols[:8] if not _token_in_migrations(c, corpus)]
            if missing or not corpus:
                errors.append(
                    f"local hand-patch / local_setup not reproducible in target env: {f} "
                    f"(need Flyway/initial-setup migration covering {missing or 'schema change'})"
                )

    # DDL hand-patches on money tables
    for row in _ddl_hand_patches_since(p):
        tokens = list(row.get("columns") or []) + list(row.get("tables") or [])
        bad = [t for t in tokens if not _token_in_migrations(str(t), corpus)]
        if bad or not has_migration_file:
            errors.append(
                "local hand-patch not reproducible in target env: "
                f"DDL on {row.get('tables')} cols={row.get('columns')} "
                f"source={row.get('source')} path={row.get('path')} "
                f"— missing migration tokens {bad or '(no Flyway in pending)'}"
            )

    # Pending Flyway files that introduce duplicates within the same service dir
    for f in files:
        if not FLYWAY_FILE_RE.search(Path(f).name):
            continue
        parent = (ROOT / f).parent if (ROOT / f).exists() else None
        if parent:
            errors.extend(find_duplicate_versions([parent]))

    migrations_ok = not any("duplicate Flyway" in e or "not reproducible" in e for e in errors)
    # seeds: masterdata sql in pending must live under flyway/sli/masterdata
    seed_files = [f for f in files if "masterdata" in f.lower() and f.endswith(".sql")]
    seeds_ok = True
    for f in seed_files:
        if "/flyway/" not in f and "db/migration" not in f:
            seeds_ok = False
            errors.append(f"masterdata seed not under Flyway/initial-setup path: {f}")

    ok = not errors
    if ok:
        summary = (
            f"LOCAL PASS — parity: migrations ✓ / seeds ✓ (predicts {train} envs)"
        )
    else:
        flags = []
        if not migrations_ok:
            flags.append("migrations ✗")
        if not seeds_ok:
            flags.append("seeds ✗")
        summary = (
            f"LOCAL PASS — parity UNPROVEN: {', '.join(flags) or 'schema'} "
            f"(does not predict {train} envs)"
        )

    result = {
        "ok": ok,
        "skipped": False,
        "summary": summary,
        "migrations_ok": migrations_ok and ok,
        "seeds_ok": seeds_ok and ok,
        "train": train,
        "errors": errors,
        "ts": _utc(),
    }
    PARITY_RESULT.parent.mkdir(parents=True, exist_ok=True)
    PARITY_RESULT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def _infer_train(pending: dict) -> str:
    repos = pending.get("repos") or []
    # Prefer accounting train from git if available
    acct = ROOT / "trustt-platform-accounting"
    if acct.is_dir() and (acct / ".git").is_dir():
        import subprocess

        r = subprocess.run(
            ["git", "-C", str(acct), "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
        )
        br = (r.stdout or "").strip()
        if br:
            return br
    if repos:
        return str(repos[0])
    return "target-train"


def main() -> int:
    ap = argparse.ArgumentParser(description="Local-parity gate (migrations vs hand-patch)")
    ap.add_argument("cmd", choices=["check", "touched", "log-sql", "summary"])
    ap.add_argument("--sql", default="")
    ap.add_argument("--file", default="")
    ap.add_argument("--source", default="cli")
    args = ap.parse_args()
    if args.cmd == "touched":
        print("yes" if schema_or_masterdata_touched() else "no")
        return 0
    if args.cmd == "log-sql":
        sql = args.sql
        if args.file:
            sql = Path(args.file).read_text(encoding="utf-8", errors="ignore")
        row = log_hand_patch(sql=sql, source=args.source, path=args.file or None)
        print(json.dumps(row or {"logged": False}))
        return 0
    if args.cmd == "summary":
        r = _load_json(PARITY_RESULT, {})
        print(r.get("summary") or "LOCAL PASS — parity: n/a")
        return 0 if r.get("ok", True) else 1
    r = check_parity()
    print(r["summary"])
    for e in r.get("errors") or []:
        print(f"  FAIL: {e}", file=sys.stderr)
    return 0 if r.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
