#!/usr/bin/env python3
"""Recover a batch job's table footprint statically, past the Spring Batch boundary.

The knowledge graph traces `request -> processor -> table` and stops where the orchestration
processor calls `parallelCommonBatchJob.runJob(jobName, ...)` — a name-based dispatch with no
static edge. Everything a batch job really writes happens on the far side of it, so
`loanAccountBillingJob` is indexed as writing one table and writes eight.

Running the job and diffing the DB (`job_footprint.py`) settles it for one job at a time.
This does it for all of them at once, because the wiring is pure convention:

  JOB_NAME = "<apiName>"     in batchnew/**/*BatchConfigService.java — the join key
  *ItemReader / *IReader     queryFromClause SQL -> FROM/JOIN tables      (reads)
  *ItemWriter / *IWriter     -> *DAOService field -> entity @Table        (direct writes)
  *Tasklet                   same, and this is where *_run_history lands
  callInternalAPI(ctx, api,) -> that API's own footprint from the platform map (indirect)
  GenericListenerV3 present  -> batch_failure_audit on skip/failure

The last two are what the static map was missing. The money tables are almost never written
by the writer — they come from an internal `postTransaction` call inside the `*BatchService`,
and the alias in argument four is not the API name, so the callee must be read from argument
two.

    batch_footprint_scan.py                 scan every batch job, write the artefact
    batch_footprint_scan.py --job NAME      one job, with the evidence for each table
    batch_footprint_scan.py --compare       where this disagrees with the KG-derived map
    batch_footprint_scan.py --repo los      same scan against a non-accounting repo

Each service invented its own config-class filename suffix for the class that declares
`JOB_NAME`. `REPO_CONFIGS` below is not a guess — it is the observed distribution of
`JOB_NAME`-declaring filename suffixes per repo, and it always includes a fallback pass
(any filename containing "config", case-insensitive) so a typo'd class
(`...BatchConfigSevice.java` in payments) is still found rather than silently dropped.
"""
from __future__ import annotations

import argparse
import collections
import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[2]
FLOW = ROOT / "cursor-bundle" / "flow-test"
OUT = FLOW / "batch_footprint.jsonl"
SCRATCH = ROOT / "scripts" / "scratch" / "batch-scan-port"

REPO_CONFIGS: dict[str, dict] = {
    "accounting": {
        "dir": "trustt-platform-accounting",
        "suffixes": ("BatchConfigService",),
        "fallback": False,
    },
    "reporting": {
        "dir": "trustt-platform-reporting",
        "suffixes": ("BatchConfigService", "BatchConfig", "ConfigService", "Config",
                     "JobConfig"),
        "fallback": True,
    },
    "payments": {
        "dir": "trustt-platform-payments",
        "suffixes": ("BatchConfigService",),
        "fallback": True,
    },
    "los": {
        "dir": "trustt-platform-los",
        "suffixes": ("ConfigService", "BatchConfigService", "BatchConfig"),
        "fallback": True,
    },
    "task": {
        "dir": "trustt-platform-task",
        "suffixes": ("BatchConfigService", "ConfigService", "BatchJobConfig"),
        "fallback": True,
    },
}

_JOB_NAME = re.compile(r'(?<![A-Za-z0-9_])JOB_NAME\s*=\s*"([^"]+)"')
_TABLE = re.compile(r'@Table\s*\(\s*name\s*=\s*"([^"]+)"')
_ENTITY_REF = re.compile(r"\b(\w+Entity|\w+Details|\w+History|LoanAccountDerivedField\w*)\b")
_FROM = re.compile(r"\b(?:FROM|JOIN)\s+([a-z_][a-z0-9_]*)", re.I)
_INTERNAL = re.compile(r'callInternalAPI\s*\(\s*[^,]+,\s*"([^"]+)"')
# Not every writer goes through a *DAOService. LADerivedFieldsIWriter calls a plain
# LADerivedFieldService, and keying only on DAO/Repository reported both derived-fields
# jobs as writing nothing at all.
_DAO_FIELD = re.compile(r"\b(\w+(?:DAOService|DaoService|Repository|Service))\b")
_LISTENER = re.compile(r"\bGenericListenerV3\b")

