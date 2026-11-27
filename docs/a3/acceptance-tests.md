# Acceptance Tests and Criteria

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
| 1.0 | 27-11-2026 | Reşat Efe Koca | Initial skeleton |
| 1.1 | 27-11-2026 | Reşat Efe Koca | Align section headings with the Assignment 3 handout; add Task Matrix |
| 1.2 | 27-11-2026 | Murat Yılmaz | Define UC1 and UC2 acceptance criteria, procedures and traceability |

## Task Matrix

**A** = accountable author, **R** = reviewer. TBD rows are assigned by the team.

| Section | Reşat | Bülent | Murat | Furkan |
|---|---|---|---|---|
| 1 Acceptance Criteria | TBD | TBD | **A** (UC1 and UC2) | TBD |
| 2 Acceptance Tests | TBD | TBD | **A** (AT-1 and AT-2) | TBD |
| 3 Test–Criteria Mapping | TBD | TBD | **A** (UC1 and UC2 rows) | TBD |

## Contribution Table

| Member | Sections / contribution |
|---|---|
| Reşat Efe Koca (@djkurbaga) | TBD |
| Bülent Çakır (@BulentCakirr) | TBD |
| Murat Yılmaz (@yilmazmurat06) | §§1.1–1.2, §§2.1–2.2 and the UC1/UC2 rows in §3 (AI-assisted) |
| Furkan Yaman (@furkany22) | TBD |

## Table of Contents

