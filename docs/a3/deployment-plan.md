# Deployment Plan

**Project:** Green Software Metrics Framework (GSMF)  
**Course:** BIL 481 Software Engineering, Fall 2026  
**Group:** Intellectual Property  
**Version:** 1.2\
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
| 1.0 | 27-11-2026 | Reşat Efe Koca | Initial skeleton and §4 Logs and Outputs |
| 1.1 | 27-11-2026 | Reşat Efe Koca | Align section headings with the Assignment 3 handout; add Task Matrix |
| 1.2 | 27-11-2026 | Murat Yılmaz | Document the demo environment, deployment procedure and cleanup in §§1–2 |

## Task Matrix

**A** = accountable author, **R** = reviewer. TBD rows are assigned by the team.

| Section | Reşat | Bülent | Murat | Furkan |
|---|---|---|---|---|
| 1 Deployment Overview | TBD | TBD | **A** | TBD |
| 2 Deployment Process | TBD | TBD | **A** | TBD |
| 3 Configuration Plan | TBD | TBD | TBD | TBD |
| 4 Logs and Outputs | **A** | TBD | TBD | TBD |

## Contribution Table

| Member | Sections / contribution |
|---|---|
| Reşat Efe Koca (@djkurbaga) | §4 Logs and Outputs; other sections TBD |
| Bülent Çakır (@BulentCakirr) | TBD |
| Murat Yılmaz (@yilmazmurat06) | §§1–2 Demo deployment, environment prerequisites and cleanup (AI-assisted) |
| Furkan Yaman (@furkany22) | TBD |

## Table of Contents

