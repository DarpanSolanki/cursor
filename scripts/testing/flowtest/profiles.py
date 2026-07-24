"""Fixture profiles — table-sets for snapshot/restore."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FixtureProfile:
    """Per-flow snapshot scope. schema_prefix must stay stable for existing bak schemas."""

    name: str
    schema_prefix: str  # e.g. dcf_bak → schema dcf_bak_<parent_lan>
    scoped_by_loan_account_id: tuple[str, ...] = ()
    scoped_by_account_id: tuple[str, ...] = ()
    scoped_by_account_number: tuple[str, ...] = ()
    # When True, purge test BILLING CRNs matching accountId||digits (DFC force-bill pattern).
    purge_numeric_billing_crn: bool = False
    notes: str = ""


# Profile #1 — DFC group parent last-child (existing bak schemas: dcf_bak_<lan>)
DCF_GROUP = FixtureProfile(
    name="dcf_group",
    schema_prefix="dcf_bak",
    scoped_by_loan_account_id=(
        "loan_due_details",
        "loan_installment_details",
        "loan_account_insurance_details",
        "loan_account_closure_details",
        "death_foreclosure_details",
        "waiver_details",
        "prepayment_details",
        "loan_account_part_prepayment_details",
        "penal_interest_accrual_details",  # F3 date-roll / penal dirt
    ),
    scoped_by_account_id=(
        "loan_account_billing_details",
        "interest_accrual_details",
    ),
    scoped_by_account_number=(
        "transaction_details",
        "transaction_partition_details",
        "death_foreclosure_insurance_staging_details",
    ),
    purge_numeric_billing_crn=True,
    notes="SHG/JLG group DFC; restore undoes labd/IAD/penal dirt + account.status",
)

# RSTCRE pilot reuses the same group fixture / bak schema (restore-reuse, no re-disburse).
RSTCRE_SPINE = FixtureProfile(
    name="rstcre_spine",
    schema_prefix="dcf_bak",
    scoped_by_loan_account_id=DCF_GROUP.scoped_by_loan_account_id,
    scoped_by_account_id=DCF_GROUP.scoped_by_account_id,
    scoped_by_account_number=DCF_GROUP.scoped_by_account_number,
    purge_numeric_billing_crn=True,
    notes="Reuses dcf_bak_* snapshot; drills childLoanEventProcessingBatchJob RSTCRE drain",
)

PROFILES: dict[str, FixtureProfile] = {
    DCF_GROUP.name: DCF_GROUP,
    RSTCRE_SPINE.name: RSTCRE_SPINE,
}

# Profile #3 — individual DPI demo LAN (6004044425). Snapshot optional;
# current F2 scenarios use dpi_restore_api_state (lift) instead of bak restore.
DPI_INDIVIDUAL = FixtureProfile(
    name="dpi_individual",
    schema_prefix="ft_dpi_bak",
    scoped_by_loan_account_id=(
        "loan_due_details",
        "loan_installment_details",
        "waiver_details",
        "prepayment_details",
        "loan_account_part_prepayment_details",
        "loan_account_closure_details",
    ),
    scoped_by_account_id=(
        "loan_account_billing_details",
        "interest_accrual_details",
    ),
    scoped_by_account_number=(
        "transaction_details",
        "transaction_partition_details",
    ),
    purge_numeric_billing_crn=False,
    notes="Individual DPI fixture LAN; prefer dpi_restore_api_state for F2 speed",
)
PROFILES[DPI_INDIVIDUAL.name] = DPI_INDIVIDUAL