_SQL_NOISE = {"select", "where", "and", "or", "on", "as", "left", "inner", "outer", "dual"}


def entity_tables(java_root: pathlib.Path) -> dict[str, str]:
    """Every `@Table(name=...)` in the repo, keyed by the Java class that declares it."""
    out: dict[str, str] = {}
    for path in java_root.rglob("*.java"):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        m = _TABLE.search(text)
        if m:
            out[path.stem] = m.group(1)
    return out


_CONFIG_WIRING = re.compile(r"Config(Service)?$")


def dao_to_entity(java_root: pathlib.Path) -> dict[str, str]:
    """`FooDAOService` -> the entity class it persists, read from its own source.

    Picking the most-frequently-mentioned entity is wrong when a DAO handles a parent and its
    child: `InterestSetupDAOService` mentions `InterestSetupDateSlabEntity` 11 times against
    `InterestSetupEntity` 10, which attributed a write of `interest_setup_date_slab` to the
    accrual jobs that only ever read `interest_setup`. Prefer the entity whose name matches the
    DAO's own stem, and fall back to frequency only when nothing matches.

    `*ConfigService` / `*BatchConfig` classes end in "...Service" (the same suffix real DAOs
    use) but wire Spring Batch steps together rather than persist anything; the entity they
    mention is usually just a step's generic type parameter
    (`CustomCommonStepBuilder<Object[], FooEntity>`). Left in the candidate pool, a config
    class matches its own class name when `scan_job` sees it referenced in the same file (a
    logger line, a constructor) and gets credited as the writer for whatever entity its
    wiring code happened to name — never the file that actually calls `.save()`.

    A facade `*Service` autowired straight into a `Tasklet`/`ItemWriter` (rather than a real
    per-entity `*DAOService`/`Repository`) is the same over-attribution one layer up:
    `CollectionToStagingSyncService` wraps ten unrelated repositories across ~30 methods for
    five different Finnone jobs, and picking its single most-mentioned entity attributed
    `bulkOutboundNpAgencyExtractJob` — whose own two calls only touch
    `file_staging_np_agency_extract` and `collection_vymo_np_agency_extract_status` — to writing
    `collection_group_info`, a table its tasklet never references. Frequency is only safe to
    fall back on when the file names exactly one entity; with more than one and no exact match,
    which entity belongs to which caller cannot be told apart from this file alone, so the DAO
    is left unresolved rather than guessed.
    """
    out: dict[str, str] = {}
    for path in java_root.rglob("*.java"):
        stem = path.stem
        if not stem.endswith(("DAOService", "DaoService", "Repository", "Service")):
            continue
        if _CONFIG_WIRING.search(stem):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        names = collections.Counter(_ENTITY_REF.findall(text))
        base = (stem.replace("DAOService", "").replace("DaoService", "")
                    .replace("Repository", "").replace("Service", "").lower())
        exact = [n for n in names if n != stem and n.lower().rstrip("entity") == base]
        if exact:
            out[stem] = exact[0]
            continue
        distinct = {n for n in names if n != stem}
        if len(distinct) == 1:
            out[stem] = next(iter(distinct))
    return out


def job_packages(java_root: pathlib.Path, suffixes: tuple[str, ...], fallback: bool
                  ) -> tuple[dict[str, pathlib.Path], dict[str, pathlib.Path], list[str]]:
    jobs: dict[str, pathlib.Path] = {}
    config_paths: dict[str, pathlib.Path] = {}
    fallback_hits: list[str] = []
    fast_path = not fallback and len(suffixes) == 1
    candidates = (java_root.rglob(f"*{suffixes[0]}.java") if fast_path
                  else java_root.rglob("*.java"))
    suffixes_low = tuple(s.lower() for s in suffixes)
    for path in candidates:
        stem_low = path.stem.lower()
        hit_suffix = fast_path or any(stem_low.endswith(s) for s in suffixes_low)
        if not hit_suffix and not (fallback and "config" in stem_low):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        m = _JOB_NAME.search(text)
        if not m:
            continue
        package = path.parent
        if package.name in ("config", "configs"):
            package = package.parent
        jobs[m.group(1)] = package
        config_paths[m.group(1)] = path
        if not hit_suffix:
            fallback_hits.append(path.stem)
    return jobs, config_paths, fallback_hits


