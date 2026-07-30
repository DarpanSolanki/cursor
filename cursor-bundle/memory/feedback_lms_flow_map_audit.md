# Feedback: LMS flow map must be audited — broad paths swallow specific APIs

**When:** 2026-07-29  
**Trigger:** TDPQA-207 — `PrepaymentDetailsRepository` mapped to `loanPrepayment` via `/loan/prepayment/` so ship impact never selected `getLoanForeclosureDetails` / BY_LATEST real API test.

## Finding (full LMS scan)

- KG: ~1883 requests, ~904 accounting processors  
- Broad package needles (`/loan/prepayment/`, `/disbursement/`, `deathforeclosure`) collapsed dozens of distinct APIs into one ship target  
- Critical misroutes fixed in `change_test_map.json` v2 (specific class/path before broad)  
- Durable audit: `python3 scripts/lib/lms_flow_map_audit.py` (CRITICAL stems fail-closed)

## Standing rules

1. Specific processor/file needles **before** package paths.  
2. Map api must be in KG `invokes` set for that processor (alias OK only when documented, e.g. ChildLoanForeclosure → individualChildLoanForeclosure for registry).  
3. Shared DAOs map to **primary** API; siblings via `domain_mandatory_suite`.  
4. Domain `api_hints` without registry cases = coverage gap (listed by audit), not silent PASS for those APIs.

## Agent rule

Before claiming “flows mapped” or money ship: run `lms_flow_map_audit.py`; CRITICAL mismatches = stop.
