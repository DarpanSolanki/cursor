#!/usr/bin/env python3
"""One command that proves the workspace itself is sound.

Every check here exists because something was silently broken and cost real time. They
are asserted together so a session can start from a known-good workspace instead of
discovering a setup gap mid-incident.

    python3 scripts/lib/test_workspace_contract.py
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
FLOW = ROOT / "cursor-bundle" / "flow-test"


def run(*args: str, timeout: int = 900) -> subprocess.CompletedProcess:
    return subprocess.run(args, cwd=str(ROOT), capture_output=True, text=True, timeout=timeout)


def jsonl(path: pathlib.Path) -> list[dict]:
    if not path.is_file():
        return []
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines()
            if l.strip() and not l.startswith("#")]


class KnowledgeGraphTest(unittest.TestCase):

    def test_kg_validates(self) -> None:
        r = run(sys.executable, "cursor-bundle/kg/bin/kg.py", "validate")
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        self.assertIn("OK", r.stdout)

    def test_kg_is_fresh_for_the_live_checkout(self) -> None:
        r = run(sys.executable, "cursor-bundle/kg/bin/kg.py", "fresh")
        self.assertNotIn("STALE", r.stdout.upper(), "KG does not match the checkout")

    def test_mcp_exposes_every_lookup_the_rules_mandate(self) -> None:
        r = run(sys.executable, "scripts/lib/test_kg_mcp_cli_parity.py")
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)

    def test_mcp_never_hangs_on_a_source_change(self) -> None:
        r = run(sys.executable, "scripts/lib/test_kg_mcp_no_hang_on_source_change.py")
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)


class DatabaseSafetyTest(unittest.TestCase):

    def test_a_guessed_column_is_refused_before_psql(self) -> None:
        r = run(sys.executable, "scripts/lib/sql_column_check.py",
                "--sql", "SELECT la.vrm_categry FROM mfi_accounting.loan_account la")
        self.assertEqual(1, r.returncode, "a nonexistent column must be refused")
        self.assertIn("loan_account", r.stderr)

    def test_a_valid_query_is_not_blocked(self) -> None:
        r = run(sys.executable, "scripts/lib/sql_column_check.py",
                "--sql", "SELECT a.account_number, la.loan_status "
                         "FROM mfi_accounting.loan_account la "
                         "JOIN mfi_accounting.account a ON a.id = la.account_id")
        self.assertEqual(0, r.returncode, r.stderr)

    def test_qa_wrapper_checks_columns_against_the_target_not_the_local_oracle(self) -> None:
        text = (ROOT / "scripts/db/db-qa.sh").read_text(encoding="utf-8")
        self.assertIn("information_schema.columns", text)
        self.assertIn("sql_column_check.py", text)

    def test_local_wrapper_runs_the_preflight(self) -> None:
        self.assertIn("sql_column_check.py",
                      (ROOT / "scripts/db-local.sh").read_text(encoding="utf-8"))

    def test_schema_live_drift_is_reportable(self) -> None:
        r = run(sys.executable, "scripts/lib/schema_live_drift.py", "--json")
        self.assertIn(r.returncode, (0, 1))
        json.loads(r.stdout)


class RoutingTest(unittest.TestCase):

    def test_every_script_path_on_an_instruction_surface_exists(self) -> None:
        r = run(sys.executable, "scripts/lib/doc_command_gate.py")
        self.assertEqual(0, r.returncode, r.stdout)

    def test_harness_wiring_and_self_tests(self) -> None:
        r = run(sys.executable, "scripts/lib/harness_audit.py", timeout=1800)
        self.assertNotIn("✗", r.stdout, r.stdout)


class ProcessDagTest(unittest.TestCase):
    """The plan is only trustworthy if the graph it is computed from is well-formed."""

    def test_the_process_dag_is_acyclic_and_fully_resolved(self) -> None:
        r = run(sys.executable, "scripts/lib/process_router.py", "validate")
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)

    def test_the_ratchet_gate_rejects_a_malformed_graph(self) -> None:
        r = run(sys.executable, "scripts/lib/test_process_router_dag.py")
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)


class KnowledgeLayoutTest(unittest.TestCase):

    def test_there_is_exactly_one_brain(self) -> None:
        self.assertFalse((ROOT / ".cursor/brain").exists(),
                         ".cursor/brain was a stale untracked copy of cursor-bundle/brain")
        self.assertTrue((ROOT / "cursor-bundle/brain").is_dir())

    def test_no_rule_points_at_the_removed_brain(self) -> None:
        for path in list((ROOT / ".cursor/rules").glob("*.md")) + [ROOT / ".cursorrules"]:
            self.assertNotIn(".cursor/brain", path.read_text(encoding="utf-8"),
                             f"{path.name} still references the removed .cursor/brain")


class CoverageHonestyTest(unittest.TestCase):

    def test_coverage_matrix_spans_the_money_surface_not_just_tested_apis(self) -> None:
        rows = jsonl(FLOW / "test_coverage.jsonl")
        money = [r for r in rows if r.get("money")]
        self.assertGreater(
            len(money), 300,
            "the matrix is built only from APIs that already have tests — untested money "
            "APIs must be seeded from the orchestration index or their gaps are invisible")

    def test_money_gap_ratchet_exists(self) -> None:
        self.assertTrue((FLOW / "money_gap_baseline.json").is_file(),
                        "money gaps must ratchet; a fixed threshold cannot bound the real number")

    def test_the_matrix_spans_the_whole_platform_not_only_money(self) -> None:
        rows = jsonl(FLOW / "test_coverage.jsonl")
        non_money = [r for r in rows if not r.get("money")]
        self.assertGreater(
            len(non_money), 1000,
            "the seeder dropped every non-money API, so read/inquiry and write-ops flows "
            "could not appear as gaps at all — 1,468 of 1,858 orchestration APIs absent")

    def test_the_non_money_surface_ratchets_too(self) -> None:
        self.assertTrue((FLOW / "platform_gap_baseline.json").is_file(),
                        "without a ratchet the non-money gap count is a number, not pressure")


class MoneyPathGuardTest(unittest.TestCase):

    def test_no_unguarded_loan_status_sweep(self) -> None:
        r = run(sys.executable, "scripts/lib/loan_status_sweep_gate.py")
        self.assertEqual(0, r.returncode, r.stdout)

    def test_the_tdpqa72_sweep_carries_a_terminal_guard(self) -> None:
        rows = json.loads(run(sys.executable, "scripts/lib/loan_status_sweep_gate.py",
                              "--json").stdout)
        shg = [r for r in rows if r["class"] == "UpdateLoanStatusForSHGProcessor"]
        self.assertTrue(shg, "UpdateLoanStatusForSHGProcessor not found")
        self.assertEqual("terminal_guard", shg[0]["guard"])


class LearningLoopTest(unittest.TestCase):

    def test_flow_cases_record_their_result(self) -> None:
        text = (ROOT / "scripts/testing/ntest.py").read_text(encoding="utf-8")
        after_flow = text[text.index("def _run_flow_case"):]
        self.assertIn("record_test_result", after_flow,
                      "flow cases must reach the learning bus; they are the e2e money cases")

    def test_bus_health_ignores_cases_that_cannot_run_on_this_train(self) -> None:
        text = (ROOT / "scripts/testing/corroborate.py").read_text(encoding="utf-8")
        self.assertIn("requires_paths", text,
                      "a case skipped on this train must not count as failing")


class InvestigationMemoryTest(unittest.TestCase):
    """A disproven hypothesis is expensive evidence; it must outlive the session."""

    def test_dead_ends_reach_the_next_session_through_kg_why(self) -> None:
        r = run(sys.executable, "cursor-bundle/kg/bin/kg_observed.py", "loanPrepayment")
        self.assertIn("observed", r.stdout.lower(), r.stdout)

    def test_kg_why_prints_observed_behaviour_not_only_structure(self) -> None:
        text = (ROOT / "cursor-bundle/kg/bin/kg.py").read_text(encoding="utf-8")
        self.assertIn("_print_observed", text,
                      "kg why must join the learning bus, or it answers a question nobody asked")

    def test_telemetry_reports(self) -> None:
        r = run(sys.executable, "scripts/bin/task-log.py", "report")
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)


class SkipIsNotPassTest(unittest.TestCase):

    def test_ntest_returns_a_distinct_code_for_a_train_skip(self) -> None:
        text = (ROOT / "scripts/testing/ntest.py").read_text(encoding="utf-8")
        self.assertIn("SKIP_RC = 3", text)
        self.assertIn("return SKIP_RC, None", text,
                      "a skip returning 0 is how three cases were reported as passing")

    def test_ship_plan_treats_a_skip_as_skipped_not_failed(self) -> None:
        text = (ROOT / "scripts/lib/ship_test_plan.py").read_text(encoding="utf-8")
        self.assertIn("NTEST_SKIP_RC", text,
                      "making SKIP non-zero must not start failing ship plans")


class KgFirstNudgeTest(unittest.TestCase):
    """The two searches that cost the most, answered before they run."""

    def _hook(self, payload: str) -> str:
        import subprocess as sp
        r = sp.run([sys.executable, str(ROOT / ".cursor/hooks/knowledge-answer.py")],
                   input=payload, capture_output=True, text=True, timeout=90,
                   cwd=str(ROOT), env={**__import__("os").environ,
                                       "CURSOR_PROJECT_DIR": str(ROOT)})
        return r.stdout

    def test_error_code_grep_is_answered_with_kg_error(self) -> None:
        out = self._hook('{"tool_name":"Grep","tool_input":{"pattern":"134291"}}')
        self.assertIn("kg_error 134291", out)

    def test_column_writer_grep_is_answered_with_kg_schema(self) -> None:
        out = self._hook('{"tool_name":"Grep","tool_input":{"pattern":"setLoanStatus"}}')
        self.assertIn("kg_schema loan_account.loan_status", out)

    def test_unrelated_grep_stays_silent(self) -> None:
        self.assertEqual("", self._hook(
            '{"tool_name":"Grep","tool_input":{"pattern":"hello world"}}').strip())


class AutonomyBoundaryTest(unittest.TestCase):

    def _classify(self, command: str):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "az", ROOT / "scripts/bin/autonomous-zone.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod.classify(command)

    def test_remote_db_write_is_gated(self) -> None:
        self.assertFalse(self._classify("psql -h 172.31.2.147 -c 'UPDATE x'")[0])

    def test_service_source_edit_is_gated(self) -> None:
        self.assertFalse(self._classify(
            "vim trustt-platform-accounting/src/main/java/F.java")[0])

    def test_rules_edit_is_gated(self) -> None:
        self.assertFalse(self._classify("sed -i s/a/b/ .cursor/rules/00-workspace-core.mdc")[0])

    def test_git_history_is_gated(self) -> None:
        self.assertFalse(self._classify("git " + "push origin main")[0])

    def test_read_only_audit_is_autonomous(self) -> None:
        self.assertTrue(self._classify("python3 scripts/lib/harness_audit.py")[0])


class FixtureAndInvariantTest(unittest.TestCase):

    def test_money_cases_inherit_universal_invariants(self) -> None:
        r = run(sys.executable, "scripts/lib/test_money_invariants_wiring.py")
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)

    def test_fixtures_are_declarative_and_never_invented(self) -> None:
        r = run(sys.executable, "scripts/lib/test_fixture_spec.py")
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)

    def test_qa_clone_exists_and_never_auto_applies(self) -> None:
        text = (ROOT / "scripts/bin/qa-clone-lan.py").read_text(encoding="utf-8")
        self.assertIn("db-local-write.sh", text)
        self.assertIn("ROLLBACK", text, "the seed must be proven before it is trusted")
        self.assertNotIn("COMMIT;\n", text.split("def dry_run")[1].split("def main")[0],
                         "the dry run must never commit")


class PreambleTest(unittest.TestCase):

    def test_preamble_is_measured_and_ratcheted(self) -> None:
        r = run(sys.executable, "scripts/lib/rules_to_gates.py")
        self.assertEqual(0, r.returncode, r.stdout)
        self.assertIn("always-on preamble", r.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
