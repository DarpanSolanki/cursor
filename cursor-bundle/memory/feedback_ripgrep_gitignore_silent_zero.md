---
name: feedback_ripgrep_gitignore_silent_zero
description: "rg/grep -r from the workspace root silently returns 0 matches for service-repo files — the root .gitignore (bare * with narrow allowlists) is honored even for a read-only search."
metadata:
  node_type: memory
  type: feedback
---

**The trap:** the workspace root `.gitignore` is `*` plus a short allowlist (it tracks
automation + knowledge only, not the 17 checked-out service repos). `ripgrep` honors
`.gitignore` by default even when just searching, not committing — so `rg "someSymbol"`
run from `/home/darpan/Documents/sliProd` returns **0 matches** for a symbol that
exists in `trustt-platform-*/src/**/*.java`. No error, no warning. It reads exactly like
"this symbol doesn't exist anywhere," which is the worst failure mode because it's
indistinguishable from a true negative.

**Cost:** an agent mapping actor's caller surface burned real time on this before noticing
the search was silently empty for a class of file it should have found immediately.

**Fix:** from the workspace root, either pass `--no-ignore` to `rg`, or `cd` into the
specific repo directory first (git repos honor their own `.gitignore`, which is normal and
correct). Plain `grep -r` is unaffected — this is a `ripgrep`-specific behavior.

## Pairs with

[[feedback_batch_assert_timing_and_coverage_lookup]] — another "silently wrong, not
loudly wrong" class of tooling trap found the same session.
