# Quality Assurance Plan

**Project:** Green Software Metrics Framework (GSMF)

**Course:** BIL 481 Software Engineering, Fall 2026

**Group:** Intellectual Property

**Date:** 15 November 2026

**Scope baseline:** `53dd212` (before this QA change)

## List of Contributors

| Contributor | Project role |
|---|---|
| Reşat Efe Koca | Project manager and measurement engineer |
| Bülent Çakır | Requirements analyst and documentation lead |
| Murat Yılmaz | Lead developer |
| Furkan Yaman | Test engineer; owner of this QA deliverable |

The contributor list belongs to the opening page when this document is exported.
Project membership does not imply that every member has reviewed this revision.

## Table of Contents

1. [QA strategy](#1-qa-strategy)
2. [Quality factors and measurable metrics](#2-quality-factors-and-measurable-metrics)
3. [Test plan](#3-test-plan)
4. [Bug tracking through GitHub Issues](#4-bug-tracking-through-github-issues)
5. [Task matrix](#5-task-matrix)
6. [Execution evidence and limitations](#6-execution-evidence-and-limitations)

<div style="page-break-after: always;"></div>

## 1 QA strategy

### 1.1 Overview and scope

QA protects configuration validity, stack isolation, metric correctness and preservation of raw results. Traceability follows [requirements.md](requirements.md) and the current [diagram index](diagrams/README.md): UC1 → FR-1, UC2 → FR-3, UC3 → FR-8, UC4 → FR-11. The older `uml-diagrams.md` calls UC4 a dashboard; this plan uses the implemented persistence/export contract. The dashboard is FR-13 and remains planned.

Review requirements and shared dataclass interfaces before changing behavior. Run the automated suite on each proposed merge, record the commit and environment, and add a regression test for each reproduced defect. Review error paths as carefully as successful paths: invalid configuration must never launch a stack; failed shutdown must block the next target; invalid measurements must never enter valid aggregates.

Current evidence covers configuration, injected Compose lifecycle control, local HTTP probes, metric calculations, SQLite persistence and CSV export. It does not establish completion of prerequisites/CPU control (FR-2), full repetition orchestration (FR-4), RAPL acquisition and remote workloads (FR-5–FR-7), confidence intervals (FR-9), SCI (FR-10), complete reporting (FR-12), dashboard (FR-13) or diagnostics (FR-14). The storage aggregate statistics are partial FR-9 support; confidence intervals are still absent. Wireframes are designs, not working commands.

### 1.2 Test levels

| Level | Method and existing evidence | Boundary |
|---|---|---|
| Unit | `test_config.py`: types, required fields, URLs and defaults; `test_metrics.py`: formulas, units and rejected records; `test_lifecycle.py`: state transitions with injected command responses | No physical energy readings or real Docker deployment |
| Integration | YAML-to-model path resolution; real temporary SQLite/CSV round trips in `test_storage.py`; local HTTP server and probe subprocess in `test_health_deadline.py`; baseline health endpoint in `test_fastapi_baseline.py` | TestClient is in-process; injected Compose output is not Docker integration |
| System | Manually execute the README UC2 demo against real Docker, then UC1/UC3/UC4 demos with a fresh database; retain logs, versions, exit codes and shutdown evidence | Full three-platform RAPL/k6 benchmark acceptance remains blocked until the remaining modules and testbed exist |
| Usability | A member other than the implementation author follows README setup, repairs invalid config and locates units/skip reasons and CSV output; record time, completion and assistance | Automated CLI assertions support this review but do not replace human observation |

### 1.3 Automated versus manual testing

Automate deterministic validation, arithmetic, database constraints, error propagation and regressions. Use temporary directories and fixed synthetic input; do not modify real benchmark databases. Lifecycle tests inject process responses and clocks, while deadline tests use local HTTP traffic. Manual testing covers environment setup, real Docker cleanup, hardware prerequisites, documentation clarity and eventual dashboard usability. Keep manual outcomes as **not run** until supported by an execution record; never interpret mock success as a successful hardware benchmark.

## 2 Quality factors and measurable metrics

The following are acceptance targets, not claims that measurement has already occurred.

| Quality factor | Metric and target | Measurement method and scope |
|---|---|---|
| Functional correctness | 100% of mandatory automated tests pass; numeric error ≤ `max(1e-12, abs(expected) × 1e-6)` for the hand-calculated metric fixtures | Run `python -m pytest -q`; compare J/task and J·s to explicit formula results using `pytest.approx` (the existing default tolerance) |
| Reliability | 100% of injected startup/health/workload/shutdown failure cases enforce cleanup or block further startup; 0 starts after unconfirmed shutdown | Lifecycle failure tests and command-call assertions; repeat real Docker cleanup checks before system acceptance |
| Data integrity | 100% of raw-record round trips retain supported values/status/reason; 0 accepted UPDATE/DELETE operations or duplicate record inserts in the tested cases | SQLite trigger, duplicate, timestamp/precision and export tests; explicitly exclude timestamp restoration by the metrics CSV reader, which currently drops `started_at` |
| Usability / reproducibility | At least 3 of 3 peer tasks completed without author assistance within 10 minutes each, after dependencies are installed | Time config validation/error correction, metrics CLI interpretation and CSV export using README; retain participant, elapsed time, mistakes and outcome. Not yet measured |

## 3 Test plan

### 3.1 Setup, entry and exit criteria

Use Python 3.11+ in an isolated environment, with a writable temporary directory and localhost networking enabled. From the repository root:

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -r comparisons/requirements.txt
python -m pytest -q
python comparisons/config_manual_vs_pydantic.py --iterations 1000 --repeats 5
```

Entry requires the selected commit, installed dependencies and readable fixtures. Tests require neither Docker Engine nor RAPL, although system checks require both Docker and, for future measurement acceptance, the documented Linux Intel RAPL testbed and separate k6 host. Capture Python/dependency versions with each run. A dependency or environment failure is blocked execution, not a passing test.

Exit for this assignment requires every automated case to pass, no unresolved critical/high defect in the selected scope, review of requirement links and reproducible comparison output. Full-product acceptance additionally requires the outstanding system/manual checks and remaining FRs. Use `python -m pytest tests/<file>.py::<function> -q` to execute any referenced case; parameterized functions run all variants.

### 3.2 Detailed automated cases

All paths below are relative to the repository root. Fixtures are synthetic and are not measured energy data.

#### QA-01 — Accept supported configuration and defaults

- **Use case / FR:** UC1 / FR-1.
- **Preconditions:** Fresh `raw_config` fixture; no Docker dependency.
- **Input:** Title `UC1 deneyi`; workload 100; concurrency 2; repetitions 3; cooldown 0; host `loadgen.local`; one target with Compose path and HTTP URLs. Repeat for fastapi, budibase and appsmith.
- **Steps:** Copy the input; set the target kind; call `validate_config`; inspect target, timeout, carbon intensity and original dictionary.
- **Expected:** Correct `PlatformKind`; timeout 120.0 seconds; carbon intensity `None`; cooldown 0.0; relative path unchanged; input unmodified.
- **Execution:** Automated — `tests/test_config.py::test_supported_platforms_and_defaults`.

#### QA-02 — Reject missing and incorrectly typed fields

- **Use case / FR:** UC1 / FR-1.
- **Preconditions:** Independent valid `raw_config` for each parameter set.
- **Input:** Remove each required top-level field. Separately replace each count with 0, -1, 1.5, 1.0, True, False, `"2"`, None or infinity.
- **Steps:** Apply exactly one mutation; call `validate_config`; capture its exception.
- **Expected:** `ConfigError` identifies the offending field; no valid model is returned. The configuration module has no stack-start operation.
- **Execution:** Automated — `tests/test_config.py::test_missing_fields` and `tests/test_config.py::test_invalid_integers`.

#### QA-03 — Resolve Compose paths against the YAML location

- **Use case / FR:** UC1 / FR-1.
- **Preconditions:** Temporary `examples` directory, writable YAML file and monkeypatched working directory.
- **Input:** Compose path `../apps/fastapi-baseline/docker-compose.yml` in `examples/benchmark.yaml`.
- **Steps:** Write valid YAML; change working directory to the temporary directory's parent; call `load_config` on the file; inspect returned path/title.
- **Expected:** Absolute path resolves to `<tmp>/apps/fastapi-baseline/docker-compose.yml`, independent of the process working directory; title preserved.
- **Execution:** Automated integration — `tests/test_config.py::test_load_resolves_paths_relative_to_yaml`.

#### QA-04 — Complete isolated lifecycle in order

- **Use case / FR:** UC2 / FR-3.
- **Preconditions:** New `StackManager`, `FakeRunner` and patched HTTP probe returning 200.
- **Input:** FastAPI target with `/tmp/demo stack/compose.yml`, timeout 1.0; command outputs for successful up, running/healthy JSON, down and empty remaining-container list.
- **Steps:** Start target; wait for health; mark running; stop; inspect state and recorded commands.
- **Expected:** STOPPED → STARTING → HEALTHY → RUNNING → STOPPED; commands are up, status, down, shutdown verification in order; finite timeouts; argument lists without shell execution.
- **Execution:** Automated — `tests/test_lifecycle.py::test_full_lifecycle`.

#### QA-05 — Block another stack after startup failure

- **Use case / FR:** UC2 / FR-3.
- **Preconditions:** Manager and injectable command runner; no real containers.
- **Input:** Each of missing Docker executable, command timeout and nonzero startup exit; then successful cleanup responses.
- **Steps:** Attempt startup and capture failure; attempt Appsmith before cleanup; inspect call count; stop original target; retry startup.
- **Expected:** `ExecutionFailure`, FAILED state and only one command issued before cleanup; next target rejected; after confirmed cleanup a new start reaches STARTING.
- **Execution:** Automated — `tests/test_lifecycle.py::test_start_failure_blocks_next_target_until_cleanup`. Shutdown-specific companion: `test_shutdown_failure_blocks_next_target` in the same file.

#### QA-06 — Compute metrics without changing the source

- **Use case / FR:** UC3 / FR-8; preservation obligation FR-11.
- **Preconditions:** VALID repetition from `make_record`.
- **Input:** Net energy 418 J; duration 18.1 s; completed tasks 1000.
- **Steps:** Compute repetition metrics; compare formulas and unit fields; snapshot source with `asdict`; call `compute_metrics`; compare source again.
- **Expected:** 0.418 J/task and 7565.8 J·s within declared tolerance; source values and identifiers retained; original record unchanged.
- **Execution:** Automated — `tests/test_metrics.py::test_valid_record_matches_manual_calculation`, `test_units_are_recorded`, `test_source_record_is_not_modified`.

#### QA-07 — Exclude unusable repetitions

- **Use case / FR:** UC3 / FR-8.
- **Preconditions:** Fresh synthetic repetition per variant.
- **Input:** FAILED with `k6 remote execution failed` and missing measurements; INVALID with usable numbers; completed tasks 0, -5 or None.
- **Steps:** Call `compute_repetition_metrics` and `skip_reason`; for the failed case also call `compute_metrics`.
- **Expected:** No metric; reason identifies failure/invalid status or completed-task problem; failed-list result is empty; no division by zero.
- **Execution:** Automated — `tests/test_metrics.py::test_failed_record_is_skipped`, `test_invalid_record_is_skipped_even_with_usable_numbers`, `test_zero_completed_tasks_is_guarded`.

#### QA-08 — Export every status and preserve raw values

- **Use case / FR:** UC4 / FR-11.
- **Preconditions:** Temporary initialized `ResultStore` with run metadata and `mixed_records` fixture.
- **Input:** Five records in order: valid, valid, invalid, valid, failed; invalid reason `net enerji negatif`; failed reason `yığın başlatılamadı`.
- **Steps:** Save all records; export raw CSV; parse headers/rows; reload through the metrics reader. In the preservation companion, calculate/store metrics, export both files and reload the database.
- **Expected:** All five statuses and reasons survive export, including blank missing measurements; first timestamp is `2026-11-15T10:00:00+00:00`; CSV reader reproduces records except its documented timestamp omission; database records remain exactly unchanged.
- **Execution:** Automated integration — `tests/test_storage.py::test_export_raw_csv_includes_all_records`, `test_exports_do_not_modify_stored_values`.

#### QA-09 — Aggregate only persisted valid metrics

- **Use case / FR:** UC4 / FR-11; partial FR-9.
- **Preconditions:** Initialized store, mixed records saved and their computed metrics persisted.
- **Input:** FastAPI valid energies 418 and 417.36 J, durations 18.1 and 18.4 s, plus invalid/failed records from the fixture.
- **Steps:** Export aggregate CSV; parse target rows, counts, means, units and sample standard deviation.
- **Expected:** FastAPI energy mean 417.68 J, EDP mean 7622.612 J·s, counts total=3/valid=2/invalid=1/failed=0; Budibase total valid=1/failed=1 with blank standard deviation. This test does not verify a confidence interval.
- **Execution:** Automated integration — `tests/test_storage.py::test_export_aggregates_from_stored_metrics`.

### 3.3 Manual and future system checks

| ID | Scope / prerequisites | Steps and input | Expected result | Status |
|---|---|---|---|---|
| QA-M01 | UC2/FR-3; Docker Engine/Compose, port 8000 free | Build baseline image; execute README isolated-stack demo; inspect Compose containers after exit; repeat with a raised workload exception | Health/workload gates succeed; shutdown verified on both paths; no next target while containers remain | Manual, not run in this QA revision; automated companions are QA-04/05 |
| QA-M02 | UC1/UC3/UC4 usability; peer and installed dependencies | Follow README to validate example, correct concurrency=0, interpret metrics from sample CSV, export to a fresh DB/directory; time the three tasks | Three tasks complete within 10 minutes each without author help; correct units and synthetic-data interpretation | Manual, not run; automated companions QA-01/02/06/08 |
| QA-M03 | Full product; RAPL testbed and remote k6, remaining modules implemented | Verify CPU controls and isolation; run all targets; inject remote workload failure; export/report/select run | Failed runs retained/excluded correctly; raw data, aggregates, report and dashboard agree; CLI help available | Blocked by implementation/testbed prerequisites; no existing full-system test claimed |

## 4 Bug tracking through GitHub Issues

Use [repository Issues](https://github.com/djkurbaga/BIL481-2026-Project/issues) as the defect register. This section defines the process; it does not claim labels or issues have already been created remotely. A reusable [bug report template](../.github/ISSUE_TEMPLATE/bug_report.md) is included.

Apply `bug`, one `severity:*`, one `area:*` (`config`, `lifecycle`, `metrics`, `storage`, `docs`) and one `status:*` label. Requirement IDs and QA/test IDs belong in the issue body. Create missing labels during repository triage; assign the relevant implementation owner and nominate a separate verifier.

| Severity label | Definition | Handling |
|---|---|---|
| `severity:critical` | Silent raw-data corruption or cross-target overlap invalidating measurements | Stop affected benchmark campaign; block release |
| `severity:high` | Required use case unavailable; missing cleanup or incorrect metrics | Resolve before selected-scope acceptance |
| `severity:medium` | Recoverable defect with a documented workaround | Prioritize in the next planning cycle |
| `severity:low` | Cosmetic or wording issue without result impact | Schedule documentation/UI maintenance |

Workflow: `status:triage` → reproduce and assign severity/owner → `status:in-progress` → link fix commit/PR and regression test → `status:verification` → a second member reruns the reproduction and affected tests → `status:done` and close. If verification fails, reopen and return to in-progress. Use `status:blocked` with the missing dependency and owner when progress is impossible. Record duplicate issues by linking their canonical issue, not silently deleting evidence. Severity describes impact; scheduling priority may be recorded separately.

Each report must include commit/branch, environment and dependency versions, UC/FR and QA ID, minimal sanitized input, exact reproduction commands, expected/actual behavior, exit status/logs, impact, workaround and regression-test reference. Exclude credentials and unrelated personal data. Preserve original failure evidence alongside successful rerun evidence.

## 5 Task matrix

This table separates recorded project responsibilities from this deliverable and pending verification. Existing assignments are sourced from [project-plan.md](project-plan.md) and [requirements.md](requirements.md); they are not invented completion claims or commit-authorship claims.

| Member | Recorded contribution / responsibility | QA deliverable task and status |
|---|---|---|
| Reşat Efe Koca | Requirements FR-8–FR-14; measurement, statistics and SCI ownership | Review arithmetic oracles and measurement acceptance boundaries — pending peer review |
| Bülent Çakır | Requirements consistency/formatting; storage, CSV and documentation ownership | Review persistence cases and traceability — pending peer review |
| Murat Yılmaz | Requirements FR-1–FR-7; architecture, lifecycle and FastAPI ownership | Review lifecycle failure cases and environment checks — pending peer review |
| Furkan Yaman | Non-functional requirements; testing, workload and benchmark validation ownership | Assigned QA strategy, quality metrics, test cases, defect workflow and config comparison; prepared in this revision with assistant support; manual peer checks remain pending |

All four members are listed as project contributors; the Git commits retain the configured assistant identity rather than impersonating a team member.

## 6 Execution evidence and limitations

The configuration comparison in [config_manual_vs_pydantic.py](../comparisons/config_manual_vs_pydantic.py) independently implements Pydantic validation and converts accepted input to the same `BenchmarkConfig` dataclass. Production `gsmf/config.py` remains the manual implementation. Both paths reject invalid inputs; their error formatting and aggregation differ. The corpus includes defaults, supported targets, missing fields, strict count types, nonfinite numbers, malformed URLs and paths, invalid roots and optional values. A finite corpus cannot prove equivalence for every Python object.

The [raw comparison output](../comparisons/results/config-2026-11-15.jsonl) contains environment, per-case acceptance/error outcomes, mismatch count and timing samples. Timing covers warmed valid-input validation plus model conversion, excluding YAML parsing, file I/O, imports and schema construction. Order alternates per repeat. These are local synthetic-input observations, not energy measurements or a universal performance ranking. See the repository README for the recorded values and command.

Observed on 15 November 2026 with Python 3.12.14 and pytest 9.2.0:
`python -m pytest -q` → **306 passed, 1 warning in 1.82s**.
The warning is an installed AnyIO pytest-plugin deprecation concerning pytest 10;
no test failed. [Captured test output](../comparisons/results/qa-tests-2026-11-15.txt)
retains the full warning. This includes 63 new comparison checks (62 corpus
variants and one report/input-preservation check) in
`tests/test_config_comparison.py`. No Docker/RAPL system run or peer usability
session was performed for this revision.
