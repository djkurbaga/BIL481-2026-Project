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

**FR-8 — Efficiency metrics.** For each valid repetition, the system shall calculate energy per completed user task as net energy divided by completed user-task count, and the Energy-Delay Product (EDP) as net energy multiplied by the measured interval duration. Units shall be recorded as joules per user task and joule-seconds. Metrics shall not be calculated for invalid or failed repetitions.

**FR-9 — Statistical aggregation.** For each target, the system shall aggregate valid repetitions and calculate the mean, median, standard deviation and 95% confidence interval of net energy, interval duration, energy per user task and EDP. It shall report the number of valid and failed repetitions used for each target. When fewer than two valid repetitions exist, the system shall report that the confidence interval cannot be calculated instead of producing a value.

**FR-10 — Operational SCI calculation.** The system shall calculate operational SCI per target as net energy in kWh multiplied by the configured grid carbon intensity in gCO2eq/kWh, divided by completed user tasks, and report it in gCO2eq per 1,000 user tasks. The grid carbon intensity, its unit and source shall be read from the configuration and stored with the results. Embodied carbon shall not be included, and the report shall state this boundary.

**FR-11 — Result persistence and export.** The system shall store every repetition record, including failed and invalid ones with their status and reason, together with the configuration, target versions and testbed settings, in an SQLite database. The user shall be able to export raw repetition records and aggregated results of a selected run as CSV files. Stored measured values shall not be modified by later calculations.

**FR-12 — Summary and report generation.** After a run completes, the system shall display a terminal summary table comparing all targets by net energy, energy per user task, EDP, operational SCI and confidence intervals. It shall generate a Markdown report containing the same results, run configuration, experimental conditions and the number of valid and failed repetitions. Reports shall be generated only from stored records.

**FR-13 — Results dashboard.** The system shall provide a local web dashboard where the user can select a completed run and view a comparison table and bar charts of energy per user task and EDP for each target. Displayed values shall match the stored aggregated results and CSV export of the same run.

**FR-14 — Optional per-container diagnostics.** When enabled in the configuration, the system shall collect per-container energy shares using Scaphandre during the workload interval and include them in the report as a secondary diagnostic. These values shall be labeled as estimates and shall not replace or alter the RAPL-based net energy results. If Scaphandre is unavailable, the system shall continue the run and record that diagnostics were skipped.

## 4\. Non-Functional Requirements

## 5\. Document-Specific Task Matrix

|Task|Responsible|
|-|-|
|Introduction and definitions|Reşat Efe Koca|
|Functional requirements FR-1 to FR-7|Murat Yılmaz|
|Functional requirements FR-8 to FR-14|Reşat Efe Koca|
|Non-functional requirements|Furkan Yaman|
|Verification column and consistency review|Bülent Çakır|
|Formatting and final PDF|Bülent Çakır|



