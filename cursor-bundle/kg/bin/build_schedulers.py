#!/usr/bin/env python3
"""
build_schedulers.py — kind=scheduler nodes from scheduler-registry (Upgrade 10).

Parses `.cursor/scheduler-registry.md` and `cursor-bundle/brain/platform/scheduler-registry.md`
for Service|Class rows and backtick job/scheduler names. Emits scheduler nodes +
triggers edges to owning service and matching request/processor labels when present.

Usage: build_schedulers.py <accumulated_raw.jsonl>
"""
import re, sys, json
from pathlib import Path

def emit(o):
    sys.stdout.write(json.dumps(o, ensure_ascii=False) + "\n")

WORKSPACE = Path(__file__).resolve().parents[3]
KNOWN_REQ: dict[str, list[str]] = {}
KNOWN_PROC: set[str] = set()
KNOWN_SVC: set[str] = set()

# Legacy novopay-* names in the registry → trustt-* repo/service ids
SVC_ALIAS = {
    "novopay-platform-lib": "trustt-platform-lib",
    "novopay-platform-accounting-v2": "trustt-platform-accounting",
    "novopay-mfi-los": "trustt-platform-los",
    "novopay-platform-payments": "trustt-platform-payments",
    "novopay-platform-task": "trustt-platform-task",
    "novopay-platform-actor": "trustt-platform-actor",
    "novopay-platform-batch": "trustt-platform-batch",
    "novopay-platform-api-gateway": "trustt-platform-api-gateway",
    "novopay-platform-notifications": "trustt-platform-notifications",
}

NAME_RE = re.compile(
    r"`([A-Za-z][A-Za-z0-9_]*(?:Job|Batch|Scheduler|ConfigService|Executor|Config)[A-Za-z0-9_]*)`"
)
EXTRA = re.compile(
    r"`(AutoScheduler|processJobs|ThreadPoolTaskScheduler|ScheduleBatchGroupExecutor|"
    r"SchedulingGroupProcessor|SchedulerCommonService|sessionPurge|rejectExpiredBatchJob)`"
)
# Table row: | service | `Class` | ...
ROW_RE = re.compile(
    r"\|\s*([a-z0-9][a-z0-9._-]*)\s*\|\s*`([A-Za-z][A-Za-z0-9_]*)`\s*\|"
)
JOB_NAME_RE = re.compile(r"JOB_NAME\s*=\s*`?([A-Za-z][A-Za-z0-9_]*)`?")


def load_known(tmp: str) -> None:
    for line in open(tmp, encoding="utf-8", errors="replace"):
        try:
            o = json.loads(line)
        except Exception:
            continue
        if o.get("t") != "node":
            continue
        kind = o.get("kind")
        if kind == "request":
            KNOWN_REQ.setdefault(o["label"], []).append(o["id"])
        elif kind == "processor":
            KNOWN_PROC.add(o["label"])
        elif kind == "service":
            KNOWN_SVC.add(o["id"])


def normalize_svc(raw: str) -> str | None:
    name = SVC_ALIAS.get(raw, raw)
    if name.startswith("trustt-") or name.startswith("novopay-"):
        return name
    return None


def link_requests(sid: str, names: set[str], rel_src: str) -> None:
    for name in names:
        if name in KNOWN_REQ:
            for rid in KNOWN_REQ[name]:
                emit({"t": "edge", "from": sid, "to": rid, "rel": "triggers", "src": rel_src,
                      "note": "label match"})
        bean = name[0].lower() + name[1:] if name and name[0].isupper() else name
        stem = re.sub(
            r"(BatchConfigService|BatchJobConfig|ConfigService|Config|Processor)$",
            "",
            name,
        )
        for cand in (name, bean, bean + "Processor", name + "Processor", stem, stem + "Job"):
            if cand in KNOWN_PROC:
                emit({"t": "edge", "from": sid, "to": f"processor:{cand}",
                      "rel": "triggers", "src": rel_src, "note": "processor match"})
                break
            if cand in KNOWN_REQ:
                for rid in KNOWN_REQ[cand]:
                    emit({"t": "edge", "from": sid, "to": rid, "rel": "triggers",
                          "src": rel_src, "note": "stem request match"})
                break


