# BIL481 — Fall 2026 Term Project

[Project Assignment 1 description](f26_assignment_1.pdf)

## Group Name

Intellectual property

## Group Members

|Full Name|GitHub Username|Email|School Number|
|-|-|-|-|
|Reşat Efe Koca|@djkurbaga|rkoca@etu.edu.tr|231301010|
|Bülent Çakır|@BulentCakirr|bulentcakir@etu.edu.tr|231301064|
|Murat Yılmaz|@yilmazmurat06|yilmazmurat@etu.edu.tr|241101063|
|Furkan Yaman|@furkany22|fyaman@etu.edu.tr|221301015|




## UC3 demo — efficiency metrics (FR-8)

`gsmf/metrics.py` computes, for every **valid** repetition:

- **Energy per completed user task** = net energy / completed user tasks, in **J/task**
- **Energy-Delay Product (EDP)** = net energy × measured duration, in **J·s**

Failed and invalid repetitions, and repetitions with zero completed tasks, are skipped and their reason is shown. Stored records are never modified.

> `examples/sample_measurements.csv` contains **illustrative sample data, not real measurements**.

Requires Python 3.11+.

```bash
pip install -r requirements.txt
python -m gsmf.metrics examples/sample_measurements.csv   # prints the results table
python -m pytest                                          # runs tests/test_metrics.py
```

If the `·` in `J·s` looks garbled on a Windows terminal, run with `PYTHONIOENCODING=utf-8`.
UML diagrams and shared interfaces are documented in [docs/diagrams/README.md](docs/diagrams/README.md).

## UC1 — YAML benchmark configuration (FR-1)

Install `requirements.txt`, then validate the example without starting Docker:

```bash
python -c 'from pathlib import Path; from gsmf.config import load_config; print(load_config(Path("examples/benchmark.yaml")))'
python -m pytest tests/test_config.py -q
```

Required top-level fields: `title`, `targets`, `workload_size`, `concurrency`,
`repetitions`, `cooldown_s`, `load_generator_host`. Each target requires `kind`,
`compose_file`, `base_url` and `health_url`. Supported kinds are `budibase`,
`appsmith` and `fastapi`. `health_timeout_s` defaults to 120 seconds;
`grid_carbon_intensity` is optional (gCO2eq/kWh).

Counts must be positive integers (booleans and numeric strings are rejected).
Cooldown and carbon intensity must be finite and non-negative; health timeout
must be finite and positive. URLs must use HTTP(S). Errors raise `ConfigError`
with the field name; loading never starts a stack. Relative Compose paths are
resolved against the YAML file's directory. File existence is checked by Compose
when starting the target. `validate_config` leaves relative paths unchanged.

## UC2 — isolated stack lifecycle (FR-3)

The baseline exposes `GET /health` and includes an image health check. With
Docker Engine and Docker Compose running, build it once and run the demo from
the repository root (port 8000 must be available):

```bash
pip install -r requirements.txt
docker compose -f apps/fastapi-baseline/docker-compose.yml build
python - <<'PY'
from pathlib import Path
from gsmf.config import load_config
from gsmf.lifecycle import StackManager, isolated_stack

config = load_config(Path("examples/benchmark.yaml"))
manager = StackManager()
with isolated_stack(manager, config.targets[0]):
    print(f"health={manager.state.value}")
    manager.mark_running()
    print(f"workload_gate={manager.state.value}")
print(f"shutdown={manager.state.value}")
PY
```

Observed output on 15 November 2026:

```text
health=healthy
workload_gate=running
shutdown=stopped
```

Use one `StackManager` for all targets in a benchmark. It runs `up -d`, waits
for running/healthy containers and an HTTP 2xx response, and runs `down` on
context exit, including startup, health and workload failures. Shutdown succeeds
only when `ps --all --quiet` returns no container IDs. Failed cleanup blocks the
next target; retry `stop` on the original target after resolving the failure.
`ExecutionFailure` retains command errors, and chained exceptions retain the
original failure if cleanup also fails.

Existing method signatures are unchanged. For Docker-free tests, assign a
`subprocess.run`-compatible callable to `manager.runner` before starting it;
return `subprocess.CompletedProcess` with text output. Commands use argument
lists and finite timeouts (`manager.command_timeout_s`, default 120 seconds).
Both lifecycle implementations run each HTTP probe in a short-lived Python
process, which is killed and reaped when the remaining timeout expires. This
bounds DNS resolution, redirects and slow response headers together, apart from
OS process startup/cleanup overhead. Tests inject command responses and a clock;
regression tests also use a real local HTTP server (Docker is not required):

```bash
python -m pytest -q
```

### Lifecycle comparison — subprocess/Compose vs Docker SDK

```bash
pip install -r comparisons/requirements.txt
docker compose -f apps/fastapi-baseline/docker-compose.yml build
python comparisons/lifecycle_subprocess_vs_docker_sdk.py --repetitions 3
```

[Raw output from 15 November 2026](comparisons/results/lifecycle-2026-11-15.jsonl)
records six real runs on macOS ARM64, Python 3.14.5, Docker Engine 29.4.3,
Compose 5.1.4 and Docker SDK 7.2.0. Every run reported `status=ok` and
`shutdown_confirmed=true`. Total lifecycle times copied from that output:

| Repetition | subprocess/Compose (s) | Docker SDK (s) |
|---|---:|---:|
| 1 | 6.179146 | 5.716658 |
| 2 | 6.172350 | 5.720124 |
| 3 | 6.183902 | 5.770919 |

