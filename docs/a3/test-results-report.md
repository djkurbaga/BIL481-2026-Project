# Test Results Report

**Project:** Green Software Metrics Framework (GSMF)  
**Course:** BIL 481 Software Engineering, Fall 2026  
**Group:** Intellectual Property  
**Version:** 1.2  
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
| 1.2 | 27-11-2026 | Bülent Çakır | Write §1 Test Results Overview, §2 Test Results Analysis and §4 Abstract |

## Task Matrix

**A** = accountable author, **R** = reviewer. TBD rows are assigned by the team.

| Section | Reşat | Bülent | Murat | Furkan |
|---|---|---|---|---|
| 1 Test Results Overview | TBD | **A** | TBD | TBD |
| 2 Test Results Analysis | TBD | **A** | TBD | TBD |
| 3 Logs and Outputs | **A** | TBD | TBD | TBD |
| 4 Abstract (optional) | TBD | **A** | TBD | TBD |

## Contribution Table

| Member | Sections / contribution |
|---|---|
| Reşat Efe Koca (@djkurbaga) | §3 Logs and Outputs; other sections TBD |
| Bülent Çakır (@BulentCakirr) | §1 Test Results Overview, §2 Test Results Analysis, §4 Abstract (AI-assisted, written from the recorded logs in `docs/a3/logs/`) |
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

