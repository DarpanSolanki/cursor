"""One-shot Jira handoff: gate, pack, post, and walk the workflow to a target state.

Enriching TDPQA-241 took ~15 agent round trips — read the skill, read owners, read mentions,
resolve mode, GET fields, GET transitions, pack, inspect, rebuild after a forbidden-text hit,
post, then POST+GET+GET per transition step. The scripts were never slow (pack 0.04s, a REST
call 0.38s); the round trips were. This does the whole thing in one process and prints one
summary, so the agent spends one tool call instead of fifteen.

    python3 scripts/bin/jira_ship.py TDPQA-241 payload.json --to QA:Test
    python3 scripts/bin/jira_ship.py TDPQA-241 payload.json --dry-run
    python3 scripts/bin/jira_ship.py TDPQA-241 payload.json --fields-only

Push gate: unless --skip-gate, the fix sha must be on origin/<train>, and entering PR-review
states additionally requires it on upstream/<train> — those states assert a review happened.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ADF = ROOT / "scripts/bin/jira-fix-adf.py"
REST = ROOT / "scripts/bin/jira-rest-oauth.py"
ROUTES = ROOT / "scripts/lib/jira_transition_routes.json"

NEVER = {"QA:Traige", "Dev:Rework", "Not an issue", "To Do", "BA Clarification",
         "Details are required from QA", "QA Tested"}
PR_STATES = ("PR: Dev Reviewing", "PR: Dev Lead Reviewing", "PR: Lead Approved")


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _git(repo: Path, *args: str) -> tuple[int, str]:
    r = subprocess.run(["git", "-C", str(repo), *args], text=True,
                       stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    return r.returncode, r.stdout.strip()


def push_gate(repo: str, sha: str, train: str) -> dict:
    path = ROOT / repo
    if not (path / ".git").exists():
        return {"ok": False, "reason": f"repo not found: {repo}"}
    _git(path, "fetch", "origin", "--quiet")
    _git(path, "fetch", "upstream", "--quiet")
    on_origin = _git(path, "merge-base", "--is-ancestor", sha, f"origin/{train}")[0] == 0
    on_upstream = _git(path, "merge-base", "--is-ancestor", sha, f"upstream/{train}")[0] == 0
    return {"ok": on_origin, "on_origin": on_origin, "on_upstream": on_upstream,
            "repo": repo, "sha": sha, "train": train}


def route_to(rest, key: str, target: str, allow_pr: bool) -> list[dict]:
    """Walk forward, one live /transitions read per step, stopping exactly at target."""
    steps: list[dict] = []
    for _ in range(10):
        _, issue = rest.jira("GET", f"/issue/{key}?fields=status")
        state = issue["fields"]["status"]["name"]
        if state == target:
            break
        _, tr = rest.jira("GET", f"/issue/{key}/transitions")
        options = {t["name"]: (t["id"], t["to"]["name"]) for t in tr.get("transitions", [])}
        forward = {k: v for k, v in options.items() if k not in NEVER and v[1] != state}
        if not allow_pr:
            forward = {k: v for k, v in forward.items()
                       if not any(v[1].startswith(p) for p in PR_STATES)}
        if not forward:
            steps.append({"from": state, "blocked": True, "available": sorted(options)})
            break
        pick = next((k for k in forward if forward[k][1] == target), None) or next(iter(forward))
        tid, to = forward[pick]
        code, _ = rest.jira("POST", f"/issue/{key}/transitions", {"transition": {"id": tid}})
        steps.append({"from": state, "via": pick, "to": to, "http": code})
        if code not in (200, 204) or to == target:
            break
    return steps


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("key")
    ap.add_argument("payload")
    ap.add_argument("--to", default="", help="target status, e.g. QA:Test. Omit to skip transitions")
    ap.add_argument("--repo", default="trustt-platform-accounting")
    ap.add_argument("--sha", default="")
    ap.add_argument("--train", default="")
    ap.add_argument("--skip-gate", action="store_true")
    ap.add_argument("--fields-only", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--comment-id", default="")
    args = ap.parse_args(argv)

    out: dict = {"issue": args.key}

    if args.sha and args.train and not args.skip_gate:
        gate = push_gate(args.repo, args.sha, args.train)
        out["push_gate"] = gate
        if not gate.get("ok"):
            out["result"] = "BLOCKED — fix not on origin/<train>"
            print(json.dumps(out, indent=1))
            return 2

    adf = _load(ADF, "jira_adf")
    payload = json.loads(Path(args.payload).read_text())
    try:
        pack = adf.build_handoff_pack(args.key, payload)
    except ValueError as e:
        out["result"] = "BLOCKED — forbidden text or missing required field"
        out["error"] = str(e)[:300]
        print(json.dumps(out, indent=1))
        return 2

    out["fields"] = sorted(pack.get("edit_fields", {}).keys())
    out["has_comment"] = bool(pack.get("comment_adf"))

    if args.dry_run:
        out["result"] = "DRY RUN — nothing posted"
        out["target"] = args.to or None
        print(json.dumps(out, indent=1))
        return 0

    rest = _load(REST, "jira_rest")
    code, _ = rest.jira("PUT", f"/issue/{args.key}", {"fields": pack["edit_fields"]})
    out["fields_http"] = code
    if code not in (200, 204):
        out["result"] = "FAILED on fields"
        print(json.dumps(out, indent=1))
        return 1

    if pack.get("comment_adf") and not args.fields_only:
        if args.comment_id:
            c, _ = rest.jira("PUT", f"/issue/{args.key}/comment/{args.comment_id}",
                             {"body": pack["comment_adf"]})
            out["comment_http"], out["comment_action"] = c, "update"
        else:
            c, body = rest.jira("POST", f"/issue/{args.key}/comment",
                                {"body": pack["comment_adf"]})
            out["comment_http"], out["comment_action"] = c, "create"
            if isinstance(body, dict):
                out["comment_id"] = body.get("id")

    if args.to:
        allow_pr = True
        if args.sha and args.train and not args.skip_gate:
            allow_pr = bool(out.get("push_gate", {}).get("on_upstream"))
            if not allow_pr:
                out["pr_states"] = "skipped — fix not on upstream/<train>, PR states would assert an unmade review"
        out["transitions"] = route_to(rest, args.key, args.to, allow_pr)

    _, issue = rest.jira("GET", f"/issue/{args.key}?fields=status")
    out["final_status"] = issue["fields"]["status"]["name"]
    out["result"] = "OK" if (not args.to or out["final_status"] == args.to) else "PARTIAL — target not reached"
    print(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
