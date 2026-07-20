#!/usr/bin/env python3
"""
Parse a disburseLoan request JSON, derive parameters for local disbursement replay reset,
persist a "reset recipe", and execute the Yugabyte/PostgreSQL reset SQL.

Input: JSON is read from stdin by default (or via --file).
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path


def _workspace_root() -> Path:
    for ancestor in Path(__file__).resolve().parents:
        if (ancestor / "trustt-platform-accounting").is_dir():
            return ancestor
    return Path(__file__).resolve().parents[3]


@dataclass(frozen=True)
class ResetRecipe:
    ext_ref: str
    member_ext_refs: str
    lan: str
    group_id: str
    product_id: str
    customer_id: str
    repayment_account_number: str
    repayment_account_type: str
    repayment_account_holder_name: str
    repayment_account_ifsc: str
    repayment_account_bank_name: str
    target_disb_status: str

    @staticmethod
    def from_request(request: dict, target_disb_status: str) -> "ResetRecipe":
        disbursement_details = request.get("disbursement_details") or {}
        group_details = request.get("group_details") or {}
        member_details = request.get("member_details")
        loan_details = request.get("loan_details") or {}

        ext_ref = str(disbursement_details.get("external_ref_number") or "").strip()
        if not ext_ref:
            raise ValueError("Missing disbursement_details.external_ref_number")

        # member_details is expected as array of members, but can also be null.
        member_ext_refs = ""
        if member_details:
            if not isinstance(member_details, list):
                raise ValueError("member_details must be a list or null")
            ext_refs: list[str] = []
            for m in member_details:
                if not isinstance(m, dict):
                    continue
                v = (m.get("external_ref_number") or "").strip()
                if v:
                    ext_refs.append(v)
            member_ext_refs = ",".join(ext_refs)

        lan = str(loan_details.get("account_number") or "").strip()
        group_id = str(group_details.get("group_id") or "").strip()
        product_id = str(loan_details.get("product_id") or "").strip()
        customer_id = str(loan_details.get("customer_id") or "").strip()
        repayment_mode = str((request.get("repayment_details") or {}).get("repayment_mode") or "").strip()
        repayment_account: dict = {}
        for account in request.get("disbursement_repayment_account_details") or []:
            if not isinstance(account, dict):
                continue
            purposes = account.get("purpose") or []
            if any(
                isinstance(purpose, dict)
                and str(purpose.get("code") or purpose.get("purpose_code") or "").strip() == "REP_ACCT"
                for purpose in purposes
            ):
                repayment_account = account
                break

        account_number_key = "external_account_number" if repayment_mode == "ACH" else "account_number"
        account_type_key = "external_account_type" if repayment_mode == "ACH" else "product_type"
        repayment_account_number = str(repayment_account.get(account_number_key) or "").strip()
        repayment_account_type = str(repayment_account.get(account_type_key) or "SAVINGS").strip()
        repayment_account_holder_name = str(
            repayment_account.get("account_holder_name") or "LOCAL DISBURSEMENT FIXTURE"
        ).strip()
        repayment_account_ifsc = str(repayment_account.get("routing_value") or "").strip()
        repayment_account_bank_name = str(repayment_account.get("bank_name") or "HDFC_BANK").strip()

        return ResetRecipe(
            ext_ref=ext_ref,
            member_ext_refs=member_ext_refs,
            lan=lan,
            group_id=group_id,
            product_id=product_id,
            customer_id=customer_id,
            repayment_account_number=repayment_account_number,
            repayment_account_type=repayment_account_type,
            repayment_account_holder_name=repayment_account_holder_name,
            repayment_account_ifsc=repayment_account_ifsc,
            repayment_account_bank_name=repayment_account_bank_name,
            target_disb_status=target_disb_status,
        )


def read_json(path: str | None) -> dict:
    if path:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    return json.loads(sys.stdin.read())


def persist_recipe(recipe: ResetRecipe, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).isoformat()
    payload = asdict(recipe) | {"saved_at_utc": ts}
    out_path = out_dir / f"{recipe.ext_ref}.json"
    out_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return out_path


def run_reset(recipe: ResetRecipe, sql_path: Path) -> None:
    # Yugabyte connection settings are hardcoded to match existing local reset usage.
    # If your env differs, pass overrides later (out of scope for now).
    base_cmd = [
        "psql",
        "-h",
        "localhost",
        "-p",
        "5433",
        "-U",
        "yugabyte",
        "-d",
        "yugabyte",
        "-v",
        "ON_ERROR_STOP=1",
        "-f",
        str(sql_path),
    ]

    cmd = base_cmd + [
        "-v",
        f"ext_ref={recipe.ext_ref}",
        "-v",
        f"member_ext_refs={recipe.member_ext_refs}",
        "-v",
        f"lan={recipe.lan}",
        "-v",
        f"group_id={recipe.group_id}",
        "-v",
        f"product_id={recipe.product_id}",
        "-v",
        f"customer_id={recipe.customer_id}",
        "-v",
        f"repayment_account_number={recipe.repayment_account_number}",
        "-v",
        f"repayment_account_type={recipe.repayment_account_type}",
        "-v",
        f"repayment_account_holder_name={recipe.repayment_account_holder_name}",
        "-v",
        f"repayment_account_ifsc={recipe.repayment_account_ifsc}",
        "-v",
        f"repayment_account_bank_name={recipe.repayment_account_bank_name}",
        "-v",
        f"target_disb_status={recipe.target_disb_status}",
    ]

    env = os.environ.copy()
    # Prevent indefinite hangs if some other process holds locks locally.
    env.setdefault("PGOPTIONS", "-c lock_timeout=5s -c statement_timeout=60s")
    subprocess.run(cmd, check=True, env=env)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", help="Path to disburseLoan request JSON. If omitted, reads stdin.")
    parser.add_argument(
        "--target-disb-status",
        default="DTFC_SUCCESS",
        help="Value for loan_account.disbursement_status after reset.",
    )
    parser.add_argument(
        "--recipes-dir",
        default="",
        help="Where to persist derived reset recipes (default: <workspace>/docs/disbursement-reset-recipes).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only derive and persist the recipe; do not execute SQL reset.",
    )
    args = parser.parse_args()

    root = _workspace_root()
    sql_path = root / "scripts" / "sql" / "reset" / "local_reset_disburse_loan_replay_mfi_yugabyte.sql"
    recipes_dir = Path(args.recipes_dir) if args.recipes_dir else root / "docs" / "disbursement-reset-recipes"

    raw = read_json(args.file)
    request = raw.get("request") if isinstance(raw, dict) else None
    if not isinstance(request, dict):
        raise ValueError("Input JSON must contain a top-level 'request' object")

    recipe = ResetRecipe.from_request(request, target_disb_status=args.target_disb_status)
    saved_path = persist_recipe(recipe, recipes_dir)

    print(f"[reset-recipe] saved: {saved_path}")
    print(
        "[reset-recipe] derived:",
        f"ext_ref={recipe.ext_ref}",
        f"member_ext_refs={recipe.member_ext_refs}",
        f"lan={recipe.lan}",
        f"group_id={recipe.group_id}",
    )

    if args.dry_run:
        print("[reset-recipe] dry-run: SQL reset not executed")
        return 0

    run_reset(recipe, sql_path=sql_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

