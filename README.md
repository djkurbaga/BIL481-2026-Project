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
