# Upstream fetch stamp must not lie

**Symptom (TDPQA-207 session):** `kg fixed-elsewhere` returned `NOT_VERIFIED_STALE_REFS` (~53h) even after `git fetch upstream` on accounting. Agents looked "stuck" waiting on MCP/CLI.

**Cause:** `scripts/lib/branch_train.py` `fetch_age_hours` preferred `.git/novopay-upstream-fetch.stamp` over real upstream ref mtimes. Raw `git fetch` / old `git-fetch-all.sh` did **not** rewrite the stamp → false STALE → REUSE_FORBIDDEN / empty MCP answers / long retries.

**Fix (2026-07-29):**
1. `fetch_age_hours` uses freshest of stamp + upstream refs + upstream-tagged FETCH_HEAD.
2. `git-fetch-all.sh` writes stamp after successful upstream fetch.
3. Unit: `test_stale_stamp_does_not_hide_fresh_upstream_ref`.

**Agent rule:** Before trusting fixed-elsewhere STALE, run `bash scripts/bin/git-fetch-all.sh` (or `ensure_upstream_fresh`). Prefer CLI `timeout 45 kg.py fixed-elsewhere` over unbounded MCP when remotes may be cold.
