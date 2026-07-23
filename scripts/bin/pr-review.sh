#!/usr/bin/env bash
# Read-only GitHub PR evidence collector. Never checks out, comments, or mutates a PR.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

usage() {
  cat <<'EOF'
Usage:
  pr-review.sh <PR_URL|owner/repo#number> [--jira KEY] [--env NAME] [--out DIR]

Collect immutable, read-only pull-request evidence using GitHub CLI.

Arguments:
  PR_URL                 https://github.com/OWNER/REPO/pull/NUMBER
  owner/repo#number      Compact pull-request identifier

Options:
  --jira KEY             Record the related Jira key (no Jira request is made)
  --env NAME             Record the target environment (for example local, QA3, UAT)
  --out DIR              Output directory inside the workspace
  -h, --help             Show this help

Default output:
  scripts/scratch/pr-review/OWNER-REPO-NUMBER-UTC_TIMESTAMP/

Artifacts:
  metadata.json, files.json, commits.json, checks.json, diff.patch,
  freshness.json, provenance.json, errors.json, manifest.json

Safety:
  This command only uses read-only `gh api` and `gh pr diff` operations.
  It never checks out a branch or posts to GitHub/Jira. Output is retained for
  the review agent; remove only this task's directory after evidence is consumed.
EOF
}

die() {
  printf 'pr-review: %s\n' "$*" >&2
  exit 2
}

command -v gh >/dev/null 2>&1 || die "GitHub CLI (gh) is required"
command -v python3 >/dev/null 2>&1 || die "python3 is required"

