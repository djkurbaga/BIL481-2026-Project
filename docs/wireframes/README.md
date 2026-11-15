# Wireframes

Low-fidelity wireframes for the user-facing parts of GSMF. Each screen is an
editable SVG with a PNG rendering (2× scale) next to it. Values such as
`x.xx`, `n` and `RUN_ID` are placeholders, not measurements.

| Screen | Requirement | Files |
|---|---|---|
| CLI validation error | FR-1 (UC1) | [SVG](cli-validation-error.svg) · [PNG](cli-validation-error.png) |
| CLI run summary table | FR-12 | [SVG](cli-run-summary.svg) · [PNG](cli-run-summary.png) |
| CSV export result | FR-11 (UC4) | [SVG](csv-export-result.svg) · [PNG](csv-export-result.png) |
| Simple results dashboard | FR-13 | [SVG](results-dashboard.svg) · [PNG](results-dashboard.png) |

The validation error text is the current `gsmf.config` message, and the CSV
file names, column names and `run_id` error come from `gsmf/storage.py`. The
`gsmf run` / `gsmf export` commands and the dashboard are not implemented yet.
