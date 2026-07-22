---
name: feedback_local_folders_match_github_trustt
description: "Local service clone folders renamed to match GitHub trustt-* repo names (2026-07-15)"
metadata:
  node_type: memory
  type: feedback
---

Local disk folders under `/home/darpan/Documents/sliProd` now equal GitHub repo names (`trustt-platform-*`).

- was `novopay-platform-accounting-v2` → `trustt-platform-accounting`
- was `novopay-mfi-los` → `trustt-platform-los`
- was `trustt-platform-ai-codegen-artifacts` → `trustt-platform-ai-codegen-artifacts-java`
- other `novopay-platform-*` → matching `trustt-platform-*`

Java packages `in.novopay.*` are unchanged. Org upstream is `trusttai` (not `khoslalabs`).

Map + legacy aliases: `scripts/lib/github_repo_map.{sh,py}`  
Guide: `docs/setup/github-org-repo-rename-developer-guide.md`

Do not `cd` into old `novopay-*` paths in tooling.

Gradle: every service `settings.gradle` must `includeBuild '../trustt-platform-lib'`.
Single-service repos no longer use a redundant `include 'novopay-platform-…'` (that created a phantom sliProd/novopay-* dir). Those settings.gradle edits are **local dirty** until committed per fork.
