#!/usr/bin/env python3
"""Answer a Grep/Glob/Read from knowledge the workspace already has, before it runs.

The grep-leak hook only ever saw shell `grep`. PreToolUse in settings.json matched Bash
only, so agent-native Grep, Glob and Read — the tools actually used most — were unhooked
entirely. That is how TDPQA-241 rediscovered the notification-message Redis cache by
reading platform-lib line by line while redis-key-registry.md:101 and GAP-058 sat unread.

Fires when the target is service source, or when the search term itself resolves to a
code symbol in the KG — a class name typed with no path is the common case and the first
version stayed silent on it.

Emits hookSpecificOutput.additionalContext: plain stdout from a PreToolUse hook reaches
the transcript, not the model, so an answer printed that way is an answer nobody reads.
Never blocks, never denies, silent when it has nothing to add.
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import time

ROOT = os.environ.get("CURSOR_PROJECT_DIR") or os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
SERVICE_HINTS = ("trustt-platform-", "novopay-platform-", "novopay-mfi-")
SOURCE_HINTS = ("/src/main/", "/src/test/", "_orc.xml", "/deploy/application/")

_ERROR_CODE = __import__("re").compile(r"\b(1[0-9]{5}|[3-9][0-9]{4})\b")
_SETTER = __import__("re").compile(r"\bset([A-Z][A-Za-z0-9]+)\s*\(?")


def _targeted(probe: str) -> list[str]:
    """The two searches that cost the most, answered before they run.

    In one session six error codes were grepped and `kg_error` — the documented first hop
    at ~213 tokens — was never called; and `setLoanStatus` was grepped for its writers when
    `kg schema loan_account.loan_status` lists every reader and writer outright. Both are
    mechanically detectable at the moment of the mistake, which is the only moment a nudge
    changes anything.

    The column suggestion resolves through the schema bindings rather than guessing, so it
    names the real table.column or says nothing.
    """
    out: list[str] = []
    for code in list(dict.fromkeys(_ERROR_CODE.findall(probe)))[:3]:
        out.append(
            f"kg_error {code}  — every throw site with file:line, the ExecutionContext keys "
            "the message needs, the runtime template, and prior shipped fixes (~213 tokens, "
            "cheaper than one grep)")
    fields = list(dict.fromkeys(_SETTER.findall(probe)))[:2]
    if fields:
        try:
            import json as _json
            binding_path = os.path.join(ROOT, "cursor-bundle", "schema", "bindings.jsonl")
            wanted = {f[0].lower() + f[1:] for f in fields}
            seen: set[str] = set()
            with open(binding_path, encoding="utf-8") as fh:
                for line in fh:
                    if not line.strip():
                        continue
                    try:
                        row = _json.loads(line)
                    except ValueError:
                        continue
                    if row.get("field") in wanted:
                        key = f"{row.get('table')}.{row.get('column')}"
                        if key not in seen:
                            seen.add(key)
                            out.append(
                                f"kg_schema {key}  — lists every reader AND writer of that "
                                "column, plus the error codes raised when its check fails")
                    if len(seen) >= 3:
                        break
        except OSError:
            pass
    return out


def _index():
    path = os.path.join(ROOT, "scripts", "lib", "knowledge_index.py")
    spec = importlib.util.spec_from_file_location("knowledge_index", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0

    tool = payload.get("tool_name") or payload.get("toolName") or ""
    args = payload.get("tool_input") or payload.get("toolInput") or {}
    if tool not in ("Grep", "Glob", "Read"):
        return 0

    if tool == "Read":
        target = str(args.get("file_path") or "")
        if not any(h in target for h in SERVICE_HINTS):
            return 0
        if not any(h in target for h in SOURCE_HINTS):
            return 0
        probe, service_scope = os.path.basename(target).rsplit(".", 1)[0], True
    else:
        probe = str(args.get("pattern") or "")
        scope = f"{args.get('path') or ''} {args.get('glob') or ''}"
        service_scope = any(h in scope for h in SERVICE_HINTS) or any(
            h in probe for h in SERVICE_HINTS
        )

    if not probe:
        return 0

    targeted = _targeted(probe)
    if targeted:
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": (
                "ASK THE KG FIRST — this search has a cheaper, more complete answer:\n"
                + "\n".join(f"  - {line}" for line in targeted)
            ),
        }}))
        return 0

    try:
        ki = _index()
        hits = ki.ask(ki.terms_from_command(probe))
    except Exception:
        return 0

    # Outside a service tree, only a hit that resolves to real code is worth interrupting
    # for — a doc-term match on a doc search is noise.
    if not service_scope:
        hits = [(t, [r for r in refs if r.startswith("kg ")]) for t, refs in hits]
        hits = [(t, refs) for t, refs in hits if refs]
    if not hits:
        # Silence is the signal. Reading service source the workspace has no note on is
        # exactly the moment knowledge is being re-derived; nothing recorded it before,
        # so the same file got read line by line again next month.
        if service_scope:
            try:
                with open(os.path.join(ROOT, ".cursor", "knowledge-miss.jsonl"), "a",
                          encoding="utf-8") as fh:
                    fh.write(json.dumps({
                        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                        "tool": tool, "probe": probe[:200],
                    }) + "\n")
            except OSError:
                pass
        return 0

    body = "\n".join(f"  - {term}: {', '.join(refs)}" for term, refs in hits)
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "additionalContext": (
            "KNOWN ALREADY — the workspace documents these terms. Read/run these "
            "before searching source:\n" + body +
            "\n  (index: scripts/lib/knowledge_index.py · silence means nothing indexed)"
        ),
    }}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
