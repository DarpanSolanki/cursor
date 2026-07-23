#!/usr/bin/env python3
"""
build_money_concepts.py — logical money table aliases + CRUD edges (Upgrade 10).

1) client_reference_number: scan @Entity fields / @Column for the column name;
   emit table:client_reference_number (logical) + resolves_to → owning @Table;
   link ClientReferenceNumberDedupProcessor (reads) and CreateTransactionMasterProcessor (writes).

2) account_entry: alias → transaction_details (posting legs) when that table exists;
   link processors that write transaction_details.

Config: cursor-bundle/kg/build_config.json money_concept_aliases (documentation only —
physical discovery is still code-driven).

Usage: build_money_concepts.py <accumulated_raw.jsonl> <repoDir> [...]
"""
import os, re, sys, json, glob

def emit(o): sys.stdout.write(json.dumps(o, ensure_ascii=False) + "\n")

KNOWN_TABLE = set()
KNOWN_PROC = set()

def load_known(tmp):
    for line in open(tmp, encoding="utf-8", errors="replace"):
        try:
            o = json.loads(line)
        except Exception:
            continue
        if o.get("t") != "node":
            continue
        if o.get("kind") == "table":
            KNOWN_TABLE.add(o["id"][len("table:"):])
        elif o.get("kind") == "processor":
            KNOWN_PROC.add(o["id"][len("processor:"):])

TABLE_RE = re.compile(r'@Table\s*\(\s*name\s*=\s*"([^"]+)"')
COLUMN_RE = re.compile(
    r'(?:@Column\s*\(\s*name\s*=\s*"client_reference_number"\s*\)|private\s+\w+\s+clientReferenceNumber\b)',
    re.I,
)
CLASS_RE = re.compile(r'\b(?:class|interface)\s+([A-Z]\w*)')

def repo_name(p):
    for seg in os.path.abspath(p).split(os.sep):
        if seg.startswith("novopay-") or seg.startswith("trustt-"):
            return seg
    return os.path.basename(p.rstrip(os.sep))

def main():
    tmp = sys.argv[1]
    repos = sys.argv[2:]
    load_known(tmp)

    # --- client_reference_number from entity columns ---
    owners = []  # (physical_table, repo, src)
    for repo_dir in repos:
        repo = repo_name(repo_dir)
        for jf in glob.glob(os.path.join(repo_dir, "src", "main", "java", "**", "*.java"), recursive=True):
            try:
                txt = open(jf, encoding="utf-8", errors="replace").read()
            except OSError:
                continue
            if "clientReferenceNumber" not in txt and "client_reference_number" not in txt:
                continue
            if "@Entity" not in txt or "@Table" not in txt:
                continue
            if not COLUMN_RE.search(txt) and "clientReferenceNumber" not in txt:
                continue
            tm = TABLE_RE.search(txt)
            if not tm:
                continue
            phys = tm.group(1)
            if phys not in KNOWN_TABLE:
                continue
            rel = os.path.relpath(jf, start=os.getcwd())
            owners.append((phys, repo, rel))

    if owners:
        # prefer transaction_master as primary resolve target when present
        owners_sorted = sorted(owners, key=lambda x: (0 if x[0] == "transaction_master" else 1, x[0]))
        primary = owners_sorted[0]
        emit({
            "t": "node", "id": "table:client_reference_number", "kind": "table",
            "label": "client_reference_number", "repo": primary[1],
            "role": "money_key_column",
            "src": primary[2],
            "note": "logical money key; physical column on one or more @Table entities",
        })
        seen_phys = set()
        for phys, repo, src in owners_sorted:
            if phys in seen_phys:
                continue
            seen_phys.add(phys)
            emit({
                "t": "edge", "from": "table:client_reference_number", "to": f"table:{phys}",
                "rel": "resolves_to", "note": "column_on", "src": src,
            })
        # Dedup + create master edges
        if "clientReferenceNumberDedupProcessor" in KNOWN_PROC:
            emit({
                "t": "edge", "from": "processor:clientReferenceNumberDedupProcessor",
                "to": "table:client_reference_number", "rel": "reads",
                "note": "dedup_lookup", "src": "build_money_concepts.py",
            })
            if "transaction_master" in KNOWN_TABLE:
                emit({
                    "t": "edge", "from": "processor:clientReferenceNumberDedupProcessor",
                    "to": "table:transaction_master", "rel": "reads",
                    "note": "findOneByClientCodeAndClientReferenceNumber", "src": "build_money_concepts.py",
                })
        if "createTransactionMasterProcessor" in KNOWN_PROC:
            emit({
                "t": "edge", "from": "processor:createTransactionMasterProcessor",
                "to": "table:client_reference_number", "rel": "writes",
                "note": "persist_crn_on_tm", "src": "build_money_concepts.py",
            })

    # --- account_entry alias → transaction_details ---
    if "transaction_details" in KNOWN_TABLE:
        # find owning repo from known nodes in tmp
        owner_repo = "trustt-platform-accounting"
        for line in open(tmp, encoding="utf-8", errors="replace"):
            try:
                o = json.loads(line)
            except Exception:
                continue
            if o.get("id") == "table:transaction_details":
                owner_repo = o.get("repo") or owner_repo
                src = o.get("src") or "build_money_concepts.py"
                break
        else:
            src = "build_money_concepts.py"
        emit({
            "t": "node", "id": "table:account_entry", "kind": "table",
            "label": "account_entry", "repo": owner_repo,
            "role": "money_alias",
            "src": src,
            "note": "conceptual posting entry → transaction_details",
        })
        emit({
            "t": "edge", "from": "table:account_entry", "to": "table:transaction_details",
            "rel": "resolves_to", "note": "alias_to", "src": "build_money_concepts.py",
        })
        for bean in ("createTransactionDetailsProcessor", "doGLTransferProcessor", "reverseTransactionProcessor"):
            if bean in KNOWN_PROC:
                emit({
                    "t": "edge", "from": f"processor:{bean}", "to": "table:account_entry",
                    "rel": "writes", "note": "posting_via_alias", "src": "build_money_concepts.py",
                })

if __name__ == "__main__":
    main()
