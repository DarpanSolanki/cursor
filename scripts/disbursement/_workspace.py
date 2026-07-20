"""Resolve sliProd workspace + disbursement paths for runners."""
from __future__ import annotations

from pathlib import Path


def workspace_root() -> Path:
    for ancestor in Path(__file__).resolve().parents:
        if (ancestor / "trustt-platform-accounting").is_dir():
            return ancestor
    return Path(__file__).resolve().parents[2]


ROOT = workspace_root()
DISBURSEMENT_DIR = ROOT / "scripts" / "disbursement"
PAYLOADS_DIR = DISBURSEMENT_DIR / "payloads" / "canonical"
SANITY_SCRIPT = ROOT / "scripts" / "disburse_loan_sanity.py"
