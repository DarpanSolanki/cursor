---
name: feedback_build_before_push
description: "Build green before every push, and \"built green\" is necessary but NOT sufficient for \"done\". Build via ./gbuild.sh <repo> build -x test (in-boundary Gradle home). Status stays \"pushed; awaiting QA retest\" until QA confirms — never say fixed/completed/done before that."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 7fc30f42-df07-4d0a-8093-68fff3c6147e
---

**Build green before every push.** Run `./gbuild.sh <repo> build -x test` (Java 17, in-boundary `GRADLE_USER_HOME=.gradle-local`) and confirm it passes before pushing. For state-machine / CAS / posting changes, also paste the expected/actual **DB-state delta** (main-vs-branch) — "built green" is necessary, not sufficient.

**Why:** A green build catches compile/contract breakage cheaply, before it reaches a shared branch. But it proves nothing about runtime correctness — only QA retest does.

**How to apply (verification gate):** build green + commit + push + changelog **≠ "done"**. Status is always **"pushed; awaiting QA retest"** until QA confirms. Do **not** say "fixed", "completed", or "done" before that. CLAUDE.md §0 Rules 4–5. Pairs with [[feedback_qa_handoff_package]], [[reference_dedicated_gradle_build_env]], [[feedback_darpan_git_via_darpansolanki]].