def scan_java_jobs(seen: set[str]) -> None:
    """Source of truth: Spring Batch JobBuilder / JOB_NAME in service Java (T5)."""
    JOB_BUILDER = re.compile(
        r'(?:JobBuilder|jobBuilder)\s*\(\s*"([^"]+)"'
        r'|JOB_NAME\s*=\s*"([^"]+)"'
        r'|(?:public|private)\s+Job\s+(\w+)\s*\('
    )
    for d in sorted(WORKSPACE.iterdir()):
        if not d.is_dir() or not (d / ".git").is_dir():
            continue
        if not (d.name.startswith("trustt-") or d.name.startswith("novopay-")):
            continue
        repo = SVC_ALIAS.get(d.name, d.name)
        for jf in d.glob("src/main/java/**/*.java"):
            try:
                txt = jf.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if "JobBuilder" not in txt and "JOB_NAME" not in txt and " Job " not in txt:
                continue
            rel = str(jf.relative_to(WORKSPACE))
            for m in JOB_BUILDER.finditer(txt):
                name = next(g for g in m.groups() if g)
                if name in seen:
                    continue
                seen.add(name)
                sid = f"scheduler:{name}"
                emit({
                    "t": "node", "id": sid, "kind": "scheduler", "label": name,
                    "repo": repo, "src": rel, "note": "spring_batch_job",
                })
                svc_id = f"service:{repo}"
                emit({"t": "edge", "from": sid, "to": svc_id, "rel": "triggers",
                      "src": rel, "note": "owns batch job"})
                link_requests(sid, {name}, rel)


def main() -> None:
    tmp = sys.argv[1]
    load_known(tmp)
    seen: set[str] = set()
    # (a) Java JobBuilder / JOB_NAME — primary source
    scan_java_jobs(seen)
    paths = [
        WORKSPACE / ".cursor" / "scheduler-registry.md",
        WORKSPACE / "cursor-bundle" / "brain" / "platform" / "scheduler-registry.md",
    ]
    # bean -> owning service
    owners: dict[str, str] = {}
    job_aliases: set[str] = set()

    for path in paths:
        if not path.is_file():
            continue
        txt = path.read_text(encoding="utf-8", errors="replace")
        rel = str(path.relative_to(WORKSPACE))
        for m in ROW_RE.finditer(txt):
            svc_raw, cls = m.group(1), m.group(2)
            svc = normalize_svc(svc_raw)
            if svc:
                owners[cls] = svc
        job_aliases |= set(JOB_NAME_RE.findall(txt))
        names = set(NAME_RE.findall(txt)) | set(EXTRA.findall(txt)) | set(owners.keys()) | job_aliases
        for name in sorted(names):
            if name in seen:
                # enrichment only — attach registry note edge if owner known
                if name in owners:
                    sid = f"scheduler:{name}"
                    svc = owners[name]
                    svc_id = f"service:{svc}"
                    if svc_id in KNOWN_SVC or svc.startswith("trustt-"):
                        emit({"t": "edge", "from": sid, "to": svc_id, "rel": "triggers",
                              "src": rel, "note": "registry enrichment"})
                continue
            seen.add(name)
            sid = f"scheduler:{name}"
            svc = owners.get(name)
            emit({
                "t": "node", "id": sid, "kind": "scheduler", "label": name,
                "repo": svc or "", "src": rel, "note": "scheduler-registry",
            })
            if svc:
                svc_id = f"service:{svc}"
                emit({"t": "edge", "from": sid, "to": svc_id, "rel": "triggers",
                      "src": rel, "note": "owns batch schedule"})
            extra = job_aliases if name.startswith("Reject") else set()
            link_requests(sid, {name} | extra, rel)

    for jn in sorted(job_aliases):
        if jn in seen:
            continue
        seen.add(jn)
        sid = f"scheduler:{jn}"
        emit({
            "t": "node", "id": sid, "kind": "scheduler", "label": jn,
            "repo": "trustt-platform-task", "src": ".cursor/scheduler-registry.md",
            "note": "JOB_NAME from registry",
        })
        emit({"t": "edge", "from": sid, "to": "service:trustt-platform-task",
              "rel": "triggers", "src": ".cursor/scheduler-registry.md",
              "note": "owns batch schedule"})
        link_requests(sid, {jn}, ".cursor/scheduler-registry.md")


if __name__ == "__main__":
    main()
