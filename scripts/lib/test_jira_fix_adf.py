#!/usr/bin/env python3
"""Unit tests for project-aware JIRA comment validation (SDCP / TDPQA field vs comment)."""
from __future__ import annotations

import importlib.util
import json
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
    assert adf.project_mode("TDPQA-83")["mode"] == "tdpqa_field_handoff"
    assert adf.project_mode("HSQA-1")["mode"] == "comment_handoff"


def test_sdcp_ping_ok_and_omit() -> None:
    adf = _load_adf()
    adf.validate_mode_comment("field_handoff", {})
    adf.validate_mode_comment(
        "field_handoff",
        {"ping_comment": "@Reema Fix is ready for QA retest on a fresh loan."},
    )


def test_tdpqa_field_ping_ok_and_omit() -> None:
    adf = _load_adf()
    adf.validate_mode_comment("tdpqa_field_handoff", {})
    adf.validate_mode_comment(
        "tdpqa_field_handoff",
        {"ping_comment": "@Srikant Fix is ready for QA. Fields are filled."},
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
        assert "SDCP ping" in str(e) or "ping" in str(e).lower()
    else:
        raise AssertionError("expected ValueError for long SDCP ping")


def test_comment_handoff_requires_structured() -> None:
    adf = _load_adf()
    try:
        adf.validate_mode_comment(
            "comment_handoff",
            {"ping_comment": "@Reema ready for QA.", **_base_aitdp()},
        )
    except ValueError as e:
        assert "structured handoff" in str(e)
    else:
        raise AssertionError("expected ValueError for comment_handoff ping-only")


def test_tdpqa_pack_fields() -> None:
    adf = _load_adf()
    payload = {
        "rca": {
            "situation": "Delayed payment interest was a little wrong after rebooking.",
            "cause": "The system kept the old rate on an open interest window.",
            "resolution": "Close the old window and start a new one with the new rate.",
        },
        "impact": [
            "Fixes delayed payment interest after rate change.",
            "Does not change loans without a rate change.",
            "Please retest on a fresh rebooked loan.",
        ],
        "pre": "NA",
        "post": "NA",
        "micro": ["accounting"],
        "dev": [
            "Fresh rebooked loan — delayed payment interest matches the new rate. Result: Pass.",
            "Loan without rate change — interest unchanged. Result: Pass.",
        ],
        "qa_retest": [
            "After the accounting build is shared, retest on a fresh rebooked loan.",
        ],
        "ping_comment": "@Srikant @Reema Fix is ready for QA. Dev Test Details below.",
        **_base_aitdp(),
    }
    pack = adf.build_handoff_pack("TDPQA-180", payload)
    assert pack["mode"] == "tdpqa_field_handoff"
    fields = pack["edit_fields"]
    assert "customfield_11999" in fields  # RCA
    assert "customfield_12008" in fields  # Impact
    assert "customfield_12007" in fields  # PrePost
    assert "customfield_12000" in fields  # AITDP remarks
    assert fields["customfield_12001"] == 75.0  # whole percent
    assert pack.get("comment_adf") is not None
    body = json.dumps(pack["comment_adf"])
    assert "Dev Test Details" in body
    assert "How to retest" in body


def test_tdpqa_pack_requires_dev() -> None:
    adf = _load_adf()
    payload = {
        "rca": {
            "situation": "A.",
            "cause": "B.",
            "resolution": "C.",
        },
        "impact": ["Fixes X.", "Does not change Y.", "Please retest Z."],
        "pre": "NA",
        "post": "NA",
        **_base_aitdp(),
    }
    try:
        adf.build_handoff_pack("TDPQA-180", payload)
    except ValueError as e:
        assert "dev[]" in str(e)
    else:
        raise AssertionError("expected ValueError when TDPQA pack omits dev[]")


if __name__ == "__main__":
    test_project_mode()
    test_sdcp_ping_ok_and_omit()
    test_tdpqa_field_ping_ok_and_omit()
    test_sdcp_ping_rejects_structured_headers()
    test_sdcp_ping_rejects_long()
    test_comment_handoff_requires_structured()
    test_tdpqa_pack_fields()
    test_tdpqa_pack_requires_dev()
    print("test_jira_fix_adf: OK")
