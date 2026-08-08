#!/usr/bin/env python3
"""Answer a Grep/Glob/Read from knowledge the workspace already has, before it runs.

The grep-leak hook only ever saw shell `grep`. Agent-native Grep/Glob/Read were
unhooked until wired on Cursor `preToolUse` (hooks.json) — that is how TDPQA-241
rediscovered Redis cache keys while redis-key-registry.md sat unread.

Fires when the target is service source, or when the search term itself resolves to a
code symbol in the KG — a class name typed with no path is the common case and the first
version stayed silent on it.

When `kg error` / `kg schema` returns a body for Grep/Glob, this hook **denies** the
tool call and puts the answer in `agent_message` (inject-only was ignored; agents kept
grepping ~50k tokens). Read stays allow+context. Silent when nothing to add.

Emits hookSpecificOutput.additionalContext on allow paths: plain stdout alone can miss
the model context channel depending on host.
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import time

ROOT = os.environ.get("CURSOR_PROJECT_DIR") or os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
SERVICE_HINTS = ("trustt-platform-", "novopay-platform-", "novopay-mfi-")
SOURCE_HINTS = ("/src/main/", "/src/test/", "_orc.xml", "/deploy/application/")
KG_PY = os.path.join(ROOT, "cursor-bundle", "kg", "bin", "kg.py")
# One wall budget for all inline kg.py calls in a single _targeted() — not per call.
# Without this, 2 codes + 2 columns × 6s = 24s worst-case if KG hangs.
TARGETED_BUDGET_S = 6.0

_ERROR_CODE = __import__("re").compile(r"\b(1[0-9]{5}|[3-9][0-9]{4})\b")
_SETTER = __import__("re").compile(r"\bset([A-Z][A-Za-z0-9]+)\s*\(?")


def _run_kg(*argv: str, timeout: float) -> str:
    if timeout <= 0.05:
        return ""
    env = dict(os.environ)
    env.setdefault("KG_NO_AUTO_REBUILD", "1")
    try:
        p = subprocess.run(
            [sys.executable, KG_PY, *argv],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    out = (p.stdout or p.stderr or "").strip()
    if len(out) > 1800:
        out = out[:1800] + "\n… (truncated — call MCP trustt-kg for full answer)"
    return out


def _targeted(probe: str) -> tuple[list[str], str]:
    """Return (hint lines, optional inline KG body). Shared deadline across kg calls."""
    out: list[str] = []
    bodies: list[str] = []
    deadline = time.monotonic() + TARGETED_BUDGET_S

    def _left() -> float:
        return max(0.0, deadline - time.monotonic())

    for code in list(dict.fromkeys(_ERROR_CODE.findall(probe)))[:2]:
        out.append(
            f"MCP trustt-kg → kg_error query={code}  (do NOT grep this code — ~160 tokens)"
        )
        ans = _run_kg("error", code, "--no-template", timeout=_left())
        if ans:
            bodies.append(f"=== kg_error {code} (precomputed) ===\n{ans}")
    fields = list(dict.fromkeys(_SETTER.findall(probe)))[:2]
    if fields:
        try:
            binding_path = os.path.join(ROOT, "cursor-bundle", "schema", "bindings.jsonl")
            wanted = {f[0].lower() + f[1:] for f in fields}
            seen: set[str] = set()
            with open(binding_path, encoding="utf-8") as fh:
                for line in fh:
                    if not line.strip():
                        continue
                    try:
                        row = json.loads(line)
                    except ValueError:
                        continue
                    if row.get("field") in wanted:
                        key = f"{row.get('table')}.{row.get('column')}"
                        if key not in seen:
                            seen.add(key)
                            out.append(
                                f"MCP trustt-kg → kg_schema query={key}  "
                                "(readers+writers+gate codes — do NOT grep setX)"
                            )
                            ans = _run_kg("schema", key, timeout=_left())
                            if ans:
                                bodies.append(f"=== kg_schema {key} (precomputed) ===\n{ans}")
                    if len(seen) >= 2:
                        break
        except OSError:
            pass
    return out, "\n\n".join(bodies)


def _index():
    path = os.path.join(ROOT, "scripts", "lib", "knowledge_index.py")
    spec = importlib.util.spec_from_file_location("knowledge_index", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _emit_deny(ctx: str) -> None:
    """Block Grep/Glob when KG already answered — agent_message carries the answer."""
    print(
        json.dumps(
            {
                "permission": "deny",
                "agent_message": ctx,
                "user_message": (
                    "Blocked Grep/Glob — KG already answered (kg_error/kg_schema). "
                    "Use MCP trustt-kg; do not re-grep the same code."
                ),
            }
        )
    )


def _emit_context(ctx: str) -> None:
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "additionalContext": ctx,
                }
            }
        )
    )


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

    targeted, inline = _targeted(probe)
    if targeted:
        ctx = (
            "STOP — use MCP trustt-kg instead of this Grep/Read. "
            "The answer is cheaper and more complete via the tools below.\n"
            + "\n".join(f"  - {line}" for line in targeted)
        )
        if inline:
            ctx += "\n\n" + inline
        # Deny only when we actually have a precomputed body and the tool is a search.
        if inline and tool in ("Grep", "Glob"):
            _emit_deny(ctx)
            return 0
        _emit_context(ctx)
        return 0

    try:
        ki = _index()
        hits = ki.ask(ki.terms_from_command(probe))
    except Exception:
        return 0

    if not service_scope:
        hits = [(t, [r for r in refs if r.startswith("kg ")]) for t, refs in hits]
        hits = [(t, refs) for t, refs in hits if refs]
    if not hits:
        if service_scope:
            try:
                with open(
                    os.path.join(ROOT, ".cursor", "knowledge-miss.jsonl"),
                    "a",
                    encoding="utf-8",
                ) as fh:
                    fh.write(
                        json.dumps(
                            {
                                "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                                "tool": tool,
                                "probe": probe[:200],
                            }
                        )
                        + "\n"
                    )
            except OSError:
                pass
        return 0

    body = "\n".join(f"  - {term}: {', '.join(refs)}" for term, refs in hits)
    _emit_context(
        "KNOWN ALREADY — prefer MCP trustt-kg / these docs before searching source:\n"
        + body
        + "\n  (index: scripts/lib/knowledge_index.py · silence means nothing indexed)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
