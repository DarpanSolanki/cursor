#!/usr/bin/env python3
"""
Spec-driven API tests — fire → assert → optional DB cross-check.

  api-test.py list
  api-test.py run dpic.overview_dpi_amounts
  api-test.py run specs/dpic/overview_dpi_amounts.json
  api-test.py run dpic.overview_dpi_amounts --watch-log
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib.api_client import fire_api, fresh_stan, health_check, load_payload
from lib.assertions import run_assertions
from lib.logs import accounting_log_path, tail_new_lines, watch_hint
from lib.paths import TESTING_DIR

SPECS_DIR = TESTING_DIR / "specs"


def _resolve_vars(spec: dict) -> dict[str, str]:
    defaults = spec.get("defaults") or {}
    raw = spec.get("vars") or {}
    out: dict[str, str] = {}
    for k, tmpl in raw.items():
        if isinstance(tmpl, str) and tmpl.startswith("${") and tmpl.endswith("}"):
            env_key = tmpl[2:-1]
            out[k] = os.environ.get(env_key, str(defaults.get(env_key, "")))
        else:
            out[k] = str(tmpl)
    # expose for SQL :ACCOUNT_NUMBER style substitution
    for env_key, val in defaults.items():
        out.setdefault(env_key, os.environ.get(env_key, str(val)))
    return out


def _find_spec(spec_id: str) -> Path:
    p = Path(spec_id)
    if p.is_file():
        return p
    if not spec_id.endswith(".json"):
        hits = list(SPECS_DIR.rglob(f"*{spec_id.split('.')[-1]}*.json"))
        for h in SPECS_DIR.rglob("*.json"):
            try:
                data = json.loads(h.read_text(encoding="utf-8"))
            except Exception:
                continue
            if data.get("id") == spec_id:
                return h
        if len(hits) == 1:
            return hits[0]
    raise FileNotFoundError(f"spec not found: {spec_id}")


def _load_spec(path: Path) -> dict:
    spec = json.loads(path.read_text(encoding="utf-8"))
    spec["_path"] = str(path)
    return spec


def cmd_list() -> int:
    specs = sorted(SPECS_DIR.rglob("*.json"))
    for p in specs:
        try:
            s = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        print(f"  {s.get('id', p.stem):<36} {s.get('title', '')}")
    print(f"\n{len(specs)} spec(s). Run: api-test.py run <id>")
    return 0


def cmd_run(spec_id: str, *, watch_log: bool, health: bool) -> int:
    path = _find_spec(spec_id)
    spec = _load_spec(path)
    api_name = spec["api_name"]
    vars_ = _resolve_vars(spec)
    payload_rel = spec.get("payload") or spec.get("payload_file")
    payload_path = path.parent.parent / payload_rel if payload_rel else None
    if not payload_path or not payload_path.is_file():
        payload_path = TESTING_DIR / payload_rel

    if health:
        ok, msg = health_check()
        print(f"health: {'OK' if ok else 'FAIL'} ({msg})")
        if not ok:
            return 2

    stan = fresh_stan(spec.get("id", "test").replace(".", "_"))
    payload = load_payload(str(payload_path), stan, vars_)
    print(f"=== {spec.get('id')} ===")
    print(f"POST {api_name}  vars={vars_}")
    result = fire_api(api_name, payload, timeout_s=float(spec.get("timeout_s", 60)))
    code, status = result.response_status()
    print(f"HTTP {result.http_status} ({result.elapsed_ms}ms)  {code}/{status}")

    run = run_assertions(result.body, result, spec, env={**os.environ, **vars_})
    for ar in run.results:
        mark = "PASS" if ar.ok else "FAIL"
        print(f"  [{mark}] {ar.name}: {ar.detail}")

    if spec.get("print_paths"):
        obj = json.loads(result.body)
        for p in spec["print_paths"]:
            from lib.json_path import get_path, path_exists
            if path_exists(obj, p):
                print(f"  → {p} = {get_path(obj, p)}")

    if watch_log:
        log = accounting_log_path()
        print(f"\n--- log errors ({log}) ---")
        for line in tail_new_lines(log, since_epoch=time.time() - 120):
            print(line)
        print(watch_hint(log))

    if not run.passed:
        if spec.get("on_fail_print_body"):
            print("\n--- response body ---")
            print(result.body[:4000])
        return 1
    print("\n✓ ALL ASSERTIONS PASSED")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Spec-driven Novopay API tests")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list", help="List specs")
    r = sub.add_parser("run", help="Run a spec by id or path")
    r.add_argument("spec_id")
    r.add_argument("--watch-log", action="store_true")
    r.add_argument("--health", action="store_true")
    args = p.parse_args()
    if args.cmd == "list":
        return cmd_list()
    return cmd_run(args.spec_id, watch_log=args.watch_log, health=args.health)


if __name__ == "__main__":
    raise SystemExit(main())
