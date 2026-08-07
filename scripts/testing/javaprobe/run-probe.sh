#!/usr/bin/env bash
# Compile and run a plain-Java probe against a service's real test runtime classpath.
#
#   scripts/testing/javaprobe/run-probe.sh <repo> <probe.java>
#   scripts/testing/javaprobe/run-probe.sh trustt-platform-accounting \
#       scripts/testing/foreclosure/probes/ShgSweepProbe.java
#
# Why this exists: `./gradlew test` cannot run in these service repos. 527 of 547 accounting
# tests use @RunWith(JUnitPlatform.class), a runner removed in junit-platform 1.11, while the
# Spring Boot BOM resolves platform-commons to 1.12.x. JUnit discovery therefore dies with
# NoSuchMethodError: ReflectionUtils.returnsVoid before a single assertion runs — and it dies
# on *every* class, so --tests cannot dodge it. Realigning that stack is a plugin-managed,
# cross-repo decision, not something to slip into a bug fix.
#
# A probe sidesteps discovery entirely: real production classes, real classpath, a main()
# that exits non-zero on failure. Good enough to prove red -> green on a processor in seconds,
# which is what a same-day fix actually needs.
#
# The classpath is cached per repo; pass --refresh after a dependency change.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"

REFRESH=""
ARGS=()
for a in "$@"; do
  case "$a" in
    --refresh) REFRESH=1 ;;
    *) ARGS+=("$a") ;;
  esac
done

if [[ ${#ARGS[@]} -lt 2 ]]; then
  sed -n '2,20p' "$0" | sed 's/^# \{0,1\}//'
  exit 1
fi

REPO="${ARGS[0]}"
PROBE="${ARGS[1]}"
REPO_DIR="$ROOT/$REPO"
[[ -d "$REPO_DIR" ]] || { echo "No such repo: $REPO_DIR" >&2; exit 1; }
[[ -f "$ROOT/$PROBE" ]] && PROBE="$ROOT/$PROBE"
[[ -f "$PROBE" ]] || { echo "No such probe: $PROBE" >&2; exit 1; }

CACHE_DIR="$ROOT/scripts/testing/javaprobe/.cache"
mkdir -p "$CACHE_DIR"
CP_FILE="$CACHE_DIR/$REPO.cp"

if [[ -n "$REFRESH" || ! -s "$CP_FILE" ]]; then
  echo "=== resolving test runtime classpath for $REPO (cached at $CP_FILE) ==="
  INIT="$REPO_DIR/tmp-printcp.init.gradle"
  if [[ ! -f "$INIT" ]]; then
    INIT="$CACHE_DIR/printcp.init.gradle"
    cat > "$INIT" <<'EOF'
allprojects {
    tasks.register("printTestRuntimeClasspath") {
        doLast { println sourceSets.test.runtimeClasspath.asPath }
    }
}
EOF
  fi
  ( cd "$REPO_DIR" && ./gradlew -q --init-script "$INIT" printTestRuntimeClasspath 2>/dev/null ) \
    | tail -1 > "$CP_FILE"
  [[ -s "$CP_FILE" ]] || { echo "Failed to resolve classpath for $REPO" >&2; exit 1; }
fi

echo "=== compiling main classes ($REPO) ==="
( cd "$REPO_DIR" && ./gradlew -q compileJava )

OUT="$CACHE_DIR/classes"
mkdir -p "$OUT"
CP="$(cat "$CP_FILE")"

echo "=== javac $(basename "$PROBE") ==="
javac -nowarn -cp "$CP" -d "$OUT" "$PROBE"

MAIN="$(basename "$PROBE" .java)"
echo "=== run $MAIN ==="
java -cp "$OUT:$CP" "$MAIN"
