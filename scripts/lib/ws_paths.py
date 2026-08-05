#!/usr/bin/env python3
"""Workspace path normalisation.

`str.lstrip("./")` strips a CHARACTER SET, not a prefix — it turns
`.cursor/rules/x.md` into `claude/rules/x.md`. Use `norm_rel` instead.
"""
from __future__ import annotations


def norm_rel(rel: str) -> str:
    """Workspace-relative form: forward slashes, no leading `./`."""
    out = (rel or "").replace("\\", "/")
    while out.startswith("./"):
        out = out[2:]
    return out
