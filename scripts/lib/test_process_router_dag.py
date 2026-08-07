#!/usr/bin/env python3
"""The process DAG's structural invariants, each proven to fail on a broken matrix.

`order_path` and `plan_waves` both assume the graph is acyclic, that every `requires` names a
real process, and that a dependency never sits in a later phase than its dependent. None of
the three was checked: a violation produced a plan that looked correct and ran gates in the
wrong order.

    python3 scripts/lib/test_process_router_dag.py
"""
from __future__ import annotations

import copy
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "lib"))

from process_router import (  # noqa: E402
    PHASE_RANK,
    compute_plan,
    load_matrix,
    plan_waves,
    validate_dag,
)


def matrix_with(**processes) -> dict:
    man = copy.deepcopy(load_matrix())
    man["processes"] = {n: dict(m) for n, m in processes.items()}
    return man


class LiveMatrixTest(unittest.TestCase):

    def test_the_shipped_matrix_is_valid(self) -> None:
        self.assertEqual([], validate_dag(), "the live process matrix violates its own invariants")

    def test_the_shipped_matrix_has_edges_to_validate(self) -> None:
        procs = load_matrix().get("processes") or {}
        edges = sum(len(m.get("requires") or []) for m in procs.values())
        self.assertGreater(edges, 0, "a DAG check over an edgeless graph proves nothing")


class CycleTest(unittest.TestCase):

    def test_a_two_node_cycle_is_reported(self) -> None:
        errs = validate_dag(matrix_with(
            a={"phase": "orient", "requires": ["b"]},
            b={"phase": "orient", "requires": ["a"]},
        ))
        self.assertTrue(any(e.startswith("cycle:") for e in errs), errs)

    def test_a_longer_cycle_is_reported_with_its_path(self) -> None:
        errs = validate_dag(matrix_with(
            a={"phase": "orient", "requires": ["b"]},
            b={"phase": "orient", "requires": ["c"]},
            c={"phase": "orient", "requires": ["a"]},
        ))
        cycles = [e for e in errs if e.startswith("cycle:")]
        self.assertTrue(cycles, errs)
        self.assertIn("→", cycles[0])

    def test_a_self_edge_is_reported(self) -> None:
        errs = validate_dag(matrix_with(a={"phase": "orient", "requires": ["a"]}))
        self.assertTrue(any(e.startswith("cycle:") for e in errs), errs)

    def test_a_diamond_is_not_a_cycle(self) -> None:
        self.assertEqual([], validate_dag(matrix_with(
            top={"phase": "orient"},
            left={"phase": "orient", "requires": ["top"]},
            right={"phase": "orient", "requires": ["top"]},
            join={"phase": "orient", "requires": ["left", "right"]},
        )))

    def test_the_wave_pass_silently_mis_schedules_a_cycle(self) -> None:
        procs = {"a": {"phase": "orient", "requires": ["b"]},
                 "b": {"phase": "orient", "requires": ["a"]}}
        flat = [n for w in plan_waves(["a", "b"], procs, {}) for n in w]
        violated = [n for n in flat
                    if any(flat.index(d) > flat.index(n) for d in procs[n]["requires"])]
        self.assertTrue(violated,
                        "a cycle cannot be satisfied, so the scheduler must be emitting an "
                        "order that violates one of its own edges — silently, which is why "
                        "the cycle has to be rejected before it reaches the scheduler")


class UnknownDependencyTest(unittest.TestCase):

    def test_a_requires_naming_no_process_is_reported(self) -> None:
        errs = validate_dag(matrix_with(a={"phase": "orient", "requires": ["typo_gate"]}))
        self.assertTrue(any("unknown dependency" in e and "typo_gate" in e for e in errs), errs)

    def test_an_unknown_dependency_is_otherwise_invisible(self) -> None:
        procs = {"a": {"phase": "orient", "requires": ["typo_gate"], "cost_s": 1}}
        self.assertEqual([["a"]], plan_waves(["a"], procs, {}),
                         "the dangling edge is dropped, so the plan looks correct")


class PhaseInversionTest(unittest.TestCase):

    def test_a_dependency_in_a_later_phase_is_reported(self) -> None:
        errs = validate_dag(matrix_with(
            early={"phase": "orient", "requires": ["late"]},
            late={"phase": "verify"},
        ))
        self.assertTrue(any("phase inversion" in e for e in errs), errs)

    def test_the_inversion_really_does_reorder_the_waves(self) -> None:
        procs = {"early": {"phase": "orient", "requires": ["late"], "cost_s": 1},
                 "late": {"phase": "verify", "cost_s": 1}}
        waves = plan_waves(["early", "late"], procs, {})
        flat = [n for w in waves for n in w]
        self.assertLess(flat.index("early"), flat.index("late"),
                        "waves key on phase before depth, so the dependent runs first")

    def test_a_dependency_in_an_earlier_phase_is_fine(self) -> None:
        self.assertEqual([], validate_dag(matrix_with(
            gate={"phase": "gate", "requires": ["orient_step"]},
            orient_step={"phase": "orient"},
        )))

    def test_same_phase_is_fine(self) -> None:
        self.assertEqual([], validate_dag(matrix_with(
            a={"phase": "gate", "requires": ["b"]},
            b={"phase": "gate"},
        )))


class PlanStillWorksTest(unittest.TestCase):

    def test_every_class_still_plans(self) -> None:
        for cls in ("money-fix", "read-only-rca", "question", "release", "docs-kb"):
            plan = compute_plan(cls, force_class=cls)
            self.assertIn("PLAN", plan["line"])
            self.assertLessEqual(plan["wave_s"], plan["est_s"] + 0.01,
                                 f"{cls}: concurrent estimate cannot exceed the serial one")

    def test_waves_respect_every_dependency_in_the_live_matrix(self) -> None:
        procs = load_matrix().get("processes") or {}
        plan = compute_plan("money-fix", force_class="money-fix")
        position = {}
        for index, wave in enumerate(plan["waves"]):
            for node in wave:
                position[node] = index
        for node, index in position.items():
            for dep in (procs.get(node) or {}).get("requires") or []:
                if dep in position:
                    self.assertLess(position[dep], index,
                                    f"{node} runs in wave {index} but requires {dep} "
                                    f"in wave {position[dep]}")

    def test_phase_rank_covers_every_phase_the_matrix_uses(self) -> None:
        procs = load_matrix().get("processes") or {}
        used = {(m.get("phase") or "orient") for m in procs.values()}
        self.assertEqual(set(), used - set(PHASE_RANK),
                         "an unranked phase silently sorts as orient")


if __name__ == "__main__":
    unittest.main(verbosity=2)
