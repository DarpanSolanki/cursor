#!/usr/bin/env bash
# Canonical local-folder → GitHub repo name map (org rename 2026-07).
# Source from sync scripts:  source "$ROOT/scripts/lib/github_repo_map.sh"
#
# As of 2026-07-15, local clone folders match GitHub (`trustt-*`).
# Legacy local names (`novopay-*`, old codegen folder) still map for URL helpers.
# Do NOT use this for Java package renaming.
#
# Docs: docs/setup/github-org-repo-rename-developer-guide.md

: "${UPSTREAM_ORG:=trusttai}"

# Local clone directory basename → GitHub repo name (origin fork + upstream).
# Forks under DarpanSolanki match upstream names (verified 2026-07-15).
github_upstream_repo() {
  local local_dir="$1"
  case "$local_dir" in
    # Legacy aliases (pre-folder-rename)
    novopay-platform-accounting-v2) echo "trustt-platform-accounting" ;;
    novopay-mfi-los) echo "trustt-platform-los" ;;
    novopay-platform-actor) echo "trustt-platform-actor" ;;
    novopay-platform-api-gateway) echo "trustt-platform-api-gateway" ;;
    novopay-platform-approval) echo "trustt-platform-approval" ;;
    novopay-platform-audit) echo "trustt-platform-audit" ;;
    novopay-platform-authorization) echo "trustt-platform-authorization" ;;
    novopay-platform-batch) echo "trustt-platform-batch" ;;
    novopay-platform-dependency-mgmt) echo "trustt-platform-dependency-mgmt" ;;
    novopay-platform-dms) echo "trustt-platform-dms" ;;
    novopay-platform-initial-setup) echo "trustt-platform-initial-setup" ;;
    novopay-platform-lib) echo "trustt-platform-lib" ;;
    novopay-platform-masterdata-management) echo "trustt-platform-masterdata-management" ;;
    novopay-platform-notifications) echo "trustt-platform-notifications" ;;
    novopay-platform-payments) echo "trustt-platform-payments" ;;
    novopay-platform-simulators) echo "trustt-platform-simulators" ;;
    novopay-platform-task) echo "trustt-platform-task" ;;
    novopay-platform-webapp) echo "trustt-platform-webapp" ;;
    trustt-platform-ai-codegen-artifacts) echo "trustt-platform-ai-codegen-artifacts-java" ;;
    novopay-*) echo "trustt-${local_dir#novopay-}" ;;
    trustt-*) echo "$local_dir" ;;
    *) echo "$local_dir" ;;
  esac
}

# Alias — forks use the same GitHub name as upstream.
github_fork_repo() {
  github_upstream_repo "$1"
}

github_upstream_url() {
  local local_dir="$1"
  echo "https://github.com/${UPSTREAM_ORG}/$(github_upstream_repo "$local_dir").git"
}

github_fork_url() {
  local local_dir="$1"
  local user="${2:-DarpanSolanki}"
  echo "https://github.com/${user}/$(github_fork_repo "$local_dir").git"
}
