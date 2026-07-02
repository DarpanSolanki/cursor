#!/usr/bin/env python3
"""Build ordered API/processor chains per Request — full internal call spine."""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

BIN = Path(__file__).resolve().parent
sys.path.insert(0, str(BIN))

from _contract_scan import (  # noqa: E402
    ScanResult,
    is_money,
    resolve_api_owner,
    scan_workspace,
)
from _paths import WORKSPACE  # noqa: E402

# Money + FTG spine requests (always emit full chain)
PRIORITY_REQUESTS = {
    "disburseLoan", "loanRepayment", "loanPrepayment", "loanAccountPartPrepayment",
    "updateCollectionBatchDetails", "collectionLoanRepayment", "loanDisbursementCancellation",
    "loanAccountTransactionReversal", "createOrUpdateLoanAccount", "postTransaction",
    "fetchLoanForeclosureSimulationDetails", "cancelLoanForeclosure", "cancelCollections",
    "interestAccrualCalculation", "interestAccrualPosting", "penalInterestAccrualBooking",
    "loanAccountDpdCalcJob", "glBalanceZeroisation", "loanWriteoff",
    "getLoanAccountOverviewDetails", "getLoanAccountBasicDetails", "getLoanAccountSummaryDetails",
    "dpiAccrualCalculation", "dpiAccrualBooking", "dpiBilling",
}


@dataclass
class ChainStep:
    seq: int
    step_type: str  # processor | api
    name: str
    callee_service: str | None = None
    function_code: str | None = None
    function_sub_code: str | None = None
    src: str = ""


@dataclass
class RequestChain:
    request: str
    repo: str
    money: bool
    steps: list[ChainStep] = field(default_factory=list)
    cross_service_apis: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        apis = [s.name for s in self.steps if s.step_type == "api"]
        procs = [s.name for s in self.steps if s.step_type == "processor"]
        cross = sorted(set(self.cross_service_apis))
        return {
            "id": f"chain:{self.repo}:{self.request}",
            "request": self.request,
            "repo": self.repo,
            "money": self.money,
            "processor_count": len(procs),
            "internal_api_count": len(apis),
            "processors": procs,
            "internal_apis": apis,
            "cross_service_apis": cross,
            "steps": [
                {
                    "seq": s.seq,
                    "type": s.step_type,
                    "name": s.name,
                    "callee_service": s.callee_service,
                    "function_code": s.function_code,
                    "function_sub_code": s.function_sub_code,
                    "src": s.src,
                }
                for s in self.steps
            ],
        }


def build_chains(result: ScanResult) -> dict[str, RequestChain]:
    """Reconstruct chains from flat api_calls grouped by (repo, request)."""
    chains: dict[str, RequestChain] = {}
    proc_seq: dict[tuple[str, str], int] = defaultdict(int)
    api_seq: dict[tuple[str, str], int] = defaultdict(int)

    # Processors from build_orchestration pattern — derive from api_calls order + separate proc scan
    # Group api calls by producer
    by_req: dict[tuple[str, str], list] = defaultdict(list)
    for call in result.api_calls:
        by_req[(call.producer_repo, call.producer_request)].append(call)

    for (repo, req), calls in by_req.items():
        key = f"{repo}:{req}"
        chain = chains.get(key) or RequestChain(
            request=req,
            repo=repo,
            money=is_money(req),
        )
        seq_base = len(chain.steps)
        for i, call in enumerate(calls, 1):
            callee = resolve_api_owner(call.api_name, call.api_id, result.request_owners)
            step = ChainStep(
                seq=seq_base + i,
                step_type="api",
                name=call.api_name,
                callee_service=callee,
                function_code=call.function_code,
                function_sub_code=call.function_sub_code,
                src=call.src,
            )
            chain.steps.append(step)
            if callee and callee != repo:
                if call.api_name not in chain.cross_service_apis:
                    chain.cross_service_apis.append(call.api_name)
        chains[key] = chain

    # Mark priority/money
    for key, chain in chains.items():
        if chain.request in PRIORITY_REQUESTS:
            chain.money = True
    return chains