_WIRING_REF = re.compile(r'\b(\w+(?:Tasklet|ItemWriter|IWriter|ItemReader|IReader|ItemProcessor'
                          r'|IProcessor))\b')


def class_index(java_root: pathlib.Path) -> dict[str, pathlib.Path]:
    out: dict[str, pathlib.Path] = {}
    for path in java_root.rglob("*.java"):
        out.setdefault(path.stem, path)
    return out


def resolve_job_files(config_path: pathlib.Path, index: dict[str, pathlib.Path],
                       max_depth: int = 1, max_files: int = 40) -> list[pathlib.Path]:
    """The config class's own wiring, not a directory or a filename guess.

    Payments and task lay every job's config/reader/writer/tasklet in one shared,
    type-bucketed directory (`batch/config/`, `batch/writer/`, ...) rather than accounting's
    one-directory-per-job layout, and their JOB_NAME string does not reliably share a common
    prefix with the sibling class names either (`RunFinoneJobBatchConfigService` declares
    `JOB_NAME = "runInboundFinoneJob"` and wires `FinoneInboundJobTasklet` — neither a
    directory walk nor a name-prefix match reaches the right file, but the `@Autowired` field
    the config class declares does). Follow that one hop, but only into step-shaped classes
    (Tasklet/ItemWriter/ItemReader/ItemProcessor) — never DAOService/Repository/Service.
    `dao_to_entity()` already resolves what a step's own DAO field writes, from that DAO's own
    source; opening the DAO's file here and re-running `_DAO_FIELD` over its *entire* body would
    attribute every repository a facade DAO wires to whichever one job happened to reach it —
    `LoanAppDaoService` mentions 134 Repository fields, `CollectionsDAOService` eleven, and
    neither is owned by any single job. Same "most-frequently-mentioned" over-attribution
    `dao_to_entity` was already fixed for, one layer up.
    """
    seen = {config_path.stem}
    files = [config_path]
    frontier = [config_path]
    for _ in range(max_depth):
        if not frontier or len(files) >= max_files:
            break
        next_frontier: list[pathlib.Path] = []
        for path in frontier:
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for name in sorted(set(_WIRING_REF.findall(text))):
                if name in seen or len(files) >= max_files:
                    continue
                seen.add(name)
                target = index.get(name)
                if target is None:
                    continue
                files.append(target)
                next_frontier.append(target)
        frontier = next_frontier
    return files


def job_parameters() -> dict[str, dict]:
    """`mfi_batch.batch_job_parameter` — how each job is configured to execute.

    The parameters decide the shape of the run, so they change what a test is even exercising.
    On this environment every job that declares `force_async` has it TRUE, which is the
    AsyncItemWriter path where the skip listener receives a Future rather than the written
    item — the contract `batch-write-skip-contract.md` exists for. `is_multi_node` is FALSE,
    so partitioning is local: single-node, grid size from `force_grid_size`.
    """
    import subprocess
    out: dict[str, dict] = {}
    query = ("select j.name||'|'||p.param_name||'|'||p.param_value "
             "from mfi_batch.batch_job_parameter p "
             "join mfi_batch.batch_job j on j.id = p.job_id")
    try:
        proc = subprocess.run(["bash", str(ROOT / "scripts/db-local.sh"), "--sql", query],
                              cwd=str(ROOT), capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.TimeoutExpired):
        return out
    if proc.returncode != 0 or "ERROR:" in (proc.stdout + proc.stderr):
        return out
    for line in proc.stdout.splitlines():
        parts = line.strip().split("|")
        if len(parts) == 3 and re.fullmatch(r"[A-Za-z][\w]*", parts[0]):
            out.setdefault(parts[0], {})[parts[1]] = parts[2]
    return out


def static_map() -> dict[str, list[str]]:
    path = FLOW / "platform_api_map.jsonl"
    out: dict[str, list[str]] = {}
    if not path.is_file():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.startswith("#"):
            row = json.loads(line)
            out.setdefault(row["api"], row["tables_written"])
    return out


