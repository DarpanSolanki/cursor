#!/usr/bin/env python3
"""Infer ship tier, apiName, registry cases, and impact from paths/git diff.

Tiers (highest wins when merging pending work):
  workspace — scripts, .cursor, cursor-bundle, system_brain, docs
  service   — any novopay-*/trustt-* code or deploy config
  money     — accounting/LOS/payments money paths, batches, Kafka consumers on money
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "scripts/testing/registry.json"
PENDING_DEFAULT = ROOT / ".cursor/.pending-ship-work.json"

sys.path.insert(0, str(ROOT / "scripts/lib"))
try:
    from kg_ship_resolve import resolve_apis_for_path, resolve_apis_for_paths
except ImportError:
    resolve_apis_for_path = None  # type: ignore
    resolve_apis_for_paths = None  # type: ignore

TIER_RANK = {"workspace": 0, "service": 1, "money": 2}

EXPLICIT: list[tuple[str, str]] = [
    ("GetLoanAccountOverviewDetails", "getLoanAccountOverviewDetails"),
    ("getLoanAccountOverviewDetails_responseTemplate", "getLoanAccountOverviewDetails"),
    ("GetLoanAccountAccruedBPIAmount", "getLoanAccountBPIAmount"),
    ("getLoanAccountBPIAmount_responseTemplate", "getLoanAccountBPIAmount"),
]

WORKSPACE_MARKERS = (
    ".cursor/",
    "scripts/",
    "cursor-bundle/",
    "system_brain/",
    "docs/",
    "AGENTS.md",
    "WORKSPACE.md",
)

MONEY_REPO_HINTS: dict[str, tuple[str, ...]] = {
    "novopay-platform-accounting-v2": (
        "Processor.java",
        "BatchService",
        "ItemWriter",
        "Consumer.java",
        "MessageBroker",
        "orchestration/",
        "postTransaction",
        "loan/",
        "disburse",
        "repay",
        "foreclos",
        "interest",
        "dpi",
        "billing",
        "accrual",
        "_responseTemplate.json",
        "templates/",
    ),
    "novopay-mfi-los": (
        "Disburse",
        "Foreclos",
        "Repay",
        "Sync",
        "Processor.java",
        "disburse",
        "foreclos",
    ),
    "novopay-platform-payments": (
        "Processor.java",
        "collection",
        "repay",
        "disburse",
    ),
}

SERVICE_HEALTH: dict[str, str] = {
    "accounting": "health.accounting",
    "actor": "health.actor",
    "task": "health.task",
    "payments": "health.payments",
}

REPO_SERVICE: dict[str, str] = {
    "novopay-platform-accounting-v2": "accounting",
    "novopay-platform-actor": "actor",
    "novopay-platform-task": "task",
    "novopay-platform-payments": "payments",
}


def load_registry() -> dict:
    if not REGISTRY.is_file():
        return {}
    return json.loads(REGISTRY.read_text(encoding="utf-8"))


def infer_repo_from_path(path: str) -> str | None:
    for part in Path(path).parts:
        if part.startswith("novopay-") or part.startswith("trustt-"):
            return part
    return None


def is_workspace_path(path: str) -> bool:
    s = path.replace("\\", "/")
    if any(s.startswith(m) or f"/{m}" in s for m in WORKSPACE_MARKERS):
        return True
    name = Path(s).name
    return name in ("AGENTS.md", "WORKSPACE.md", ".cursorrules")


def is_service_path(path: str) -> bool:
    repo = infer_repo_from_path(path)
    if not repo:
        return False
    s = path.replace("\\", "/")
    return any(
        x in s
        for x in (
            "/src/",
            "/deploy/",
            "build.gradle",
            "settings.gradle",
            "/orchestration/",
            "/templates/",
        )
    )


def is_money_path(path: str) -> bool:
    s = path.replace("\\", "/")
    repo = infer_repo_from_path(s)
    if repo and repo in MONEY_REPO_HINTS:
        if any(h.lower() in s.lower() for h in MONEY_REPO_HINTS[repo]):
            return True
    if "/orchestration/" in s and s.endswith(".xml"):
        return True
    if "LmsMessageBrokerConsumer" in s or "MessageBroker.xml" in s:
        return True
    if "novopay-platform-lib/" in s and any(
        x in s for x in ("RedisCache", "message-broker", "navigation", "service-gateway")
    ):
        return True
    return False


def classify_path(path: str) -> str:
    if is_money_path(path):
        return "money"
    if is_service_path(path):
        return "service"
    if is_workspace_path(path) or infer_repo_from_path(path):
        return "workspace" if is_workspace_path(path) else "service"
    return "workspace"


def is_ship_path(path: str) -> bool:
    if is_workspace_path(path):
        return True
    if is_service_path(path):
        return True
    if is_money_path(path):
        return True
    if infer_repo_from_path(path):
        return True
    if path.endswith((".java", ".xml", ".json", ".sql", ".sh", ".py", ".mdc", ".md")):
        return "novopay-" in path or "trustt-" in path or "scripts/" in path
    return False


def merge_tier(current: str | None, new: str) -> str:
    cur = current or "workspace"
    return new if TIER_RANK.get(new, 0) > TIER_RANK.get(cur, 0) else cur


def infer_from_path(path: str) -> str | None:
    for needle, api in EXPLICIT:
        if needle in path:
            return api
    m = re.search(r"/([A-Z][a-zA-Z0-9]*)Processor\.java", path)
    if m:
        name = m.group(1)
        return name[0].lower() + name[1:]
    m = re.search(r"/(\w+)_responseTemplate\.json", path)
    if m:
        return m.group(1)
    p = Path(path)
    if p.suffix == ".xml" and "orchestration" in path:
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
            for m in re.finditer(r'<Request\s+name="([^"]+)"', text):
                return m.group(1)
        except OSError:
            pass
    return None


def registry_case_for_api(api: str, reg: dict | None = None) -> str:
    reg = reg if reg is not None else load_registry()
    for cid, c in reg.items():
        if cid.startswith("_") or not isinstance(c, dict):
            continue
        if c.get("api") == api:
            return cid
    return ""


def smoke_cases_for_tier(tier: str, reg: dict | None = None) -> list[str]:
    reg = reg if reg is not None else load_registry()
    out: list[str] = []
    for cid, c in reg.items():
        if cid.startswith("_") or not isinstance(c, dict):
            continue
        if c.get("smoke_tier") == tier:
            out.append(cid)
    return sorted(out)


def health_cases_for_repos(repos: list[str], reg: dict | None = None) -> list[str]:
    reg = reg if reg is not None else load_registry()
    out: list[str] = []
    for repo in repos:
        svc = REPO_SERVICE.get(repo)
        if not svc:
            continue
        hid = SERVICE_HEALTH.get(svc)
        if hid and hid in reg and hid not in out:
            out.append(hid)
    return sorted(out)


def git_diff_paths(repo: str) -> list[str]:
    rdir = ROOT / repo
    if not (rdir / ".git").is_dir():
        return []
    paths: set[str] = set()
    for args in (
        ["git", "-C", str(rdir), "diff", "--name-only", "HEAD"],
        ["git", "-C", str(rdir), "diff", "--name-only", "--cached"],
    ):
        out = subprocess.run(args, capture_output=True, text=True, check=False)
        paths.update(p.strip() for p in out.stdout.splitlines() if p.strip())
    return sorted(paths)


def git_dirty_repos() -> list[str]:
    repos: list[str] = []
    for d in sorted(ROOT.iterdir()):
        if not d.is_dir() or not (d / ".git").is_dir():
            continue
        if not (d.name.startswith("novopay-") or d.name.startswith("trustt-")):
            continue
        out = subprocess.run(
            ["git", "-C", str(d), "status", "--porcelain"],
            capture_output=True,
            text=True,
            check=False,
        )
        if out.stdout.strip():
            repos.append(d.name)
    return repos


def resolve_apis_smart(paths: list[str]) -> list[str]:
    """KG-aware apiName resolution — only flows touched by changed paths."""
    if resolve_apis_for_paths and paths:
        apis = resolve_apis_for_paths(paths)
        if apis:
            return apis
    apis: list[str] = []
    for p in paths:
        api = infer_from_path(p)
        if api and api not in apis:
            apis.append(api)
    return apis


def _focus_apis_for_paths(paths: list[str], apis: list[str]) -> list[str]:
    """When a util is shared across flows, prefer apis matching the touched package."""
    if len(apis) <= 1:
        return apis
    hints: list[str] = []
    for p in paths:
        if resolve_apis_for_path:
            from kg_ship_resolve import _domain_hint_api  # noqa: WPS433

            h = _domain_hint_api(p)
            if h:
                hints.append(h)
    if not hints:
        return apis
    focused = [a for a in apis if a in hints]
    return focused if focused else apis[:1]


def build_impact(paths: list[str]) -> dict:
    reg = load_registry()
    repos: list[str] = []
    tier = "workspace"
    for p in paths:
        if not is_ship_path(p):
            continue
        tier = merge_tier(tier, classify_path(p))
        repo = infer_repo_from_path(p)
        if repo and repo not in repos:
            repos.append(repo)

    apis = _focus_apis_for_paths(paths, resolve_apis_smart(paths))

    cases = [registry_case_for_api(a, reg) for a in apis]
    cases = [c for c in cases if c]
    smoke_money = smoke_cases_for_tier("money", reg) if tier == "money" else []
    smoke_service = smoke_cases_for_tier("smoke", reg) if tier in ("money", "service") else []
    health = health_cases_for_repos(repos, reg) if tier in ("money", "service") and not apis else []

    return {
        "tier": tier,
        "apis": apis,
        "repos": repos,
        "registry_cases": cases,
        "smoke_money_cases": smoke_money,
        "smoke_service_cases": smoke_service,
        "health_cases": health,
    }


def read_pending_tier(pending_path: Path | None = None) -> str:
    p = pending_path or PENDING_DEFAULT
    if not p.is_file():
        return "workspace"
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        return d.get("tier") or "workspace"
    except Exception:
        return "workspace"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--git-diff", metavar="REPO")
    ap.add_argument("--git-diff-all", action="store_true", help="All dirty novopay/trustt repos")
    ap.add_argument("--path", action="append", default=[])
    ap.add_argument("--registry-case", metavar="API")
    ap.add_argument("--smoke-tier", metavar="TIER")
    ap.add_argument("--classify", metavar="PATH", help="Print tier for one path")
    ap.add_argument("--is-ship-path", metavar="PATH", help="Exit 0 if ship path")
    ap.add_argument("--pending-tier", action="store_true")
    ap.add_argument("--impact-json", action="store_true")
    args = ap.parse_args()

    reg = load_registry()

    if args.pending_tier:
        print(read_pending_tier())
        return 0

    if args.classify:
        print(classify_path(args.classify))
        return 0

    if args.is_ship_path:
        sys.exit(0 if is_ship_path(args.is_ship_path) else 1)

    if args.registry_case:
        print(registry_case_for_api(args.registry_case, reg))
        return 0

    if args.smoke_tier:
        for cid in smoke_cases_for_tier(args.smoke_tier, reg):
            print(cid)
        return 0

    paths: list[str] = list(args.path)
    if args.git_diff:
        paths.extend(git_diff_paths(args.git_diff))
    if args.git_diff_all:
        for repo in git_dirty_repos():
            paths.extend(git_diff_paths(repo))

    if args.impact_json or paths:
        impact = build_impact(paths)
        if args.impact_json:
            print(json.dumps(impact, indent=2))
            return 0

    apis: list[str] = []
    for p in paths:
        api = infer_from_path(p)
        if api and api not in apis:
            apis.append(api)

    for api in apis:
        print(api)
    return 0


if __name__ == "__main__":
    sys.exit(main())
