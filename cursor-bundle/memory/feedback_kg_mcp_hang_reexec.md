# The KG MCP hang was the hot-reload re-exec, not a slow query

Darpan, 2026-08-07: *"when any trustt-kg tool is called, the system starts hanging and it
gets stuck, multiple times since 3-4 days."*

## Cause

`kg_mcp_server.py` re-execs itself when `kg.py` or the server file changes on disk, so the
IDE never has to restart. That `os.execv` ran **inside `tools/call` handling, before the
response was written**. The client was left waiting on a request id the replaced process had
never seen — a permanent hang, not a slow call.

So **editing `kg.py` cost the very next MCP call, every time.** That is why it looked
intermittent and why it kept coming back after being "fixed": the timeouts wrapped around
the worker were never the bug.

A second defect sat in the same path: `main()` does `dup2(2, 1)` to keep stray prints off the
protocol stream, so the re-exec'd process would inherit **stderr** as its output channel —
alive, answering into nowhere, every subsequent call hanging forever.

## Fix

Re-exec is deferred to **between** requests, and the real pipe is restored onto fd 1 before
handover. Encoded in `scripts/lib/test_kg_mcp_no_hang_on_source_change.py`, which drives the
real protocol over pipes and fails on a lost id.

**The old test asserted that the string `os.execv` appeared in the source**, so it passed the
entire time the bug existed. A test that cannot observe the failure is not coverage.

## Consequence to remember

Sessions that edit `cursor-bundle/kg/**` were the ones that hung. If a `trustt-kg` call ever
stalls again, check whether a KG source file was just written, and prefer the CLI
(`python3 cursor-bundle/kg/bin/kg.py …`) for that one call rather than abandoning the KG.

Related: [[reference_java_probe_harness]]
