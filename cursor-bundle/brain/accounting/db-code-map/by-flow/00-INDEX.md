# By-flow → tables touched

For each major LMS flow, this folder lists the tables it writes/reads in execution order, with code anchors. Use this when you need to know "what does this flow actually touch in the DB?".

| Flow | Doc |
|---|---|
| Disbursement (LOS → accounting → bank) | [disbursement.md](disbursement.md) |
| Repayment | [repayment.md](repayment.md) |
| SHG/JLG fan-out | [shg-jlg-fanout.md](shg-jlg-fanout.md) |
| EOD/BOD daily cycle | [eod-bod.md](eod-bod.md) |
| NPA classification | [npa-classification.md](npa-classification.md) |
| Foreclosure & closure | [foreclosure.md](foreclosure.md) |

Each doc cross-links to:
- The flow narrative in `claude/flows/`
- The per-table docs in `../tables/`
- Runbooks in `claude/runbooks/`