def scan_job(job: str, package: pathlib.Path, files: list[pathlib.Path], tables: dict,
             daos: dict, api_tables: dict) -> dict:
    writes: dict[str, str] = {}
    reads: set[str] = set()
    internal: set[str] = set()
    listener = False

    for path in sorted(set(files)):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        rel = str(path.relative_to(ROOT))
        stem = path.stem

        if _LISTENER.search(text):
            listener = True

        for api in _INTERNAL.findall(text):
            internal.add(api)

        if stem.endswith(("ItemReader", "IReader")) or "queryFromClause" in text:
            for name in _FROM.findall(text):
                if name.lower() not in _SQL_NOISE:
                    reads.add(name.lower())

        if stem.endswith(("ItemWriter", "IWriter", "Tasklet", "DaoService", "DAOService",
                          "Service")):
            for dao in set(_DAO_FIELD.findall(text)):
                entity = daos.get(dao)
                table = tables.get(entity or "")
                if table:
                    writes.setdefault(table, f"{rel} -> {dao} -> {entity}")

    indirect: dict[str, list[str]] = {}
    for api in sorted(internal):
        for table in api_tables.get(api, []):
            indirect.setdefault(table, []).append(api)

    if listener:
        writes.setdefault("batch_failure_audit", "GenericListenerV3 skip/failure listener")

    direct = sorted(writes)
    return {
        "job": job,
        "package": str(package.relative_to(ROOT)),
        "tables_written_direct": direct,
        "tables_written_via_internal_api": sorted(indirect),
        "tables_written": sorted(set(direct) | set(indirect)),
        "tables_read": sorted(reads),
        "internal_apis": sorted(internal),
        "writes_batch_failure_audit": listener,
        "evidence": writes,
        "indirect_via": {k: sorted(v) for k, v in indirect.items()},
    }


def build(java_root: pathlib.Path, suffixes: tuple[str, ...],
          fallback: bool) -> tuple[list[dict], list[str]]:
    tables, daos, api_tables = entity_tables(java_root), dao_to_entity(java_root), static_map()
    params = job_parameters()
    jobs, config_paths, fallback_hits = job_packages(java_root, suffixes, fallback)

    dir_job_counts: dict[str, int] = collections.Counter(str(p) for p in jobs.values())
    disambiguate = fallback or len(suffixes) > 1
    index = class_index(java_root) if disambiguate else {}

    rows = []
    for job, package in sorted(jobs.items()):
        shared = disambiguate and dir_job_counts[str(package)] > 1
        files = (resolve_job_files(config_paths[job], index) if shared
                 else sorted(package.rglob("*.java")))
        row = scan_job(job, package, files, tables, daos, api_tables)
        if disambiguate:
            row["scoped_by_wiring"] = shared
        cfg = params.get(job, {})
        row["parameters"] = cfg
        row["force_async"] = (cfg.get("force_async", "").upper() == "TRUE")
        row["multi_node"] = (cfg.get("is_multi_node", "").upper() == "TRUE")
        row["grid_size"] = cfg.get("force_grid_size")
        row["chunk"] = cfg.get("force_chunk")
        rows.append(row)
    return rows, fallback_hits


CURATED = ROOT / "cursor-bundle" / "kg" / "curated" / "batch_footprint.jsonl"


# Beans that run in many unrelated flows. Attaching a job's table writes to one of these
# claims, for example, that `populateUserDetails` writes the enach representation tables —
# it runs in six services. 84 of the first 486 emitted edges did exactly that.
_SHARED_BEANS = {"populateUserDetails", "populateUserStoryProcessor", "dummyProcessor",
                 "setCommonAttributesProcessor", "fetchBulkUniqueMasterData",
                 "constructRequestDataForApproval", "getMakerCheckerEnabledForUseCaseProcessor"}


def pick_bean(job: str, processors: list[str], exists) -> str | None:
    """The processor that IS this job, never a shared pre-step that merely runs alongside it."""
    stem = job.lower().removesuffix("job").removesuffix("batch")
    candidates = [b for b in processors if b not in _SHARED_BEANS and exists(f"processor:{b}")]
    for test in (lambda b: stem and stem in b.lower(),
                 lambda b: b.endswith(("BatchProcessor", "JobProcessor")),
                 lambda b: True):
        for bean in candidates:
            if test(bean):
                return bean
    return None


