"""Post-test analysis hints — KG why, crud, logs, canned SQL, prior learnings."""
from __future__ import annotations

from .kg_orient import kg_query
from .logs import boot_log_path, run_log_snap, service_log_path, tail_errors, watch_hint
from .paths import ROOT
from .test_learnings import format_learnings_block

# api field patterns → canned script (scripts/db/canned)
CANNED_BY_CONTEXT = {
    "loan_account": "01-loan-status-by-lan",
    "loan_due_details": "01-loan-status-by-lan",
    "dpi_accrual": "11-accruals-by-lan",
    "batch_failure": "17-batch-failures-recent",
    "client_request_response": "07-crr-by-lan",
}


def analyze_failure(api_name: str, service: str, *, body: str, http_status: int) -> str:
    lines = [
        f"\n## Analysis hints for {api_name}",
        f"- App log: `{service_log_path(service)}`",
        f"- Boot log: `{boot_log_path(service)}`",
        f"- Snap: `bash scripts/bin/novopay-logs.sh snap {service}`",
        f"- Live:\n{watch_hint(service=service)}",
    ]
    why = kg_query("why", api_name)
    if why and "not found" not in why.lower():
        lines.append(f"\n### kg why (silent surfaces)\n```\n{why[:2500]}\n```")
    crud = kg_query("crud", api_name)
    if crud:
        lines.append(f"\n### DB tables touched\n```\n{crud[:1500]}\n```")
        for key, canned in CANNED_BY_CONTEXT.items():
            if key in crud.lower():
                lines.append(f"- Canned SQL: `scripts/db-local.sh --canned {canned} --param account_number=$ACCOUNT_NUMBER`")
    if "batch" in api_name.lower() or api_name.endswith("Job"):
        lines.append("- Batch blockers: `scripts/db-local.sh --canned 17-batch-failures-recent`")
        lines.append("- Audit table: `mfi_accounting.batch_failure_audit`")
    if http_status >= 400 or "FAIL" in body.upper():
        lines.append(f"\n### Response excerpt\n```\n{body[:1200]}\n```")
        errs = tail_errors(service=service, max_lines=8)
        if errs and not errs[0].startswith("(no error"):
            lines.append("\n### Recent log errors\n```")
            lines.extend(errs)
            lines.append("```")
    block = format_learnings_block(api_name, body)
    if block:
        lines.append(block)
    # Test map / FTG linkage (proof-backed)
    try:
        import json as _json
        cov_path = ROOT / "cursor-bundle/flow-test/test_coverage.jsonl"
        if cov_path.is_file():
            for line in cov_path.read_text(encoding="utf-8").splitlines():
                if not line.strip() or line.startswith("#"):
                    continue
                row = _json.loads(line)
                if row.get("api") == api_name:
                    lines.append("\n### Test map (test_coverage.jsonl)")
                    lines.append(f"- FTG: `{', '.join(row.get('ftg_ids') or [])}`")
                    lines.append(f"- ntest: `{', '.join(row.get('ntest_cases') or [])}`")
                    lines.append(f"- footprint: **{row.get('footprint_best')}**  gaps: {row.get('gaps') or []}")
                    if row.get("gaps"):
                        lines.append(f"- Run: `ntest map --api {api_name}` · `ftg show {row['ftg_ids'][0]}`" if row.get("ftg_ids") else "")
                    break
    except Exception:
        pass
    return "\n".join(lines)
