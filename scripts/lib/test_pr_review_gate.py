#!/usr/bin/env python3
"""Unit tests for pr_review_gate — every check is proven red before it is trusted."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pr_review_gate import (  # noqa: E402
    finding_errors,
    freshness_errors,
    gate_errors,
    provenance_errors,
    question_errors,
    split_sections,
    verdict_errors,
)

HEAD = "a576b8634fb6f0a51d0e8c6f0e0ec25aa769f912"
BASE = "3955f2879a2b3c1fcbc7b53c5a97c89ce3ff7e31"

ARTIFACTS = {
    "freshness": {
        "status": "VERIFIED",
        "base": {
            "git_ref_initial_sha": BASE,
            "git_ref_final_sha": BASE,
            "metadata_initial_sha": BASE,
            "metadata_final_sha": BASE,
        },
        "head": {
            "pull_ref_initial_sha": HEAD,
            "pull_ref_final_sha": HEAD,
            "metadata_initial_sha": HEAD,
            "metadata_final_sha": HEAD,
        },
    },
    "provenance": {
        "target": {
            "base": {"sha": BASE},
            "head": {"sha": HEAD},
        }
    },
}

GOOD_REPORT = f"""PR Review: interest accrual distribution
Verdict: REQUEST CHANGES
Confidence: CONFIRMED

Provenance
- PR: https://github.com/trusttai/trustt-platform-accounting/pull/7859
- Repository: trusttai/trustt-platform-accounting
- Base: mfi_integration_v3.4.2.4@{BASE}
- Head: mfi_integration_v3.4.2.4@{HEAD}
- Environment: local
- Jira: not provided
- Train status: ALIGNED — both repos on 3.4.2.4
- Collected: 2026-08-04T07:17:53Z
- Freshness: base and head agree across initial and final collection

Scope and requirements
- Commits/files: 9 files

Claim status
- Independently verified: distribution sums to parent

Findings
1. [BLOCKING][CONFIRMED] InterestAccrualCalculationItemReader.java:21 — positional mapper drift. Append the column last.

Questions
1. [QUESTION][SUSPECTED] BookChildLoanProcessor.java:271 — is the residual INT intended to absorb rounding?

Verification
- PASS: interest_jobs_matrix 12/12

Residual risks
- none

