#!/usr/bin/env python3
"""PROCESSOR_MIRROR_SIM — ntest flow FAIL-exit + defaults pin (TDPQA-72 draft.ntest.dcf_e2e_fail_exit).

Proves:
  1) registry ``defaults`` are applied into the child env (PARENT_LAN pin reaches e2e)
  2) a child that prints ``FAIL:`` but exits 0 is forced to rc=1
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "testing"))

import ntest  # noqa: E402


def _run_fake_flow(script: str, defaults: dict | None = None) -> int:
    with tempfile.NamedTemporaryFile("w", suffix=".sh", delete=False) as fh:
        fh.write(script)
        path = fh.name
    os.chmod(path, 0o755)
    try:
        case = {
            "type": "flow",
            "cmd": f"bash {path}",
            "defaults": defaults or {},
        }
        return ntest._run_flow_case("ntest.dcf_e2e_fail_exit.sim", case)
    finally:
        os.unlink(path)


def main() -> int:
    # (1) defaults applied
    script = r"""#!/usr/bin/env bash
set -euo pipefail
if [[ "${PARENT_LAN:-}" != "6000137433" ]]; then
  echo "FAIL: PARENT_LAN not applied from defaults (got='${PARENT_LAN:-}')" >&2
  exit 1
fi
echo "defaults_pin PASS PARENT_LAN=$PARENT_LAN"
exit 0
"""
    rc = _run_fake_flow(script, {"PARENT_LAN": "6000137433"})
    if rc != 0:
        print(f"FAIL: defaults pin expected rc=0 got {rc}", file=sys.stderr)
        return 1

    # (2) printed FAIL + exit 0 → forced non-zero
    script = r"""#!/usr/bin/env bash
echo "FAIL: synthetic harness lie (exit 0)" >&2
exit 0
"""
    rc = _run_fake_flow(script, {})
    if rc == 0:
        print("FAIL: printed FAIL with exit 0 was not coerced", file=sys.stderr)
        return 1
    print(f"fail_exit PASS: printed FAIL forced rc={rc}")

    # (3) clean PASS still exits 0
    script = r"""#!/usr/bin/env bash
echo "=== PASS: clean ==="
exit 0
"""
    rc = _run_fake_flow(script, {})
    if rc != 0:
        print(f"FAIL: clean PASS expected rc=0 got {rc}", file=sys.stderr)
        return 1
    print("clean_pass PASS: rc=0")
    print("=== PASS: ntest.dcf_e2e_fail_exit sim ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