def curated_lines(rows: list[dict], repo_dir: str) -> tuple[list[str], list[tuple[str, str]], int]:
    """Build the curated-overlay edge lines for one repo's scanned rows, without writing them.

    Nothing new is invented: every batch job's processor bean is already a KG node, so the
    edges attach to the existing graph and `kg crud <job>` reaches them. `src` names this
    scanner rather than a `.java` line, because these edges are scan-derived and must never be
    mistaken for source-proven.
    """
    import sqlite3
    db = ROOT / "cursor-bundle" / "kg" / "data" / "kg.db"
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True) if db.is_file() else None

    def exists(node_id: str) -> bool:
        if con is None:
            return True
        return con.execute("SELECT 1 FROM nodes WHERE id=?", (node_id,)).fetchone() is not None

    existing = set()
    if con is not None:
        for f, t, r in con.execute(
                "SELECT src_id, dst_id, rel FROM edges WHERE rel IN ('reads','writes','deletes') "
                "AND src_id LIKE 'processor:%' AND (src IS NULL OR src NOT LIKE '%batch_footprint_scan%')"):
            existing.add((f, t, r))

    api = static_map_rows(repo_dir)
    lines, skipped, dupes = [], [], 0
    for row in rows:
        meta = api.get(row["job"])
        if not meta:
            continue
        bean = pick_bean(row["job"], meta["processors"], exists)
        if not bean:
            skipped.append((row["job"], "no processor bean in the KG"))
            continue
        for rel, tables in (("writes", row["tables_written"]),
                            ("reads", row["tables_read"])):
            for table in tables:
                if not exists(f"table:{table}"):
                    skipped.append((row["job"], f"no table node: {table}"))
                    continue
                if (f"processor:{bean}", f"table:{table}", rel) in existing:
                    dupes += 1
                    continue
                lines.append(json.dumps({
                    "t": "edge", "from": f"processor:{bean}", "to": f"table:{table}",
                    "rel": rel,
                    "note": f"batch-footprint scan ({row['job']}): past parallelCommonBatchJob "
                            "dispatch, which the orchestration index cannot follow",
                    "src": "scripts/testing/batch_footprint_scan.py",
                }))
    if con is not None:
        con.close()
    return lines, skipped, dupes


def emit_curated(rows: list[dict], repo_key: str = "accounting",
                 repo_dir: str = "trustt-platform-accounting") -> int:
    """Fold the scanned edges into the KG through its curated overlay.

    `build_curated.py` re-emits `cursor-bundle/kg/curated/*.jsonl` verbatim on every full
    build, and the files are tracked in git, so this survives a rebuild. Writing straight into
    kg.db would not — it would vanish at the next cache-miss build with no error.

    Accounting is regenerated in place, exactly as before this function took a repo argument —
    the only caller left on that path is `--repo accounting --emit-curated`, so its output stays
    byte-identical to what was already tracked. Every other repo only APPENDS: it never
    regenerates accounting's block, and it dedupes its own new lines both against each other and
    against every line already sitting in the file (`curated_lines`'s own kg.db-existing check
    excludes rows this scanner already sourced, since the accounting block already carries that
    `src`, so the in-file check here is the only thing that would catch a coincidental repeat).
    """
    lines, skipped, dupes = curated_lines(rows, repo_dir)
    CURATED.parent.mkdir(parents=True, exist_ok=True)
    if repo_key == "accounting":
        CURATED.write_text("\n".join(lines) + "\n", encoding="utf-8")
        added = len(lines)
        file_dupes = 0
    else:
        existing_lines = set()
        if CURATED.is_file():
            existing_lines = {l for l in CURATED.read_text(encoding="utf-8").splitlines() if l}
        new_lines: list[str] = []
        file_dupes = 0
        for line in lines:
            if line in existing_lines or line in new_lines:
                file_dupes += 1
                continue
            new_lines.append(line)
        if new_lines:
            with CURATED.open("a", encoding="utf-8") as fh:
                for line in new_lines:
                    fh.write(line + "\n")
        added = len(new_lines)
    print(f"curated overlay ({repo_key}): {added} edge(s) → {CURATED.relative_to(ROOT)}")
    if dupes:
        print(f"  {dupes} dropped — already derived from source, and build.sh does not dedup")
    if file_dupes:
        print(f"  {file_dupes} dropped — already present in the tracked overlay file")
    if skipped:
        print(f"  {len(skipped)} skipped (node absent from the KG, never invented):")
        for job, why in skipped[:8]:
            print(f"    {job:40} {why}")
    print("  rebuild: bash cursor-bundle/kg/bin/build.sh --force && kg validate")
    return 0


