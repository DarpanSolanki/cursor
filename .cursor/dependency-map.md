# Dependency & version risk map

**Scan:** all `**/build.gradle` under workspace service roots + `novopay-platform-lib/**/build.gradle` + `novopay-platform-dependency-mgmt/build.gradle`. **`pom.xml`:** none in tree. **`package.json`:** `novopay-platform-webapp/package.json` (Angular 20.x — separate from JVM stack). **`requirements.txt`:** none. **Date:** 2026-04-07.

## 1. Platform / Novopay Gradle plugin coordinates (by consuming root)

| Service / root | Buildscript plugin coordinate (classpath) | Risk |
|----------------|------------------------------------------|------|
| novopay-platform-accounting-v2 | `in.novopay:accounting.dependency.gradle.plugin:3.2.6.6-1` | **Drift vs BOM** — see below |
| novopay-mfi-los | `in.novopay:los.dependency.gradle.plugin:3.2.6.6-1` | Same |
| novopay-platform-actor | `actor.dependency.gradle.plugin:3.2.6.6-1` | Aligned patch train |
| novopay-platform-api-gateway | *(no novopay plugin in first lines; plain Boot)* | Uses Boot 3.5.6 — resolves BOM externally |
| novopay-platform-payments | `payments.dependency.gradle.plugin:3.2.6.6-1` | Aligned |
| novopay-platform-task | `task.dependency.gradle.plugin:3.2.6.6-1` | Aligned |
| novopay-platform-audit | `audit.dependency.gradle.plugin:3.2.6.6-1` | Aligned |
| novopay-platform-batch | `batch.dependency.gradle.plugin:3.2.6.6-1` | Aligned |
| novopay-platform-notifications | `notifications.dependency.gradle.plugin:3.2.6.6-1` | Aligned |
| novopay-platform-approval | `approval.dependency.gradle.plugin:3.2.6.6-1` | Aligned |
| novopay-platform-authorization | `authorization.dependency.gradle.plugin:3.2.6.6-1` | Aligned |
| novopay-platform-masterdata-management | `masterdata.dependency.gradle.plugin:3.2.6.6-1` | Aligned |
| novopay-platform-dms | `dms.dependency.gradle.plugin:3.2.6.6-1` | Aligned |
| novopay-platform-simulators/chameleon | `chameleon.dependency.gradle.plugin:3.2.6.6-1` | Note: **dependency-mgmt** publishes chameleon **3.2.7-2** — verify which is canonical |
| novopay-platform-lib/infra-platform | `infra.platform.dependency.gradle.plugin:3.2.4-1` | **Older infra plugin on lib source tree** |
| novopay-platform-lib/infra-accounting | `infra.accounting.dependency.gradle.plugin:3.2.4-1` | **Older** |
| novopay-platform-lib/infra-transaction-hdfc | `infra.transaction.hdfc.dependency.gradle.plugin:3.2.6.3-1` | **3.2.6.3-1** train |
| novopay-platform-lib/util-platform | `infra.util.platform.dependency.gradle.plugin:3.2.6.3-1` | **3.2.6.3-1** |
| novopay-platform-lib/infra-transaction-interface | `infra.transaction.interface.dependency.gradle.plugin:3.2.6.3-1` | **3.2.6.3-1** |
| novopay-platform-lib/infra-transaction-internal-interface | `infra.transaction.internal.interface.dependency.gradle.plugin:3.2.6.3-1` | **3.2.6.3-1** |
| novopay-platform-dependency-mgmt (published catalog) | Multiple plugins at **`3.2.6.6.2-1`**; `infra.navigation` **`3.2.7-2`**; `reporting` **`3.3.2-1`**; domain infra plugins **`3.2.4-1`** | **Source of truth for released versions** |

### platform-lib version alignment

- **Not identical:** services uniformly declare **`3.2.6.6-1`** on the classpath line while **`novopay-platform-dependency-mgmt`** publishes **`3.2.6.6.2-1`** for the same logical plugins — agents must assume **resolved artifact wins** at publish time; the **two patch strings differ** and are a **release hygiene risk** (documented as High in `gaps-and-risks.md`).
- **Within `novopay-platform-lib`:** mix of **`3.2.4-1`**, **`3.2.6.3-1`**, and modules inheriting from composite — expect **non-uniform** infra BOM alignment inside the monorepo build.

## 2. Spring Boot (major / minor) — services

| Dependency | Version | Where | Risk |
|------------|---------|-------|------|
| `org.springframework.boot` plugin | **3.5.6** | accounting-v2, los, actor, payments, task, audit, batch, notifications, approval, authorization, masterdata, dms, api-gateway | **Higher** than infra-platform/lib subprojects documented at **3.2.11** in `.cursor/architecture.md` — **major Boot skew** between **application** and **library** compile targets is intentional per composite build but increases “works in service / breaks in lib” drift risk |
| Spring Cloud BOM (accounting-v2 ext) | **2023.0.1** | `novopay-platform-accounting-v2/build.gradle` `ext.springCloudVersion` | Medium — verify other services use same BOM where applicable |

## 3. Dead / orphan dependencies

| Item | Note |
|------|------|
| No unused `requirements.txt` | N/A |
| Webapp | Uses **npm** stack only for UI; not part of Gradle multi-service BOM — not “dead”, but **not validated by this Gradle scan** |

## 4. Duplicated coordinates with different versions (conflict risk)

| Coordinate family | Versions observed | Risk |
|--------------------|-------------------|------|
| Novopay Gradle plugins | `3.2.4-1` vs `3.2.6.3-1` vs `3.2.6.6-1` vs `3.2.6.6.2-1` vs `3.2.7-2` vs `3.3.2-1` | **High** — accidental resolution of wrong plugin line can change transitive `novopay-platform-lib` artifacts |
| Chameleon | `3.2.6.6-1` in simulator `build.gradle` vs `3.2.7-2` in dependency-mgmt | Medium — verify release pipeline |

---

**Evidence paths:** `novopay-platform-accounting-v2/build.gradle`, `novopay-mfi-los/build.gradle`, `novopay-platform-dependency-mgmt/build.gradle`, `novopay-platform-lib/infra-platform/build.gradle`, `novopay-platform-lib/infra-transaction-hdfc/build.gradle`.
