# QA database environments (read-only RCA)

**Manifest (no secrets):** `scripts/db/env/qa-manifest.json`  
**Credentials (gitignored):** `scripts/db/env/qa{N}.env`

| Env | Host | Alt host | DB | User | Wrapper |
|-----|------|----------|-----|------|---------|
| qa1 | 172.31.2.82 | 172.31.2.198 | mfi_qa1 | qateam | `scripts/db-qa1.sh` |
| qa2 | 172.31.2.70 | — | mfi_qa2 | qateam | `scripts/db-qa2.sh` |
| qa3 | 172.31.2.98 | — | mfi_qa3 | qateam | `scripts/db-qa3.sh` |
| qa4 | 172.31.2.147 | — | mfi_qa4 | qateam | `scripts/db-qa4.sh` |
| qa5 | 172.31.2.7 | — | mfi_qa5 | qateam | `scripts/db-qa5.sh` |
| qa6 | 172.31.2.61 | — | mfi_qa6 | qateam | `scripts/db-qa6.sh` |

**Users:** `qateam` (primary in env files). `devteam` is documented fallback for QA1 if `qateam` auth fails — update `PGUSER`/`PGPASSWORD` in the matching gitignored `qa1.env` only.

## Agent RCA rule

When the user says **QA2 issue**, **mfi_qa3**, etc. → use the matching `db-qa{N}.sh`, **not** `db-local.sh`.

```bash
scripts/db-qa.sh --list
scripts/bin/setup-qa-db.sh --all
scripts/db-qa3.sh --canned 01-loan-status-by-lan --param account_number=<LAN>
```

Read-only by default. `--allow-write` only when user explicitly requests a QA data change.

Preflight verified: 2026-07-20 (hosts rotated — re-run `setup-qa-db.sh --all` after credential changes).
