# SHG-only group children

- Only **SHG** group loans have child LANs (`parent_loan_account_id` set).
- **JLG** and **INDL** do not have child loans — never describe or filter them as parent/child group members.
- Interest accrual reader/partitioner exclude: `parent_loan_account_id IS NULL` (drops SHG children only; JLG/INDL already null).
