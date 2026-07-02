---
name: reference-dedicated-gradle-build-env
description: Build darpan repos via ./gbuild.sh (dedicated in-boundary GRADLE_USER_HOME); shared ~/.gradle has a corrupted inode.
metadata: 
  node_type: memory
  type: reference
  originSessionId: 908c2836-d3df-4293-b92a-b4bde5c9c584
---

**RULE: NEVER run bare `./gradlew` or `JAVA_HOME=… ./gradlew` in a darpan repo.** Bare gradlew
uses `GRADLE_USER_HOME=/home/darpan/.gradle` (shared/corruptible, no warm daemon) → cold,
slow (~4–5 min) builds every time. ALWAYS build through `gbuild.sh`, which is the only
sanctioned build command here. Running bare gradlew repeatedly was the cause of the
"why are builds so slow" complaint.

Build any darpan repo with `/home/darpan/darpan/gbuild.sh <repo-dir> <gradle args>`
(e.g. `./gbuild.sh novopay-platform-accounting-v2 build -x test`). It sets
`GRADLE_USER_HOME=/home/darpan/darpan/.gradle-local` + `JAVA_HOME=java-17` so we use
our OWN cache + warm daemon, never the shared `~/.gradle`.

**Why:** `/home/darpan/.gradle/caches/modules-2/files-2.1/org.apache.groovy/groovy-bom/4.0.22`
is a filesystem-corrupted directory (`ls`/`rm` return `Input/output error`, shows as
`d?????????`). Any build using the default `~/.gradle` fails at dependency resolution with
"Could not download groovy-bom-4.0.22.pom". `rm` can't remove it — needs infra `fsck`.

**Perf:** `.gradle-local` (≈726M, pre-warmed) gives cold compile ≈4m45s, warm incremental ≈41s.
Box is a shared 16-core host (load often >16 from other users: aitdp/rnd) — CPU contention
can't be fixed from gradle config; only the cache/daemon isolation is in our scope.
Do NOT `kill -9` the gradle daemon (forces slow cold restarts). Config lives in
`.gradle-local/gradle.properties` (daemon on, bounded -Xmx2g).
