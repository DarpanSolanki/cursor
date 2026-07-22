# JIRA AiTDP Remarks — agent-help narrative, no product brand (STANDING)

**Triggered by:** SDCP-11058 AiTDP Remarks said "Used Cursor…" / short tool slogans. User corrected: field must describe **how the agent helped**, never name Cursor / Cursor IDE / product brand.

## Hard rules

1. **AiTDP Remarks (`customfield_11677`)** — 2–4 sentences on how AI assisted: analysis (logs + QA data + code path), root cause found, fix chosen, what the developer verified. Prefer plain "AI-assisted RCA…" / "assisted analysis" — **never** "Cursor", "Cursor IDE", or other IDE brand names unless the user explicitly asks.
2. **Still forbidden in remarks** — branch, SHA, processor/class, ntest/registry/e2e (same as RCA/Impact/Dev).
3. **Yes / %** — `customfield_11477` Yes when AI helped; `customfield_11676` honest % (ask user; never leave `1`).
4. **Scan** — `jira-fix-adf.py scan` rejects `\bCursor\b` / `Cursor IDE` (capital C only — verb "cursor" OK).

## Do not ask again

Apply on every SDCP AiTDP fill / JIRA enrich.
