#!/usr/bin/env python3
"""Unit tests for project-aware JIRA comment validation (SDCP ping vs TDPQA handoff)."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ADF_PATH = ROOT / "scripts" / "bin" / "jira-fix-adf.py"


def _load_adf():
    spec = importlib.util.spec_from_file_location("jira_fix_adf", ADF_PATH)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _base_aitdp() -> dict:
    return {
        "aitdp_percent": 0.75,
        "aitdp_remarks": (
            "AI helped isolate the overdue-date gate and draft the handoff. "
            "Human verified amounts on a fresh loan and edited the ticket."
        ),
    }


def test_project_mode() -> None:
    adf = _load_adf()
    assert adf.project_mode("SDCP-1")["mode"] == "field_handoff"
    assert adf.project_mode("TDPQA-83")["mode"] == "comment_handoff"


def test_sdcp_ping_ok_and_omit() -> None:
    adf = _load_adf()
    adf.validate_mode_comment("field_handoff", {})
    adf.validate_mode_comment(
        "field_handoff",
        {"ping_comment": "@Reema Fix is ready for QA retest on a fresh loan."},
    )


def test_sdcp_ping_rejects_structured_headers() -> None:
    adf = _load_adf()
    try:
        adf.validate_mode_comment(
            "field_handoff",
            {"ping_comment": "RCA\nSomething broke.\nImpact\nEverything."},
        )
    except ValueError as e:
        assert "section headers" in str(e)
    else:
        raise AssertionError("expected ValueError for SDCP structured ping")


def test_sdcp_ping_rejects_long() -> None:
    adf = _load_adf()
    ping = "Ready. " * 80
    try:
        adf.validate_mode_comment("field_handoff", {"ping_comment": ping})
    except ValueError as e:
        assert "SDCP ping" in str(e)
    else:
        raise AssertionError("expected ValueError for long SDCP ping")


def test_tdpqa_requires_structured_handoff() -> None:
    adf = _load_adf()
    try:
        adf.validate_mode_comment(
            "comment_handoff",
            {"ping_comment": "@Reema ready for QA.", **_base_aitdp()},
        )
    except ValueError as e:
        assert "structured handoff" in str(e)
    else:
        raise AssertionError("expected ValueError for TDPQA ping-only")


def test_tdpqa_pack_ok_with_comment_id() -> None:
    adf = _load_adf()
    payload = {
        "lead_in": "@Reema @Srikant Fix is ready for QA retest.",
        "rca": {
            "situation": "Foreclosure DPI amount was incomplete.",
            "cause": "Projection skipped the business-day accrual slice.",
            "resolution": "Include business day in broken-period projection.",
        },
        "impact": ["Foreclosure DPI display for loans past business date."],
        "dev": ["Fresh loan foreclosure sim. Result: Pass."],
        "comment_id": "388469",
        **_base_aitdp(),
    }
    pack = adf.build_handoff_pack("TDPQA-83", payload)
    assert pack["mode"] == "comment_handoff"
    assert pack["comment_id"] == "388469"
    assert pack["prefer_edit_in_place"] is True
    assert pack["mcp_hint"]["addCommentToJiraIssue"] is None
    assert pack["mcp_hint"]["editComment"]["commentId"] == "388469"


if __name__ == "__main__":
    test_project_mode()
    test_sdcp_ping_ok_and_omit()
    test_sdcp_ping_rejects_structured_headers()
    test_sdcp_ping_rejects_long()
    test_tdpqa_requires_structured_handoff()
    test_tdpqa_pack_ok_with_comment_id()
    print("test_jira_fix_adf: OK")
