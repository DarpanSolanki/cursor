#!/usr/bin/env python3
"""Impact mapping must not invent service apis from harness paths."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/lib"))

from infer_ship_apis import infer_repo_from_path, resolve_apis_smart  # noqa: E402
from kg_ship_resolve import _domain_hint_api, resolve_apis_for_path  # noqa: E402
from ship_change_scope import is_workspace_push_safe_paths, resolve_change_scope  # noqa: E402


class InferRepoNoFilenameFalsePositive(unittest.TestCase):
    def test_service_dir_ok(self) -> None:
        self.assertEqual(
            "trustt-platform-accounting",
            infer_repo_from_path(
                "trustt-platform-accounting/src/main/java/in/novopay/accounting/Foo.java"
            ),
        )

    def test_novopay_service_sh_not_a_repo(self) -> None:
        self.assertIsNone(infer_repo_from_path("scripts/bin/novopay-service.sh"))

    def test_novopay_framework_md_not_a_repo(self) -> None:
        self.assertIsNone(
            infer_repo_from_path(".cursor/skills/architect-thinking/novopay-framework.md")
        )


class DpicPathDoesNotMapToOverviewApi(unittest.TestCase):
    def test_dpic_runner_no_domain_hint(self) -> None:
        self.assertIsNone(_domain_hint_api("scripts/dpic/run_dpi_full_gate.sh"))
        self.assertEqual([], resolve_apis_for_path("scripts/dpic/run_dpi_full_gate.sh"))
        self.assertEqual([], resolve_apis_smart(["scripts/dpic/run_dpi_shg_parent_child_parity.sh"]))

    def test_dpi_skill_doc_no_false_api(self) -> None:
        self.assertEqual(
            [],
            resolve_apis_for_path(
                ".cursor/skills/accounting-knowledge/dpi-base-and-shg-distribute.md"
            ),
        )

    def test_real_dpi_java_still_hints(self) -> None:
        hint = _domain_hint_api(
            "trustt-platform-accounting/src/main/java/in/novopay/accounting/batchnew/dpi/dpibilling/DpiBillingBatchService.java"
        )
        self.assertIsNotNone(hint)


class HarnessBulkPushSafe(unittest.TestCase):
    def test_bulk_harness_port_is_push_safe(self) -> None:
        paths = [
            "scripts/bin/novopay-service.sh",
            "scripts/dpic/run_dpi_full_gate.sh",
            "scripts/lib/path_leak_gate.py",
            "scripts/lib/kg_ship_resolve.py",
            ".cursor/skills/architect-thinking/novopay-framework.md",
            "cursor-bundle/memory/MEMORY.md",
        ]
        self.assertTrue(is_workspace_push_safe_paths(paths))
        scope = resolve_change_scope(paths)
        self.assertTrue(scope["harness_only"] or not scope["partitions"]["service"])
        self.assertEqual([], scope["repos"])


if __name__ == "__main__":
    unittest.main()
