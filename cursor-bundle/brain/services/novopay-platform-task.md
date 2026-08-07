# `novopay-platform-task` — Operator task store, TAT/escalation, delegation

> The "what's on my plate" service. Every operator-facing action — review a maker draft, follow up a collection, dispatch a document, complete a BET — surfaces as a row in this service. Owns task creation, lifecycle (open/in-progress/closed/reopened), TAT escalation, delegation, and BPMN-style workflow chaining.

## Identity

| Field | Value |
|---|---|
| Java root package | `in.novopay` (top-level for legacy reasons) |
| DB schema | `mfi_task` |
| Repo | [`novopay-platform-task/`](../../novopay-platform-task/) |
| Service .cursorrules | [`trustt-platform-task/.cursorrules`](../../trustt-platform-task/.cursorrules) |

## API surface

| XML | Lines | Domain |
|---|---:|---|
| `ServiceOrchestrationXML.xml` | 793 | Generic CRUD + lifecycle + employee/office tree |
| `mfi_orchestration.xml` | 722 | MFI-specific task ops + LOS task views + delegation |
| `orc_collection.xml` | 77 | Collection-specific task lookups |

**Top Requests** (Service + MFI XMLs):
- CRUD: `deleteTaskType`, `getTaskTypeDetails`, `getTaskTypeList`, `createOrUpdateTask`, `deleteTask`, `getTaskDetails`, `getTaskList`, `getLifecycleList`
- Lifecycle: `updateTaskStatus`, `bulkUpdateTaskStatus`, `reopenClosedTask`, `getTaskListCount`
- Hierarchy: `getEmployeeChildren`, `getOfficeBreadcrumbs`
- MFI extras: `createOrUpdateTaskMfi`, `deleteTaskMfi`, `getTaskDetailsMfi`, `getRoleCodesByTaskIds`, `createOrUpdateMfiTaskByCode`
- LOS-side views: `getLosTaskCount`, `getLosTaskList`, `getPoolTasks`
- Status + chained execution: `updateTaskStatusAndCallApi` (the pattern that runs an arbitrary follow-up API after status flip)
- Delegation: `getTasklistForDelegation`, `createTaskDelegation`, `updateTaskDelegation`
- Home + bulk: `getHomeScreenCount`, `bulkCreateTask`, `getTaskSubTypeList`
- TAT: `notifyUsersForPendingTasksJob` (scheduled; sends user reminders)
- Collection-specific (orc_collection.xml): `getTaskActivityList`, `getTaskListByIds`, `getCollectionLimitIncreaseHistory`, `getCollectionDepositTimeExtensionHistory`, `updateAooTaskDetailsNewApprover`

## Kafka

Producer: `producer_id_task`.

| Consumer | Topic prefix |
|---|---|
| `taskUserTatConsumer` | `task_user_tat_*` |
| `collectionTaskCreationConsumer` | `collection_task_creation_*` |
| `finnoneCollectionTaskCreationConsumer` | `finnone_collection_task_creation_*` |

## Outbound HTTP

- actor (employee/office hierarchy resolution; cascades drive delegation/escalation)
- approval (maker-checker on task config changes)
- authorization (role/permission check)
- notifications (TAT escalation, assignment alerts)
- task itself (`getTimelineAction` for delegation context)

## Inbound — who creates tasks

- LOS — every workflow stage that needs operator action (BET schedule, doc dispatch, CU review)
- Accounting — every maker-checker step that asks for an operator (e.g. foreclosure approval task)
- Payments — collection follow-ups, supervisory review
- Webapp + android task screens — direct user actions
- Approval service — checker pickup tasks

## DB clusters

| Cluster | Tables |
|---|---|
| Core | `task`, `task_attributes` |
| Lifecycle | `task_activity`, `task_extension` |
| Delegation | `task_delegation`, `task_delegation_details` |
| Workflow | `workflow_master`, `workflow_master_stages`, `workflow_stage_details` |
| Config | `task_type`, `task_type_version` |
| Async | `task_api_execution_pending`, `task_delegation_api_execution` |
| Escalation | `tat_escalation_matrix` |

## Concepts owned

- **Task type** — class of task (e.g. `LOAN_FORECLOSURE_REVIEW`, `COLLECTION_FOLLOWUP`). Versioned via `task_type_version`.
- **Task lifecycle** — open → in-progress → closed (or reopened). `task_activity` is the event log.
- **TAT escalation** — `tat_escalation_matrix` defines threshold + escalation target; jobs `rejectExpiredBatchJob`, `calculateUserTatBatch` enforce.
- **Delegation** — temporary reassignment of tasks across the hierarchy.
- **Workflow** — chain of stages (`workflow_master` → `workflow_master_stages` → `workflow_stage_details`); used for multi-step approvals.

## Known gotchas

1. **`task_activity` grows fast** — partitioning required at scale.
2. **Hierarchy must match actor** — `getEmployeeChildren` calls actor; out-of-sync hierarchy causes mis-delegation.
3. **TAT batch jobs (`rejectExpiredBatchJob`, `calculateUserTatBatch`) must run reliably** — failures leave tasks with stale TAT.
4. **`updateTaskStatusAndCallApi`** is a powerful pattern but couples task state to arbitrary downstream effects; trace carefully when debugging.
