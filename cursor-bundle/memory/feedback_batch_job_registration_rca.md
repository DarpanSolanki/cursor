---
name: feedback_batch_job_registration_rca
description: "For 'is job X registered / why doesn't EOD job run' — trace the buildJobForTenant loader path, not bean-exists/build-green. api_master ≠ batch_job registration. I missed the DPIC EOD-loader gap."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: a76fd569-6e50-4bd0-9bf8-cc808921e5b4
---

**The miss (2026-06-12, DPIC):** User asked why new DPI EOD batch jobs weren't registering at startup. I checked that the `@Component` beans existed + were uniquely named + build was green, declared "registration is fine," and **asked for the log tail** instead of tracing the registration path. The actual cause was statically discoverable: the three `Dpi*BatchConfigService` were never added to `LoanSystemDailyJobLoader` (constructor + `loadJobs()`), so their `buildJobForTenant()` is never called. User found it; I didn't. They were (rightly) furious.

**Why:** I conflated **Spring bean registration** (beans exist — irrelevant) with **batch-job tenant registration** (the explicit wiring that creates `mfi_batch.batch_job` rows and logs `Successfully registered job: <name>`).

**How EOD/daily batch jobs actually register in accounting-v2 (the mechanism to check):**
`Loader.initJobs()` (@PostConstruct) loops tenants → calls `*JobLoader.loadJobs(tenant)` (e.g. `loanSystemDailyJobLoader`, `siJobsLoader`, `trialBalanceJobsLoader`…) → each loader injects `*BatchConfigService` and calls `buildJobForTenant()` → `parallelCommonBatchJob.setUpJobAdvanceV2(...)` → logs `Successfully registered job` + inserts `mfi_batch.batch_job` / group linkage. A job with a `BatchConfigService.buildJobForTenant()` that **no loader invokes** is dead at startup.

**How to apply — for ANY "is job X wired / why doesn't job X run / new batch job not registering":**
1. Don't stop at "bean exists / build green / unique name." Trace `Loader` → which `*JobLoader.loadJobs()` → is `<job>BatchConfigService.buildJobForTenant()` actually CALLED? Grep `grep -rln <ConfigService>` and check callers OUTSIDE its own package.
2. Compare the new job to its **analog in the same loader** (DPI EOD mirrors interest `interestAccrualCalculation/Booking + loanAccountBilling` in `LoanSystemDailyJobLoader`). If the analog is in the loader and the new one isn't → that's the gap.
3. `platform_master.api_master` only enables **HTTP routing** to the orchestration Request. It is NOT batch registration. Don't treat api_master rows (or orchestration XML, or the Java impl) as proof a batch job will run.
4. Don't defer to "send me the logs" when the answer is statically discoverable — the symptom ("not registering") points straight at the loader wiring. Use the `batch-atlas-lookup` skill's registration knowledge, don't just name it.

Reinforces [[feedback_proof_backed_agent_discipline]] (widen-search-before-deciding-absent) and [[feedback_config_resolution_rca]] (trace to the real decision-point). Skill: batch-atlas-lookup.
