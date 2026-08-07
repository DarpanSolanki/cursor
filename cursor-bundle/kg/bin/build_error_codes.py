#!/usr/bin/env python3
"""
build_error_codes.py — index every error-code THROW SITE from Java source.

Why: an RCA almost always starts from an error code. Before this layer the KG only
knew the 13 codes that happened to be mentioned in brain/changelog/CHANGELOG.md, so
`kg error 132168` answered "not seen in any case" and the agent fell back to grep.

Accuracy contract (do not weaken):
  * DERIVED, never inferred — every edge carries repo/path:line from a real parse.
  * BRANCH-QUALIFIED — each throw site records the branch+sha of the repo it was read
    from. A code thrown at different sites on different trains yields several edges,
    each labelled; nothing silently picks one.
  * CONSTANTS ARE NOT GUESSED — a constant token resolves only against a literal found
    in the SAME repo, or a globally unambiguous one. `MFIConstants.INVALID_ERROR_CODE`
    is "LOS-0016" in los and reporting; a name carrying two different values in one
    repo is left unresolved rather than picked.
  * DYNAMIC SITES ARE NOT INVENTED — `throw new NovopayFatalException(errorCode)` and
    rethrows (`e.getErrorCode()`) are counted as dynamic and skipped, never mapped to
    a plausible code.
  * NO TEMPLATES FROM HERE — code -> message templates live only in runtime (Redis db2
    / notification_message), not in any repo, so they are NOT branch truth and are
    resolved at query time with an explicit provenance label instead.

Usage: build_error_codes.py <accumulated_raw.jsonl> <repoDir> [<repoDir> ...]
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

CODE_SHAPE = re.compile(r"^(?:\d{3,6}|[A-Z][A-Z0-9]{1,7}(?:-[A-Z0-9]+)+)$")
EXC = re.compile(r"new\s+Novopay(Fatal|NonFatal)Exception\s*\(\s*([^),]+)")
STR_CONST = re.compile(r'\bString\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*"([^"]{2,24})"')
STR_ANY = re.compile(r'\bString\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*"([^"]{1,64})"')
CLASS_RE = re.compile(r"\b(?:class|interface|enum)\s+([A-Z]\w*)")
DYNAMIC = re.compile(r"^[a-z_]\w*$|\)|\(")
# Placeholder keys the message template will need: the executionContext.put(...) calls
# immediately preceding a throw are what StrSubstitutor resolves ${...} against.
EC_PUT = re.compile(r"\.put(?:Local)?\s*\(\s*([A-Za-z_][\w.]*|\"[^\"]+\")\s*,")
CTX_WINDOW = 600


def emit(o) -> None:
    sys.stdout.write(json.dumps(o, ensure_ascii=False) + "\n")


def git(d: str, *a: str) -> str:
    try:
        return subprocess.check_output(
            ["git", "-C", d, *a], text=True, stderr=subprocess.DEVNULL
        ).strip()
    except Exception:
        return ""


def strip_comments(txt: str) -> str:
    """Blank comments WITHOUT moving any line.

    Collapsing a block comment to one space shifts every line after a licence header,
    which silently produced wrong file:line for ~40% of sites. Keep the newlines.
    """
    txt = re.sub(r"/\*.*?\*/", lambda m: "\n" * m.group(0).count("\n"), txt, flags=re.S)
    return re.sub(r"//[^\n]*", "", txt)


def bean_name(cls: str) -> str:
    if len(cls) > 1 and cls[0].isupper() and cls[1].isupper():
        return cls
    return cls[0].lower() + cls[1:] if cls else cls


def load_known_processors(tmp: str) -> set[str]:
    known: set[str] = set()
    try:
        for line in open(tmp, encoding="utf-8", errors="replace"):
            try:
                o = json.loads(line)
            except Exception:
                continue
            if o.get("t") == "node" and o.get("kind") == "processor":
                known.add(o["id"][len("processor:"):])
    except OSError:
        pass
    return known


def collapse(seen: dict[str, set[str]]) -> dict[str, str]:
    return {k: next(iter(v)) for k, v in seen.items() if len(v) == 1}


def main() -> None:
    if len(sys.argv) < 3:
        print("usage: build_error_codes.py <raw.jsonl> <repo> [repo...]", file=sys.stderr)
        sys.exit(2)
    tmp, repos = sys.argv[1], sys.argv[2:]
    known_proc = load_known_processors(tmp)

    files: dict[str, list[tuple[Path, str]]] = {}
    per_repo: dict[str, dict[str, set[str]]] = {}
    global_seen: dict[str, set[str]] = defaultdict(set)
    key_seen: dict[str, set[str]] = defaultdict(set)
    qualified_codes: dict[str, str] = {}
    qualified_keys: dict[str, str] = {}

    for repo in repos:
        keep: list[tuple[Path, str]] = []
        seen: dict[str, set[str]] = defaultdict(set)
        for f in Path(repo).rglob("src/main/java/**/*.java"):
            try:
                raw = f.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if '= "' not in raw and "NovopayFatalException" not in raw \
                    and "NovopayNonFatalException" not in raw:
                continue
            txt = strip_comments(raw)
            cmatch = CLASS_RE.search(txt)
            owner = cmatch.group(1) if cmatch else f.stem
            for const, val in STR_CONST.findall(txt):
                if CODE_SHAPE.match(val):
                    seen[const].add(val)
                    global_seen[const].add(val)
                    qualified_codes[f"{owner}.{const}"] = val
            for const, val in STR_ANY.findall(txt):
                key_seen[const].add(val)
                qualified_keys[f"{owner}.{const}"] = val
            if "NovopayFatalException" in txt or "NovopayNonFatalException" in txt:
                keep.append((f, txt))
        files[repo] = keep
        per_repo[repo] = seen

    global_consts = collapse(global_seen)
    ctx_consts = collapse(key_seen)

    def ctx_keys(txt: str, pos: int) -> list[str]:
        out: list[str] = []
        for km in EC_PUT.finditer(txt, max(0, pos - CTX_WINDOW), pos):
            tok = km.group(1)
            if tok.startswith('"'):
                val = tok.strip('"')
            else:
                val = qualified_keys.get(tok) or ctx_consts.get(tok.split(".")[-1], "")
            if val and re.match(r"^[a-z][a-z0-9_]*$", val) and val not in out:
                out.append(val)
        return out

    codes: dict[str, dict] = {}
    edges: list[dict] = []
    dynamic = unresolved = 0

    for repo in repos:
        branch = git(repo, "rev-parse", "--abbrev-ref", "HEAD")
        sha = git(repo, "rev-parse", "--short=10", "HEAD")
        repo_consts = collapse(per_repo[repo])
        for f, txt in files[repo]:
            local = {c: v for c, v in STR_CONST.findall(txt) if CODE_SHAPE.match(v)}
            cm = CLASS_RE.search(txt)
            cls = cm.group(1) if cm else f.stem
            rel = str(f).replace("\\", "/")

            for m in EXC.finditer(txt):
                sev, tok = m.group(1), m.group(2).strip()
                line = txt.count("\n", 0, m.start()) + 1
                code = None
                via = "literal"
                lit = re.match(r'^"([^"]+)"$', tok)
                if lit:
                    if not CODE_SHAPE.match(lit.group(1)):
                        unresolved += 1
                        continue
                    code = lit.group(1)
                else:
                    key = tok.split(".")[-1].strip()
                    if DYNAMIC.search(tok) and key not in local and tok not in qualified_codes \
                            and key not in repo_consts and key not in global_consts:
                        dynamic += 1
                        continue
                    if key in local:
                        code, via = local[key], f"const:{key}@file"
                    elif tok in qualified_codes:
                        code, via = qualified_codes[tok], f"const:{tok}@qualified"
                    elif key in repo_consts:
                        code, via = repo_consts[key], f"const:{key}@repo"
                    elif key in global_consts:
                        code, via = global_consts[key], f"const:{key}@global"
                if not code:
                    unresolved += 1
                    continue

                site = f"{rel}:{line}"
                nid = f"error:{code}"
                rec = codes.setdefault(
                    nid,
                    {"t": "node", "id": nid, "kind": "error", "label": code,
                     "role": "throw_site", "src": site, "sites": 0, "branches": []},
                )
                rec["sites"] += 1
                if branch and branch not in rec["branches"]:
                    rec["branches"].append(branch)

                bean = bean_name(cls)
                frm = f"processor:{bean}" if bean in known_proc else f"symbol:{repo}/{cls}"
                keys = ctx_keys(txt, m.start())
                edges.append({
                    "t": "edge", "from": frm, "to": nid, "rel": "throws",
                    "src": site, "repo": repo, "branch": branch, "sha": sha,
                    "severity": "FATAL" if sev == "Fatal" else "NON_FATAL",
                    "cls": cls, "resolved_via": via,
                    **({"ctx_keys": ",".join(keys)} if keys else {}),
                })
                for k in keys:
                    if k not in rec.setdefault("ctx_keys", []):
                        rec["ctx_keys"].append(k)

    for rec in codes.values():
        rec["branches"] = ",".join(sorted(rec["branches"]))
        if rec.get("ctx_keys"):
            rec["ctx_keys"] = ",".join(rec["ctx_keys"])
        emit(rec)
    for e in edges:
        emit(e)

    print(
        f"build_error_codes: {len(codes)} codes, {len(edges)} throw sites "
        f"({dynamic} dynamic, {unresolved} unresolved — skipped, not guessed)",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
