#!/usr/bin/env python3
"""Unit tests for java_comment_lint."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "lib"))

from java_comment_lint import _scan_text, is_dpi_java  # noqa: E402


def test_is_dpi_java() -> None:
    assert is_dpi_java("trustt-platform-accounting/src/main/java/in/novopay/accounting/batchnew/dpi/x/Foo.java")
    assert is_dpi_java(".../DpiAccrualBookingBatchService.java")
    assert not is_dpi_java(".../InterestAccrualCalculationBatchService.java")


def test_consecutive_slashes_fail() -> None:
    text = "\n".join(
        [
            "class X {",
            "\t\t// line one narrative",
            "\t\t// line two narrative",
            "\t\t// line three narrative",
            "\t\tint x = 1;",
            "}",
        ]
    )
    f = _scan_text("dpi/Foo.java", text)
    assert any(x["kind"] == "consecutive_slashes" for x in f)


def test_long_javadoc_fail() -> None:
    text = "\n".join(
        [
            "\t/**",
            "\t * First line mirrors interest accrual.",
            "\t * Second line of parity essay.",
            "\t * Third line of essay.",
            "\t */",
            "\tvoid m() {}",
        ]
    )
    f = _scan_text("dpi/Foo.java", text)
    assert any(x["kind"] == "long_essay_javadoc" for x in f)


def test_plain_long_javadoc_ok() -> None:
    """Class docs without essay markers are allowed (pre-existing DPI docs)."""
    text = "\n".join(
        [
            "\t/**",
            "\t * Resolves per-loan DPI config from product scheme.",
            "\t * Uses repayment frequency and effective rate.",
            "\t * Callers must pass a non-null loan account.",
            "\t */",
            "\tvoid m() {}",
        ]
    )
    assert _scan_text("dpi/Foo.java", text) == []


def test_ticket_marker_fail() -> None:
    text = "\t// TDPQA-83 temporary note about mirrors interest parity\n\tint x;\n"
    f = _scan_text("dpi/Foo.java", text)
    assert any(x["kind"] == "ticket_or_essay" for x in f)


def test_concise_invariant_ok() -> None:
    text = "\n".join(
        [
            "\t// Seal rows only on EMI due or month-end — never grace/overdue exit.",
            "\tList<Long> x = List.of();",
            "\t/** Accrue on/after stored overdue_date (>=). */",
            "\tboolean ok() { return true; }",
        ]
    )
    f = _scan_text("dpi/Foo.java", text)
    assert f == [], f


def test_diff_volume_fail_and_pass() -> None:
    import subprocess, tempfile
    from java_comment_lint import diff_findings

    with tempfile.TemporaryDirectory() as d:
        repo = Path(d)
        run = lambda *a: subprocess.run(["git", "-C", d, *a], check=True, capture_output=True)
        run("init", "-q")
        run("config", "user.email", "t@t")
        run("config", "user.name", "t")
        src = repo / "Dpi.java"
        src.write_text("class A {\n  int x;\n}\n")
        run("add", "-A"); run("commit", "-qm", "base")

        src.write_text("class A {\n  int x;\n  /** one. */\n  int y;\n}\n")
        run("add", "-A"); run("commit", "-qm", "few")
        assert diff_findings(repo, "HEAD~1") == [], "1 added comment must pass"

        src.write_text(
            "class A {\n  int x;\n  /** one. */\n  int y;\n"
            "  /** two. */\n  int z;\n  // three\n  // four\n  int w;\n}\n"
        )
        run("add", "-A"); run("commit", "-qm", "many")
        f = diff_findings(repo, "HEAD~1")
        assert any(x["kind"] == "added_comment_volume" for x in f), f


if __name__ == "__main__":
    test_is_dpi_java()
    test_consecutive_slashes_fail()
    test_long_javadoc_fail()
    test_plain_long_javadoc_ok()
    test_ticket_marker_fail()
    test_concise_invariant_ok()
    test_diff_volume_fail_and_pass()
    print("test_java_comment_lint: OK")