1. [Deployment Overview](#1-deployment-overview)
   1. [Approach](#11-approach)
   2. [Tools](#12-tools)
   3. [Environment](#13-environment)
2. [Deployment Process](#2-deployment-process)
   1. [Step-by-Step Procedure](#21-step-by-step-procedure)
   2. [Scripts and Tools](#22-scripts-and-tools)
   3. [Configurations](#23-configurations)
3. [Configuration Plan](#3-configuration-plan)
   1. [Final Configuration](#31-final-configuration)
   2. [Changes Made During Deployment](#32-changes-made-during-deployment)
4. [Logs and Outputs](#4-logs-and-outputs)

<div style="page-break-after: always;"></div>

## 1 Deployment Overview

### 1.1 Approach

Run the Assignment 3 demo from a specific Git revision in a local Python environment. UC1 validates the benchmark YAML (FR-1). UC2 builds and deploys the FastAPI baseline in a dedicated Docker Compose project, checks readiness and verifies shutdown (FR-3). UC3 calculates metrics from illustrative sample records (FR-8). UC4 stores and exports the FastAPI sample records using SQLite and CSV (FR-11).

The FastAPI service binds to `127.0.0.1:8000` on the host for the duration of UC2. The demo exercises the workload gate by moving the stack to `running`. A controlled benchmark requires the Linux testbed and remote k6 workload described in the [requirements](../requirements.md).

### 1.2 Tools

| Tool | Use |
|---|---|
| Git | Select the source revision and record the commit used for the run. |
| Python 3.11+, `venv` and `pip` | Run the demo and install the dependencies from [`requirements.txt`](../../requirements.txt). SQLite comes from the Python standard library. |
| Docker Engine and the Compose plugin | Build, start, inspect and remove the FastAPI demo stack. |
| Bash or PowerShell | Invoke the demo through the wrapper for the host. |
| pytest | Run the automated suite and optionally write a JUnit XML result. |

### 1.3 Environment

Use a local checkout on Windows with Docker Desktop or Linux with Docker Engine and the Compose plugin. Confirm that `docker info` can reach the selected engine, `docker compose version` succeeds, and host port 8000 is available. The first build may need registry and package-index access to retrieve the base image and Python dependencies. Use a fresh output directory for each acceptance run to preserve previous results.

The recorded run in [§4](#4-logs-and-outputs) used Windows 11, Python 3.14.2, Docker Desktop 29.9.3 and Compose v5.7.1 at commit `a437796`. The declared Python minimum is 3.11. See [environment.txt](logs/environment.txt) for the exact recorded versions.

## 2 Deployment Process

### 2.1 Step-by-Step Procedure

1. From the repository root at the revision under test, record `git rev-parse HEAD`, the OS, `python --version`, `docker info` and `docker compose version` with the run evidence.
2. Create a virtual environment and install the dependencies. On Linux, activate it in the current shell.

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   python -m pip install -r requirements.txt
   ```

   On Windows PowerShell, set `PYTHON` so the wrapper uses the virtual environment's interpreter.

   ```powershell
   python -m venv .venv
   $env:PYTHON = (Resolve-Path .\.venv\Scripts\python.exe).Path
   & $env:PYTHON -m pip install -r requirements.txt
   ```

3. Validate the Compose configuration with `docker compose -f apps/fastapi-baseline/docker-compose.yml config --quiet`. Run the automated tests with `python -m pytest -q` on Linux or `& $env:PYTHON -m pytest -q` on PowerShell. Add `--junitxml=<path>` when collecting machine-readable results.
4. Run the demo in acceptance mode with `--require-docker`, using a separate `--out` path for each evidence run.

   ```bash
   bash scripts/demo.sh --require-docker --out results/a3-acceptance
   ```

   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts/demo.ps1 --require-docker --out results/a3-acceptance
   ```

5. Review all four step results against the [acceptance tests](acceptance-tests.md#2-acceptance-tests). Full acceptance requires four `PASS` results and zero failures or skips. UC2 should reach `healthy`, `running` and `stopped`, and the container listing for the printed project should be empty. Save the demo stdout, automated test results, environment details and CSV exports with the tested revision.
6. If startup or cleanup fails, retain the error output. Use the project name and Compose path printed by UC2 for diagnosis and recovery. In the commands below, replace `PROJECT` and `COMPOSE_FILE` with those values. Capture any available status and logs before running cleanup. Verify that the last command succeeds and prints no container IDs before repeating the run.

   ```text
   docker compose -p PROJECT -f "COMPOSE_FILE" ps --all
   docker compose -p PROJECT -f "COMPOSE_FILE" logs --no-color
   docker compose -p PROJECT -f "COMPOSE_FILE" down --remove-orphans
   docker compose -p PROJECT -f "COMPOSE_FILE" ps --all --quiet
   ```

### 2.2 Scripts and Tools

[`scripts/demo.sh`](../../scripts/demo.sh) and [`scripts/demo.ps1`](../../scripts/demo.ps1) switch to the repository root, select Python and forward arguments and the exit status of [`scripts/demo.py`](../../scripts/demo.py). The Python script checks Docker availability and builds the image before the UC2 health timer starts. It uses the same generated project name and configured Compose file for the build and for the calls through [`gsmf/lifecycle.py`](../../gsmf/lifecycle.py). The lifecycle context attempts cleanup on success or failure. It confirms shutdown only when the project's container listing is empty.

The script exits with code `1` if a step fails. If Docker is unavailable, `--require-docker` reports UC2 as `FAIL`. The default demo reports UC2 as `SKIPPED` and can exit successfully when the other steps pass.

### 2.3 Configurations

The demo reads the checked-in positive and negative YAML fixtures and the sample measurement CSV. The demo wrappers pass `--out` through to the Python script. The default is `results/demo/`. Each run replaces `gsmf-demo.db`, `raw_demo-run.csv` and `aggregates_demo-run.csv` at the chosen output path, so use a dedicated directory for generated files.

## 3 Configuration Plan

### 3.1 Final Configuration

To be written by: TBD

### 3.2 Changes Made During Deployment

To be written by: TBD

## 4 Logs and Outputs

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
