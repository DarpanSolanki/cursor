---
name: feedback_changelog
description: "Changelog format — a single claude/changelog/CHANGELOG.md, newest-first, short 2-line entries; no per-entry files under entries/ (that folder was deleted 2026-05-07). Detail lives in git show <sha>. Prepend an entry in the same task turn as every commit."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 7fc30f42-df07-4d0a-8093-68fff3c6147e
---

The audit log is a **single file**: `claude/changelog/CHANGELOG.md`, newest-first. Entries are **short — 2 lines** (the user does not want long entries); the full detail lives in `git show <sha>`. There is **no per-entry detail file under `entries/`** — that folder was deleted 2026-05-07.

**Why:** One queryable file keeps the audit log scannable and feeds the system KG case graph (each CHANGELOG entry becomes a `case` node). Long entries duplicate what `git show` already holds.

**How to apply:** Prepend a 2-line entry **in the same task turn as every commit** (author = `DarpanSolanki <darpan@novopay.in>`), via the **`changelog-add`** skill — which then runs `claude/kg/bin/build.sh` to fold the entry into the case graph. .cursorrules §0 Rule 4. Pairs with [[feedback_keep_knowledge_current]], [[reference_system_kg]].
