#!/usr/bin/env python3
"""
ntest — one entry for local API + flow testing (KG-aware, registry-driven).

  ntest list [--api|--flow]
  ntest run <id>              # registry case (api or flow)
  ntest smoke                 # all registry api cases
  ntest smoke --quick         # health + quick-tagged cases only
  ntest validate              # registry.json schema check
  ntest health [service]      # actuator probe
  ntest ensure [service] [--compile]  # restart service if API probe fails
  ntest api <service> <api> [--var K=V] [--batch] [--job-time MS] [-f payload.json]
  ntest auto <apiName>        # AUTONOMOUS: kg-switch → resolve → test → analyze (no hand-holding)
  ntest orient <apiName>      # KG flow + crud + cases before you test/fix
  ntest logs [service] [paths|errors|boot|snap]  # canonical log paths + RCA
  ntest diagnose [service]                       # snap when stuck
  ntest learn --api <api> --kind gotcha --text "..."   # append test learning (self-learning)
  ntest learnings [--api <api>]                        # list prior learnings

Registry: scripts/testing/registry.json — add cases inline; `auto` uses KG + templates when no registry row.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from lib.api_client import fire_api, fresh_stan, health_check, load_payload
from lib.assertions import run_assertions
from lib.envelope import batch_envelope, build_envelope
from lib.expect import expand_expect
from lib.json_path import get_path, path_exists
from lib.analyze import analyze_failure
from lib.kg_orient import orient_api
from lib.kg_resolve import registry_match, resolve_api
from lib.logs import run_log_snap, service_log_path, tail_new_lines, watch_hint
from lib.paths import ROOT
from lib.services import SERVICES
from lib.test_learnings import LEARNINGS, append_learning, load_learnings
from lib.validate_registry import validate_registry

REGISTRY = HERE / "registry.json"
KG_ENSURE = ROOT / "scripts" / "bin" / "kg-ensure-fresh.sh"
KG_SESSION = ROOT / "scripts" / "bin" / "kg-session-sync.sh"
AGENT_OPS = ROOT / "scripts" / "bin" / "agent-ops.sh"
SYNC_ENGINE = HERE / "sync_engine.py"


def _trigger_intel_sync() -> None:
    if os.environ.get("NTEST_NO_INTEL_SYNC") == "1":
        return
    if not SYNC_ENGINE.is_file():
        return
    subprocess.run(
        [sys.executable, str(SYNC_ENGINE), "fast-sync", "--quiet"],
        cwd=str(ROOT),
        timeout=45,
        check=False,
        capture_output=True,
    )


def _is_batch_api(api: str, case: dict) -> bool:
    if case.get("batch") or case.get("type") == "batch":
        return True
    low = api.lower()
    return "dpi" in low or low.endswith("job") or api.endswith(("Calculation", "Booking", "Billing"))


def _is_money_api(api: str, case: dict) -> bool:
    low = api.lower()
    return _is_batch_api(api, case) or "disburse" in low or "foreclos" in low


def _auto_before_test(api: str, service: str, case: dict) -> int:
    if os.environ.get("NTEST_NO_ENSURE") == "1":
        return 0
    if not _is_money_api(api, case):
        ok, _ = health_check(service)
        return 0 if ok else subprocess.call(["bash", str(AGENT_OPS), "before-test", api, service]) if AGENT_OPS.is_file() else 2
    if AGENT_OPS.is_file():
        return subprocess.call(["bash", str(AGENT_OPS), "before-test", api, service])
    ok, msg = health_check(service)
    if ok:
        return 0
    print(f"service down: {msg}", file=sys.stderr)
    return 2


def _auto_on_failure(service: str, api: str, job_time: str = "") -> None:
    if AGENT_OPS.is_file():
        subprocess.run(
            ["bash", str(AGENT_OPS), "on-failure", service, api, job_time],
            cwd=str(ROOT),
            check=False,
        )
    else:
        print(run_log_snap(service))


def _load_registry_raw() -> dict[str, Any]:
    return json.loads(REGISTRY.read_text(encoding="utf-8"))


def _load_registry() -> dict[str, Any]:
    return {k: v for k, v in _load_registry_raw().items() if not k.startswith("_")}


def _correlators() -> dict[str, str]:
    raw = _load_registry_raw().get("_correlators") or {}
    return {k: os.environ.get(k, str(v)) for k, v in raw.items()}


def _resolve_defaults(case: dict) -> dict[str, str]:
    out = {k: os.environ.get(k, str(v)) for k, v in (case.get("defaults") or {}).items()}
    for k, tmpl in (case.get("vars") or {}).items():
        if isinstance(tmpl, str) and tmpl.startswith("${") and tmpl.endswith("}"):
            out[k] = os.environ.get(tmpl[2:-1], out.get(tmpl[2:-1], ""))
        else:
            out[k] = str(tmpl)
    return out


def _subst_request(obj: Any, env: dict[str, str]) -> Any:
    if isinstance(obj, dict):
        return {k: _subst_request(v, env) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_subst_request(v, env) for v in obj]
    if isinstance(obj, str) and obj.startswith("${") and obj.endswith("}"):
        return env.get(obj[2:-1], obj)
    return obj


def cmd_list(args: argparse.Namespace) -> int:
    reg = _load_registry()
    for cid, c in sorted(reg.items()):
        t = c.get("type", "?")
        if args.api and t != "api":
            continue
        if args.flow and t != "flow":
            continue
        print(f"  {cid:<28} [{t:4}] {c.get('title', '')}")
    print(f"\n{len(reg)} case(s). Run: ntest run <id> | ntest smoke")
    return 0


def _telemetry(case_id: str, passed: bool, duration_s: float = 0.0) -> None:
    try:
        from ntest_telemetry import append_case_result

        append_case_result(case_id, passed, duration_s)
    except Exception:
        pass
    if passed:
        try:
            import sys

            sys.path.insert(0, str(ROOT / "scripts" / "lib"))
            from ship_credit_pass import record_pass

            record_pass(case_id, duration_s)
        except Exception:
            pass
    else:
        try:
            import sys

            sys.path.insert(0, str(ROOT / "scripts" / "lib"))
            from ship_credit_pass import clear_pass

            clear_pass(case_id)
        except Exception:
            pass


def _batch_counts(job_name: str, before_exec: str) -> tuple[int, int]:
    """Items read and written by executions of `job_name` newer than `before_exec`.

    Spring Batch records this per step in `mfi_batch.batch_step_execution`, and it is the only
    honest measure of a batch job's work: `loanAccountDpdCalcJob` reads and writes all 2154
    active loans while `loan_account.updated_on` moves for none of them, because Hibernate
    issues no UPDATE for an entity whose fields did not change. A row-count or timestamp diff
    therefore understates every Spring Batch job.

    The sum spans every step of the execution, and a partitioned job reports counts on both
    the master step and each partition — so `loanAccountDpdCalcJob` returns 4308 for 2154
    loans. This is a proof-of-work signal ("did this execution move anything"), not an item
    count, and must not be quoted as one.
    """
    import subprocess as _sp
    sql = (
        "SELECT COALESCE(SUM(s.read_count),0)||'|'||COALESCE(SUM(s.write_count),0) "
        "FROM mfi_batch.batch_step_execution s "
        "JOIN mfi_batch.batch_job_execution e ON e.job_execution_id = s.job_execution_id "
        "JOIN mfi_batch.batch_job_instance i ON i.job_instance_id = e.job_instance_id "
        f"WHERE i.job_name = '{job_name}' AND e.job_execution_id > {int(before_exec or 0)}"
    )
    try:
        out = _sp.check_output(
            ["psql", "-h", os.environ.get("YB_HOST", "127.0.0.1"),
             "-p", os.environ.get("YB_PORT", "5433"),
             "-U", os.environ.get("YB_USER", "yugabyte"),
             "-d", os.environ.get("YB_DB", "yugabyte"),
             "-t", "-A", "-v", "ON_ERROR_STOP=1", "-c", sql],
            env={**os.environ, "PGPASSWORD": os.environ.get("PGPASSWORD", "yugabyte")},
            text=True, timeout=60).strip()
        read_s, _, write_s = out.partition("|")
        return int(read_s or 0), int(write_s or 0)
    except Exception as exc:  # noqa: BLE001
        print(f"  [WARN] batch_counts failed: {exc}", file=sys.stderr)
        return -1, -1


def _batch_planned(job_name: str, before_exec: str) -> int:
    """How many rows the job itself decided to process, from its own `batch_record_count` param.

    A partitioned job counts its candidates before it runs and stores the figure in
    `batch_job_execution_params`. Comparing it against `read_count` is the check that catches a
    job which planned for N rows and then read none of them — GAP-095, where the partitioner's
    date arithmetic was the mirror image of the reader's, so the partitions were bounded to an
    id range that structurally could not contain the reader's own candidates. `COMPLETED` with
    read=0 is indistinguishable from "nothing due today" without this number.

    Returns -1 when the job records no such parameter, which most non-partitioned jobs do not.
    """
    import subprocess as _sp
    sql = (
        "SELECT COALESCE(MAX(p.parameter_value::bigint),-1) "
        "FROM mfi_batch.batch_job_execution_params p "
        "JOIN mfi_batch.batch_job_execution e ON e.job_execution_id = p.job_execution_id "
        "JOIN mfi_batch.batch_job_instance i ON i.job_instance_id = e.job_instance_id "
        f"WHERE i.job_name = '{job_name}' AND e.job_execution_id > {int(before_exec or 0)} "
        "AND p.parameter_name = 'batch_record_count'"
    )
    try:
        out = _sp.check_output(
            ["psql", "-h", os.environ.get("YB_HOST", "127.0.0.1"),
             "-p", os.environ.get("YB_PORT", "5433"),
             "-U", os.environ.get("YB_USER", "yugabyte"),
             "-d", os.environ.get("YB_DB", "yugabyte"),
             "-t", "-A", "-v", "ON_ERROR_STOP=1", "-c", sql],
            env={**os.environ, "PGPASSWORD": os.environ.get("PGPASSWORD", "yugabyte")},
            text=True, timeout=60).strip()
        return int(out or -1)
    except Exception as exc:  # noqa: BLE001
        print(f"  [WARN] batch_planned query failed, plan check skipped: {exc}", file=sys.stderr)
        return -1


def _run_api_case(case_id: str, case: dict, *, watch: bool, health: bool) -> tuple[int, Any]:
    t0 = time.time()
    env = {**_correlators(), **_resolve_defaults(case)}
    service = case.get("service", "accounting")
    api = case.get("api", case_id)

    # Trains diverge in both directions: a case that needs a feature absent from the checked-out
    # train is out of scope there, not broken. Declaring the path keeps this self-maintaining —
    # no per-train list to rot. Skips are not recorded as runs.
    missing = [p for p in (case.get("requires_paths") or []) if not (ROOT / p).exists()]
    if missing:
        print(f"=== {case_id} SKIP — not on this train (absent: {missing[0]})")
        return 0, None

    if health:
        ok, msg = health_check(service)
        print(f"health: {'OK' if ok else 'FAIL'} — {msg}")
        if not ok:
            _telemetry(case_id, False, time.time() - t0)
            return 2, None

    r = _auto_before_test(api, service, case)
    if r != 0:
        _telemetry(case_id, False, time.time() - t0)
        return r, None

    stan = fresh_stan(case_id.replace(".", "_"))
    # Dedup-guarded write APIs need a value that differs every run, or the second run fails on
    # the guard rather than on the behaviour under test.
    env["STAN"] = stan
    if case.get("payload_file"):
        payload = load_payload(str(ROOT / case["payload_file"]), stan, env)
    elif case.get("batch") or case.get("type") == "batch":
        payload = batch_envelope(api, env.get("JOB_TIME"), stan)
    else:
        req = _subst_request(case.get("request") or {}, env)
        if service == "actor" and "user_id" in req:
            env["user_id"] = str(req["user_id"])
        header_overrides = {}
        if case.get("function_sub_code"):
            header_overrides["function_sub_code"] = str(case["function_sub_code"])
        if isinstance(case.get("headers"), dict):
            header_overrides.update(case["headers"])
        payload = build_envelope(
            service,
            req,
            stan=stan,
            vars=env,
            header_overrides=header_overrides or None,
        )

    print(f"=== {case_id} [{service}] {api} ===")
    before_exec = "0"
    will_wait_batch = (
        case.get("wait_batch") is not False
        and (case.get("batch") or case.get("type") == "batch")
    )
    if will_wait_batch:
        job_name_pre = case.get("batch_job_name") or api
        try:
            import subprocess as _sp
            before_exec = _sp.check_output(
                [
                    "psql",
                    "-h", os.environ.get("YB_HOST", "127.0.0.1"),
                    "-p", os.environ.get("YB_PORT", "5433"),
                    "-U", os.environ.get("YB_USER", "yugabyte"),
                    "-d", os.environ.get("YB_DB", "yugabyte"),
                    "-t", "-A", "-v", "ON_ERROR_STOP=1",
                    "-c",
                    f"SELECT COALESCE(MAX(bje.job_execution_id), 0) "
                    f"FROM mfi_batch.batch_job_execution bje "
                    f"JOIN mfi_batch.batch_job_instance bji "
                    f"ON bji.job_instance_id = bje.job_instance_id "
                    f"WHERE bji.job_name = '{job_name_pre}'",
                ],
                env={**os.environ, "PGPASSWORD": os.environ.get("PGPASSWORD", "yugabyte")},
                text=True,
            ).strip() or "0"
        except Exception as exc:  # noqa: BLE001
            print(f"  [WARN] before_exec capture failed: {exc}", file=sys.stderr)
            before_exec = "0"
    result = fire_api(api, payload, service=service)
    if os.environ.get("NTEST_NO_AUTO_RECOVER") != "1" and result.http_status in (0, 502, 503, 504):
        print("(connection failed — agent-ops retry)")
        if AGENT_OPS.is_file():
            subprocess.call(["bash", str(AGENT_OPS), "before-test", api, service])
        else:
            cmd_ensure(argparse.Namespace(service=service, compile=True))
        result = fire_api(api, payload, service=service)
    print(f"URL {result.url}")
    code, status = result.response_status()
    print(f"HTTP {result.http_status} ({result.elapsed_ms}ms)  {code}/{status}")

    all_rules = expand_expect(case.get("expect") or {})
    # A batch trigger returns 200 the moment the job is accepted, so any assert on what the
    # job produced — a file on disk or a row in the database — has to wait for COMPLETED.
    # Evaluated immediately it reads the state the PREVIOUS run left behind, which passes or
    # fails for reasons that have nothing to do with this run.
    DEFERRED_RULE_TYPES = {"file_exists", "file_row_count", "db_matches_path"}
    if will_wait_batch:
        immediate_rules = [r for r in all_rules if r["type"] not in DEFERRED_RULE_TYPES]
        deferred_rules = [r for r in all_rules if r["type"] in DEFERRED_RULE_TYPES]
    else:
        immediate_rules = all_rules
        deferred_rules = []

    spec = {
        "assertions": immediate_rules,
        "on_fail_print_body": True,
    }
    run = run_assertions(result.body, result, spec, env={**os.environ, **env})
    for ar in run.results:
        print(f"  [{'PASS' if ar.ok else 'FAIL'}] {ar.name}: {ar.detail}")

    if (
        run.passed
        and case.get("wait_batch") is not False
        and (case.get("batch") or case.get("type") == "batch")
    ):
        job_name = case.get("batch_job_name") or api
        job_time = str(env.get("JOB_TIME") or "")
        wait_script = ROOT / "scripts" / "dpic" / "lib" / "wait_batch_job.sh"
        if wait_script.is_file() and job_time:
            print(f"  wait_batch: {job_name} job_time={job_time} before_exec={before_exec}")
            wb = subprocess.run(
                ["bash", str(wait_script), job_name, job_time, before_exec],
                cwd=str(ROOT),
                env={**os.environ, "BATCH_WAIT_ARG3": "before"},
            )
            if wb.returncode != 0:
                print(f"  [FAIL] batch_completed: wait_batch_job exited {wb.returncode}", file=sys.stderr)
                _auto_on_failure(service, api, job_time)
                _telemetry(case_id, False, time.time() - t0)
                return 1, result
            print("  [PASS] batch_completed: COMPLETED")

            planned = _batch_planned(job_name, before_exec)
            if planned > 0:
                read_n, _ = _batch_counts(job_name, before_exec)
                ok = read_n > 0
                print(f"  [{'PASS' if ok else 'FAIL'}] batch_read_plan: "
                      f"planned={planned} read={read_n}",
                      file=sys.stdout if ok else sys.stderr)
                if not ok:
                    print("        the job counted candidates and then read none of them — "
                          "see GAP-095", file=sys.stderr)
                    _telemetry(case_id, False, time.time() - t0)
                    return 1, result

            if deferred_rules:
                dspec = {"assertions": deferred_rules, "on_fail_print_body": False}
                drun = run_assertions(result.body, result, dspec, env={**os.environ, **env})
                for ar in drun.results:
                    print(f"  [{'PASS' if ar.ok else 'FAIL'}] {ar.name}: {ar.detail}",
                          file=sys.stdout if ar.ok else sys.stderr)
                if not drun.passed:
                    _auto_on_failure(service, api, job_time)
                    _telemetry(case_id, False, time.time() - t0)
                    return 1, result
        elif case.get("wait_batch"):
            print("  [WARN] wait_batch skipped — set JOB_TIME default or env", file=sys.stderr)
            if deferred_rules:
                # Deferring an assert past a wait that never happens deletes it. The case would
                # go green having evaluated only the immediate rules, which is the failure the
                # deferral was introduced to prevent, one step further along.
                names = ", ".join(r["type"] for r in deferred_rules)
                print(f"  [FAIL] deferred_asserts_unevaluated: {names} — wait_batch was skipped, "
                      "so nothing checked what the job produced", file=sys.stderr)
                _telemetry(case_id, False, time.time() - t0)
                return 1, result

    if case.get("print"):
        obj = json.loads(result.body)
        for p in case["print"]:
            if path_exists(obj, p):
                print(f"  → {p} = {get_path(obj, p)}")

    if watch:
        log = service_log_path(service)
        for line in tail_new_lines(log, since_epoch=time.time() - 120):
            print(line)
        print(watch_hint(log))

    if not run.passed:
        print(result.body[:3000])
        _auto_on_failure(service, api, str(env.get("JOB_TIME", "")))
        print(analyze_failure(api, case.get("service", "accounting"), body=result.body, http_status=result.http_status))
        try:
            from cross_learn import record_test_result
            record_test_result(api=api, case_id=case_id, passed=False, service=service, body=result.body, http_status=result.http_status)
        except Exception:
            pass
        _trigger_intel_sync()
        _telemetry(case_id, False, time.time() - t0)
        return 1, result
    try:
        from cross_learn import record_test_result
        record_test_result(api=api, case_id=case_id, passed=True, service=service, http_status=result.http_status)
    except Exception:
        pass
    _trigger_intel_sync()
    print("✓ PASS")
    _telemetry(case_id, True, time.time() - t0)
    return 0, result


def _run_flow_case(case_id: str, case: dict) -> int:
    """Run a registry flow case. Fail-closed: non-zero child rc OR printed FAIL with rc=0.

    Applies ``defaults`` (same as API cases) then optional ``env`` overlays so pinned
    DCF fixtures (PARENT_LAN/…) actually reach the e2e script. Captures combined
    output so a printed ``FAIL:`` line cannot exit 0 (draft.ntest.dcf_e2e_fail_exit).
    """
    import re

    cmd = case["cmd"]
    env = os.environ.copy()
    # defaults first (os.environ wins when already set — empty string keeps unpinned)
    env.update(_resolve_defaults(case))
    env.update({k: str(v) for k, v in (case.get("env") or {}).items()})
    env.setdefault("FLOWTEST_CASE_ID", case_id)
    env.setdefault("NTEST_CASE_ID", case_id)
    print(f"=== {case_id} [flow] ===\n$ {cmd}", flush=True)
    t0 = time.time()
    proc = subprocess.run(
        cmd,
        shell=True,
        cwd=str(ROOT),
        env=env,
        text=True,
        capture_output=True,
    )
    # Live-echo for operators (preserve prior UX); keep combined text for FAIL scan.
    out = (proc.stdout or "") + (proc.stderr or "")
    if proc.stdout:
        sys.stdout.write(proc.stdout)
        sys.stdout.flush()
    if proc.stderr:
        sys.stderr.write(proc.stderr)
        sys.stderr.flush()
    rc = int(proc.returncode or 0)
    # Defense-in-depth: unrecovered printed FAIL must never report as PASS.
    # Prefer trailing === PASS: on stdout (stderr may flush FAIL lines later when
    # nested harness self-tests deliberately print FAIL then PASS).
    if rc == 0:
        stdout = proc.stdout or ""
        stderr = proc.stderr or ""
        combined = stdout + stderr
        tail_lines = [ln for ln in stdout.rstrip().splitlines() if ln.strip()]
        trailing_pass = bool(tail_lines) and tail_lines[-1].startswith("=== PASS:")
        has_fail = re.search(r"(?m)^FAIL:\s", combined) is not None
        if has_fail and not trailing_pass:
            print(
                f"=== {case_id} FAIL — child printed unrecovered FAIL: with exit 0; "
                f"forcing rc=1 (ntest.dcf_e2e_fail_exit)",
                file=sys.stderr,
            )
            rc = 1
    _telemetry(case_id, rc == 0, time.time() - t0)
    return rc


def cmd_run(args: argparse.Namespace) -> int:
    reg = _load_registry()
    case = reg.get(args.id)
    if not case:
        print(f"unknown case: {args.id}", file=sys.stderr)
        return 2
    q = case.get("quarantine")
    if q and not getattr(args, "include_quarantine", False):
        # quarantine may be bool true OR {label, reason} — both mean skip
        if isinstance(q, dict):
            label = q.get("label") or "QUARANTINE"
            reason = q.get("reason") or "quarantined in registry"
        else:
            label = "QUARANTINE"
            reason = "quarantined in registry (bool flag)"
        print(
            f"=== {args.id} SKIP [{label}] — {reason}\n"
            f"    (re-run with --include-quarantine to force)"
        )
        return 0
    if case.get("type") == "flow":
        return _run_flow_case(args.id, case)
    if case.get("type") == "health":
        return _run_health_case(args.id, case)
    rc, _ = _run_api_case(args.id, case, watch=args.watch_log, health=args.health)
    return rc


def _kg_sync() -> None:
    """Cache-first KG sync — skip full build when branch-set unchanged."""
    if KG_ENSURE.is_file():
        subprocess.run(["bash", str(KG_ENSURE), "--quiet"], cwd=str(ROOT), check=False)
    elif KG_SESSION.is_file():
        subprocess.run(["bash", str(KG_SESSION), "--quiet"], cwd=str(ROOT), check=False)


def cmd_auto(args: argparse.Namespace) -> int:
    """Autonomous: sync KG → resolve apiName → test → analyze on failure."""
    _kg_sync()
    reg = _load_registry()
    env = {**_correlators(), **_parse_vars(args.var)}

    rid = registry_match(reg, args.api)
    if rid:
        print(f"(registry hit: {rid})")
        svc = reg[rid].get("service", "accounting")
        if args.ensure and not args.no_ensure:
            r = _maybe_ensure_service(svc, True, args.compile)
            if r != 0:
                return r
        rc, res = _run_api_case(rid, reg[rid], watch=args.watch_log, health=args.health)
        if rc != 0 and res:
            print(analyze_failure(args.api, svc, body=res.body, http_status=res.http_status))
        return rc

    try:
        resolved = resolve_api(args.api, env)
    except LookupError as ex:
        print(ex, file=sys.stderr)
        print("Try: scripts/bin/kg-switch.sh && ntest orient", args.api, file=sys.stderr)
        return 2

    if args.ensure and not args.no_ensure:
        r = _maybe_ensure_service(resolved["service"], True, args.compile)
        if r != 0:
            return r

    print(f"## auto-resolve\n  repo: {resolved['repo']}\n  service: {resolved['service']}\n  src: {resolved['src']}")
    if resolved.get("template"):
        print(f"  template: {resolved['template']}")
    if resolved["is_batch"]:
        print("  mode: BATCH (job_time from JOB_TIME correlator)")

    case: dict[str, Any] = {
        "type": "batch" if resolved["is_batch"] or args.batch else "api",
        "service": resolved["service"],
        "api": args.api,
        "request": resolved["request"],
        "defaults": env,
        "expect": {"status": "SUCCESS"},
        "print": [],
    }
    if resolved["is_batch"] or args.batch:
        case["batch"] = True

    if args.orient:
        print(orient_api(args.api)[:2000])

    rc, res = _run_api_case(f"auto:{args.api}", case, watch=args.watch_log, health=args.health)
    if (rc != 0 or args.analyze) and res:
        print(analyze_failure(args.api, resolved["service"], body=res.body, http_status=res.http_status))
    return rc


def _tier_for_case(case_id: str) -> str | None:
    """Resolve tier from test_map.jsonl if built."""
    tm = ROOT / "cursor-bundle/flow-test/test_map.jsonl"
    if not tm.is_file():
        return None
    for line in tm.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if row.get("case_id") == case_id:
            return row.get("tier")
    return None


def cmd_smoke(args: argparse.Namespace) -> int:
    reg = _load_registry()
    if args.tier:
        api_cases = [
            (k, v) for k, v in reg.items()
            if v.get("type") in ("api", "batch", "flow", "health")
            and (
                v.get("smoke_tier") == args.tier
                or (_tier_for_case(k) or ("smoke" if v.get("quick") else "regression")) == args.tier
            )
        ]
    elif args.quick:
        api_cases = [(k, v) for k, v in reg.items()
                     if v.get("type") == "health" or v.get("quick")]
    else:
        api_cases = [(k, v) for k, v in reg.items() if v.get("type") in ("api", "batch")]
    if not api_cases:
        print("no cases for smoke" + (" --quick" if args.quick else ""))
        return 1
    rc = 0
    for cid, c in api_cases:
        if c.get("type") == "health":
            r = _run_health_case(cid, c)
        elif c.get("type") == "flow":
            r = _run_flow_case(cid, c)
        else:
            r, _ = _run_api_case(cid, c, watch=False, health=args.health)
        if r != 0:
            rc = 1
        print()
    return rc


def _run_health_case(case_id: str, case: dict) -> int:
    service = case["service"]
    if service not in SERVICES:
        print(f"=== {case_id} FAIL — unknown service {service}")
        return 1
    svc = SERVICES[service]
    probe_api = case.get("probe_api") or svc.get("probe_api")
    env = _correlators()
    if probe_api:
        req_tmpl = case.get("probe_request") if case.get("probe_request") is not None else svc.get("probe_request") or {}
        req = _subst_request(req_tmpl, env)
        stan = fresh_stan(f"health_{service}")
        if service == "actor" and "user_id" in req:
            env["user_id"] = str(req["user_id"])
        payload = build_envelope(service, req, stan=stan, vars=env)
        print(f"=== {case_id} [health] {service} — probe {probe_api} ===")
        result = fire_api(probe_api, payload, service=service)
        code, status = result.response_status()
        up = 200 <= result.http_status < 500
        print(f"  HTTP {result.http_status} ({result.elapsed_ms}ms)  {code}/{status}")
        if up:
            print("  OK (service reachable)")
            return 0
        print(f"  FAIL — body snippet: {result.body[:200]}")
        return 1
    ok, msg = health_check(service)
    print(f"=== {case_id} [health] {service} ===\n  {msg}")
    return 0 if ok else 1


def cmd_validate(args: argparse.Namespace) -> int:
    errs = validate_registry(REGISTRY)
    if errs:
        for e in errs:
            print(f"  - {e}", file=sys.stderr)
        return 1
    n = len(_load_registry())
    print(f"registry OK — {n} case(s)")
    return 0


def cmd_health(args: argparse.Namespace) -> int:
    rc = 0
    for svc in (args.service,) if args.service else SERVICES:
        r = _run_health_case(f"health.{svc}", {"service": svc, "type": "health"})
        if r != 0:
            rc = 1
    return rc


def cmd_ensure(args: argparse.Namespace) -> int:
    svc = args.service or "accounting"
    script = ROOT / "scripts" / "bin" / "novopay-service.sh"
    cmd = ["bash", str(script), "ensure", svc]
    if args.compile:
        cmd.append("--compile")
    return subprocess.call(cmd)


def _maybe_ensure_service(service: str, ensure: bool, compile_: bool) -> int:
    if not ensure:
        return 0
    return cmd_ensure(argparse.Namespace(service=service, compile=compile_))


def _parse_vars(items: list[str] | None) -> dict[str, str]:
    out: dict[str, str] = {}
    for item in items or []:
        if "=" in item:
            k, v = item.split("=", 1)
            out[k] = v
    return out


def cmd_api(args: argparse.Namespace) -> int:
    vars_ = _parse_vars(args.var)
    stan = fresh_stan(args.api)
    if args.file:
        payload = load_payload(args.file, stan, vars_)
    elif args.batch:
        payload = batch_envelope(args.api, args.job_time or os.environ.get("JOB_TIME"), stan)
    else:
        req = json.loads(args.request) if args.request else {}
        if args.service == "actor" and "user_id" in req:
            vars_["user_id"] = str(req["user_id"])
        payload = build_envelope(args.service, req, stan=stan, vars=vars_)
    if args.health:
        ok, msg = health_check(args.service)
        print(f"health: {msg}")
        if not ok:
            return 2
    result = fire_api(args.api, payload, service=args.service)
    print(f"HTTP {result.http_status}\n{result.body}")
    return 0 if 200 <= result.http_status < 300 else 1


def cmd_orient(args: argparse.Namespace) -> int:
    print(orient_api(args.api))
    return 0


def cmd_learn(args: argparse.Namespace) -> int:
    rec = append_learning(
        api=args.api,
        kind=args.kind,
        text=args.text,
        error_code=args.error_code or "",
        correlator=args.correlator or "",
        value=args.value or "",
        canned=args.canned or "",
    )
    try:
        from learning_bus import append_event
        append_event(
            "gotcha",
            source="ntest.learn",
            api=args.api,
            detail=args.text[:200],
            meta={"kind": args.kind, "error_code": args.error_code or ""},
        )
    except Exception:
        pass
    print(f"Appended → {LEARNINGS}")
    print(json.dumps(rec, indent=2))
    return 0


def cmd_learnings(args: argparse.Namespace) -> int:
    rows = load_learnings(args.api or "")
    if not rows:
        print("No learnings yet. Use: ntest learn --api ... --kind gotcha --text '...'")
        return 0
    for r in rows:
        print(f"- [{r.get('kind')}] {r.get('api')} — {r.get('text')}")
    print(f"\n{len(rows)} learning(s) in {LEARNINGS}")
    return 0


def cmd_logs(args: argparse.Namespace) -> int:
    svc = args.service or "accounting"
    mode = args.mode or "errors"
    script = ROOT / "scripts" / "bin" / "novopay-logs.sh"
    if not script.is_file():
        print(f"missing {script}", file=sys.stderr)
        return 1
    if mode == "tail":
        return subprocess.call(["bash", str(script), "tail", svc, str(args.lines)])
    return subprocess.call(["bash", str(script), mode, svc])


def cmd_diagnose(args: argparse.Namespace) -> int:
    svc = args.service or "accounting"
    print(run_log_snap(svc))
    return 0


def cmd_super(args: argparse.Namespace) -> int:
    cmd = [sys.executable, str(HERE / "super_agent.py"), args.super_cmd]
    if args.arg:
        cmd.append(args.arg)
    if args.money:
        cmd.append("--money")
    if args.kg:
        cmd.append("--kg")
    return subprocess.call(cmd, cwd=str(ROOT))


def cmd_map(args: argparse.Namespace) -> int:
    tmb = HERE / "test_map_builder.py"
    if args.api:
        return subprocess.call([sys.executable, str(tmb), "show", "--api", args.api], cwd=str(ROOT))
    if args.case:
        return subprocess.call([sys.executable, str(tmb), "show", "--case", args.case], cwd=str(ROOT))
    if args.gaps:
        c = [sys.executable, str(tmb), "gaps"]
        if args.money:
            c.append("--money")
        return subprocess.call(c, cwd=str(ROOT))
    c = [sys.executable, str(tmb), "stats"]
    if args.json:
        c.append("--json")
    return subprocess.call(c, cwd=str(ROOT))


def cmd_coverage(args: argparse.Namespace) -> int:
    return cmd_map(argparse.Namespace(stats=True, json=args.json, api=None, case=None, gaps=False, money=False))


def main() -> int:
    p = argparse.ArgumentParser(prog="ntest", description="Novopay local test runner")
    sub = p.add_subparsers(dest="cmd", required=True)

    ls = sub.add_parser("list", help="Registry cases")
    ls.add_argument("--api", action="store_true")
    ls.add_argument("--flow", action="store_true")
    ls.set_defaults(func=cmd_list)

    rn = sub.add_parser("run", help="Run registry case")
    rn.add_argument("id")
    rn.add_argument("--watch-log", action="store_true")
    rn.add_argument("--health", action="store_true")
    rn.add_argument(
        "--include-quarantine",
        action="store_true",
        help="Run cases marked quarantine in registry (default: skip with rc=0)",
    )
    rn.set_defaults(func=cmd_run)

    sm = sub.add_parser("smoke", help="Registry API cases (or --quick / --tier)")
    sm.add_argument("--health", action="store_true")
    sm.add_argument("--quick", action="store_true", help="health.* + cases with quick:true only")
    sm.add_argument("--tier", choices=["local", "smoke", "regression", "full", "money"], help="Filter by test_map or registry smoke_tier")
    sm.set_defaults(func=cmd_smoke)

    va = sub.add_parser("validate", help="Validate registry.json schema + correlators")
    va.set_defaults(func=cmd_validate)

    hl = sub.add_parser("health", help="Actuator health for service(s)")
    hl.add_argument("service", nargs="?", choices=list(SERVICES))
    hl.set_defaults(func=cmd_health)

    en = sub.add_parser("ensure", help="Restart service if API probe fails (novopay-service.sh)")
    en.add_argument("service", nargs="?", default="accounting", choices=list(SERVICES))
    en.add_argument("--compile", action="store_true", help="Run compileJava before bootRun")
    en.set_defaults(func=cmd_ensure)

    ap = sub.add_parser("api", help="Ad-hoc API (no registry)")
    ap.add_argument("service", choices=list(SERVICES))
    ap.add_argument("api")
    ap.add_argument("-f", "--file")
    ap.add_argument("--batch", action="store_true")
    ap.add_argument("--job-time")
    ap.add_argument("--request", help="JSON request body")
    ap.add_argument("--var", action="append", metavar="K=V", help="Request/header vars")
    ap.add_argument("--health", action="store_true")
    ap.set_defaults(func=cmd_api)

    pr = sub.add_parser("probe", help="Fire API, print body (alias: api without extras)")
    pr.add_argument("service", choices=list(SERVICES))
    pr.add_argument("api")
    pr.add_argument("-f", "--file")
    pr.add_argument("--batch", action="store_true")
    pr.set_defaults(func=cmd_api)

    o = sub.add_parser("orient", help="KG flow/crud/cases for an apiName")
    o.add_argument("api")
    o.set_defaults(func=cmd_orient)

    au = sub.add_parser("auto", help="Autonomous test by apiName (KG resolve + fire + assert)")
    au.add_argument("api")
    au.add_argument("--var", action="append", metavar="K=V")
    au.add_argument("--batch", action="store_true", help="Force BATCH envelope")
    au.add_argument("--watch-log", action="store_true")
    au.add_argument("--health", action="store_true", help="Pre-check actuator (optional)")
    au.add_argument("--ensure", action="store_true", help="Force restart service before fire")
    au.add_argument("--no-ensure", action="store_true", help="Skip agent-ops before-test (NTEST_NO_ENSURE=1)")
    au.add_argument("--compile", action="store_true", help="Force compileJava on ensure")
    au.add_argument("--orient", action="store_true", help="Print KG orient before fire")
    au.add_argument("--analyze", action="store_true", help="Print analysis hints even on success")
    au.set_defaults(func=cmd_auto)

    lr = sub.add_parser("learn", help="Append test learning to brain/testing/learnings.jsonl")
    lr.add_argument("--api", default="*")
    lr.add_argument("--kind", required=True)
    lr.add_argument("--text", required=True)
    lr.add_argument("--error-code")
    lr.add_argument("--key", dest="correlator")
    lr.add_argument("--value")
    lr.add_argument("--canned")
    lr.set_defaults(func=cmd_learn)

    lrs = sub.add_parser("learnings", help="List test learnings")
    lrs.add_argument("--api", default="")
    lrs.set_defaults(func=cmd_learnings)

    lg = sub.add_parser("logs", help="Service logs (paths|errors|boot|snap|tail)")
    lg.add_argument("service", nargs="?", default="accounting", choices=list(SERVICES))
    lg.add_argument("mode", nargs="?", default="errors", choices=["paths", "errors", "boot", "snap", "tail", "guide"])
    lg.add_argument("--lines", type=int, default=40)
    lg.set_defaults(func=cmd_logs)

    dg = sub.add_parser("diagnose", help="RCA snap when service/batch seems stuck")
    dg.add_argument("service", nargs="?", default="accounting", choices=list(SERVICES))
    dg.set_defaults(func=cmd_diagnose)

    mp = sub.add_parser("map", help="Test map — registry ↔ FTG ↔ footprint")
    mp.add_argument("--api")
    mp.add_argument("--case")
    mp.add_argument("--stats", action="store_true")
    mp.add_argument("--gaps", action="store_true")
    mp.add_argument("--money", action="store_true")
    mp.add_argument("--json", action="store_true")
    mp.set_defaults(func=cmd_map)

    cv = sub.add_parser("coverage", help="Test coverage matrix stats")
    cv.add_argument("--json", action="store_true")
    cv.set_defaults(func=cmd_coverage)

    sa = sub.add_parser("super", help="Super agent unified orient/sync/gaps")
    sa.add_argument("super_cmd", choices=["orient", "sync", "gaps", "session"])
    sa.add_argument("arg", nargs="?", default="")
    sa.add_argument("--money", action="store_true")
    sa.add_argument("--kg", action="store_true")
    sa.set_defaults(func=cmd_super)

    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
