# Test Results Report

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
| 1.0 | 27-11-2026 | Reşat Efe Koca | Initial skeleton and §9 Logs and Outputs |

## Contribution Table

| Member | Sections / contribution |
|---|---|
| Reşat Efe Koca (@djkurbaga) | §9 Logs and Outputs; other sections TBD |
| Bülent Çakır (@BulentCakirr) | TBD |
| Murat Yılmaz (@yilmazmurat06) | TBD |
| Furkan Yaman (@furkany22) | TBD |

## Table of Contents

1. [Introduction](#1-introduction)
   1. [Purpose](#11-purpose)
   2. [Scope (UC1–UC4)](#12-scope-uc1uc4)
2. [Test Environment](#2-test-environment)
3. [Test Execution Summary](#3-test-execution-summary)
   1. [Automated Tests](#31-automated-tests)
   2. [End-to-End Demo](#32-end-to-end-demo)
4. [Results by Use Case](#4-results-by-use-case)
   1. [UC1 — Configure Benchmark (FR-1)](#41-uc1--configure-benchmark-fr-1)
   2. [UC2 — Manage Isolated Stack Lifecycle (FR-3)](#42-uc2--manage-isolated-stack-lifecycle-fr-3)
   3. [UC3 — Compute Efficiency Metrics (FR-8)](#43-uc3--compute-efficiency-metrics-fr-8)
   4. [UC4 — Persist and Export Results (FR-11)](#44-uc4--persist-and-export-results-fr-11)
5. [Defects and Resolutions](#5-defects-and-resolutions)
6. [Coverage and Traceability](#6-coverage-and-traceability)
7. [Limitations and Untested Areas](#7-limitations-and-untested-areas)
8. [Conclusion and Recommendations](#8-conclusion-and-recommendations)
9. [Logs and Outputs](#9-logs-and-outputs)

<div style="page-break-after: always;"></div>

## 1 Introduction

### 1.1 Purpose

To be written by: TBD

### 1.2 Scope (UC1–UC4)

To be written by: TBD

## 2 Test Environment

To be written by: TBD

## 3 Test Execution Summary

### 3.1 Automated Tests

To be written by: TBD

### 3.2 End-to-End Demo

To be written by: TBD

## 4 Results by Use Case

### 4.1 UC1 — Configure Benchmark (FR-1)

To be written by: TBD

### 4.2 UC2 — Manage Isolated Stack Lifecycle (FR-3)

To be written by: TBD

### 4.3 UC3 — Compute Efficiency Metrics (FR-8)

To be written by: TBD

### 4.4 UC4 — Persist and Export Results (FR-11)

To be written by: TBD

## 5 Defects and Resolutions

To be written by: TBD

## 6 Coverage and Traceability

To be written by: TBD

## 7 Limitations and Untested Areas

To be written by: TBD

## 8 Conclusion and Recommendations

To be written by: TBD

## 9 Logs and Outputs

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