1. [Acceptance Criteria](#1-acceptance-criteria)
   1. [UC1 — Configure Benchmark (FR-1)](#11-uc1--configure-benchmark-fr-1)
   2. [UC2 — Manage Isolated Stack Lifecycle (FR-3)](#12-uc2--manage-isolated-stack-lifecycle-fr-3)
   3. [UC3 — Compute Efficiency Metrics (FR-8)](#13-uc3--compute-efficiency-metrics-fr-8)
   4. [UC4 — Persist and Export Results (FR-11)](#14-uc4--persist-and-export-results-fr-11)
   5. [Non-Functional Criteria](#15-non-functional-criteria)
2. [Acceptance Tests](#2-acceptance-tests)
   1. [AT-1 — UC1 Configure Benchmark (FR-1)](#21-at-1--uc1-configure-benchmark-fr-1)
   2. [AT-2 — UC2 Manage Isolated Stack Lifecycle (FR-3)](#22-at-2--uc2-manage-isolated-stack-lifecycle-fr-3)
   3. [AT-3 — UC3 Compute Efficiency Metrics (FR-8)](#23-at-3--uc3-compute-efficiency-metrics-fr-8)
   4. [AT-4 — UC4 Persist and Export Results (FR-11)](#24-at-4--uc4-persist-and-export-results-fr-11)
3. [Test–Criteria Mapping](#3-testcriteria-mapping)

<div style="page-break-after: always;"></div>

## 1 Acceptance Criteria

### 1.1 UC1 — Configure Benchmark (FR-1)

| Criterion | Expected behavior |
|---|---|
| AC-1.1 | A valid YAML file loads the selected targets, workload size, concurrency, repetition count and cooldown. A relative Compose path resolves from the YAML file's directory. |
| AC-1.2 | Missing required fields, unsupported targets, nonpositive or noninteger workload size, concurrency or repetition count, and negative or nonfinite cooldown cause a `ConfigError` that identifies the input problem. The validation step ends before any Compose startup. |

### 1.2 UC2 — Manage Isolated Stack Lifecycle (FR-3)

| Criterion | Expected behavior |
|---|---|
| AC-2.1 | The configured Compose stack starts, its required container and HTTP health checks pass within the configured health deadline, and only then does the workload gate open. |
| AC-2.2 | On normal exit or after a startup, health check or workload failure, the stack manager attempts shutdown. It reports `stopped` only after `docker compose ps --all --quiet` returns no container IDs. |
| AC-2.3 | A failed startup, health check or shutdown is reported as an `ExecutionFailure`. The same manager blocks a subsequent target until shutdown of the previous target is confirmed. |

### 1.3 UC3 — Compute Efficiency Metrics (FR-8)

To be written by: TBD

### 1.4 UC4 — Persist and Export Results (FR-11)

To be written by: TBD

### 1.5 Non-Functional Criteria

To be written by: TBD

## 2 Acceptance Tests

### 2.1 AT-1 — UC1 Configure Benchmark (FR-1)

**Preconditions.** Run from the repository root with Python 3.11+ and the dependencies installed. AT-1 itself has no Docker prerequisite. See the [deployment procedure](deployment-plan.md#21-step-by-step-procedure).

1. Run `python scripts/demo.py --out results/a3-acceptance` and inspect the UC1 block. For [the valid YAML](../../examples/benchmark.yaml), expect target `fastapi`, workload size `10`, concurrency `1`, repetitions `1` and cooldown `0.0` seconds.
2. In the same block, confirm that [the invalid YAML](../../examples/invalid-benchmark.yaml) raises `ConfigError` naming `targets[0].kind` and `bubble` before any stack-start step. Confirm that the summary marks UC1 `PASS`.
3. Run `python -m pytest -q tests/test_config.py`. Confirm the supported target, path resolution, required field and numeric validation cases pass.

**Pass condition.** Both YAML outcomes match and the configuration suite passes. Use the UC1 status in the demo summary to evaluate AT-1 independently of the other demo steps. Capture the demo and test outputs with the revision and interpreter version.

### 2.2 AT-2 — UC2 Manage Isolated Stack Lifecycle (FR-3)

**Preconditions.** Install the dependencies and make Docker Engine and Docker Compose available. Use a test environment with host port `8000` free. Follow the [deployment procedure](deployment-plan.md#21-step-by-step-procedure).

1. Run `python scripts/demo.py --require-docker --out results/a3-acceptance`. Record the Compose project name printed by UC2. Confirm the FastAPI Compose image builds and the lifecycle reaches `healthy`, `running` and `stopped` in that order. The example config sets a 60-second health deadline and probes `http://127.0.0.1:8000/health`. The `running` status marks the workload gate in the demo.
2. From the repository root, run `docker compose --project-name PROJECT -f apps/fastapi-baseline/docker-compose.yml ps --all --quiet`, substituting the project name from the run for `PROJECT`. Require a successful command with empty output and a UC2 `PASS` in the demo summary.
3. Run `python -m pytest -q tests/test_lifecycle.py tests/test_health_deadline.py`. Confirm that the failure-path assertions pass, including health timeout, cleanup after failure and blocking a second start while shutdown is unconfirmed. The lifecycle tests inject Compose responses. The deadline tests exercise the HTTP probe against a local server.

**Pass condition.** The real FastAPI lifecycle and shutdown check succeed and the automated lifecycle and deadline tests pass. Docker unavailability fails UC2 in the required-Docker invocation. A default run that reports UC2 `SKIPPED` leaves AT-2 unexecuted. Capture both sets of output with the revision and environment. Real-stack evidence covers the FastAPI happy path. The failure cases use controlled test inputs.

### 2.3 AT-3 — UC3 Compute Efficiency Metrics (FR-8)

To be written by: TBD

### 2.4 AT-4 — UC4 Persist and Export Results (FR-11)

To be written by: TBD

## 3 Test–Criteria Mapping

| Requirement | Criteria | Acceptance test | Evidence |
|---|---|---|---|
| FR-1 / UC1 | AC-1.1, AC-1.2 | [AT-1](#21-at-1--uc1-configure-benchmark-fr-1) | [UC1 demo output](logs/demo-output.txt), [configuration tests](../../tests/test_config.py) and [recorded pytest results](logs/pytest-output.txt) |
| FR-3 / UC2 | AC-2.1, AC-2.2, AC-2.3 | [AT-2](#22-at-2--uc2-manage-isolated-stack-lifecycle-fr-3) | [FastAPI demo output](logs/demo-output.txt) for AC-2.1 and normal exit under AC-2.2; [lifecycle tests](../../tests/test_lifecycle.py), [HTTP deadline tests](../../tests/test_health_deadline.py) and [recorded pytest results](logs/pytest-output.txt) for failure paths and AC-2.3 |

The archived demo output is from `a437796`, which ran UC2 in the default `gsmf-fastapi-baseline` Compose project. The AT-2 procedure above uses a per-run project and `--require-docker` in the current demo.

UC3, UC4 and non-functional mappings are pending team assignment.
