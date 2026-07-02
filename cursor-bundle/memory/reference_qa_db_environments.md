# QA database environments (read-only RCA)

**Manifest (no secrets):** `scripts/db/env/qa-manifest.json`  
**Credentials (gitignored):** `scripts/db/env/qa{N}.env`

| Env | Host | DB | User | Wrapper |
|-----|------|-----|------|---------|
| qa1 | 172.31.2.87 | mfi_qa1 | appuser | `scripts/db-qa1.sh` |
| qa2 | 172.31.2.84 | mfi_qa2 | qateam | `scripts/db-qa2.sh` |
| qa3 | 172.31.2.37 | mfi_qa3 | qateam | `scripts/db-qa3.sh` |
| qa4 | 172.31.2.236 | mfi_qa4 | darpan | `scripts/db-qa4.sh` |
| qa5 | 172.31.2.138 | mfi_qa5 | qateam | `scripts/db-qa5.sh` |

## Agent RCA rule

When the user says **QA2 issue**, **mfi_qa3**, etc. → use the matching `db-qa{N}.sh`, **not** `db-local.sh`.

```bash
scripts/db-qa.sh --list
scripts/bin/setup-qa-db.sh --all
scripts/db-qa3.sh --canned 01-loan-status-by-lan --param account_number=<LAN>
```

Read-only by default. `--allow-write` only when user explicitly requests a QA data change.

Preflight verified: 2026-06-22 (all 5 reachable from local machine).