Self-review: attempted to falsify each finding against the reviewed head; unproven items were dropped or downgraded.
"""


class TestFreshness(unittest.TestCase):
    def test_clean_artifacts_pass(self):
        self.assertEqual(freshness_errors(ARTIFACTS), [])

    def test_shifted_head_sha_fails(self):
        bad = {**ARTIFACTS, "freshness": {**ARTIFACTS["freshness"], "head": {
            "pull_ref_initial_sha": HEAD,
            "pull_ref_final_sha": "0" * 40,
        }}}
        self.assertTrue(any("disagree" in e for e in freshness_errors(bad)))

    def test_unverified_status_fails(self):
        bad = {"freshness": {**ARTIFACTS["freshness"], "status": "PARTIAL"}}
        self.assertTrue(any("not VERIFIED" in e for e in freshness_errors(bad)))

    def test_missing_freshness_fails(self):
        self.assertTrue(freshness_errors({}))


class TestProvenance(unittest.TestCase):
    def test_complete_block_passes(self):
        self.assertEqual(provenance_errors(GOOD_REPORT, ARTIFACTS), [])

    def test_missing_label_fails(self):
        text = GOOD_REPORT.replace("- Train status: ALIGNED — both repos on 3.4.2.4\n", "")
        self.assertTrue(any("Train status" in e for e in provenance_errors(text, ARTIFACTS)))

    def test_wrong_head_sha_fails(self):
        text = GOOD_REPORT.replace(HEAD, "b" * 40)
        errors = provenance_errors(text, ARTIFACTS)
        self.assertTrue(any("head SHA" in e for e in errors))


class TestFindings(unittest.TestCase):
    def sections(self, text: str):
        return split_sections(text)

    def test_confirmed_finding_passes(self):
        self.assertEqual(finding_errors(self.sections(GOOD_REPORT)), [])

    def test_suspected_finding_fails(self):
        text = GOOD_REPORT.replace("[BLOCKING][CONFIRMED]", "[BLOCKING][SUSPECTED]")
        self.assertTrue(any("not CONFIRMED" in e for e in finding_errors(self.sections(text))))

    def test_not_verified_finding_fails(self):
        text = GOOD_REPORT.replace("[BLOCKING][CONFIRMED]", "[MAJOR][NOT-VERIFIED]")
        self.assertTrue(any("not CONFIRMED" in e for e in finding_errors(self.sections(text))))

    def test_finding_without_evidence_fails(self):
        text = GOOD_REPORT.replace(
            "InterestAccrualCalculationItemReader.java:21 — positional mapper drift. Append the column last.",
            "the reader looks risky",
        )
        self.assertTrue(
            any("no file:line" in e for e in finding_errors(self.sections(text)))
        )

    def test_untagged_finding_fails(self):
        text = GOOD_REPORT.replace("[BLOCKING][CONFIRMED] ", "")
        self.assertTrue(any("no [SEVERITY]" in e for e in finding_errors(self.sections(text))))

    def test_check_id_counts_as_evidence(self):
        text = GOOD_REPORT.replace(
            "InterestAccrualCalculationItemReader.java:21", "check:build-7859"
        )
        self.assertEqual(finding_errors(self.sections(text)), [])


class TestQuestions(unittest.TestCase):
    def test_neutral_question_passes(self):
        self.assertEqual(question_errors(split_sections(GOOD_REPORT)), [])

    def test_directive_question_fails(self):
        text = GOOD_REPORT.replace(
            "is the residual INT intended to absorb rounding?",
            "change the residual INT handling.",
        )
        self.assertTrue(
            any("directive" in e for e in question_errors(split_sections(text)))
        )

    def test_confirmed_question_fails(self):
        text = GOOD_REPORT.replace("[QUESTION][SUSPECTED]", "[QUESTION][CONFIRMED]")
        self.assertTrue(
            any("must be SUSPECTED" in e for e in question_errors(split_sections(text)))
        )


class TestVerdict(unittest.TestCase):
    def test_request_changes_with_blocker_passes(self):
        self.assertEqual(verdict_errors(GOOD_REPORT), [])

    def test_approve_with_blocker_fails(self):
        text = GOOD_REPORT.replace("Verdict: REQUEST CHANGES", "Verdict: APPROVE")
        self.assertTrue(any("contradicts" in e for e in verdict_errors(text)))

    def test_comment_with_blocker_fails(self):
        text = GOOD_REPORT.replace("Verdict: REQUEST CHANGES", "Verdict: COMMENT")
        self.assertTrue(any("contradicts" in e for e in verdict_errors(text)))

    def test_blocker_downgraded_to_not_verified_fails(self):
        text = GOOD_REPORT.replace("Verdict: REQUEST CHANGES", "Verdict: NOT VERIFIED")
        self.assertTrue(any("downgraded" in e for e in verdict_errors(text)))

    def test_approve_on_mixed_train_fails(self):
        text = (
            GOOD_REPORT.replace("Verdict: REQUEST CHANGES", "Verdict: APPROVE")
            .replace("Train status: ALIGNED", "Train status: MIXED")
            .replace(
                "1. [BLOCKING][CONFIRMED] InterestAccrualCalculationItemReader.java:21 "
                "— positional mapper drift. Append the column last.\n",
                "",
            )
        )
        self.assertTrue(any("MIXED" in e for e in verdict_errors(text)))

    def test_missing_verdict_fails(self):
        text = GOOD_REPORT.replace("Verdict: REQUEST CHANGES", "")
        self.assertTrue(verdict_errors(text))


class TestGateAggregate(unittest.TestCase):
    def test_good_report_passes(self):
        self.assertEqual(gate_errors(GOOD_REPORT, ARTIFACTS), [])

    def test_missing_self_review_fails(self):
        text = GOOD_REPORT.replace("Self-review: attempted to falsify", "Reviewed carefully")
        self.assertTrue(any("Self-review" in e for e in gate_errors(text, ARTIFACTS)))

    def test_empty_report_fails(self):
        self.assertTrue(gate_errors("", ARTIFACTS))


if __name__ == "__main__":
    unittest.main(verbosity=2)
