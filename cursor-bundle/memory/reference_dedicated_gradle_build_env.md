---
name: reference-dedicated-gradle-build-env
description: Build service repos with `cd <repo> && ./gradlew build -x test` (Java 17). Historical gbuild.sh wrapper removed.
metadata: 
  node_type: memory
  type: reference
  originSessionId: 908c2836-d3df-4293-b92a-b4bde5c9c584
---

**RULE (2026-07-23):** Build with `cd <service-repo> && ./gradlew build -x test` (Java 17). The old `/home/darpan/darpan/gbuild.sh` + `.gradle-local` wrapper is **gone** — do not invent a parallel wrapper in the workspace.

**History:** Shared `~/.gradle` once had a corrupted `groovy-bom` inode (`Input/output error`) that forced an isolated `GRADLE_USER_HOME`. That path is no longer present on this box; default Gradle home is usable again. If corruption returns, restore an out-of-tree wrapper or set `GRADLE_USER_HOME` to a clean cache — do not commit a second build script into service repos.

**Perf:** Prefer a warm daemon; do NOT `kill -9` the gradle daemon (forces slow cold restarts). Box is a shared host — CPU contention is out of scope.

**Repo names:** use `trustt-*` directories (legacy `novopay-*` renamed 2026-07-15).
