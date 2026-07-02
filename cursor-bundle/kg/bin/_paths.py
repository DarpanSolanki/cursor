"""Resolve sliProd + cursor-bundle paths (no hardcoded /home/darpan/darpan)."""
from pathlib import Path

BIN = Path(__file__).resolve().parent
BUNDLE = BIN.parent.parent
WORKSPACE = BUNDLE.parent
BRAIN = BUNDLE / "brain"
CURATED = BUNDLE / "kg" / "curated"
CHANGELOG = BRAIN / "changelog" / "CHANGELOG.md"
KG_DATA = BUNDLE / "kg" / "data"
