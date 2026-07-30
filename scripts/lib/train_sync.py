#!/usr/bin/env python3
"""Parse user-named integration trains and run scoped sync-branches + KG refresh.

kg_align = detect only (watermark/live vs expected).
kg_enhance with train + sync_domain = checkout scoped repos then kg-switch.
Autopilot calls apply when the user message names a train ≠ live primary repo branch.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/lib"))

from train_banner import domain_repos  # noqa: E402

TRAIN_VERSION_RE = re.compile(
    r"\b(?:on\s+branch\s+)?(?:mfi_(?:integration|release)_v)?(\d+(?:\.\d+){1,4})\b",
    re.I,
)
TRAIN_FULL_RE = re.compile(
    r"\b(mfi_(?:integration|release)_v\d+(?:\.\d+)+)\b",
    re.I,
)

DOMAIN_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("dpi", ("dpi", "delayed payment", "dpic")),
    ("dfc", ("dfc", "death foreclosure", "death_foreclosure")),
    ("disburse", ("disburse", "disbursement")),
    ("foreclosure", ("foreclosure", "force bill", "forceful", "force-bill")),
    ("repayment", ("repayment", "recurring payment")),
    ("los", (" los", "loan origination", "novopay-platform-los", "trustt-platform-los")),
    ("payments", (" neft", "payment gateway", "trustt-platform-payments")),
    (
        "accounting",
        (
            "accounting",
            "interest",
            "accrual",
            "billing",
            "gl ",
            "ledger",
            "int component",
            "shg",
            "parent child",
            "parent-child",
        ),
    ),
]


def normalize_train(raw: str) -> str:
    s = (raw or "").strip()
    if not s:
        return ""
    if s.startswith("mfi_"):
        return s
    if re.match(r"^\d", s):
        return f"mfi_integration_v{s}"
    return s


def parse_train_from_text(text: str) -> str | None:
    if not text:
        return None
    m_full = TRAIN_FULL_RE.search(text)
    if m_full:
        return m_full.group(1)
    m_ver = TRAIN_VERSION_RE.search(text)
    if m_ver:
        return normalize_train(m_ver.group(1))
    return None


def infer_sync_domain(text: str) -> str:
    t = (text or "").lower()
    for domain, keys in DOMAIN_KEYWORDS:
        if any(k in t for k in keys):
            return domain
    return "accounting"


def primary_repo(domain: str) -> str:
    repos = domain_repos(domain)
    return repos[0] if repos else "trustt-platform-accounting"


def live_branch(repo: str, root: Path | None = None) -> str:
    root = root or ROOT
    repo_path = root / repo
    if not (repo_path / ".git").is_dir():
        return ""
    r = subprocess.run(
        ["git", "-C", str(repo_path), "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True,
        text=True,
        timeout=15,
    )
    return (r.stdout or "").strip() if r.returncode == 0 else ""


def sync_plan(text: str, *, root: Path | None = None) -> dict:
    root = root or ROOT
    train = parse_train_from_text(text)
    domain = infer_sync_domain(text)
    repo = primary_repo(domain)
    live = live_branch(repo, root) if train else ""
    needs = bool(train and live and live != train)
    return {
        "train": train,
        "domain": domain,
        "primary_repo": repo,
        "live_branch": live,
        "needs_sync": needs,
        "aligned": bool(train and live == train),
    }


def run_sync(
    train: str,
    domain: str,
    *,
    dry_run: bool = False,
    root: Path | None = None,
) -> tuple[int, str]:
    root = root or ROOT
    cmd = [
        "bash",
        str(root / "scripts/bin/sync-branches.sh"),
        "--domain",
        domain,
        "--train",
        train,
        "--yes",
    ]
    env = {**os.environ}
    if dry_run:
        env["SYNC_DRY_RUN"] = "1"
    r = subprocess.run(
        cmd,
        cwd=str(root),
        env=env,
        capture_output=True,
        text=True,
        timeout=600,
    )
    out = (r.stdout or "") + (r.stderr or "")
    return r.returncode, out


def cmd_plan(args: argparse.Namespace) -> int:
    payload = sync_plan(args.text or "")
    print(json.dumps(payload, indent=2))
    return 0


def cmd_apply(args: argparse.Namespace) -> int:
    train = normalize_train(args.train or "")
    domain = (args.domain or "accounting").strip().lower()
    if not train:
        print("train_sync: missing --train", file=sys.stderr)
        return 2
    plan = {
        "train": train,
        "domain": domain,
        "primary_repo": primary_repo(domain),
        "live_branch": live_branch(primary_repo(domain)),
    }
    plan["needs_sync"] = plan["live_branch"] != train
    if not plan["needs_sync"]:
        print(
            json.dumps(
                {**plan, "skipped": True, "reason": "already on requested train"},
                indent=2,
            )
        )
        return 0
    rc, out = run_sync(train, domain, dry_run=bool(args.dry_run))
    tail = out.splitlines()[-12:] if out else []
    print(
        json.dumps(
            {
                **plan,
                "sync_rc": rc,
                "dry_run": bool(args.dry_run),
                "tail": tail,
            },
            indent=2,
        )
    )
    return rc


def cmd_apply_from_text(args: argparse.Namespace) -> int:
    plan = sync_plan(args.text or "")
    if not plan.get("train"):
        print(json.dumps({"error": "no train in text", **plan}, indent=2))
        return 2
    if not plan.get("needs_sync"):
        print(json.dumps({"skipped": True, **plan}, indent=2))
        return 0
    args.train = plan["train"]
    args.domain = plan["domain"]
    return cmd_apply(args)


def main() -> int:
    p = argparse.ArgumentParser(description="User-train → scoped sync-branches")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_plan = sub.add_parser("plan", help="JSON plan from task text")
    p_plan.add_argument("text", nargs="?", default="")
    p_plan.set_defaults(func=cmd_plan)

    p_apply = sub.add_parser("apply", help="sync-branches --domain … --train … --yes")
    p_apply.add_argument("--train", required=True)
    p_apply.add_argument("--domain", default="accounting")
    p_apply.add_argument("--dry-run", action="store_true")
    p_apply.set_defaults(func=cmd_apply)

    p_text = sub.add_parser("apply-from-text", help="plan + apply from user message")
    p_text.add_argument("text", nargs="?", default="")
    p_text.add_argument("--dry-run", action="store_true")
    p_text.set_defaults(func=cmd_apply_from_text)

    args = p.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
