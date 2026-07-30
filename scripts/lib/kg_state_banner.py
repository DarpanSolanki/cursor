#!/usr/bin/env python3
"""KG train-safety banner + telemetry (Upgrade 6 — light version).

Computed from watermark + composite key — never hand-written.
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STATS = ROOT / "cursor-bundle" / "kg" / "data" / "stats.json"
KEY_FILE = ROOT / ".cursor" / ".kg-composite-key"
STATE_MD = ROOT / ".cursor" / "workspace-kg-state.md"
TELEMETRY_MARK = "## Telemetry (last 20)"
RELEASE = re.compile(r"^mfi_(integration|release)_v[0-9]")

# Import composite helpers without hardcoding paths
sys.path.insert(0, str(ROOT / "cursor-bundle" / "kg" / "bin"))
try:
    from kg_composite import composite_key, list_repos, repo_state  # type: ignore
except Exception:  # noqa: BLE001
    composite_key = None  # type: ignore
    list_repos = None  # type: ignore
    repo_state = None  # type: ignore

try:
    from train_banner import money_or_cross_service  # type: ignore
except Exception:  # noqa: BLE001

    def money_or_cross_service(task_text: str = "", classification: str = "") -> bool:  # type: ignore
        t = (task_text or "").lower()
        return any(
            k in t
            for k in (
                "disburse",
                "money",
                "foreclos",
                "accounting",
                "kafka",
                "payment",
                "cross-service",
                "dpi",
                "dfc",
            )
        )


HARD_STOP = (
    "HARD STOP [KG PROVISIONAL/MISMATCH]: money/cross-service KG conclusions blocked until you "
    "(a) align via kg-switch.sh / kg-ensure-fresh.sh, "
    "(b) run analysis under KG_STRICT=1, or "
    "(c) get explicit user acknowledgment of provisional/mismatched KG risk. "
    "Do not treat flow/crud/why as production-train truth until cleared."
)

FULL_BUILD_WARN_S = 90  # doctor threshold


def _utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load_wm() -> dict:
    if not STATS.is_file():
        return {}
    try:
        return json.loads(STATS.read_text(encoding="utf-8")).get("watermark") or {}
    except Exception:
        return {}


def _live_key() -> str:
    if composite_key is None:
        return "?"
    try:
        return composite_key()
    except Exception:
        return "?"


def _stored_key() -> str:
    if KEY_FILE.is_file():
        try:
            return KEY_FILE.read_text(encoding="utf-8").strip().splitlines()[0].strip()
        except Exception:
            pass
    return ""


def _wip_repos(wm: dict) -> list[str]:
    out = []
    for repo, info in (wm.get("repos") or {}).items():
        br = (info or {}).get("branch") or ""
        if br and not RELEASE.match(br):
            short = repo.replace("trustt-platform-", "").replace("novopay-platform-", "")[:12]
            out.append(f"{short}={br.split('/')[-1][:16]}")
    return out


def _key_mismatch(live: str, stored: str, wm: dict) -> bool:
    if stored and live and stored != live and live != "?":
        return True
    # Drift: live HEAD/branch vs watermark
    if repo_state is None or list_repos is None:
        return False
    for repo, info in (wm.get("repos") or {}).items():
        try:
            live_rs = repo_state(repo)
        except Exception:
            continue
        wb = (info or {}).get("branch") or ""
        ws = ((info or {}).get("sha") or "")[:10]
        lb = live_rs.get("branch") or ""
        ls = (live_rs.get("sha") or "")[:10]
        if wb and lb and wb != lb:
            return True
        if ws and ls and ws != ls:
            return True
    return False


def compute_kg_state() -> dict:
    wm = _load_wm()
    live = _live_key()
    stored = _stored_key()
    built = wm.get("built_at") or "?"
    repos_n = len(wm.get("repos") or {})
    wip = _wip_repos(wm)
    mismatch = _key_mismatch(live, stored, wm)
    provisional = bool(wip) or mismatch or not wm
    tag = " [PROVISIONAL]" if provisional else " [ALIGNED]"
    wip_s = ",".join(wip[:6]) if wip else "-"
    if len(wip) > 6:
        wip_s += f"+{len(wip) - 6}"
    key_short = (live or stored or "?")[:8]
    line = (
        f"KG STATE: built@{built} set={key_short} repos={repos_n} "
        f"WIP: {wip_s}{tag}"
    )
    if mismatch and stored and live and stored != live:
        line = line.replace(tag, f" mismatch_stored={stored[:8]}{tag}")
    return {
        "line": line,
        "built_at": built,
        "key": live,
        "key_short": key_short,
        "repos_n": repos_n,
        "wip": wip,
        "wip_n": len(wip),
        "mismatch": mismatch,
        "provisional": provisional,
    }


def provenance_header() -> str:
    """One-line header for every KG answer (MCP + CLI). Includes STALE when KG-paths drifted."""
    st = compute_kg_state()
    base = f"[KG @{st['built_at']} set={st['key_short']} WIP:{st['wip_n']}]"
    if st.get("provisional") and st.get("wip"):
        repos = ",".join(st["wip"][:8])
        base += f" PROVISIONAL:{repos}"
    try:
        sys.path.insert(0, str(ROOT / "cursor-bundle" / "kg" / "bin"))
        import kg as _kg  # type: ignore

        _b, drift, _d, files = _kg._drift_check()
        if drift or files:
            n = len(files) if files else len(drift)
            base += f" STALE:{n}"
            if files:
                base += " files=" + ",".join(files[:5])
                if len(files) > 5:
                    base += f"+{len(files) - 5}"
    except Exception:
        pass
    return base


def banner_and_stop(task_text: str = "", classification: str = "") -> tuple[str, str | None]:
    st = compute_kg_state()
    stop = None
    if st["provisional"] and money_or_cross_service(task_text, classification):
        stop = HARD_STOP
        append_telemetry("gate", 0.0, "gate", note=st["key_short"])
    return st["line"], stop


def _read_telemetry_lines(text: str) -> list[str]:
    if TELEMETRY_MARK not in text:
        return []
    after = text.split(TELEMETRY_MARK, 1)[1]
    lines = []
    for ln in after.splitlines():
        if ln.startswith("## "):
            break
        if ln.strip().startswith("20") and "|" in ln:
            lines.append(ln.strip())
    return lines


def append_telemetry(
    hit_miss: str,
    duration_s: float,
    trigger: str,
    *,
    note: str = "",
    key_short: str | None = None,
) -> None:
    """Append one telemetry line; keep last 20 under ## Telemetry in workspace-kg-state.md."""
    STATE_MD.parent.mkdir(parents=True, exist_ok=True)
    st = compute_kg_state()
    ks = key_short or st["key_short"]
    utc = _utc()
    line = f"{utc} | {hit_miss} | {duration_s:.1f}s | set={ks} | trigger={trigger}"
    if note:
        line += f" | {note}"

    text = STATE_MD.read_text(encoding="utf-8") if STATE_MD.is_file() else (
        "# Workspace KG state (auto-generated — do not edit)\n\n"
    )
    existing = _read_telemetry_lines(text)
    existing.append(line)
    existing = existing[-20:]
    block = TELEMETRY_MARK + "\n\n" + "\n".join(existing) + "\n"

    if TELEMETRY_MARK in text:
        pre, rest = text.split(TELEMETRY_MARK, 1)
        idx = rest.find("\n## ", 1)
        if idx >= 0:
            text = pre.rstrip() + "\n\n" + block + "\n" + rest[idx + 1 :]
        else:
            text = pre.rstrip() + "\n\n" + block
    else:
        text = text.rstrip() + "\n\n" + block

    STATE_MD.write_text(text, encoding="utf-8")


