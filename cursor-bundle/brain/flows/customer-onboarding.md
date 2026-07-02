# Flow — Customer onboarding (individual + SHG/JLG group)

## Mental model

A new borrower is captured in **LOS first** (lead → KYC → personal details), persisted in `los.borrower_*` and `los.loan_app__customer_details`, and then **promoted to actor** as a `customer` row. For SHG/JLG, multiple customers are bound into a `group_details` row. Documents go into DMS; OTPs through notifications. No money moves yet.

## Services involved

| Service | What it does |
|---|---|
| LOS | Captures lead, KYC, personal/financial details, group formation |
| actor | Stores customer master, promotes from LOS, group/meeting-centre |
| dms | Stores KYC documents |
| notifications | OTP for Aadhaar/mobile verification |
| masterdata | Pin-code, state/district/VTC lookups |
| audit | Framework-emitted audit rows |

## Step-by-step (individual)

```
1. Field officer scans Aadhaar / enters PAN on android app
   ▼
2. Webapp/android → gateway → LOS:createOrUpdateLead
   ─ INSERT los.lead row
   ─ initial dedupe via performInternalMobileDedupe (sync)
   ▼
3. KYC capture: LOS:createOrUpdateBorrowerKycDetails
   ─ Aadhaar OTP via notifications service (Redis DB 0, no DB row)
   ─ panValidation, voterIdAuthentication
   ─ DMS upload of KYC docs
   ─ writes borrower_reference, aadhaar_ref_mapping, aadhaar_redaction_status
   ▼
4. Personal + address: LOS:createOrUpdateLoanAppPersonalDetails
   ─ resolves pin → state/district/VTC via masterdata
   ─ writes loan_app__customer_details, address (LOS-side)
   ▼
5. Bureau pipeline (async):
   - LOS publishes to Kafka topics indl_qde_borrower_*_factiva_*, _posidex_*, _multi_bureau_*
   - LOS consumers (factivaConsumer, posidexConsumer, multiBureauConsumer) process responses
   - Result captured as deviation/eligibility decision
   ▼
6. Promotion to actor: LOS:createMfiCustomer ─HTTP─▶ actor:createMfiCustomer
   ─ INSERT actor.customer + actor.address rows
   ─ returns customer_id back to LOS
   ▼
7. customer_id stored on loan_app__customer_details
```

## Step-by-step (SHG/JLG group formation — additional)

```
After 5 group members are individually onboarded (steps 1-7 above) per member:

8. LOS:createOrUpdateGroup → creates group_details (LOS-side)
   ─ writes group__member_details (one per member with member_loan_app_id)
9. Group eligibility checks (FLCC, dedupe across members, household income aggregation)
   ─ processGroupFormationEligibilityRules
   ─ writes loan_app__flcc_group, loan_app__flcc_group_member
10. LOS:updateGroupSignatories → identifies the 2-3 group officers
11. Meeting centre allocation: actor:allocateMeetingCenter
    ─ writes meeting_center_allocation (mapping group → centre → field officer)
12. Group state advances: GroupStatusTypeEnum transitions
```

The group, once formed, is what the **loan application** (next flow) is created against. Disbursement creates a parent loan_account with `parent_account_id IS NULL`, and per-member child loan_accounts.

## DB writes summary

| Service | Tables |
|---|---|
| LOS | `lead`, `loan_app`, `loan_app__customer_details`, `borrower_reference`, `aadhaar_ref_mapping`, `aadhaar_redaction_status`, `re_kyc_details`, `posidex_status_log`, `group_details`, `group__member_details`, `loan_app__flcc_group(_member)` |
| actor | `customer`, `address`, `actor__address__mapping`, `meeting_center_allocation` |
| dms | `document_master`, `file_master`, `document_tags` |
| audit | `audit_log` (via framework `<AuditData>`) |

## Failure modes

| Symptom | First check |
|---|---|
| OTP not received | notifications service `notification_sms_*` consumer health; Redis DB 0 OTP key TTL |
| Aadhaar dedup mismatch | `borrower_reference` + `aadhaar_redaction_status`; verify recent re-KYC |
| Bureau call hung | LOS bureau consumers (factiva/posidex/multibureau); check retry topics |
| `createMfiCustomer` failed | actor service log; common: schema validation on phone format / DOB |
| Group not formed | `loan_app__flcc_group` validation; `processGroupFormationEligibilityRules` deviation list |

## Where to dig deeper

- LOS service brain: [`../services/novopay-mfi-los.md`](../services/novopay-mfi-los.md) §"Lifecycle stages"
- actor service brain: [`../services/novopay-platform-actor.md`](../services/novopay-platform-actor.md)
- Bureau Kafka topology: [`../system/08-kafka-topology.md`](../system/08-kafka-topology.md)
- Notifications + OTP: [`../services/novopay-platform-notifications.md`](../services/novopay-platform-notifications.md)