def preview_curated(rows: list[dict], repo_key: str, repo_dir: str) -> int:
    """Same edges `emit_curated` would produce, written outside the tracked KG overlay.

    Emitting into the graph is a separate gated step — this only proves what that step would
    write, so a repo can be reviewed before `cursor-bundle/kg/curated/` or `kg.db` ever change.
    """
    lines, skipped, dupes = curated_lines(rows, repo_dir)
    preview_path = SCRATCH / f"{repo_key}_curated_preview.jsonl"
    preview_path.parent.mkdir(parents=True, exist_ok=True)
    preview_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"curated preview ({repo_key}): {len(lines)} edge(s) → "
          f"{preview_path.relative_to(ROOT)} (not written into the KG)")
    if dupes:
        print(f"  {dupes} dropped — already derived from source, and build.sh does not dedup")
    if skipped:
        print(f"  {len(skipped)} skipped (node absent from the KG, never invented):")
        for job, why in skipped[:8]:
            print(f"    {job:40} {why}")
    return 0


def static_map_rows(repo_dir: str) -> dict[str, dict]:
    path = FLOW / "platform_api_map.jsonl"
    out: dict[str, dict] = {}
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip() and not line.startswith("#"):
                r = json.loads(line)
                if r["repo"] == repo_dir:
                    out.setdefault(r["api"], r)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--repo", choices=sorted(REPO_CONFIGS), default="accounting")
    ap.add_argument("--job")
    ap.add_argument("--compare", action="store_true")
    ap.add_argument("--emit-curated", action="store_true")
    ap.add_argument("--curated-preview", action="store_true")
    args = ap.parse_args()

    cfg = REPO_CONFIGS[args.repo]
    java_root = ROOT / cfg["dir"] / "src" / "main" / "java"
    repo_dir = cfg["dir"]

    rows, fallback_hits = build(java_root, cfg["suffixes"], cfg["fallback"])

    if args.emit_curated:
        return emit_curated(rows, args.repo, repo_dir)
    if args.curated_preview:
        return preview_curated(rows, args.repo, repo_dir)
    if args.job:
        row = next((r for r in rows if r["job"] == args.job), None)
        if not row:
            print(f"no batch job named {args.job}. known: "
                  + ", ".join(r["job"] for r in rows))
            return 1
        print(json.dumps(row, indent=1))
        return 0

    out_path = OUT if args.repo == "accounting" else SCRATCH / f"{args.repo}_batch_footprint.jsonl"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as fh:
        fh.write("# Batch job table footprint, scanned past the Spring Batch boundary.\n")
        for r in rows:
            fh.write(json.dumps(r) + "\n")

    known = static_map()
    print(f"batch footprint ({args.repo}): {len(rows)} job(s) with a JOB_NAME")
    print(f"{'job':44}{'static':>7}{'scanned':>8}{'gained':>7}")
    total_gain = 0
    for r in rows:
        was = set(known.get(r["job"], []))
        now = set(r["tables_written"])
        gained = len(now - was)
        total_gain += gained
        print(f"{r['job'][:42]:44}{len(was):>7}{len(now):>8}{gained:>7}")
    print(f"\n{total_gain} table-write edges the KG-derived map does not have")
    print(f"  → {out_path.relative_to(ROOT)}")
    if fallback_hits:
        print(f"\n{len(fallback_hits)} job(s) matched only via the config-substring fallback "
              f"(filename suffix not in {cfg['suffixes']}):")
        for stem in fallback_hits:
            print(f"    {stem}")

    if args.compare:
        for r in rows:
            missing = sorted(set(r["tables_written"]) - set(known.get(r["job"], [])))
            if missing:
                print(f"\n{r['job']}: +{len(missing)}")
                for t in missing[:12]:
                    why = r["evidence"].get(t) or f"via {', '.join(r['indirect_via'].get(t, []))}"
                    print(f"    {t:44} {why[:70]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
