---
name: feedback_brain_first_then_code
description: "Brain-first, code-second — answer from the claude/ brain docs (and the precedence ladder: memory → brain docs → skills → live data → system KG → service code) before grepping service code. Stops the re-read-700-line-files-every-session pattern."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 7fc30f42-df07-4d0a-8093-68fff3c6147e
---

Answer from the `/home/darpan/darpan/claude/` brain docs **before** grepping service code. Follow the precedence ladder (CLAUDE.md §2), descending only when the layer above is exhausted:
1. **Memory** (this dir, indexed by MEMORY.md) — who the user is, standing corrections, conventions.
2. **Brain docs** (`claude/`) — authored understanding of the LMS (engines, accounting flows, platform contracts, runbooks, per-service one-pagers). Use the `brain-find` skill to map a flow keyword → the right doc.
3. **Skills** — encode *how* to do recurring work; prefer them over re-deriving a procedure.
4. **Live data** — DB (`db-access`/`lan-360`), APM/Git/Jira read-only MCP — to ground a claim against reality.
5. **System KG** (`claude/kg/`) — flow spine, cross-service deps, impact, case precedent; orient here before grepping.
6. **Service code** (the checkouts) — the final fallback; verify against code before any state-machine/CAS/posting change.

**Why:** Re-reading large files every session is slow and error-prone; the brain docs are the curated substrate the KG indexes. Brain-first keeps responses fast and consistent.

**How to apply:** Start every investigation with `brain-find` / the relevant brain doc, then the KG, then code only to verify or when the docs are exhausted. When you find new implementation or stale docs, update the single relevant brain doc in the same turn (per [[feedback_keep_knowledge_current]]). CLAUDE.md §0 Rule 2, §2.
