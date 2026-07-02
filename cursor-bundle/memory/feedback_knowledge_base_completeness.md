---
name: feedback_knowledge_base_completeness
description: "STANDING DIRECTIVE: the workspace must be the complete known-LMS knowledge base. Capture the activation/wiring/bootstrap layer (what makes a flow EXIST & reachable), not just business flows + runtime. Proactively scan the WHOLE system for systemic gaps and curate docs+KG+skills+memory — don't narrowly fix only the reported symptom."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: a76fd569-6e50-4bd0-9bf8-cc808921e5b4
---

**The directive (2026-06-12, user escalated twice, "I will not tell you again"):** "Find ALL the gaps — not only batch — which you have not included in the KG and working setup. Read everything, understand what is happening, then curate documents and improve the setup. Make the workspace the complete known-LMS system."

**The blind spot it exposed:** the knowledge base (brain docs + KG + skills) is organized around **business flows** (Request → processors → tables → GL) and the **runtime** path. It has **no first-class treatment of the application activation/bootstrap/wiring layer** — the things that must exist for a flow to be reachable AT ALL:
- batch-job registration (`Loader.initJobs @PostConstruct → *JobLoader.loadJobs → BatchConfigService.buildJobForTenant → setUpJobAdvanceV2 → mfi_batch.batch_job/batch_schedule auto-seed`), `BatchJobPlaceholderConfig` stub beans — see [[feedback_batch_job_registration_rca]];
- `api_master`/ServiceRegistry HTTP routing (≠ batch registration);
- orchestration `<Request>` load-order across the *_orc.xml files;
- Kafka consumer/producer wiring (MessageBroker.xml);
- scheduler mechanisms (@Scheduled vs batch-service AutoScheduler vs task-cron);
- cache registration + @CacheEvict pairing; multi-tenant bootstrap (ThreadLocalContext / tenant-prefixed schema); Flyway version allocation across modules.
Every artifact answered "what does this DO," none answered "what makes this EXIST." That is why coded-but-never-wired features (the dpi* EOD jobs) were missed repeatedly.

**How to apply (standing):**
1. When investigating ANY "why doesn't X run / is X wired" — trace the activation chain, not just the flow. "Code exists + build green + api_master row" ≠ "it runs."
2. When a systemic mechanism is found undocumented, curate it into the substrate the same turn — a structural brain doc (not a loose island), the feature-development-playbook placement matrix, the relevant skill, AND the KG (doc node / curated edge), then rebuild `claude/kg/bin/build.sh`. Reinforces [[feedback_keep_knowledge_current]].
3. The feature-development-playbook 12-layer matrix MUST include the activation layers (loader wiring, placeholder bean, api_master, consumer wiring, scheduler, cache eviction) so green-field features don't drop them silently.
4. Proactively hunt the gap CLASS, not just the reported instance — "not only batch." The dimension is "activation/wiring/bootstrap" across all 17 services.

Master discipline: [[feedback_proof_backed_agent_discipline]] (widen-search). Worked instance: [[feedback_batch_job_registration_rca]].
