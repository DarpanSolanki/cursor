#!/bin/bash
set -euo pipefail
IFS=$'\n\t'

########################################
# CONFIG
########################################
# Branch: first argument, or default below
BRANCH="${1:-mfi_integration_v3.2.8.4}"
UPSTREAM_ORG="khoslalabs"

########################################
# INPUT (args: branch [username] [base_path])
########################################
if [[ -z "${2:-}" ]]; then
  read -rp "Enter your GitHub username: " USERNAME
else
  USERNAME="$2"
fi
if [[ -z "${3:-}" ]]; then
  read -rp "Enter base path where repos are stored: " BASE_PATH
else
  BASE_PATH="$3"
fi

if [[ ! -d "$BASE_PATH" ]]; then
  echo "❌ Base path does not exist"
  exit 1
fi

cd "$BASE_PATH"

echo
echo "🔎 Scanning for git repositories..."
echo

########################################
# FIND ALL REPOS
########################################
REPOS=$(find . -maxdepth 1 -type d -not -path '.')

########################################
# PROCESS REPOS
########################################
for dir in $REPOS; do

repo=$(basename "$dir")

if [[ ! -d "$repo/.git" ]]; then
  continue
fi

echo
echo "================================="
echo "▶ Processing $repo"
echo "================================="

cd "$repo"

########################################
# FIX ORIGIN
########################################
EXPECTED_ORIGIN="https://github.com/${USERNAME}/${repo}.git"

if git remote | grep -qx origin; then
  git remote set-url origin "$EXPECTED_ORIGIN"
else
  git remote add origin "$EXPECTED_ORIGIN"
fi

########################################
# ADD UPSTREAM IF MISSING
########################################
EXPECTED_UPSTREAM="https://github.com/${UPSTREAM_ORG}/${repo}.git"

if ! git remote | grep -qx upstream; then
  echo "➕ Adding upstream"
  git remote add upstream "$EXPECTED_UPSTREAM"
fi

########################################
# FETCH
########################################
git fetch origin --prune
git fetch upstream --prune

########################################
# SMART BRANCH HANDLING
########################################
echo "🔍 Checking branch $BRANCH"

if git show-ref --verify --quiet "refs/heads/$BRANCH"; then

  echo "✔ Local branch exists"
  git checkout "$BRANCH"

elif git ls-remote --heads origin "$BRANCH" | grep -q "$BRANCH"; then

  echo "✔ Branch found in origin"
  git checkout -b "$BRANCH" "origin/$BRANCH"

elif git ls-remote --heads upstream "$BRANCH" | grep -q "$BRANCH"; then

  echo "✔ Branch found in upstream → creating branch"
  git checkout -b "$BRANCH" "upstream/$BRANCH"
  git push -u origin "$BRANCH"

else

  echo "⚠ Branch does not exist anywhere → skipping"
  cd ..
  continue

fi

########################################
# SYNC WITH ORIGIN
########################################
git pull --rebase origin "$BRANCH" || true

########################################
# REBASE UPSTREAM
########################################
if git ls-remote --heads upstream "$BRANCH" | grep -q "$BRANCH"; then
  git rebase "upstream/$BRANCH" || {
    echo "⚠ Rebase conflict — manual fix required"
    cd ..
    continue
  }
fi

########################################
# PUSH
########################################
git push --force-with-lease origin "$BRANCH"

echo "✅ DONE"

cd ..

done

echo
echo "🎉 All repositories processed successfully"
