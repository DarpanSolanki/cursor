#!/usr/bin/env python3
"""
Fire any accounting API locally — quick RCA loop: POST → print response → optional log hints.

Examples:
  api-fire.py disburseLoan -f ../dpic/payload/disburse_mft_6367.json
  api-fire.py dpiAccrualBooking --batch --job-time 1781267400000
  api-fire.py loanAccountDpdCalcJob --batch
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Allow `python3 scripts/testing/api-fire.py` without package install
sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib.api_client import batch_envelope, fire_api, fresh_stan, health_check, load_payload
from lib.logs import accounting_log_path, tail_new_lines, watch_hint


def main() -> int:
    p = argparse.ArgumentParser(description="POST to accounting /api/v1/<apiName>")
    p.add_argument("api_name", help="Orchestration apiName (e.g. disburseLoan, dpiAccrualBooking)")
    p.add_argument("-f", "--file", help="Full JSON envelope (headers + request)")
    p.add_argument("--batch", action="store_true", help="Use standard BATCH job envelope")
    p.add_argument("--job-time", default=None, help="job_time for --batch (default: env JOB_TIME or now ms)")
    p.add_argument("--stan", default=None, help="Override stan / {{$timestamp}} substitution")
    p.add_argument("--timeout", type=float, default=60.0)
    p.add_argument("--health", action="store_true", help="Check actuator/health before call")
    p.add_argument("--watch-log", action="store_true", help="Print recent error lines from accounting log")
    p.add_argument("--json-out", metavar="PATH", help="Write response body to file")
    args = p.parse_args()

    if args.health:
        ok, msg = health_check()
        print(f"health: {'OK' if ok else 'FAIL'} ({msg})")
        if not ok:
            return 2

    import os
    import time

    job_time = args.job_time or os.environ.get("JOB_TIME") or str(int(time.time() * 1000))
    stan = args.stan or fresh_stan(args.api_name)

    if args.file:
        payload = load_payload(args.file, stan)
    elif args.batch:
        payload = batch_envelope(args.api_name, job_time=job_time, stan=stan)
    else:
        print("Provide -f <payload.json> or --batch", file=sys.stderr)
        return 2

    print(f"POST {args.api_name} stan={stan}")
    result = fire_api(args.api_name, payload, timeout_s=args.timeout)
    code, status = result.response_status()
    print(f"HTTP {result.http_status}  ({result.elapsed_ms}ms)  response_status: {code} / {status}")
    print(result.body)
    if args.json_out:
        Path(args.json_out).write_text(result.body, encoding="utf-8")
        print(f"→ wrote {args.json_out}")

    if args.watch_log:
        log = accounting_log_path()
        print(f"\n--- recent errors in {log} ---")
        for line in tail_new_lines(log, since_epoch=time.time() - 120):
            print(line)
        print(f"\nLive: {watch_hint(log)}")

    if result.http_status < 200 or result.http_status >= 300:
        return 1
    if status and status.upper() not in ("", "SUCCESS", "DTFC_SUCCESS", "NEFT_STAGE_1_PENDING", "NEFT_STAGE_2_PENDING", "LOAN_BOOKED", "LRS_GENERATED"):
        if code not in ("000", "0", "MFI-40000", "B0", "B1", ""):
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
