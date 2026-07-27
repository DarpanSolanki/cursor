#!/usr/bin/env bash
# Canonical ntest entry (SU-STITCH-001): always prefer scripts/bin/ntest.sh over
# calling scripts/testing/ntest.py directly. Thin wrapper — no logic duplication.
exec python3 "$(cd "$(dirname "$0")/.." && pwd)/testing/ntest.py" "$@"