Both paths use the same prebuilt image, port and health endpoint. Build time and
client setup are excluded; per-phase timings and the image ID are in the raw
output. This recorded snapshot predates the total HTTP timeout fix; rerun the
comparison to measure the current implementation's additional probe process cost. Order alternates between repetitions. Compose manages its project
network; the SDK path creates the single baseline container on Docker's default
network. These are local end-to-end observations, not a general speed ranking or
energy measurements. GSMF keeps Compose for multi-service targets; the SDK demo
only implements this baseline. The script exits nonzero on failure and stops
further runs when shutdown cannot be confirmed.

The implementation follows Docker's documented
[Compose container status output](https://docs.docker.com/reference/cli/docker/compose/ps/)
and [SDK container lifecycle API](https://docker-py.readthedocs.io/en/stable/containers.html).

## UC4 — result persistence and CSV export (FR-11)

`gsmf/storage.py` (`ResultStore`) writes everything to one SQLite file:

- `runs`: configuration (scalar columns plus the full config as JSON) and testbed settings
- `run_targets`: each target in config order, with its version, Compose file and URLs
- `repetitions`: every repetition, **including failed and invalid ones**, with status and reason
- `metrics`: computed FR-8 metrics, kept separate from the raw records

The store only inserts rows. Duplicate runs, repetitions or metrics raise
`StorageError`. SQLite triggers reject every `UPDATE`/`DELETE` on all four
tables, so stored measured values cannot be changed later. INVALID/FAILED
records need a non-empty `reason`. NaN is rejected because SQLite would store it
as NULL; save an unreadable value as `None` and put the cause in `reason`.
Metrics are only accepted for stored VALID repetitions whose net energy, duration
and task count match the stored values.

Exports for a selected run (an `out_path` that does not end in `.csv` is used as
a directory and created if needed):

- `export_raw_csv` → `raw_<run_id>.csv`: one row per repetition, floats written
  without rounding. The columns can be read by `gsmf.metrics.load_records_csv`.
- `export_aggregates_csv` → `aggregates_<run_id>.csv`: one row per target with
  version, valid/invalid/failed counts, and mean/median/sample stdev/min/max of
  net energy, duration, energy per task and EDP from the stored `metrics` rows.
  Confidence intervals (FR-5) are not computed here yet.

Demo with the **illustrative sample data** (run from the repository root):

```bash
mkdir -p results
python - <<'PY'
from pathlib import Path
from gsmf.config import load_config
from gsmf.metrics import compute_metrics, load_records_csv
from gsmf.models import PlatformKind, TestbedSettings
from gsmf.storage import ResultStore

store = ResultStore(Path("results/gsmf.db"))
store.initialize_schema()
store.save_run("demo-run", load_config(Path("examples/benchmark.yaml")),
               {PlatformKind.FASTAPI: "baseline-0.1.0"},
               TestbedSettings("demo-host", "performance", True, ("package-0",)))
for record in load_records_csv(Path("examples/sample_measurements.csv")):
    if record.target is PlatformKind.FASTAPI:
        store.save_repetition(record)
store.save_metrics(compute_metrics(store.load_repetitions("demo-run")))
print(store.export_raw_csv("demo-run", Path("results/")))
print(store.export_aggregates_csv("demo-run", Path("results/")))
PY
python -m pytest tests/test_storage.py -q
```

Output on 15 November 2026, followed by `results/raw_demo-run.csv` and the first
columns of `results/aggregates_demo-run.csv`:

```text
results/raw_demo-run.csv
results/aggregates_demo-run.csv
```

```text
run_id,target,repetition_index,status,reason,idle_power_w,gross_energy_j,duration_s,net_energy_j,completed_tasks,workload_errors,started_at
demo-run,fastapi,1,valid,,12.0,635.2,18.1,418.0,1000,0,
demo-run,fastapi,2,valid,,12.1,640.0,18.4,417.36,1000,0,
demo-run,fastapi,3,failed,k6 remote execution failed,,,,,,0,
```

```text
run_id,target,target_version,repetitions_total,valid_count,invalid_count,failed_count,metrics_count,net_energy_j_mean
demo-run,fastapi,baseline-0.1.0,3,2,0,1,2,417.68
```

Running `UPDATE repetitions SET net_energy_j = 0` against that database printed
`IntegrityError: repetitions kayıtları değiştirilemez (FR-11)`.

### Storage comparison — SQLite vs CSV vs JSON Lines

```bash
python comparisons/storage_sqlite_vs_csv_json.py --records 5000 --repeats 5
```

The script writes the same 5,000 synthetic records (fixed seed; 4,692 valid,
49 invalid, 259 failed; not energy measurements) to each format one record at
a time, reads them back, then tries to append a duplicate and change a stored
value. [Raw output from 15 November 2026](comparisons/results/storage-2026-11-15.jsonl)
(Linux x86_64, Python 3.13.18, SQLite 3.53.1); write/read times are medians of
5 runs:

| Format | Write (s) | Read (s) | Size (bytes) | Round trip equal | Duplicate append | Edit stored value |
|---|---:|---:|---:|---|---|---|
| SQLite (`ResultStore`) | 5.966098 | 0.017424 | 737280 | true | rejected | rejected by trigger |
| CSV | 0.046329 | 0.027063 | 673399 | true (without `started_at`) | appended | changed |
| JSON Lines | 0.065257 | 0.030254 | 1682823 | true | appended | changed |

SQLite writes were the slowest here because `ResultStore` commits each record in
its own transaction, while the CSV/JSONL writers only append to a file. One
repetition takes a full workload run, so a few milliseconds per write does not
affect a benchmark. SQLite was the only format that rejected duplicates and
edits by itself, which is why FR-11 data is stored there and CSV is used for
export. The CSV row uses `gsmf.metrics.load_records_csv`, which does not read
`started_at`. These timings are from one container, not a general speed ranking.

Wireframes for the CLI, CSV export and dashboard are in
[docs/wireframes/](docs/wireframes/README.md).