def build_chains_from_kg_jsonl(kg_jsonl: Path, result: ScanResult) -> dict[str, RequestChain]:
    """Merge processor invokes order from kg.jsonl if present."""
    chains = build_chains(result)
    if not kg_jsonl.is_file():
        return chains

    invokes: dict[str, list[tuple[int, str, str]]] = defaultdict(list)
    for line in kg_jsonl.read_text(encoding="utf-8").splitlines():
        try:
            o = json.loads(line)
        except json.JSONDecodeError:
            continue
        if o.get("t") != "edge" or o.get("rel") != "invokes":
            continue
        src = o.get("from", "")
        if not src.startswith("request:"):
            continue
        req = src.split(":", 1)[1]
        repo = o.get("repo", "")
        dst = o.get("to", "")
        if not dst.startswith("processor:"):
            continue
        proc = dst.split(":", 1)[1]
        invokes[f"{repo}:{req}"].append((o.get("seq") or 0, proc, o.get("src", "")))

    for key, procs in invokes.items():
        if key not in chains:
            repo, req = key.split(":", 1)
            chains[key] = RequestChain(request=req, repo=repo, money=is_money(req) or req in PRIORITY_REQUESTS)
        chain = chains[key]
        existing_procs = {s.name for s in chain.steps if s.step_type == "processor"}
        merged: list[ChainStep] = []
        seq = 0
        for pseq, proc, src in sorted(procs, key=lambda x: x[0]):
            if proc in existing_procs:
                continue
            seq += 1
            merged.append(ChainStep(seq=seq, step_type="processor", name=proc, src=src))
        # Interleave: processors first (orchestration order), then apis appended
        api_steps = [s for s in chain.steps if s.step_type == "api"]
        proc_steps = merged + [s for s in chain.steps if s.step_type == "processor"]
        proc_steps.sort(key=lambda s: s.seq)
        reseq: list[ChainStep] = []
        n = 0
        for s in proc_steps:
            n += 1
            reseq.append(ChainStep(seq=n, step_type="processor", name=s.name, src=s.src,
                                    function_code=s.function_code, function_sub_code=s.function_sub_code))
        for s in api_steps:
            n += 1
            reseq.append(ChainStep(seq=n, step_type="api", name=s.name, callee_service=s.callee_service,
                                    function_code=s.function_code, function_sub_code=s.function_sub_code, src=s.src))
        chain.steps = reseq
    return chains


def emit_chain_jsonl(chains: dict[str, RequestChain], out_path: Path, *, all_money: bool = True,
                     priority_only: bool = False) -> int:
    rows: list[dict] = []
    for chain in sorted(chains.values(), key=lambda c: (c.repo, c.request)):
        if priority_only and chain.request not in PRIORITY_REQUESTS and not chain.money:
            continue
        if all_money and not chain.money and chain.request not in PRIORITY_REQUESTS:
            continue
        if not chain.steps and chain.request not in PRIORITY_REQUESTS:
            continue
        rows.append(chain.to_dict())
    lines = ["# API chains — ordered processors + internal <API> calls per Request"]
    for row in rows:
        lines.append(json.dumps(row, separators=(",", ":")))
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return len(rows)


def build_api_index(chains: dict[str, RequestChain]) -> list[dict]:
    index: dict[str, dict] = {}
    for chain in chains.values():
        for step in chain.steps:
            if step.step_type != "api":
                continue
            ent = index.setdefault(step.name, {
                "api": step.name,
                "callee_services": set(),
                "called_from": [],
            })
            if step.callee_service:
                ent["callee_services"].add(step.callee_service)
            ent["called_from"].append({
                "request": chain.request,
                "repo": chain.repo,
                "seq": step.seq,
            })
    out = []
    for api, ent in sorted(index.items()):
        out.append({
            "api": api,
            "callee_services": sorted(ent["callee_services"]),
            "caller_count": len(ent["called_from"]),
            "callers": ent["called_from"][:20],
        })
    return out


def main() -> int:
    import argparse
    p = argparse.ArgumentParser(description="Build API chain spine")
    p.add_argument("--all-money", action="store_true", default=True)
    p.add_argument("--priority-only", action="store_true")
    p.add_argument("--out", type=Path, default=WORKSPACE / "cursor-bundle/flow-test/chains.jsonl")
    p.add_argument("--index-out", type=Path, default=WORKSPACE / "cursor-bundle/flow-test/api_index.jsonl")
    args = p.parse_args()

    result = scan_workspace(WORKSPACE)
    kg_jsonl = WORKSPACE / "cursor-bundle/kg/data/kg.jsonl"
    chains = build_chains_from_kg_jsonl(kg_jsonl, result)
    n = emit_chain_jsonl(chains, args.out, all_money=not args.priority_only, priority_only=args.priority_only)

    idx_rows = build_api_index(chains)
    idx_lines = ["# API index — who calls each internal API"]
    for row in idx_rows:
        idx_lines.append(json.dumps(row, separators=(",", ":")))
    args.index_out.write_text("\n".join(idx_lines) + "\n", encoding="utf-8")

    print(f"chains: {n} written → {args.out.relative_to(WORKSPACE)}")
    print(f"api_index: {len(idx_rows)} apis → {args.index_out.relative_to(WORKSPACE)}")
    print(f"total requests scanned: {len(result.request_owners)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
