---
name: feedback_workspace_hygiene
description: "Keep the workspace clutter-free and disk-lean — write scratch to /tmp not the repo tree; delete any temp file you create once the task is done; prune stale temp/log/scratch with scripts/bin/cleanup.sh. Never delete curated knowledge, code, build caches, or anything you didn't create without confirmation."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 7fc30f42-df07-4d0a-8093-68fff3c6147e
---

Keep `/home/darpan/Documents/sliProd/` clean and disk-lean — temp/scratch/stale files must not accumulate.

**Prevent at the source:** write scratch (build logs, ad-hoc SQL output, draft text, intermediate dumps) to **`/tmp`** (ephemeral, OS-cleared, outside the repo tree) — NOT inside the workspace. If a tool must write a temp file into the tree, **delete it in the same task once done** (the KG `build.sh` already `rm`s its `.raw.jsonl`/`orch.err` — match that pattern).

**Prune periodically:** `scripts/bin/cleanup.sh` removes only an explicit **allow-list of regenerable scratch** — editor backups (`*~`/`*.swp`/`*.orig`/`*.bak`/`*.rej`), `.aitdp/logs/*.log`, KG build leftovers, and `/tmp` session scratch — older than N days (default 7). **Dry-run by default; `--confirm` to delete; `--days N` to set the age.** Run it when you notice clutter or at the end of a heavy session.

**NEVER delete (without explicit user confirmation):** curated knowledge (`claude/**/*.md`, skills, memory), source code, the KG artifacts (`kg.db`/`kg.jsonl`/`stats.json` — regenerable but keep), and the `.gradle-local` build cache (787M but *needed* — deleting forces a full re-download; it is NOT stale). `claude/` is **not** under git, so deletions there are permanent — be conservative. Anything you didn't create, or that contradicts how it was described, is off-limits to auto-delete.

**Why:** unbounded scratch inflates disk and clutters searches/greps; but blind deletion of curated docs or build caches is far costlier than the disk it saves. The allow-list + dry-run + "scratch goes to /tmp" balances both.

**Boundary:** all deletion stays inside `/home/darpan/Documents/sliProd/` + `/tmp` session scratch (CLAUDE.md Rule 1, [[feedback_darpan_boundary]]). Pairs with [[feedback_keep_knowledge_current]] (no loose markdown islands either).