The four acceptance tests AT-1 to AT-4 are defined in [acceptance-tests.md §2](acceptance-tests.md#2-acceptance-tests). Each one is executed by the matching step of the demo script (`scripts/demo.ps1` on Windows, `scripts/demo.sh` on Linux, both run `scripts/demo.py`). The script reports every step as PASS, FAIL or SKIPPED and exits with code 1 if any step fails. Results below are copied from [demo-output.txt](logs/demo-output.txt), recorded on 27 November 2026 (Windows 11, Python 3.14.2, Docker Desktop 29.9.3, Compose v5.7.1, commit `a437796`).

| Test | Use case / FR | Result | Evidence from the recorded output |
|---|---|---|---|
| AT-1 | UC1 Configure benchmark / FR-1 | **PASS** | `examples/benchmark.yaml` accepted (target `fastapi`, `workload_size=10`, `concurrency=1`, `repetitions=1`, `cooldown_s=0.0`); `examples/invalid-benchmark.yaml` rejected with `ConfigError: targets[0].kind: desteklenmeyen hedef 'bubble'; ...`; no Docker stack was started. |
| AT-2 | UC2 Manage isolated stack lifecycle / FR-3 | **PASS** | Real Docker Compose stack (FastAPI baseline): state `healthy` after the health check, `running` at the workload gate, `stopped` after shutdown; `docker compose ps --all --quiet` returned no containers. |
| AT-3 | UC3 Compute efficiency metrics / FR-8 | **PASS** | 6 of 9 repetitions used for metrics, 3 skipped with their reason (1 failed, 2 invalid). Example: FastAPI #1, 418.00 J / 1000 tasks = 0.4180 J/task; 418.00 J × 18.10 s = 7,565.8 J·s. |
| AT-4 | UC4 Persist and export results / FR-11 | **PASS** | 3 repetitions stored (2 valid, 1 failed with reason), 2 metrics rows stored; duplicate insert and direct `UPDATE` both rejected; [raw](logs/uc4-export/raw_demo-run.csv) and [aggregate](logs/uc4-export/aggregates_demo-run.csv) CSV files exported. |

**Summary:** 4 passed, 0 failed, 0 skipped.

The automated test suite was run on the same machine and commit ([pytest-output.txt](logs/pytest-output.txt), [pytest-junit.xml](logs/pytest-junit.xml)):

| Suite | Tests | Passed | Failed | Errors | Skipped | Time |
|---|---:|---:|---:|---:|---:|---:|
| `python -m pytest` (all modules) | 307 | 307 | 0 | 0 | 0 | 4.42 s |

### 1.2 Issues Encountered

| # | Issue | Effect | Resolution |
|---|---|---|---|
| 1 | On Windows, the stored Compose file path used backslashes (`apps\fastapi\...`) while `tests/test_storage.py` expected `apps/fastapi/...`. | One UC4 test failed on Windows only. | Paths are stored with `as_posix()`; a regression test with `PureWindowsPath` was added (commit `ba5dc95`). |
| 2 | `with sqlite3.connect(...)` in `comparisons/storage_sqlite_vs_csv_json.py` ended the transaction but did not close the connection, so Windows could not delete the temporary folder. | `tests/test_storage_comparison.py` failed on Windows only. | The connection is wrapped in `contextlib.closing(...)` (commit `ba5dc95`, comments in `14b211f`). |
| 3 | A follow-up comment commit (`14b211f`) introduced wrong indentation in `gsmf/storage.py`. | `main` could not be imported and test collection stopped with `IndentationError` until the next commit. | Fixed in `68d58ac`; all 307 tests passed again. |

After these fixes the recorded Windows run in §1.1 has no failures.

## 2 Test Results Analysis

### 2.1 Discrepancies

The recorded results match the expected results of all four acceptance tests. The following limits of the test run should be kept in mind when reading them:

- **Python version.** The project requires Python 3.11+, but the recorded run used Python 3.14.2. The tests were not repeated on Python 3.11, so compatibility with the minimum version is assumed, not shown.
- **Sample data.** AT-3 and AT-4 use `examples/sample_measurements.csv`, which is illustrative sample data, not real measurements. They verify the calculation and storage logic, not the accuracy of energy values.
- **Targets.** AT-2 used only the FastAPI baseline stack. The Budibase and Appsmith stacks were not deployed in this run.
- **Testbed settings.** The testbed settings stored in AT-4 are demo placeholders, because the FR-2 prerequisite checks (CPU governor, Turbo Boost, RAPL access) are not implemented yet.
- **Aggregates.** The aggregate CSV contains mean, median, standard deviation, minimum and maximum, but no 95% confidence intervals; these belong to FR-9, which is not implemented yet.

### 2.2 Failure Causes

No acceptance test failed and none was skipped in the recorded run. The demo script marks AT-2 as SKIPPED only when Docker is not available; Docker Desktop was running, so AT-2 ran against a real stack.

The failures seen before the recorded run (§1.2) had two causes: platform differences between Linux/macOS and Windows (path separators and the rule that an open file cannot be deleted), and a manual edit that was pushed without running the tests.

### 2.3 Potential Solutions

| Risk or gap | Proposed action | Owner |
|---|---|---|
| Untested minimum Python version | Run the test suite on Python 3.11 and the latest Python, on both Windows and Linux, e.g. with a GitHub Actions matrix. | Team |
| Broken commits reaching `main` (issue 3) | Run `python -m pytest -q` before every push; a CI check on pull requests would block such merges. | Team |
| Locale-dependent decoding of Docker output | `gsmf/lifecycle.py` reads Compose output with `text=True` but no explicit encoding, so on Windows it uses the system code page; non-ASCII output could fail to decode. Passing `encoding="utf-8", errors="replace"` (as `gsmf/health.py` already does) removes this risk. | UC2 owner (Murat) |
| Only one target deployed | Add and run Compose files for Budibase and Appsmith in the acceptance run. | FR-2 reference app owners |
| Placeholder testbed settings, no confidence intervals | Implement FR-2 prerequisite checks and FR-9 statistics, then repeat AT-4 with real settings. | FR-2 / FR-9 owners |

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

This report summarizes the Assignment 3 acceptance testing of the Green Software Metrics Framework (GSMF). Four acceptance tests, one per implemented use case (UC1/FR-1 configuration, UC2/FR-3 stack lifecycle, UC3/FR-8 efficiency metrics, UC4/FR-11 persistence and export), were executed with the demo script on Windows 11 with Docker Desktop and Python 3.14.2. All four passed, and the full automated suite of 307 tests passed with no failures or skips. Two Windows-only test failures found earlier were fixed before the recorded run. The main limits are that the energy values are illustrative sample data, only the FastAPI stack was deployed, and the tests were not repeated on the minimum supported Python version (3.11).