if [[ $# -eq 0 ]]; then
  usage >&2
  exit 2
fi

case "${1:-}" in
  -h|--help)
    usage
    exit 0
    ;;
esac

pr_input="$1"
shift
jira=""
environment=""
out_arg=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --jira)
      [[ $# -ge 2 && -n "$2" ]] || die "--jira requires a value"
      jira="$2"
      shift 2
      ;;
    --env)
      [[ $# -ge 2 && -n "$2" ]] || die "--env requires a value"
      environment="$2"
      shift 2
      ;;
    --out)
      [[ $# -ge 2 && -n "$2" ]] || die "--out requires a value"
      out_arg="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      die "unknown argument: $1"
      ;;
  esac
done

owner=""
repo=""
number=""
if [[ "$pr_input" =~ ^https://github\.com/([^/]+)/([^/]+)/pull/([0-9]+)/?$ ]]; then
  owner="${BASH_REMATCH[1]}"
  repo="${BASH_REMATCH[2]}"
  number="${BASH_REMATCH[3]}"
elif [[ "$pr_input" =~ ^([^/[:space:]]+)/([^/#[:space:]]+)#([0-9]+)$ ]]; then
  owner="${BASH_REMATCH[1]}"
  repo="${BASH_REMATCH[2]}"
  number="${BASH_REMATCH[3]}"
else
  die "invalid PR identifier; use a GitHub PR URL or owner/repo#number"
fi

[[ "$owner" =~ ^[A-Za-z0-9_.-]+$ ]] || die "invalid GitHub owner"
[[ "$repo" =~ ^[A-Za-z0-9_.-]+$ ]] || die "invalid GitHub repository"
[[ "$number" =~ ^[0-9]+$ ]] || die "invalid pull-request number"

if ! gh auth status >/dev/null 2>&1; then
  die "GitHub CLI is not authenticated; run gh auth login outside this collector"
fi

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
if [[ -z "$out_arg" ]]; then
  out_arg="$ROOT/scripts/scratch/pr-review/${owner}-${repo}-${number}-${timestamp}"
elif [[ "$out_arg" != /* ]]; then
  out_arg="$PWD/$out_arg"
fi

out="$(
  ROOT="$ROOT" OUT_ARG="$out_arg" python3 - <<'PY'
import os
from pathlib import Path

root = Path(os.environ["ROOT"]).resolve()
out = Path(os.environ["OUT_ARG"]).resolve()
try:
    out.relative_to(root)
except ValueError:
    raise SystemExit("pr-review: --out must resolve inside the workspace")
print(out)
PY
)" || exit 2

if [[ -e "$out" ]] && [[ -n "$(ls -A "$out" 2>/dev/null || true)" ]]; then
  die "output directory already exists and is not empty: $out"
fi
mkdir -p "$out"

raw_pr="$out/.raw-pr.json"
raw_pr_final="$out/.raw-pr-final.json"
raw_pull_ref="$out/.raw-pull-ref.json"
raw_pull_ref_final="$out/.raw-pull-ref-final.json"
raw_base_ref="$out/.raw-base-ref.json"
raw_base_ref_final="$out/.raw-base-ref-final.json"
raw_files="$out/.raw-files.json"
raw_commits="$out/.raw-commits.json"
raw_check_runs="$out/.raw-check-runs.json"
raw_status="$out/.raw-status.json"
errors_ndjson="$out/.errors.ndjson"
: >"$errors_ndjson"

record_error() {
  local stage="$1"
  local required="$2"
  local message_file="$3"
  STAGE="$stage" REQUIRED="$required" MESSAGE_FILE="$message_file" \
    python3 - <<'PY' >>"$errors_ndjson"
import json
import os
import re
from pathlib import Path

text = Path(os.environ["MESSAGE_FILE"]).read_text(encoding="utf-8", errors="replace")
text = re.sub(r"\x1b\[[0-9;]*m", "", text).strip()
print(json.dumps({
    "stage": os.environ["STAGE"],
    "required": os.environ["REQUIRED"] == "true",
    "message": text[-2000:],
}, sort_keys=True))
PY
}

run_required() {
  local stage="$1"
  local destination="$2"
  shift 2
  local stderr_file="$out/.${stage}.stderr"
  local attempt
  for attempt in 1 2 3; do
    if "$@" >"$destination" 2>"$stderr_file"; then
      rm -f "$stderr_file"
      return 0
    fi
    if [[ "$attempt" -lt 3 ]]; then
      sleep "$attempt"
    fi
  done
  record_error "$stage" true "$stderr_file"
  normalize_errors_only
  printf 'pr-review: required collection stage failed after 3 attempts: %s\n' "$stage" >&2
  printf 'pr-review: diagnostic artifacts retained at %s\n' "$out" >&2
  exit 3
}

normalize_errors_only() {
  ERRORS_NDJSON="$errors_ndjson" ERRORS_JSON="$out/errors.json" python3 - <<'PY'
import json
import os
from pathlib import Path

src = Path(os.environ["ERRORS_NDJSON"])
items = [
    json.loads(line)
    for line in src.read_text(encoding="utf-8").splitlines()
    if line.strip()
]
Path(os.environ["ERRORS_JSON"]).write_text(
    json.dumps(items, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
)
PY
}

repo_slug="$owner/$repo"
api_headers=(-H "Accept: application/vnd.github+json")

run_required metadata "$raw_pr" \
  gh api "${api_headers[@]}" "repos/$repo_slug/pulls/$number"

readarray -t pr_refs < <(
  RAW_PR="$raw_pr" python3 - <<'PY'
import json
import os
from pathlib import Path
from urllib.parse import quote

data = json.loads(Path(os.environ["RAW_PR"]).read_text(encoding="utf-8"))
print(data["base"]["repo"]["full_name"])
print(quote(data["base"]["ref"], safe=""))
PY
)
base_repo_slug="${pr_refs[0]}"
base_ref_encoded="${pr_refs[1]}"

run_required pull_ref "$raw_pull_ref" \
  gh api "${api_headers[@]}" "repos/$repo_slug/git/ref/pull/$number/head"

run_required base_ref "$raw_base_ref" \
  gh api "${api_headers[@]}" "repos/$base_repo_slug/git/ref/heads/$base_ref_encoded"

run_required files "$raw_files" \
  gh api --paginate "${api_headers[@]}" \
    "repos/$repo_slug/pulls/$number/files?per_page=100" --jq '.[]'

run_required commits "$raw_commits" \
  gh api --paginate "${api_headers[@]}" \
    "repos/$repo_slug/pulls/$number/commits?per_page=100" --jq '.[]'

head_sha="$(
  RAW_PR="$raw_pr" python3 - <<'PY'
import json
import os
from pathlib import Path

data = json.loads(Path(os.environ["RAW_PR"]).read_text(encoding="utf-8"))
print(data["head"]["sha"])
PY
)"

checks_ok=true
checks_stderr="$out/.checks.stderr"
if ! gh api --paginate "${api_headers[@]}" \
  "repos/$repo_slug/commits/$head_sha/check-runs?per_page=100" \
  --jq '.check_runs[]' \
  >"$raw_check_runs" 2>"$checks_stderr"; then
  checks_ok=false
  : >"$raw_check_runs"
  record_error checks false "$checks_stderr"
fi
rm -f "$checks_stderr"

status_ok=true
status_stderr="$out/.status.stderr"
if ! gh api "${api_headers[@]}" "repos/$repo_slug/commits/$head_sha/status" \
  >"$raw_status" 2>"$status_stderr"; then
  status_ok=false
  printf '{"state":"unknown","statuses":[]}\n' >"$raw_status"
  record_error statuses false "$status_stderr"
fi
rm -f "$status_stderr"

run_required diff "$out/diff.patch" \
  gh api -H "Accept: application/vnd.github.v3.diff" \
    "repos/$repo_slug/pulls/$number"

run_required pull_ref_final "$raw_pull_ref_final" \
  gh api "${api_headers[@]}" "repos/$repo_slug/git/ref/pull/$number/head"

run_required base_ref_final "$raw_base_ref_final" \
  gh api "${api_headers[@]}" "repos/$base_repo_slug/git/ref/heads/$base_ref_encoded"

run_required metadata_final "$raw_pr_final" \
  gh api "${api_headers[@]}" "repos/$repo_slug/pulls/$number"

ROOT="$ROOT" OUT="$out" INPUT="$pr_input" OWNER="$owner" REPO="$repo" \
NUMBER="$number" JIRA="$jira" ENVIRONMENT="$environment" \
CHECKS_OK="$checks_ok" STATUS_OK="$status_ok" \
RAW_PR="$raw_pr" RAW_PR_FINAL="$raw_pr_final" \
RAW_PULL_REF="$raw_pull_ref" RAW_PULL_REF_FINAL="$raw_pull_ref_final" \
RAW_BASE_REF="$raw_base_ref" RAW_BASE_REF_FINAL="$raw_base_ref_final" \
RAW_FILES="$raw_files" RAW_COMMITS="$raw_commits" \
RAW_CHECK_RUNS="$raw_check_runs" RAW_STATUS="$raw_status" \
ERRORS_NDJSON="$errors_ndjson" python3 - <<'PY'
import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

out = Path(os.environ["OUT"])


def read_json(name: str):
    return json.loads(Path(os.environ[name]).read_text(encoding="utf-8"))


def read_ndjson(name: str):
    return [
        json.loads(line)
        for line in Path(os.environ[name]).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


pr = read_json("RAW_PR")
pr_final = read_json("RAW_PR_FINAL")
pull_ref = read_json("RAW_PULL_REF")
pull_ref_final = read_json("RAW_PULL_REF_FINAL")
base_ref = read_json("RAW_BASE_REF")
base_ref_final = read_json("RAW_BASE_REF_FINAL")
files_raw = read_ndjson("RAW_FILES")
commits_raw = read_ndjson("RAW_COMMITS")
check_runs_raw = read_ndjson("RAW_CHECK_RUNS")
status_raw = read_json("RAW_STATUS")
collected_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

expected_repo = f"{os.environ['OWNER']}/{os.environ['REPO']}".lower()
actual_repo = pr.get("base", {}).get("repo", {}).get("full_name", "").lower()
if int(pr.get("number", -1)) != int(os.environ["NUMBER"]) or actual_repo != expected_repo:
    raise SystemExit("PR metadata does not match requested repository/number")

initial_base_sha = pr["base"]["sha"]
initial_head_sha = pr["head"]["sha"]
final_base_sha = pr_final["base"]["sha"]
final_head_sha = pr_final["head"]["sha"]
initial_pull_ref_sha = pull_ref["object"]["sha"]
final_pull_ref_sha = pull_ref_final["object"]["sha"]
initial_base_ref_sha = base_ref["object"]["sha"]
final_base_ref_sha = base_ref_final["object"]["sha"]

freshness = {
    "schema_version": 1,
    "status": "VERIFIED",
    "base": {
        "repository": pr["base"]["repo"]["full_name"],
        "ref": pr["base"]["ref"],
        "metadata_initial_sha": initial_base_sha,
        "metadata_final_sha": final_base_sha,
        "git_ref_initial_sha": initial_base_ref_sha,
        "git_ref_final_sha": final_base_ref_sha,
    },
    "head": {
        "repository": (pr["head"].get("repo") or {}).get("full_name"),
        "ref": pr["head"]["ref"],
        "metadata_initial_sha": initial_head_sha,
        "metadata_final_sha": final_head_sha,
        "pull_ref_initial_sha": initial_pull_ref_sha,
        "pull_ref_final_sha": final_pull_ref_sha,
    },
}

# Freshness (Upgrade 9):
# - Head: metadata + refs/pull/N/head must agree (stable during collection).
# - Base: compare only the PR's base.sha (metadata) across the collection window.
#   Live branch tip (git_ref_*) may advance after merge — informational, not STALE.
head_shas = {
    initial_head_sha,
    final_head_sha,
    initial_pull_ref_sha,
    final_pull_ref_sha,
}
base_meta_shas = {initial_base_sha, final_base_sha}
same_identity = (
    pr_final.get("number") == pr.get("number")
    and pr_final.get("base", {}).get("repo", {}).get("full_name")
    == pr.get("base", {}).get("repo", {}).get("full_name")
    and pr_final.get("base", {}).get("ref") == pr.get("base", {}).get("ref")
    and pr_final.get("head", {}).get("ref") == pr.get("head", {}).get("ref")
)
freshness["base"]["tip_advanced"] = (
    initial_base_ref_sha != initial_base_sha or final_base_ref_sha != initial_base_sha
)
if len(base_meta_shas) != 1 or len(head_shas) != 1 or not same_identity:
    freshness["status"] = "STALE"
    (out / "freshness.json").write_text(
        json.dumps(freshness, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    raise SystemExit(
        "PR base/head changed or refs disagreed during collection; "
        "discard this evidence and run the collector again"
    )

metadata = {
    "schema_version": 1,
    "collected_at": collected_at,
    "input": os.environ["INPUT"],
    "jira": os.environ["JIRA"] or None,
    "environment": os.environ["ENVIRONMENT"] or None,
    "repository": pr["base"]["repo"]["full_name"],
    "number": pr["number"],
    "url": pr["html_url"],
    "title": pr["title"],
    "body": pr.get("body") or "",
    "state": pr["state"],
    "draft": bool(pr.get("draft")),
    "author": (pr.get("user") or {}).get("login"),
    "base": {
        "ref": pr["base"]["ref"],
        "sha": pr["base"]["sha"],
        "repository": pr["base"]["repo"]["full_name"],
    },
    "head": {
        "ref": pr["head"]["ref"],
        "sha": pr["head"]["sha"],
        "repository": (pr["head"].get("repo") or {}).get("full_name"),
    },
    "mergeable": pr.get("mergeable"),
    "mergeable_state": pr.get("mergeable_state"),
    "created_at": pr.get("created_at"),
    "updated_at": pr.get("updated_at"),
    "additions": pr.get("additions"),
    "deletions": pr.get("deletions"),
    "changed_files": pr.get("changed_files"),
    "labels": sorted(label["name"] for label in pr.get("labels", [])),
    "requested_reviewers": sorted(
        reviewer["login"] for reviewer in pr.get("requested_reviewers", [])
    ),
}

files = [
    {
        "path": item["filename"],
        "status": item["status"],
        "additions": item["additions"],
        "deletions": item["deletions"],
        "changes": item["changes"],
        "previous_path": item.get("previous_filename"),
    }
    for item in files_raw
]
files.sort(key=lambda item: item["path"])

commits = []
for index, item in enumerate(commits_raw, start=1):
    commit = item.get("commit") or {}
    author = commit.get("author") or {}
    committer = commit.get("committer") or {}
    commits.append({
        "position": index,
        "sha": item["sha"],
        "message": commit.get("message") or "",
        "author": author.get("name"),
        "author_date": author.get("date"),
        "committer": committer.get("name"),
        "committer_date": committer.get("date"),
        "url": item.get("html_url"),
    })

check_runs = []
for item in check_runs_raw:
    check_runs.append({
        "name": item.get("name"),
        "status": item.get("status"),
        "conclusion": item.get("conclusion"),
        "started_at": item.get("started_at"),
        "completed_at": item.get("completed_at"),
        "url": item.get("html_url"),
        "app": (item.get("app") or {}).get("slug"),
    })
check_runs.sort(key=lambda item: (
    item.get("name") or "",
    item.get("app") or "",
    item.get("url") or "",
))

statuses = [
    {
        "context": item.get("context"),
        "state": item.get("state"),
        "description": item.get("description"),
        "target_url": item.get("target_url"),
        "created_at": item.get("created_at"),
        "updated_at": item.get("updated_at"),
    }
    for item in status_raw.get("statuses", [])
]
statuses.sort(key=lambda item: (item.get("context") or "", item.get("target_url") or ""))

errors = [
    json.loads(line)
    for line in Path(os.environ["ERRORS_NDJSON"]).read_text(encoding="utf-8").splitlines()
    if line.strip()
]

try:
    gh_version = subprocess.run(
        ["gh", "--version"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()[0]
except Exception:
    gh_version = "unknown"

provenance = {
    "schema_version": 1,
    "collector": "scripts/bin/pr-review.sh",
    "collector_mode": "read-only",
    "collected_at": collected_at,
    "gh_version": gh_version,
    "workspace_root": str(Path(os.environ["ROOT"]).resolve()),
    "working_tree_checkout_performed": False,
    "external_mutation_performed": False,
    "source": "GitHub REST API PR metadata, refs, diff, checks, and statuses",
    "target": {
        "repository": metadata["repository"],
        "number": metadata["number"],
        "base": metadata["base"],
        "head": metadata["head"],
    },
    "collection": {
        "metadata": "complete",
        "files": "complete",
        "commits": "complete",
        "diff": "complete",
        "freshness": "verified",
        "check_runs": "complete" if os.environ["CHECKS_OK"] == "true" else "unavailable",
        "commit_statuses": "complete" if os.environ["STATUS_OK"] == "true" else "unavailable",
    },
}

outputs = {
    "metadata.json": metadata,
    "files.json": files,
    "commits.json": commits,
    "checks.json": {
        "head_sha": metadata["head"]["sha"],
        "combined_state": status_raw.get("state", "unknown"),
        "check_runs": check_runs,
        "statuses": statuses,
    },
    "provenance.json": provenance,
    "freshness.json": freshness,
    "errors.json": errors,
}
for filename, value in outputs.items():
    (out / filename).write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

manifest_files = [
    "metadata.json",
    "files.json",
    "commits.json",
    "checks.json",
    "diff.patch",
    "freshness.json",
    "provenance.json",
    "errors.json",
]
manifest = {
    "schema_version": 1,
    "repository": metadata["repository"],
    "pr_number": metadata["number"],
    "head_sha": metadata["head"]["sha"],
    "files": {},
}
for filename in manifest_files:
    content = (out / filename).read_bytes()
    manifest["files"][filename] = {
        "sha256": hashlib.sha256(content).hexdigest(),
        "bytes": len(content),
    }
(out / "manifest.json").write_text(
    json.dumps(manifest, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
)
PY

rm -f \
  "$raw_pr" "$raw_pr_final" "$raw_pull_ref" "$raw_pull_ref_final" \
  "$raw_base_ref" "$raw_base_ref_final" \
  "$raw_files" "$raw_commits" "$raw_check_runs" "$raw_status" \
  "$errors_ndjson"

printf 'PR evidence collected: %s\n' "$out"
printf 'Target: %s#%s\n' "$repo_slug" "$number"
printf 'Head SHA: %s\n' "$head_sha"
if [[ "$checks_ok" != true || "$status_ok" != true ]]; then
  printf 'Warning: one or more optional check/status sources were unavailable; see errors.json\n' >&2
fi
