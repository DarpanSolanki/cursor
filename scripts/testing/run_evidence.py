"""Per-API run evidence derived from the learning bus.

`footprints.jsonl` records `status: verified` from a flag typed into `capture-flow.sh` —
nothing ties it to a run, so the money-proof metric could be satisfied by writing a line.
Meanwhile `ntest` already emits a `test_pass` / `test_fail` event for every case it runs,
and nothing consumed it. This turns that stream into the evidence the metric should use.

    python3 scripts/testing/run_evidence.py                      # per-API summary
    python3 scripts/testing/run_evidence.py --api disburseLoan
    python3 scripts/testing/run_evidence.py --json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BUS = ROOT / "cursor-bundle/flow-test/learning_bus.jsonl"


def _rows(path: Path):
    if not path.is_file():
        return
    for line in path.read_text(errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            yield json.loads(line)
        except json.JSONDecodeError:
            continue


def current_train(service: str = "accounting") -> str:
    import subprocess

    repo = ROOT / "trustt-platform-accounting"
    if service != "accounting":
        repo = ROOT / f"trustt-platform-{service}"
    if not (repo / ".git").exists():
        return ""
    out = subprocess.run(
        ["git", "-C", str(repo), "branch", "--show-current"],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
    )
    return out.stdout.strip()


REGISTRY = ROOT / "scripts/testing/registry.json"


def _inapplicable_cases() -> set[str]:
    """Cases whose `requires_paths` are absent from this checkout.

    Their recorded results describe a train that no longer applies, so keeping them would
    report a not-on-this-train case as a regression — the exact error 40-knowledge-upkeep
    warns about.
    """
    try:
        reg = json.loads(REGISTRY.read_text())
    except (OSError, json.JSONDecodeError):
        return set()
    out = set()
    for case_id, case in reg.items():
        if not isinstance(case, dict):
            continue
        for path in case.get("requires_paths") or []:
            if not (ROOT / path).exists():
                out.add(case_id)
                break
    return out


def evidence(train: str | None = None) -> dict[str, dict]:
    """api -> {passes, fails, last_pass, last_fail, cases}. Latest event per case wins.

    Trains diverge in both directions, so a run recorded on another branch is not evidence
    about this one. Pass `train` to keep only same-train events; events recorded before the
    train stamp existed carry no train and are kept (they are all the history there is).
    """
    skip_cases = _inapplicable_cases()
    per_case: dict[tuple[str, str], dict] = {}
    for row in _rows(BUS):
        if row.get("type") not in ("test_pass", "test_fail"):
            continue
        api = row.get("api")
        if not api:
            continue
        meta = row.get("meta") or {}
        row_train = meta.get("train") or ""
        if train and row_train and row_train != train:
            continue
        case = meta.get("case_id") or (row.get("detail") or "").replace("case=", "") or "-"
        if case in skip_cases:
            continue
        key = (api, case)
        prior = per_case.get(key)
        if prior is None or row.get("ts", "") >= prior["ts"]:
            per_case[key] = {"ts": row.get("ts", ""), "type": row["type"], "train": row_train}

    out: dict[str, dict] = {}
    for (api, case), rec in per_case.items():
        bucket = out.setdefault(
            api,
            {"passes": 0, "fails": 0, "last_pass": "", "last_fail": "", "cases": [], "trains": []},
        )
        bucket["cases"].append(case)
        if rec["train"]:
            bucket["trains"].append(rec["train"])
        if rec["type"] == "test_pass":
            bucket["passes"] += 1
            bucket["last_pass"] = max(bucket["last_pass"], rec["ts"])
        else:
            bucket["fails"] += 1
            bucket["last_fail"] = max(bucket["last_fail"], rec["ts"])
    for bucket in out.values():
        bucket["cases"] = sorted(set(bucket["cases"]))
        bucket["trains"] = sorted(set(bucket["trains"]))
    return out


def status_for(api: str, ev: dict[str, dict] | None = None) -> str:
    """run_verified when a case for this API last ran green; run_failed when it last ran red."""
    ev = ev if ev is not None else evidence()
    row = ev.get(api)
    if not row:
        return "none"
    if row["passes"] and row["last_pass"] >= row["last_fail"]:
        return "run_verified"
    if row["fails"]:
        return "run_failed"
    return "none"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    ev = evidence()
    if args.api:
        row = ev.get(args.api)
        if not row:
            print(f"{args.api}: no recorded run")
            return 1
        print(json.dumps({args.api: {**row, "status": status_for(args.api, ev)}}, indent=1))
        return 0
    if args.json:
        print(json.dumps({a: {**r, "status": status_for(a, ev)} for a, r in ev.items()}, indent=1))
        return 0
    print(f"{'api':44s} {'status':12s} pass fail  last")
    for api, row in sorted(ev.items()):
        print(
            f"{api:44s} {status_for(api, ev):12s} {row['passes']:4d} {row['fails']:4d}  "
            f"{row['last_pass'] or row['last_fail']}"
        )
    print(f"\n{len(ev)} API(s) with recorded runs")
    return 0


if __name__ == "__main__":
    sys.exit(main())
