#!/usr/bin/env bash
set -uo pipefail

WORKSPACE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
INITIAL_SETUP_ROOT="${WORKSPACE_ROOT}/trustt-platform-initial-setup"
FLYWAY_ROOT="${INITIAL_SETUP_ROOT}/flyway"
LOCAL_CONF="${FLYWAY_ROOT}/conf/localhost.conf"

usage() {
  cat <<'EOF'
Usage:
  initial-setup-local.sh accounting-core
  initial-setup-local.sh <service> [service...]

accounting-core runs only the dependency-led local schema set:
  masterdata actor authorization accounting batch

The wrapper never calls `localhost.sh all`. It preflights duplicate migration
versions, runs each safe service independently, continues after failures, and
leaves trustt-platform-initial-setup tracked files untouched.
EOF
}

if [[ $# -eq 0 ]]; then
  usage
  exit 2
fi

if [[ ! -x "${FLYWAY_ROOT}/flyway" || ! -f "${FLYWAY_ROOT}/localhost.sh" ]]; then
  echo "ERROR: initial-setup Flyway runner not found at ${FLYWAY_ROOT}" >&2
  exit 2
fi

if ! grep -Eq '^flyway\.url=jdbc:postgresql://(127\.0\.0\.1|localhost):5433/' "${LOCAL_CONF}"; then
  echo "ERROR: refusing non-local Flyway target in ${LOCAL_CONF}" >&2
  exit 2
fi

if ! git -C "${INITIAL_SETUP_ROOT}" diff --quiet -- flyway/localhost.sh; then
  echo "ERROR: flyway/localhost.sh differs from HEAD; restore it before using this wrapper" >&2
  exit 2
fi

if [[ "$1" == "accounting-core" ]]; then
  shift
  services=(masterdata actor authorization accounting batch "$@")
else
  services=("$@")
fi

duplicate_versions() {
  local service="$1"
  local directory file version
  local -a versions=()

  for directory in \
    "${FLYWAY_ROOT}/sli/common" \
    "${FLYWAY_ROOT}/sli/${service}/sql/product" \
    "${FLYWAY_ROOT}/sli/${service}/sql/mfi"; do
    [[ -d "$directory" ]] || continue
    for file in "$directory"/V*__*.sql; do
      [[ -e "$file" ]] || continue
      version="$(basename "$file")"
      versions+=("${version%%__*}")
    done
  done

  printf '%s\n' "${versions[@]}" | sort | uniq -d
}

failed=()
skipped=()

for service in "${services[@]}"; do
  config="${FLYWAY_ROOT}/conf/${service}.conf"
  if [[ ! -f "$config" ]]; then
    echo "SKIP ${service}: missing ${config}"
    skipped+=("${service}:missing-conf")
    continue
  fi

  duplicates="$(duplicate_versions "$service")"
  if [[ -n "$duplicates" ]]; then
    echo "SKIP ${service}: duplicate Flyway version(s): $(tr '\n' ' ' <<<"$duplicates")"
    echo "  Do not rename tracked initial-setup files locally; see GAP-077 and the canonical runbook."
    skipped+=("${service}:duplicate-version")
    continue
  fi

  echo "===== ${service} ====="
  if ! (cd "${FLYWAY_ROOT}" && sh localhost.sh "$service"); then
    failed+=("$service")
  fi
done

echo "===== initial-setup local summary ====="
echo "Completed services: $(( ${#services[@]} - ${#failed[@]} - ${#skipped[@]} ))"
echo "Failed services: ${failed[*]:-none}"
echo "Skipped services: ${skipped[*]:-none}"

if (( ${#failed[@]} > 0 || ${#skipped[@]} > 0 )); then
  exit 1
fi
