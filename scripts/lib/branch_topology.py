"""
Small helper used by ship-loop tooling to print a branch-mix warning.

The full implementation may live in other workspace variants; in this repo we keep
the interface stable so automation does not break.
"""

from __future__ import annotations


def active_branch_mix_note() -> str:
    """
    Return a short human-readable note when the workspace has mixed branches.

    This minimal implementation is intentionally conservative and returns empty,
    keeping the ship loop functional without enforcing branch topology checks.
    """

    return ""

