# QA catch-up SQL queue (per-env)

Updated: 2026-07-31 — bone JOURNEY+TRAIN+ENV

| Env | Status NOW | Catch-up block | Ready? |
|-----|------------|----------------|--------|
| local | REACHABLE | N/A (fixture) | — |
| qa1 | REACHABLE | See `ready/qa1_placeholder.sql` — no owed money patch this bone | READY empty |
| qa2 | **UNREACHABLE** | Blocked until VPN/DB up — do not run | BLOCKED |
| qa3 | REACHABLE | empty — no owed SQL this bone | READY empty |
| qa4 | REACHABLE | empty | READY empty |
| qa5 | REACHABLE | empty | READY empty |
| qa6 | **UNREACHABLE** | Blocked | BLOCKED |
| uat/prod | N/A | forbidden writes | — |

When a money fix needs QA data verify: add `ready/<env>_<ticket>.sql` (SELECT-only by default) and set Ready=YES.
