# Test Results Report

**Project:** Green Software Metrics Framework (GSMF)  
**Course:** BIL 481 Software Engineering, Fall 2026  
**Group:** Intellectual Property  
**Version:** 1.1  
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
| 1.0 | 27-11-2026 | Reşat Efe Koca | Initial skeleton and §3 Logs and Outputs |
| 1.1 | 27-11-2026 | Reşat Efe Koca | Align section headings with the Assignment 3 handout; add Task Matrix |

## Task Matrix

**A** = accountable author, **R** = reviewer. TBD rows are assigned by the team.

| Section | Reşat | Bülent | Murat | Furkan |
|---|---|---|---|---|
| 1 Test Results Overview | TBD | TBD | TBD | TBD |
| 2 Test Results Analysis | TBD | TBD | TBD | TBD |
| 3 Logs and Outputs | **A** | TBD | TBD | TBD |
| 4 Abstract (optional) | TBD | TBD | TBD | TBD |

## Contribution Table

| Member | Sections / contribution |
|---|---|
| Reşat Efe Koca (@djkurbaga) | §3 Logs and Outputs; other sections TBD |
| Bülent Çakır (@BulentCakirr) | TBD |
| Murat Yılmaz (@yilmazmurat06) | TBD |
| Furkan Yaman (@furkany22) | TBD |

## Table of Contents

1. [Test Results Overview](#1-test-results-overview)
   1. [Pass/Fail per Acceptance Test](#11-passfail-per-acceptance-test)
   2. [Issues Encountered](#12-issues-encountered)
2. [Test Results Analysis](#2-test-results-analysis)
   1. [Discrepancies](#21-discrepancies)
   2. [Failure Causes](#22-failure-causes)
   3. [Potential Solutions](#23-potential-solutions)
3. [Logs and Outputs](#3-logs-and-outputs)
4. [Abstract (optional)](#4-abstract-optional)

<div style="page-break-after: always;"></div>

## 1 Test Results Overview

### 1.1 Pass/Fail per Acceptance Test

To be written by: TBD

### 1.2 Issues Encountered

To be written by: TBD

## 2 Test Results Analysis

### 2.1 Discrepancies

To be written by: TBD

### 2.2 Failure Causes

To be written by: TBD

### 2.3 Potential Solutions

To be written by: TBD

## 3 Logs and Outputs

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

## 4 Abstract (optional)

To be written by: TBD
