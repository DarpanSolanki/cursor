#!/usr/bin/env python3
"""One question, every map: what is this thing and what touches it?

The maps hold the answers but each in its own file, and an incident does not arrive labelled
with which one to open. A report says `134207 on disburseLoan` — that is an error code, a
flow, a processor, a table and a set of GL legs, and knowing that takes five lookups.

This takes the name, works out what kind of thing it is, and answers from whichever maps
know about it. Everything is read from the generated artefacts, so it costs a file read and
never a repo grep.

    platform_lookup.py 134207              an error code: where thrown, which flows surface it
    platform_lookup.py disburseLoan        a flow: contract, tables, callers, codes
    platform_lookup.py loan_account        a table: columns, writers, readers
    platform_lookup.py ExecuteTransaction… a processor: flows it runs in, what it touches
    platform_lookup.py disburse_loan_api   a topic: producers and consumers
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
FLOW = ROOT / "cursor-bundle" / "flow-test"


def load(name: str, key: str) -> dict[str, dict]:
    path = FLOW / name
    if not path.is_file():
        return {}
    out: dict[str, dict] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.startswith("#"):
            row = json.loads(line)
            out.setdefault(str(row[key]), row)
    return out


def suggest(name: str, keys, limit: int = 4) -> list[str]:
    """Nearest names, by edit distance and by substring.

    Substring alone answered nothing for `loanFroeclosure`, which is the case a suggestion is
    for — someone who has the name almost right.
    """
    import difflib
    close = difflib.get_close_matches(name, list(keys), n=limit, cutoff=0.7)
    if close:
        return close
    lowered = name.lower()
    return [k for k in keys if lowered in k.lower()][:limit]


def bullet(label: str, values, limit: int = 10) -> None:
    if not values:
        return
    if isinstance(values, (list, tuple, set)):
        shown = list(values)[:limit]
        more = f" (+{len(values)-limit} more)" if len(values) > limit else ""
        print(f"  {label:22} {', '.join(str(v) for v in shown)}{more}")
    else:
        print(f"  {label:22} {values}")


def show_error(code: str, row: dict) -> None:
    print(f"ERROR {code}")
    bullet("thrown at", row["throw_site"])
    bullet("throw sites", row["sites"])
    bullet("branches", row["branches"])
    bullet("thrown directly by", row["raised_by"])
    bullet("surfaces in", row["surfaces_in"], limit=12)
    bullet("context keys", row["context_keys"], limit=12)
    if not row["raised_by"] and not row["surfaces_in"]:
        print("  reachable from no orchestration entry point — batch writer, consumer or "
              "platform-lib")


def show_api(name: str, row: dict) -> None:
    print(f"FLOW {name}  [{row['repo']}]")
    bullet("orchestration", row["orchestration"])
    bullet("request template", row["request_template"])
    bullet("headers", [f"{k}={v}" for k, v in (row["headers"] or {}).items()])
    bullet("mandatory", row["mandatory_fields"])
    bullet("processors", f"{len(row['processors'])} — {', '.join(row['processors'][:5])}")
    bullet("writes", row["tables_written"])
    bullet("reads", row["tables_read"], limit=8)
    bullet("calls (other repo)", row["cross_service_apis"])
    bullet("calls (internal)", row["internal_apis"])
    bullet("called by", row["called_by"], limit=8)
    bullet("codes (direct)", row["error_codes"], limit=12)
    bullet("codes (via calls)", row.get("error_codes_via_calls"), limit=12)
    bullet("reached by webapp", row.get("ui_reachable"))
    bullet("gateway-routed", row.get("registered"))


def show_table(name: str, row: dict) -> None:
    print(f"TABLE {name}  [{row.get('schema') or '?'}]")
    bullet("columns", row["column_count"])
    bullet("primary key", row["primary_key"])
    bullet("column names", row["columns"], limit=14)
    bullet("indexes / FKs", f"{row['indexes']} / {row['foreign_keys']}"
           if row["indexes"] is not None else None)
    bullet("written by", row["written_by"], limit=12)
    bullet("read by", row["read_by"], limit=8)
    bullet("entities", row["entities"])
    if not row["in_local_schema"]:
        print("  not in the local DB — train divergence, not proof it does not exist")


def show_processor(name: str, row: dict) -> None:
    print(f"PROCESSOR {name}  [{row['repo']}]")
    bullet("declared at", row["src"])
    bullet("runs in", f"{row['flow_count']} flow(s)")
    bullet("spans repos", row["spans_repos"])
    bullet("writes", row["writes"])
    bullet("reads", row["reads"], limit=8)
    bullet("throws", row["throws"], limit=12)
    bullet("calls", row["calls"])
    bullet("used by", row["used_by_flows"], limit=8)


def show_topic(name: str, row: dict) -> None:
    print(f"TOPIC {name}  [{row['repo']}]")
    bullet("produced at", row["producer_site"])
    bullet("consumer services", row["consumer_services"])
    bullet("consumer classes", row["consumer_classes"])
    if row["orphan"]:
        print("  no consumer indexed" + ("" if row["literal"] else
              " — and the name came from a variable, so treat it as unknown"))


def show_gl(txn: str, rows: list[dict]) -> None:
    print(f"TRANSACTION TYPE {txn}")
    for r in sorted(rows, key=lambda x: x["sequence"] or 0):
        print(f"  #{r['sequence']:<3} {str(r['reference_code']):24} "
              f"DR {str(r['debit_placeholder']):26} CR {r['credit_placeholder']}")
    if rows and rows[0]["selected_by"]:
        bullet("selected by", rows[0]["selected_by"])


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("name")
    args = ap.parse_args()
    name = args.name

    errors = load("platform_errors.jsonl", "code")
    apis = load("platform_api_map.jsonl", "api")
    tables = load("platform_tables.jsonl", "table")
    procs = load("platform_processors.jsonl", "processor")
    topics = load("platform_events.jsonl", "topic")
    if not any((errors, apis, tables, procs, topics)):
        print("no maps built — run platform_api_map.py and platform_surface.py",
              file=sys.stderr)
        return 2

    gl = [json.loads(l) for l in (FLOW / "platform_gl_rules.jsonl").read_text().splitlines()
          if l.strip() and not l.startswith("#")] if (FLOW / "platform_gl_rules.jsonl").is_file() else []

    found = False
    for source, shower in ((errors, show_error), (apis, show_api), (tables, show_table),
                           (procs, show_processor), (topics, show_topic)):
        if name in source:
            if found:
                print()
            shower(name, source[name])
            found = True

    legs = [g for g in gl if g["txn_type"] == name and g["is_posting_rule"]]
    if legs:
        if found:
            print()
        show_gl(name, legs)
        found = True

    if not found:
        print(f"not in any map: {name}")
        for label, keys in (("flow", apis), ("table", tables), ("processor", procs),
                            ("topic", topics), ("error", errors)):
            near = suggest(name, keys)
            if near:
                print(f"  nearest {label}(s): " + ", ".join(near))
        print("  a name absent from every map is not proof it does not exist — a Java service "
              "class is not an orchestration bean, and neither is indexed here.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
