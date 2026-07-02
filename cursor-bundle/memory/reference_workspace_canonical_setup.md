---
name: reference_workspace_canonical_setup
description: Canonical paths + self-contained setup for the darpan LMS workspace after the 2026-06-10 relocation cleanup.
metadata: 
  node_type: memory
  type: reference
  originSessionId: 7fc30f42-df07-4d0a-8093-68fff3c6147e
---

The workspace lives entirely at **`/home/darpan/darpan/`** (user `darpan`); memory at **`/home/darpan/.claude/projects/-home-darpan-darpan/memory/`**. It was relocated across `/home/aitdp/` → `/home/rnd/` → `/home/darpan/` and the config had not followed — fixed 2026-06-10.

Setup is **self-contained: no dependency on any other folder or user.** Verified:
- All `/home/aitdp/darpan` + `/home/rnd/darpan` refs across CLAUDE.md, `claude/`, `.claude/skills`, `scripts/`, settings → normalized to `/home/darpan/darpan`. Audit is clean (zero foreign-home deps).
- `.claude/settings.json`: discipline-gate hook now uses `$CLAUDE_PROJECT_DIR/.claude/hooks/...` (relocation-proof, was pointed at dead `/home/rnd/darpan`); db-tools allow-paths corrected to `/home/darpan/darpan`.
- `.claude/settings.local.json`: memory-read perm → `/home/darpan/.claude/...`; broad `Read(//home/aitdp/**)` → `Read(//home/darpan/**)`; redundant `/home/aitdp/workspace/...UD docx` additionalDirectory removed (UD doc mirrored in-tree at `UDs/`).
- **DB works**: `claude/db-tools/bin/db-query.sh mfi_qa3` → YugabyteDB responds; creds + `.venv` are in-tree.
- **Jira works** (read-only): `mcp__aitdp-jira__jira_*`. Writes refused per boundary.
- **KG** (`mcp__kms-kb__*`, namespace is `kms-kb` not `kms-aitdp`): supplement-only; service was down (connection refused) on 2026-06-10 — not a dependency, brain docs are the substrate.
- **Build**: `./gbuild.sh <repo> build -x test` (in-boundary `GRADLE_USER_HOME=.gradle-local`). See [[reference_dedicated_gradle_build_env]].

Cleanup done same day: deleted 19 `.aitdp/logs` dirs, `.gradle-verify`, and unreferenced `downloads/oracleJdk-26` (~383 MB reclaimed); archived loose `dfc-*`/`DFC-*`/`sdcp-10080-*` task docs to `claude/archive/`.

Related: [[feedback_darpan_git_via_darpansolanki]], [[feedback_fetch_latest_before_checking_code]].
