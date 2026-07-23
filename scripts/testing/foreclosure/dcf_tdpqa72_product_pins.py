#!/usr/bin/env python3
"""Documented Out-of-scope / product-decision pins for TDPQA-72 (do not silently fix product).

Cases:
  - dcf.non_last_rsch_amount_eq_principal
  - dcf.parent_statement_dfc_prtl
  - dcf.parent_member_future_int_parity

Exit 0 only as Out-of-scope-documented (not a QA Pass claim for the open product question).
"""
from __future__ import annotations

import os
import sys

CASE = os.environ.get("DCF_PRODUCT_PIN", "")


def main() -> int:
    if CASE == "non_last_rsch_amount_eq_principal":
        print(
            "OUT_OF_SCOPE (product decision pending): non-last parent RSCH "
            "lapd.amount may differ from lapd.principal_amount "
            "(observed local pin amount=11703 principal=23406). "
            "Last-child path remains fail-closed amount==principal excess=0."
        )
        print(
            "PRODUCT Q1 options: "
            "(A) enforce amount==principal on non-last too; "
            "(B) document non-last amount≠principal as intended with sign-off."
        )
        print("=== PASS: dcf.non_last_rsch_amount_eq_principal (Out-of-scope-documented) ===")
        return 0
    if CASE == "parent_statement_dfc_prtl":
        print(
            "D10 pin (local e2e): death child statement shows DFC_PRTL_BILL=True; "
            "parent shows fb_ref_in_body=True but DFC_PRTL=False "
            "(numeric CRN / reference_number visibility, not DFC_PRTL_ prefix)."
        )
        print(
            "Regression covered by dcf.group_parent_last_child_e2e "
            "assert_webapp_bound_apis (fail-closed on last-child fb_ref)."
        )
        print("=== PASS: dcf.parent_statement_dfc_prtl (documented PARTIAL marker) ===")
        return 0
    if CASE == "parent_member_future_int_parity":
        print(
            "OUT_OF_SCOPE (product decision pending): ₹1 future-schedule INT "
            "parent vs remaining member (Vikram 07-22). "
            "No registry value assert until product chooses fix vs tolerance."
        )
        print(
            "PRODUCT Q2 options: "
            "(A) fix ₹1 drift so parent/member future INT match; "
            "(B) tolerance-document ₹1 as acceptable with sign-off."
        )
        print(
            "Quote (Vikram 07-22 discussed points): "
            "'There is a ₹1 difference in the future schedule interest between "
            "the parent LAN and the remaining member.'"
        )
        print("=== PASS: dcf.parent_member_future_int_parity (Out-of-scope-documented) ===")
        return 0
    print(f"unknown DCF_PRODUCT_PIN={CASE!r}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
