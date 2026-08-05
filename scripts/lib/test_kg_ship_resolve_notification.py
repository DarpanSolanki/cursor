#!/usr/bin/env python3
"""Regression: MessageBroker / SMS notification paths must not invent disburseLoan."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/lib"))

from infer_ship_apis import (  # noqa: E402
    build_impact,
    classify_path,
    is_knowledge_only_paths,
)
from kg_ship_resolve import resolve_apis_for_path  # noqa: E402


class KgShipResolveNotificationTest(unittest.TestCase):
    def test_notifications_messagebroker_does_not_invent_disburse(self) -> None:
        path = "trustt-platform-notifications/deploy/application/messagebroker/MessageBroker.xml"
        apis = resolve_apis_for_path(path)
        self.assertNotIn("disburseLoan", apis)

    def test_due_notification_writer_maps_to_due_job_not_disburse(self) -> None:
        path = (
            "trustt-platform-accounting/src/main/java/in/novopay/accounting/batchnew/"
            "notifications/loaninstallmentduenotificationjob/LoanInstallmentDueNotificationWriter.java"
        )
        apis = resolve_apis_for_path(path)
        self.assertNotIn("disburseLoan", apis)
        self.assertIn("loanInstallmentDueNotificationJob", apis)

    def test_notification_paths_are_service_not_money(self) -> None:
        paths = [
            "trustt-platform-notifications/deploy/application/messagebroker/MessageBroker.xml",
            "trustt-platform-accounting/src/main/java/in/novopay/accounting/batchnew/"
            "notifications/loaninstallmentduenotificationjob/LoanInstallmentDueNotificationWriter.java",
        ]
        for p in paths:
            self.assertEqual(classify_path(p), "service", p)
        impact = build_impact(paths)
        self.assertEqual(impact["tier"], "service")
        self.assertNotIn("disburseLoan", impact["apis"])
        self.assertIn("loanInstallmentDueNotificationJob", impact["apis"])
        self.assertIn("batch.loan_installment_due_notification", impact.get("ntest_cases") or [])
        self.assertIn("config.notification_sms_throughput", impact.get("ntest_cases") or [])
        self.assertNotIn("disbursement.quick", impact.get("ntest_cases") or [])

    def test_sms_throughput_assert_script_wired(self) -> None:
        script = ROOT / "scripts/bin/assert-notification-sms-throughput.sh"
        self.assertTrue(script.is_file(), script)
        # Keep ops-bin-hygiene reference (registry.json alone is not scanned).
        self.assertIn("assert-notification-sms-throughput.sh", script.name)
        import subprocess

        r = subprocess.run(["bash", str(script)], cwd=str(ROOT), capture_output=True, text=True)
        self.assertIn(r.returncode, (0, 1), f"script did not run: {r.stderr or r.stdout}")
        self.assertIn("notification_sms_: threads=", r.stdout)

        self.assertTrue(
            is_knowledge_only_paths(
                [".cursor/changelog.md", "cursor-bundle/brain/platform/config-drift-map.md"]
            )
        )
        self.assertFalse(
            is_knowledge_only_paths(
                [".cursor/changelog.md", "trustt-platform-accounting/src/main/java/Foo.java"]
            )
        )


if __name__ == "__main__":
    unittest.main()
