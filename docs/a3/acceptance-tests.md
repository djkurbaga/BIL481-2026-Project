# Acceptance Tests and Criteria

<!-- Section headings are a proposed structure. Check them against the Assignment 3 handout before filling in. -->

**Project:** Green Software Metrics Framework (GSMF)  
**Course:** BIL 481 Software Engineering, Fall 2026  
**Group:** Intellectual Property  
**Version:** 1.0  
**Date:** 27-11-2026

## List of Contributors

| Name | GitHub | School Number |
|---|---|---|
| Reşat Efe Koca | @djkurbaga | 231301010 |
| Bülent Çakır | @BulentCakirr | 231301064 |
| Murat Yılmaz | @yilmazmurat06 | 241101063 |
| Furkan Yaman | @furkany22 | 221301015 |

## Change Record

| Version | Date | Author | Description |
|---|---|---|---|
| 1.0 | 27-11-2026 | Reşat Efe Koca | Initial skeleton and §8 Logs and Outputs |

## Contribution Table

| Member | Sections / contribution |
|---|---|
| Reşat Efe Koca (@djkurbaga) | §8 Logs and Outputs; other sections TBD |
| Bülent Çakır (@BulentCakirr) | TBD |
| Murat Yılmaz (@yilmazmurat06) | TBD |
| Furkan Yaman (@furkany22) | TBD |

## Table of Contents

1. [Introduction](#1-introduction)
   1. [Purpose](#11-purpose)
   2. [Scope (UC1–UC4)](#12-scope-uc1uc4)
2. [Acceptance Criteria](#2-acceptance-criteria)
   1. [UC1 — Configure Benchmark (FR-1)](#21-uc1--configure-benchmark-fr-1)
   2. [UC2 — Manage Isolated Stack Lifecycle (FR-3)](#22-uc2--manage-isolated-stack-lifecycle-fr-3)
   3. [UC3 — Compute Efficiency Metrics (FR-8)](#23-uc3--compute-efficiency-metrics-fr-8)
   4. [UC4 — Persist and Export Results (FR-11)](#24-uc4--persist-and-export-results-fr-11)
3. [Acceptance Test Cases](#3-acceptance-test-cases)
   1. [UC1 — Configure Benchmark (FR-1)](#31-uc1--configure-benchmark-fr-1)
   2. [UC2 — Manage Isolated Stack Lifecycle (FR-3)](#32-uc2--manage-isolated-stack-lifecycle-fr-3)
   3. [UC3 — Compute Efficiency Metrics (FR-8)](#33-uc3--compute-efficiency-metrics-fr-8)
   4. [UC4 — Persist and Export Results (FR-11)](#34-uc4--persist-and-export-results-fr-11)
4. [Test Environment and Data](#4-test-environment-and-data)
5. [Execution Procedure](#5-execution-procedure)
6. [Pass/Fail Rules and Sign-off](#6-passfail-rules-and-sign-off)
7. [Traceability Matrix](#7-traceability-matrix)
8. [Logs and Outputs](#8-logs-and-outputs)

<div style="page-break-after: always;"></div>

## 1 Introduction

### 1.1 Purpose

To be written by: TBD

### 1.2 Scope (UC1–UC4)

To be written by: TBD

## 2 Acceptance Criteria

### 2.1 UC1 — Configure Benchmark (FR-1)

To be written by: TBD

### 2.2 UC2 — Manage Isolated Stack Lifecycle (FR-3)

To be written by: TBD

### 2.3 UC3 — Compute Efficiency Metrics (FR-8)

To be written by: TBD

### 2.4 UC4 — Persist and Export Results (FR-11)

To be written by: TBD

## 3 Acceptance Test Cases

### 3.1 UC1 — Configure Benchmark (FR-1)

To be written by: TBD

### 3.2 UC2 — Manage Isolated Stack Lifecycle (FR-3)

To be written by: TBD

### 3.3 UC3 — Compute Efficiency Metrics (FR-8)

To be written by: TBD

### 3.4 UC4 — Persist and Export Results (FR-11)

To be written by: TBD

## 4 Test Environment and Data

To be written by: TBD

## 5 Execution Procedure

To be written by: TBD

## 6 Pass/Fail Rules and Sign-off

To be written by: TBD

## 7 Traceability Matrix

To be written by: TBD

## 8 Logs and Outputs

Recorded by Reşat Efe Koca on 27 November 2026 from commit `a437796` (branch `feature/a3-demo-and-logs`). The files are unedited command outputs; see [environment.txt](logs/environment.txt) for the exact commands and versions.

| File | Contents | Result |
|---|---|---|
| [pytest-output.txt](logs/pytest-output.txt) | `python -m pytest -v --junitxml=...` (full verbose output) | 307 passed, 0 failed |
| [pytest-junit.xml](logs/pytest-junit.xml) | JUnit XML of the same run | `tests="307"`, no failures or errors |
| [demo-output.txt](logs/demo-output.txt) | `scripts/demo.ps1 --out docs/a3/logs/uc4-export` | UC1, UC2, UC3, UC4: PASS (4 passed, 0 failed, 0 skipped) |
| [uc4-export/raw_demo-run.csv](logs/uc4-export/raw_demo-run.csv) | UC4 raw export of the demo run | 3 repetitions: 2 valid, 1 failed with reason |
| [uc4-export/aggregates_demo-run.csv](logs/uc4-export/aggregates_demo-run.csv) | UC4 aggregate export of the demo run | 1 target (fastapi), 2 metrics rows aggregated |
| [environment.txt](logs/environment.txt) | Date, git commit, OS, Python, Docker, Docker Compose, `pip freeze` | Windows 11, Python 3.14.2, Docker 29.9.3, Compose v5.7.1 |

Notes on these outputs:

- UC2 ran against a real Docker Compose stack (FastAPI baseline); it was not skipped.
- UC3 and UC4 use `examples/sample_measurements.csv`, which is **illustrative sample data, not real measurements**. UC4 stores only the FastAPI rows because `examples/benchmark.yaml` configures only that target.
- The UC4 testbed settings in the demo are placeholders; FR-2 prerequisite checks are not implemented yet.
- The SQLite file created by the demo is not committed; it is recreated by running the demo.
- To reproduce: `pip install -r requirements.txt`, then `powershell -ExecutionPolicy Bypass -File scripts/demo.ps1` (Windows) or `bash scripts/demo.sh` (Linux).
