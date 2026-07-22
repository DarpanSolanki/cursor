#!/usr/bin/env python3
"""Compute mixed-train banner from .cursor/git-workspace-state.json (never hand-written)."""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STATE = ROOT / ".cursor" / "git-workspace-state.json"
TRAIN = re.compile(r"^mfi_(?:integration|release)_v(?P<ver>\d+(?:\.\d+)*)$")

# Short labels for the banner
_LABEL = {
    "trustt-platform-accounting": "acc",
    "novopay-platform-accounting-v2": "acc",
    "trustt-platform-payments": "pay",
    "trustt-platform-los": "los",
    "trustt-platform-actor": "actor",
    "trustt-platform-lib": "lib",
    "novopay-platform-lib": "lib",
    "trustt-platform-batch": "batch",
    "trustt-platform-webapp": "web",
    "trustt-platform-initial-setup": "setup",
    "trustt-platform-task": "task",
    "trustt-platform-authorization": "authz",
    "trustt-platform-masterdata-management": "mdm",
    "trustt-platform-notifications": "notif",
    "trustt-platform-api-gateway": "gw",
}

# Domain → repos to sync (scoped). Keep small & explicit.
DOMAIN_REPOS: dict[str, list[str]] = {
    "dfc": ["trustt-platform-accounting", "trustt-platform-initial-setup"],
    "death_foreclosure": ["trustt-platform-accounting", "trustt-platform-initial-setup"],
    "disburse": [
        "trustt-platform-accounting",
        "trustt-platform-los",
        "trustt-platform-payments",
        "trustt-platform-lib",
        "novopay-platform-lib",
    ],
    "disbursement": [
        "trustt-platform-accounting",
        "trustt-platform-los",
        "trustt-platform-payments",
        "trustt-platform-lib",
        "novopay-platform-lib",
    ],
    "dpi": [
        "trustt-platform-accounting",
        "trustt-platform-actor",
        "trustt-platform-authorization",
        "trustt-platform-masterdata-management",
        "trustt-platform-notifications",
        "trustt-platform-initial-setup",
        "trustt-platform-webapp",
    ],
    "los": ["trustt-platform-los", "trustt-platform-lib", "novopay-platform-lib"],
    "payments": ["trustt-platform-payments", "trustt-platform-accounting", "trustt-platform-lib"],
    "accounting": ["trustt-platform-accounting", "trustt-platform-lib", "novopay-platform-lib"],
    "foreclosure": ["trustt-platform-accounting", "trustt-platform-payments"],
    "repayment": ["trustt-platform-accounting", "trustt-platform-payments"],
}


def _load_repos() -> dict[str, str]:
    """repo → branch"""
    if not STATE.is_file():
        return {}
    try:
        data = json.loads(STATE.read_text(encoding="utf-8"))
    except Exception:
        return {}
    repos = data.get("repos") or {}
    out: dict[str, str] = {}
    for name, meta in repos.items():
        if isinstance(meta, dict):
            br = meta.get("branch") or meta.get("head_branch") or ""
        else:
            br = str(meta)
        if br:
            out[name] = br
    return out


def _bucket(branch: str) -> str:
    m = TRAIN.match(branch)
    if m:
        return m.group("ver")
    if "delayed_payment_interest" in branch or branch.startswith("feature/"):
        return "DPI" if "delayed_payment" in branch or "dpi" in branch.lower() else f"feat:{branch.split('/')[-1][:12]}"
    return branch[:16] if branch else "?"


def compute_train_banner(repos: dict[str, str] | None = None) -> str:
    repos = repos if repos is not None else _load_repos()
    if not repos:
        return "TRAINS: (no git-workspace-state.json — run scripts/bin/git-workspace-status.sh)"

    # Prefer known money-path labels
    parts: list[str] = []
    used: set[str] = set()
    for repo, label in (
        ("trustt-platform-accounting", "acc"),
        ("trustt-platform-payments", "pay"),
        ("trustt-platform-los", "los"),
        ("trustt-platform-lib", "lib"),
        ("novopay-platform-lib", "lib"),
    ):
        if repo in repos and label not in used:
            parts.append(f"{label}={_bucket(repos[repo])}")
            used.add(label)

    # Collapse remaining into groups by bucket
    by_b: dict[str, list[str]] = {}
    for repo, br in sorted(repos.items()):
        lab = _LABEL.get(repo)
        if lab and lab in used:
            continue
        by_b.setdefault(_bucket(br), []).append(lab or repo.replace("trustt-platform-", "")[:8])

    # DPI cluster
    dpi_n = sum(1 for br in repos.values() if "delayed_payment" in br)
    if dpi_n:
        # remove DPI from by_b display if we add actor+N=DPI
        parts.append(f"actor+{max(0, dpi_n - 1)}={_bucket(next(br for br in repos.values() if 'delayed_payment' in br))}")
        by_b.pop("DPI", None)

    # Dominant lib train
    for ver, names in sorted(by_b.items(), key=lambda x: -len(x[1])):
        if ver.startswith("feat:") or ver == "DPI":
            continue
        if len(names) >= 3:
            parts.append(f"libs={ver}")
            break
        elif names and ver not in {p.split("=")[-1] for p in parts}:
            parts.append(f"{names[0]}={ver}")

    buckets = {_bucket(b) for b in repos.values()}
    mixed = len(buckets) > 1
    tag = " [MIXED]" if mixed else " [ALIGNED]"
    return "TRAINS: " + " ".join(parts) + tag


HARD_STOP = (
    "HARD STOP [MIXED]: cross-service/money conclusions blocked until you "
    "(a) scope analysis to one named train (sync-branches.sh --domain … --train …) "
    "or (b) get explicit user acknowledgment of mixed-train risk. "
    "Do not conclude cross-repo contracts from mismatched trains."
)


def money_or_cross_service(task_text: str, classification: str = "") -> bool:
    t = (task_text or "").lower()
    c = (classification or "").upper()
    if any(x in c for x in ("MONEY", "FIX+SHIP", "BUG/RCA", "FEATURE", "SHIP", "RELEASE")):
        # Money-ish classifications still need keyword OR money path words
        pass
    keys = (
        "disburse", "repay", "foreclos", "death", "dfc", "dpi", "kafka", "los",
        "payment", "accounting", "money", "gl ", "ledger", "neft", "cross-service",
        "multi-service", "cross repo", "cross-repo", "sync", "entity_type",
        "train", "branch", "mixed",
    )
    if any(k in t for k in keys):
        return True
    if any(x in c for x in ("BUG/RCA", "FIX+SHIP", "MONEY")) and any(
        k in t for k in ("loan", "batch", "billing", "accrual", "npa", "qa")
    ):
        return True
    return False


def banner_and_stop(task_text: str = "", classification: str = "") -> tuple[str, str | None]:
    banner = compute_train_banner()
    stop = None
    if "[MIXED]" in banner and money_or_cross_service(task_text, classification):
        stop = HARD_STOP
    return banner, stop


def domain_repos(domain: str) -> list[str]:
    d = (domain or "").strip().lower()
    return list(DOMAIN_REPOS.get(d) or [])


if __name__ == "__main__":
    import sys

    text = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else ""
    b, s = banner_and_stop(text)
    print(b)
    if s:
        print(s)
