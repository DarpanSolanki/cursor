"""sliProd workspace paths for local testing."""
from __future__ import annotations

from pathlib import Path


def workspace_root() -> Path:
    for ancestor in Path(__file__).resolve().parents:
        if (ancestor / "novopay-platform-accounting-v2").is_dir():
            return ancestor
    return Path(__file__).resolve().parents[3]


ROOT = workspace_root()
TESTING_DIR = ROOT / "scripts" / "testing"
USECASES_FILE = TESTING_DIR / "usecases.json"
DISBURSEMENT_DIR = ROOT / "scripts" / "disbursement"
DPIC_DIR = ROOT / "scripts" / "dpic"
