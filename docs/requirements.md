# Requirements Document

**Project:** Green Software Metrics Framework (GSMF)
**Course:** BIL 481 Software Engineering, Fall 2026
**Group:** Intellectual Property
**Document date:** 01-11-2026

**Contributors to this document:**

|Name|GitHub|School Number|
|-|-|-|
|Reşat Efe Koca|@djkurbaga|231301010|
|Bülent Çakır|@BulentCakirr|231301064|
|Murat Yılmaz|@yilmazmurat06|241101063|
|Furkan Yaman|@furkany22|221301015|

\---

## Table of Contents

1. [Introduction](#1-introduction)
2. [Definitions](#2-definitions)
3. [Functional Requirements](#3-functional-requirements)
4. [Non-Functional Requirements](#4-non-functional-requirements)
5. [Document-Specific Task Matrix](#5-document-specific-task-matrix)

\---

## 1\. Introduction

This document lists the functional and non-functional requirements of GSMF, a CLI-based framework that measures and compares the energy consumption and efficiency of the same reference application running on Budibase, Appsmith (self-hosted in Docker) and a hand-coded FastAPI baseline. Each requirement is numbered and written so that it can be verified by a test or a demonstration.

## 2\. Definitions

* **Target:** one platform stack under test (Budibase, Appsmith or FastAPI baseline).
* **Testbed:** the Linux machine that runs the target and reads RAPL energy counters.
* **Load generator:** a separate machine that runs the k6 workload against the testbed.
* **User task (R):** one completed sequence of create item + paginated list + batch update.
* **Net energy:** gross RAPL energy during the workload minus idle power × workload duration.
* **EDP:** Energy-Delay Product = net energy (J) × duration (s).
* **Operational SCI:** (E × I) / R, where E is net energy in kWh, I is grid carbon intensity (gCO2eq/kWh), reported per 1,000 user tasks.

## 3\. Functional Requirements

### FR-1 to FR-7 — Benchmark Execution and Measurement

**FR-1 — Benchmark configuration.** The system shall load a YAML configuration specifying target platforms, workload size, concurrency, repetition count and cooldown duration. It shall reject missing required fields, unsupported targets and invalid numeric values with an explanatory error before starting a platform stack. Workload size, concurrency and repetition count shall be positive integers; cooldown duration shall be non-negative.

**FR-2 — Execution prerequisites.** Before a benchmark begins, the system shall check Docker availability, access to the required RAPL counters and connectivity to the load generator with k6 available. It shall record the testbed CPU governor and Turbo Boost setting, and prevent execution when the required fixed-governor and disabled-Turbo conditions cannot be confirmed. Failed checks shall identify the unmet prerequisite.

**FR-3 — Isolated stack lifecycle.** The system shall start each selected target using its Docker Compose configuration and wait for its health checks to pass within a defined timeout before measuring it. It shall stop the target after completion or failure and shall not start the next target until shutdown is confirmed. A failed startup, health check or shutdown shall be reported as an execution failure.

**FR-4 — Repetition and cooldown control.** The system shall execute the configured number of repetitions for each selected platform and apply the configured cooldown between consecutive repetitions and platform transitions. It shall assign each repetition an identifier and record its target, configuration and completion status. Failed repetitions shall be retained as failed records and excluded from valid measurement aggregates.

**FR-5 — Idle baseline measurement.** With the target running and no reference workload active, the system shall measure RAPL energy over a recorded idle interval and calculate average idle power as idle energy divided by interval duration. It shall record the sampled RAPL domains and use the same domains for the corresponding workload measurement. Unreadable counters or a non-positive interval shall invalidate the measurement.

**FR-6 — Remote reference workload.** The system shall trigger the k6 workload on the separate load-generator machine using the configured workload size and concurrency. The workload shall implement the defined user-task sequence of item creation, paginated listing and batch update. The system shall collect execution status, elapsed time, completed user-task count and workload errors; only fully successful sequences shall count as completed user tasks. Remote execution failures shall mark the repetition as failed.

**FR-7 — Workload energy and baseline correction.** The system shall measure gross RAPL energy over the workload interval and calculate net energy as gross energy minus average idle power multiplied by the measured interval duration. Counter differences shall account for wraparound using the reported counter range. Each record shall retain gross energy, idle power, interval duration, net energy and completed user-task count. Unusable counter readings, negative net energy or zero completed user tasks shall be flagged as invalid and excluded from valid measurement aggregates, without silently replacing the measured values.

## 4\. Non-Functional Requirements

| ID | Category | Requirement | Verification |
|---|---|---|---|
| NFR-1 | Reliability / measurement rigor | Before a run, the system must set the CPU governor to `performance`, disable Turbo Boost and refuse to start if these settings cannot be applied (unless an override flag is given). | Run log reports applied settings; failure case is tested. |
| NFR-2 | Accuracy | The load generator must run on a separate machine from the testbed so that its CPU usage is not included in the energy readings. | Configuration validation rejects a load-generator address equal to the testbed. |
| NFR-3 | Performance | The measurement process on the testbed must use less than 2% CPU on average during a run. | Measured with `pidstat` during a benchmark. |
| NFR-4 | Reproducibility | A full benchmark must be reproducible from the repository README and configuration file without code changes; platform versions must be pinned in Compose files. | A team member who did not write the code runs the benchmark successfully. |
| NFR-5 | Statistical quality | With default settings, the 95% confidence interval half-width of mean net energy should be below 10% of the mean for each target. | Checked in the summary report. |
| NFR-6 | Usability | All main actions (run, report, export, dashboard) must be available as CLI commands with `--help` documentation. | Each command prints usage help. |
| NFR-7 | Portability | The tool must run on Ubuntu 22.04 or 24.04 on Intel x86 hardware with RAPL support, and must report a clear error if RAPL is not available. | Tested on the testbed and on a machine without RAPL access. |
| NFR-8 | Cost | The system must use only free or open-source software and require no paid services. | Dependency list review. |

## 5\. Document-Specific Task Matrix

|Task|Responsible|
|-|-|
|Introduction and definitions|Reşat Efe Koca|
|Functional requirements FR-1 to FR-7|Murat Yılmaz|
|Functional requirements FR-8 to FR-14|Reşat Efe Koca|
|Non-functional requirements|Furkan Yaman|
|Verification column and consistency review|Bülent Çakır|
|Formatting and final PDF|Bülent Çakır|



