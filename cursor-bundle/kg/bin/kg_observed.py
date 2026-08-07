#!/usr/bin/env python3
"""What has actually gone wrong here — the behavioural half of `kg why`.

The KG indexes structure: processors, tables, error throw sites, flows. The learning bus
records behaviour: which case passed, which API failed, which error code fired, what the
gotcha was. They are two stores with two query paths, and nothing joined them.

That gap is why the KG loses to grep. It can answer "what is connected to what" when the
question in an RCA is always "what usually goes wrong here". Structure alone cannot say
*this API failed four times last month, always 134291*. The bus can, and nobody asked it.

    from kg_observed import observed_for
    observed_for("loanPrepayment")   # -> Observed(fails=4, codes={"134291": 3}, ...)

Read-only over `cursor-bundle/flow-test/learning_bus.jsonl`. Silent and empty when the
bus is missing — an absent history is not evidence of health, and must never read as such.
"""
from __future__ import annotations

import json
import pathlib
import re
import sys
from collections import Counter
from dataclasses import dataclass, field

ROOT = pathlib.Path(__file__).resolve().parents[3]
BUS = ROOT / "cursor-bundle" / "flow-test" / "learning_bus.jsonl"

_CODE = re.compile(r"\b(1[0-9]{5}|[3-9][0-9]{4})\b")


@dataclass
class Observed:
    api: str
    passes: int = 0
    fails: int = 0
    last_fail: str = ""
    last_pass: str = ""
    codes: Counter = field(default_factory=Counter)
    cases: Counter = field(default_factory=Counter)
    gotchas: list[str] = field(default_factory=list)
    dead_ends: list[str] = field(default_factory=list)

    @property
    def has_history(self) -> bool:
        return bool(self.passes or self.fails or self.gotchas or self.dead_ends)

    def render(self) -> list[str]:
        if not self.has_history:
            return []
        out = ["--- observed (learning bus — behaviour, not structure) ---"]
        verdict = f"    runs: {self.passes} pass / {self.fails} fail"
        if self.last_fail:
            verdict += f"   last fail {self.last_fail[:10]}"
        if self.fails and self.last_pass and self.last_pass > self.last_fail:
            verdict += "  (recovered since)"
        out.append(verdict)
        if self.codes:
            top = ", ".join(f"{c}×{n}" for c, n in self.codes.most_common(5))
            out.append(f"    codes seen: {top}")
        if self.cases:
            top = ", ".join(f"{c}({n})" for c, n in self.cases.most_common(4))
            out.append(f"    cases: {top}")
        for text in self.gotchas[:3]:
            out.append(f"    gotcha: {text[:130]}")
        for text in self.dead_ends:
            out.append(f"    already disproven: {text[:120]}")
        return out


def _rows() -> list[dict]:
    if not BUS.is_file():
        return []
    out = []
    for line in BUS.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def observed_for(api: str, *, rows: list[dict] | None = None) -> Observed:
    api_l = (api or "").lower()
    got = Observed(api=api)
    if not api_l:
        return got
    for row in rows if rows is not None else _rows():
        if (row.get("api") or "").lower() != api_l:
            continue
        kind = row.get("type") or ""
        ts = str(row.get("ts") or "")
        detail = str(row.get("detail") or "")
        case = detail[5:].strip() if detail.startswith("case=") else ""
        if kind in ("test_pass", "sanity_pass"):
            got.passes += 1
            got.last_pass = max(got.last_pass, ts)
            if case:
                got.cases[case] += 0
        elif kind in ("test_fail", "sanity_fail"):
            got.fails += 1
            got.last_fail = max(got.last_fail, ts)
            if case:
                got.cases[case] += 1
        elif kind == "gotcha":
            if detail:
                got.gotchas.append(detail)
        blob = json.dumps(row)
        if kind in ("test_fail", "sanity_fail", "gotcha"):
            for code in _CODE.findall(blob):
                got.codes[code] += 1

    # A hypothesis already disproven is the most expensive evidence an investigation
    # produces, and it used to die with the session.
    try:
        sys.path.insert(0, str(ROOT / "scripts" / "bin"))
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "task_log", ROOT / "scripts" / "bin" / "task-log.py")
        if spec and spec.loader:
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            for rec in mod.dead_ends_for(api):
                text = str(rec.get("text") or "")
                ev = str(rec.get("evidence") or "")
                got.dead_ends.append(f"{text}" + (f"  [{ev}]" if ev else ""))
    except Exception:
        pass
    return got


def render_for(api: str) -> str:
    lines = observed_for(api).render()
    return "\n".join(lines)


def main() -> int:
    import sys
    if len(sys.argv) < 2:
        print("usage: kg_observed.py <apiName>")
        return 2
    text = render_for(sys.argv[1])
    print(text or f"no observed history for {sys.argv[1]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
