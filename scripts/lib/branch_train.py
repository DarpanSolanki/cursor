#!/usr/bin/env python3
"""Cross-branch fix discovery and forward-port analysis.

Read-only by design: this module never checks out, merges, cherry-picks, or pushes.
Upstream refs are the source of truth; callers decide when to fetch them.
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import subprocess
import sys
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path

import forward_merge

ROOT = Path(__file__).resolve().parents[2]
KG_DB = ROOT / "cursor-bundle/kg/data/kg.db"
TRAIN_REF = re.compile(r"^upstream/(mfi_(?:integration|release)_v\d+(?:\.\d+)*)$")
BRANCH_NAME = re.compile(r"^mfi_(?:integration|release)_v\d+(?:\.\d+)*$")
SHA = re.compile(r"^[0-9a-f]{7,40}$")
REUSE_POLICY = (
    "REUSE_POLICY: propose cherry-pick/port ONLY for VERIFIED_FIXED_CLEAN. "
    "CANDIDATE_ONLY / FILE_TOUCH_HINTS / VERIFIED_FIXED_DIVERGED / stale refs = REUSE_FORBIDDEN."
)


class GitError(RuntimeError):
    pass


def git(repo: Path, *args: str, check: bool = True) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if check and result.returncode:
        raise GitError(result.stderr.strip() or "git command failed")
    return result.stdout.strip()


def resolve_repo(value: str | Path) -> Path:
    candidate = Path(value)
    if not candidate.is_absolute():
        candidate = ROOT / candidate
    candidate = candidate.resolve()
    if not (candidate / ".git").exists():
        raise GitError(f"not a git repository: {candidate}")
    return candidate


def upstream_branches(
    repo: Path, *, base: str | None = None, active_limit: int | None = None
) -> dict[str, str]:
    rows = git(
        repo,
        "for-each-ref",
        "--sort=-committerdate",
        "--format=%(refname:short)\t%(objectname)\t%(committerdate:unix)",
        "refs/remotes/upstream",
    )
    all_branches: list[tuple[str, str]] = []
    for row in rows.splitlines():
        if row.count("\t") < 2:
            continue
        ref, commit, _ = row.split("\t", 2)
        match = TRAIN_REF.match(ref)
        if match:
            all_branches.append((match.group(1), commit))
    if active_limit is None:
        return dict(all_branches)
    selected = all_branches[:active_limit]
    if base and all(branch != base for branch, _ in selected):
        selected.extend(row for row in all_branches if row[0] == base)
    return dict(selected)


def version_key(branch: str) -> tuple[int, ...]:
    version = branch.rsplit("_v", 1)[-1]
    return tuple(int(piece) for piece in version.split("."))


def fetch_age_hours(repo: Path) -> float | None:
    """Upstream freshness only — an origin fetch must not hide stale upstream refs.

    Prefer the *freshest* signal among stamp + upstream ref mtimes. A stale
    ``novopay-upstream-fetch.stamp`` must not override a newer real upstream
    fetch (raw ``git fetch upstream`` does not rewrite the stamp).
    """
    candidates: list[float] = []
    stamp = repo / ".git/novopay-upstream-fetch.stamp"
    if stamp.is_file():
        try:
            candidates.append(float(stamp.read_text().strip()))
        except ValueError:
            pass
    upstream_dir = repo / ".git/refs/remotes/upstream"
    if upstream_dir.is_dir():
        for path in upstream_dir.rglob("*"):
            if path.is_file():
                candidates.append(path.stat().st_mtime)
    packed = repo / ".git/packed-refs"
    if packed.is_file():
        try:
            text = packed.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            text = ""
        if "refs/remotes/upstream/" in text:
            candidates.append(packed.stat().st_mtime)
    fetch_head = repo / ".git/FETCH_HEAD"
    if fetch_head.is_file():
        try:
            text = fetch_head.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            text = ""
        if re.search(r"\bupstream\b", text):
            candidates.append(fetch_head.stat().st_mtime)
    if not candidates:
        return None
    return (time.time() - max(candidates)) / 3600


def fetch_warning(repo: Path) -> str | None:
    age = fetch_age_hours(repo)
    if age is None:
        return (
            "upstream freshness UNKNOWN (no upstream stamp/refs); "
            "fetch upstream before decisions"
        )
    if age > 12:
        return f"upstream refs STALE ({age:.1f}h since upstream fetch); fetch upstream before decisions"
    return None


def ensure_upstream_fresh(repo: Path, *, fetch_if_stale: bool) -> str | None:
    warning = fetch_warning(repo)
    if warning and fetch_if_stale:
        print(f"REFRESH: {warning}; fetching upstream")
        git(repo, "fetch", "upstream")
        stamp = repo / ".git/novopay-upstream-fetch.stamp"
        stamp.write_text(f"{time.time():.3f}\n", encoding="utf-8")
        warning = fetch_warning(repo)
    return warning


def branch_graph(
    repo: Path, *, base: str | None = None
) -> tuple[dict[str, set[str]], list[str]]:
    """Return source->target merge-train edges plus diagnostics."""
    branches = upstream_branches(repo, base=base, active_limit=24)
    graph: dict[str, set[str]] = {branch: set() for branch in branches}
    notes: list[str] = []

    # Branch-tip ancestry is the proof. Keep only the cover relation so old
    # history does not create thousands of transitive/non-actionable edges.
    proven: dict[str, set[str]] = defaultdict(set)
    names = list(branches)
    for source in names:
        for target in names:
            if source == target:
                continue
            source_v, target_v = version_key(source), version_key(target)
            if source_v > target_v:
                continue
            if source_v == target_v:
                same_train_pair = (
                    source.startswith("mfi_integration_")
                    and target.startswith("mfi_release_")
                )
                if not same_train_pair:
                    continue
            if branches[source] == branches[target] or _is_ancestor(
                repo, branches[source], branches[target]
            ):
                proven[source].add(target)
    for source, targets in proven.items():
        immediate = set(targets)
        for target in targets:
            for middle in targets:
                if middle == target:
                    continue
                if target in proven.get(middle, set()):
                    immediate.discard(target)
                    break
        graph[source].update(immediate)

    if not any(graph.values()):
        notes.append(
            "no provable branch-tip ancestry edges found; version ordering is display-only"
        )
    return graph, notes


def _is_ancestor(repo: Path, ancestor: str, descendant: str) -> bool:
    result = subprocess.run(
        ["git", "-C", str(repo), "merge-base", "--is-ancestor", ancestor, descendant],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return result.returncode == 0


def resolve_commit(repo: Path, sha: str) -> str:
    """Resolve to a unique full object. Ambiguous/short collisions fail closed."""
    try:
        return git(repo, "rev-parse", "--verify", f"{sha}^{{commit}}")
    except GitError as exc:
        raise GitError(
            f"commit not uniquely resolvable ({sha}); refuse reuse to avoid false positives"
        ) from exc


def commit_files(repo: Path, sha: str) -> tuple[str, ...]:
    full = resolve_commit(repo, sha)
    return tuple(
        line
        for line in git(repo, "show", "--format=", "--name-only", full).splitlines()
        if line
    )


def diverge_after_sha(
    repo: Path, sha: str, target: str, files: tuple[str, ...] | None = None
) -> tuple[bool, list[str]]:
    """True when target has later commits on the fix files after sha (not the fix itself)."""
    full = resolve_commit(repo, sha)
    paths = files if files is not None else commit_files(repo, full)
    if not paths:
        return False, []
    target_ref = target if target.startswith("upstream/") else f"upstream/{target}"
    log = git(
        repo,
        "log",
        "--no-merges",
        "--format=%H%x09%s",
        f"{full}..{target_ref}",
        "--",
        *paths,
        check=False,
    )
    rows = [line for line in log.splitlines() if "\t" in line]
    return bool(rows), rows


def branches_containing(repo: Path, sha: str) -> set[str]:
    rows = git(
        repo,
        "for-each-ref",
        f"--contains={sha}",
        "--format=%(refname:short)",
        "refs/remotes/upstream",
        check=False,
    )
    result: set[str] = set()
    for ref in rows.splitlines():
        match = TRAIN_REF.match(ref)
        if match:
            result.add(match.group(1))
    return result


def descendants(graph: dict[str, set[str]], branch: str) -> list[str]:
    seen: set[str] = set()
    queue = deque(sorted(graph.get(branch, ()), key=version_key))
    while queue:
        item = queue.popleft()
        if item in seen:
            continue
        seen.add(item)
        queue.extend(sorted(graph.get(item, ()), key=version_key))
    return sorted(seen, key=version_key)


def shortest_paths(graph: dict[str, set[str]], source: str) -> dict[str, list[str]]:
    paths = {source: [source]}
    queue = deque([source])
    while queue:
        current = queue.popleft()
        for nxt in sorted(graph.get(current, ()), key=version_key):
            if nxt not in paths:
                paths[nxt] = paths[current] + [nxt]
                queue.append(nxt)
    return paths


def _strip_src(src: str, repo_name: str) -> str | None:
    path = src.split(":", 1)[0]
    prefix = repo_name + "/"
    if path.startswith(prefix):
        return path[len(prefix) :]
    return None


@dataclass(frozen=True)
class QueryContext:
    repo: str
    node_id: str | None
    files: tuple[str, ...]
    cases: tuple[tuple[str, str], ...]


def kg_context(query: str, repo_hint: str | None = None) -> QueryContext:
    if not KG_DB.exists():
        raise GitError(f"KG missing: {KG_DB}")
    conn = sqlite3.connect(KG_DB)
    conn.row_factory = sqlite3.Row
    try:
        node = conn.execute(
            """
            SELECT id, repo, json FROM nodes
            WHERE id IN (?, ?, ?) OR label = ?
            ORDER BY CASE kind WHEN 'request' THEN 0 WHEN 'processor' THEN 1 ELSE 2 END
            LIMIT 1
            """,
            (query, f"request:{query}", f"processor:{query}", query),
        ).fetchone()
        if node is None:
            hits = conn.execute(
                "SELECT id,repo,json FROM nodes WHERE id LIKE ? LIMIT 2",
                (f"%{query}%",),
            ).fetchall()
            if len(hits) == 1:
                node = hits[0]
        if node is None:
            if not repo_hint:
                raise GitError(f"KG query not found or ambiguous: {query}")
            return QueryContext(repo_hint, None, (), ())

        repo_name = repo_hint or node["repo"]
        if not repo_name:
            raise GitError(f"KG node has no owning repo: {node['id']}")
        files: set[str] = set()
        payload = json.loads(node["json"] or "{}")
        if payload.get("src"):
            path = _strip_src(payload["src"], repo_name)
            if path:
                files.add(path)

        processor_ids = [node["id"]]
        if node["id"].startswith("request:"):
            processor_ids.extend(
                row[0]
                for row in conn.execute(
                    "SELECT dst_id FROM edges WHERE src_id=? AND rel='invokes'",
                    (node["id"],),
                )
            )
        for processor in processor_ids:
            processor_name = processor.split(":", 1)[-1].lower()
            for row in conn.execute(
                "SELECT src FROM edges WHERE src_id=? AND src IS NOT NULL",
                (processor,),
            ):
                path = _strip_src(row[0], repo_name)
                if path and Path(path).stem.lower() == processor_name:
                    files.add(path)

        cases = tuple(
            (row["sha"], row["label"])
            for row in conn.execute(
                """
                SELECT json_extract(n.json,'$.sha') AS sha, n.label
                FROM edges e JOIN nodes n ON n.id=e.src_id
                WHERE e.dst_id=? AND n.kind='case' AND e.rel='touches'
                ORDER BY json_extract(n.json,'$.date') DESC
                """,
                (node["id"],),
            )
            if row["sha"]
        )
        return QueryContext(repo_name, node["id"], tuple(sorted(files)), cases)
    finally:
        conn.close()


def query_context(query: str, repo_hint: str | None = None) -> QueryContext:
    path = Path(query)
    if repo_hint:
        repo = resolve_repo(repo_hint)
        repo_path = path if path.is_absolute() else repo / path
        if repo_path.exists():
            rel = str(repo_path.resolve().relative_to(repo))
            return QueryContext(str(repo), None, (rel,), ())
    if repo_hint and SHA.match(query):
        repo = resolve_repo(repo_hint)
        full = resolve_commit(repo, query)
        files = commit_files(repo, full)
        # Direct SHA is itself the precedent — required for VERIFIED_FIXED_CLEAN path.
        return QueryContext(
            str(repo),
            None,
            files,
            ((full, f"direct-sha:{full[:10]}"),),
        )
    return kg_context(query, repo_hint)


def current_train_branch(repo: Path) -> str:
    branch = git(repo, "branch", "--show-current")
    if not BRANCH_NAME.fullmatch(branch):
        raise GitError(f"current branch is not a release train: {branch or '(detached)'}")
    return branch


def fixed_elsewhere(
    query: str,
    *,
    repo_hint: str | None = None,
    base: str | None = None,
    limit: int = 8,
    fetch_if_stale: bool = False,
    show_candidates: bool = False,
) -> int:
    context = query_context(query, repo_hint)
    repo = resolve_repo(context.repo)
    base = base or current_train_branch(repo)
    warning = ensure_upstream_fresh(repo, fetch_if_stale=fetch_if_stale)
    if warning:
        print(f"RESULT: NOT_VERIFIED_STALE_REFS — {warning}")
        print("REUSE_FORBIDDEN")
        print(REUSE_POLICY)
        return 3
    branches = upstream_branches(repo)
    if base not in branches:
        raise GitError(f"upstream/{base} not found")
    graph, notes = branch_graph(repo, base=base)
    targets = descendants(graph, base)

    print(f"FIXED-ELSEWHERE query={query} repo={repo.name} base=upstream/{base}")
    print(REUSE_POLICY)
    for note in notes:
        print(f"NOTE: {note}")
    if context.node_id:
        print(f"KG: {context.node_id}")
    print(f"FILES ({len(context.files)}):")
    for path in context.files[:20]:
        print(f"  {path}")
    if not targets:
        print("RESULT: NO_FORWARD_TARGETS — no higher branch reachable in live merge DAG")
        print("REUSE_FORBIDDEN")
        return 0

    clean = 0
    diverged = 0
    candidates = 0
    unresolved = 0
    for target in targets:
        target_ref = f"upstream/{target}"
        target_clean: list[tuple[str, str]] = []
        target_diverged: list[tuple[str, str, list[str]]] = []
        for sha, label in context.cases:
            try:
                full = resolve_commit(repo, sha)
            except GitError as exc:
                unresolved += 1
                print(f"CASE_SHA_UNRESOLVED [{sha[:10]}] — {exc}")
                continue
            if not _is_ancestor(repo, full, target_ref):
                continue
            if _is_ancestor(repo, full, f"upstream/{base}"):
                # Already on the reported/lower train tip — not "elsewhere".
                continue
            files = context.files or commit_files(repo, full)
            is_div, rows = diverge_after_sha(repo, full, target_ref, files)
            if is_div:
                target_diverged.append((full, label, rows))
            else:
                target_clean.append((full, label))

        if target_clean:
            clean += len(target_clean)
            print(f"VERIFIED_FIXED_CLEAN upstream/{target}")
            for sha, label in target_clean:
                print(f"  PROOF sha={sha[:12]} contained_by={target_ref}; diverge=CLEAN")
                print(f"  [{sha[:10]}] {label}")
            continue

        if target_diverged:
            diverged += len(target_diverged)
            print(f"VERIFIED_FIXED_DIVERGED upstream/{target} — DO NOT blind-reuse")
            for sha, label, rows in target_diverged:
                print(
                    f"  PROOF sha={sha[:12]} contained_by={target_ref}; "
                    f"diverge=YES ({len(rows)} later file-touch commit(s))"
                )
                print(f"  [{sha[:10]}] {label}")
                for row in rows[:3]:
                    print(f"    later: {row}")
            continue

        if not context.files:
            continue
        log = git(
            repo,
            "log",
            "--no-merges",
            "--format=%H%x09%s",
            f"upstream/{base}..{target_ref}",
            "--",
            *context.files,
            check=False,
        )
        rows = [line.split("\t", 1) for line in log.splitlines() if "\t" in line]
        if rows:
            candidates += len(rows)
            print(
                f"FILE_TOUCH_HINTS upstream/{target} ({len(rows)} commit(s)) — "
                "NOT the same fix; REUSE_FORBIDDEN"
            )
            if show_candidates:
                for sha, subject in rows[:limit]:
                    print(f"  CANDIDATE_ONLY [{sha[:10]}] {subject}")

    if clean:
        print(f"RESULT: REUSE_ALLOWED — {clean} VERIFIED_FIXED_CLEAN match(es)")
        print("NEXT: cherry-pick/port only those SHAs after human confirm; origin-only push")
    elif diverged:
        print(
            f"RESULT: REUSE_FORBIDDEN — {diverged} SHA containment(s) but target files diverged"
        )
        print("NEXT: reconcile with --diverge; do not blind-merge")
    elif candidates:
        print(
            f"RESULT: REUSE_FORBIDDEN — {candidates} file-touch hint(s), zero verified cases"
        )
        print("NEXT: inventing a fix from FILE_TOUCH_HINTS is forbidden; RCA on reported train")
    else:
        print("RESULT: REUSE_FORBIDDEN — NO_KNOWN_FIX")
        if unresolved:
            print(f"NOTE: {unresolved} KG case SHA(s) unresolved in this repo object store")
    if not clean:
        print("REUSE_FORBIDDEN")
    return 0


def print_train(repo: Path) -> int:
    graph, notes = branch_graph(repo)
    if warning := fetch_warning(repo):
        print(f"WARN: {warning}")
    for note in notes:
        print(f"NOTE: {note}")
    edges = [(source, target) for source, targets in graph.items() for target in targets]
    for source, target in sorted(edges, key=lambda edge: (version_key(edge[0]), version_key(edge[1]))):
        print(f"{source} --> {target}")
    if not edges:
        print("NO_MERGE_DAG_EDGES")
    return 0


def print_path(repo: Path, source: str) -> int:
    graph, _ = branch_graph(repo, base=source)
    paths = shortest_paths(graph, source)
    targets = [branch for branch in paths if branch != source]
    if not targets:
        print(f"NO_FORWARD_PATH from {source}")
        return 0
    for target in sorted(targets, key=version_key):
        print(" -> ".join(paths[target]))
    return 0


def missing_branches(repo: Path, sha: str, floor: str | None = None) -> int:
    branches = upstream_branches(repo)
    containing = branches_containing(repo, sha)
    selected = sorted(branches, key=version_key)
    if floor:
        selected = [branch for branch in selected if version_key(branch) >= version_key(floor)]
    source = current_train_branch(repo)
    arriving = set(forward_merge.downstream(source)) if source else set()
    for branch in selected:
        if branch in containing:
            print(f"{'HAS':7} upstream/{branch}")
            continue
        route = "arrives by forward merge" if branch in arriving else "needs explicit port"
        print(f"{'MISSING':7} upstream/{branch}  ({route})")
    if source:
        print(f"# forward-merge source {source}: {forward_merge.coverage_note(source)}")
    return 0


def diverge(repo: Path, sha: str, target: str) -> int:
    is_div, rows = diverge_after_sha(repo, sha, target)
    target_ref = target if target.startswith("upstream/") else f"upstream/{target}"
    if is_div:
        print(f"DIVERGED {target_ref} — {len(rows)} later commit(s) touched fix files after sha")
        for row in rows[:20]:
            print(f"  {row}")
        return 2
    print(f"CLEAN {target_ref} — no later target-side commits touched fix files after sha")
    return 0


def audit(repo: Path) -> int:
    if not KG_DB.exists():
        raise GitError(f"KG missing: {KG_DB}")
    conn = sqlite3.connect(KG_DB)
    # Prefer case.repo / case.json.repo (build_cases); fall back to touched target.repo.
    rows = conn.execute(
        """
        SELECT DISTINCT c.id, c.label, c.json
        FROM nodes c
        LEFT JOIN edges e ON e.src_id=c.id AND e.rel='touches'
        LEFT JOIN nodes target ON target.id=e.dst_id
        WHERE c.kind='case'
          AND (
            c.repo = ?
            OR json_extract(c.json,'$.repo') = ?
            OR target.repo = ?
          )
        ORDER BY c.id DESC
        """,
        (repo.name, repo.name, repo.name),
    ).fetchall()
    conn.close()
    found = 0
    branches = upstream_branches(repo)
    for _cid, label, raw in rows:
        payload = json.loads(raw or "{}")
        sha = payload.get("sha")
        if not sha:
            continue
        present = sorted(branches_containing(repo, sha) & branches.keys())
        if not present:
            print(f"UNMERGED [{sha[:10]}] {payload.get('label') or label}")
            found += 1
    print(f"AUDIT: {found} KG case(s) absent from every upstream train branch")
    return 0


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)

    fixed = sub.add_parser("fixed-elsewhere")
    fixed.add_argument("query")
    fixed.add_argument("--repo")
    fixed.add_argument("--base")
    fixed.add_argument("--limit", type=int, default=8)
    fixed.add_argument("--fetch-if-stale", action="store_true")
    fixed.add_argument(
        "--show-candidates",
        action="store_true",
        help="Print FILE_TOUCH_HINTS commit subjects (still REUSE_FORBIDDEN)",
    )

    train = sub.add_parser("train")
    train.add_argument("repo")
    path = sub.add_parser("path")
    path.add_argument("repo")
    path.add_argument("source")
    missing = sub.add_parser("missing")
    missing.add_argument("repo")
    missing.add_argument("sha")
    missing.add_argument("floor", nargs="?")
    div = sub.add_parser("diverge")
    div.add_argument("repo")
    div.add_argument("sha")
    div.add_argument("target")
    aud = sub.add_parser("audit")
    aud.add_argument("repo")
    return p


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "fixed-elsewhere":
            return fixed_elsewhere(
                args.query,
                repo_hint=args.repo,
                base=args.base,
                limit=args.limit,
                fetch_if_stale=args.fetch_if_stale,
                show_candidates=args.show_candidates,
            )
        repo = resolve_repo(args.repo)
        if args.command == "train":
            return print_train(repo)
        if args.command == "path":
            return print_path(repo, args.source)
        if args.command == "missing":
            return missing_branches(repo, args.sha, args.floor)
        if args.command == "diverge":
            return diverge(repo, args.sha, args.target)
        if args.command == "audit":
            return audit(repo)
    except GitError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        print("REUSE_FORBIDDEN", file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