def doctor_telemetry_flags() -> tuple[list[str], list[str]]:
    """Return (fail_flags, warn_flags) for workspace-doctor."""
    fails: list[str] = []
    warns: list[str] = []
    if not STATE_MD.is_file():
        return fails, warns
    lines = _read_telemetry_lines(STATE_MD.read_text(encoding="utf-8"))
    if not lines:
        return fails, warns
    streak = 0
    for ln in reversed(lines):
        parts = [p.strip() for p in ln.split("|")]
        if len(parts) < 2:
            break
        kind = parts[1]
        if kind == "miss":
            streak += 1
        else:
            break
    if streak >= 3:
        fails.append(f"KG telemetry: {streak} consecutive cache misses — silent sync failure risk")
    for ln in lines[-5:]:
        parts = [p.strip() for p in ln.split("|")]
        if len(parts) < 3:
            continue
        try:
            dur = float(parts[2].rstrip("s"))
        except ValueError:
            continue
        if parts[1] == "miss" and dur >= FULL_BUILD_WARN_S:
            fails.append(f"KG full-build slow: {dur:.0f}s ≥ {FULL_BUILD_WARN_S}s ({parts[0]})")
            break
    gate_hits = sum(1 for ln in lines if "trigger=gate" in ln)
    if gate_hits:
        warns.append(f"KG gate triggers in last 20: {gate_hits} (feeds kg-profiles revisit)")
    return fails, warns


if __name__ == "__main__":
    text = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "money accounting"
    if text.strip() == "--header":
        print(provenance_header())
        raise SystemExit(0)
    if text.strip() == "--doctor":
        fails, warns = doctor_telemetry_flags()
        for f in fails:
            print(f"FAIL {f}")
        for w in warns:
            print(f"WARN {w}")
        raise SystemExit(1 if fails else 0)
    b, s = banner_and_stop(text)
    print(b)
    if s:
        print(s)
    print(provenance_header())
