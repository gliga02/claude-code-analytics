# Claude Code Analytics Platform (documentation)

## Operator runbook

**Python:** 3.10 or newer.

**Install (pick one):**

- **Editable package (recommended for development):** from the repository root, run `pip install -e .` for runtime only, or `pip install -e ".[dev]"` to include pytest and mypy.
- **Flat requirements files:** `pip install -r requirements.txt` for runtime dependencies, or `pip install -r requirements-dev.txt` before running the full test suite.

**Environment variables:**

| Variable | Default | Purpose |
| -------- | ------- | ------- |
| `PROVECTUS_DATA_DIR` | `output/` under the project root | Directory containing `employees.csv` and `telemetry_logs.jsonl`. |
| `PROVECTUS_DATABASE_PATH` | `data/analytics.db` under the project root | SQLite file for the analytics database. |

**Typical workflow:** run `python generate_fake_data.py`, create the schema and load the database (commands below), then `streamlit run src/app.py`.

**Tests:** from the project root, run `python -m pytest tests/ -q` for the full suite. Use `pytest tests/test_stepN_*.py -v` to focus on one step module.

**Locked export (optional):** in a clean virtual environment, install this project with `pip install -e ".[dev]"`, then run `pip freeze > requirements-lock.txt` for a full transitive pin. The committed `requirements.txt` lists direct runtime dependencies only and stays aligned with `pyproject.toml`; it is not a transitive lock.

---

## Data: create `output/` locally (not in Git)

The **`output/`** directory is **gitignored** because generated `telemetry_logs.jsonl` can be very large. After you clone this repository, create CSV and JSONL under `output/` by running:

```bash
python generate_fake_data.py
```

For a larger, more realistic dataset:

```bash
python generate_fake_data.py --num-users 100 --num-sessions 5000 --days 60
```

Defaults write to `output/` (see `--output-dir`). Then run `init_schema` and `load_database()` as below. **Automated tests** use small files under `tests/fixtures/` and do not require `output/` to exist.

---

# Synthetic telemetry dataset (`generate_fake_data.py`)

Synthetic telemetry data for Claude Code, Anthropic's CLI tool for AI-assisted software engineering.

## Quick start (generator only)

Uses the Python standard library only:

```bash
python generate_fake_data.py
```

### Options

| Flag | Default | Description |
|------|---------|-------------|
| `--num-users` | 30 | Number of engineers |
| `--num-sessions` | 500 | Total coding sessions |
| `--days` | 30 | Time span in days |
| `--output-dir` | `output` | Output directory |
| `--seed` | 42 | Random seed for reproducibility |

## Output files

| File | Format | Description |
|------|--------|-------------|
| `telemetry_logs.jsonl` | JSONL | Telemetry log batches |
| `employees.csv` | CSV | Employee directory |

## Telemetry structure

Each log record contains a batch of `logEvents`. Each event has a JSON `message` with:

- `body`: event type
- `attributes`: event-specific fields
- `scope`: instrumentation metadata
- `resource`: host and user environment info

## Employee table

| Column | Description |
|--------|-------------|
| email | Employee email |
| full_name | Full name |
| practice | Engineering practice |
| level | Seniority level (L1 through L10) |
| location | Country |

---

## Analytics SQLite database

The analytics platform (see [PLAN.md](PLAN.md) in this folder) stores data in SQLite via SQLAlchemy.

- **Default path:** `data/analytics.db` under the project root (created on first use).
- **Override:** set environment variable `PROVECTUS_DATABASE_PATH` to your SQLite file path.

After `pip install -e ".[dev]"` from the repo root, create empty tables:

```bash
python -c "from database.session import create_engine_instance, init_schema; init_schema(create_engine_instance())"
```

Verify the schema with pytest:

```bash
pytest tests/test_step1_database.py -v
```

### Input data directory (ingestion)

Ingestion reads `employees.csv` and `telemetry_logs.jsonl` from a directory set by `PROVECTUS_DATA_DIR`. When unset, it defaults to `output/` under the project root (the folder produced by `generate_fake_data.py`).

Verify parsers and cleaning with pytest:

```bash
pytest tests/test_step2_ingestion.py -v
```

### Load data into SQLite (ETL)

After tables exist (`init_schema`), reload all rows from the configured data directory into the database (truncate and insert, with `employee_id` resolved from `user_email`):

```bash
python -c "from database.load import load_database; print(load_database())"
```

Use `PROVECTUS_DATA_DIR` and `PROVECTUS_DATABASE_PATH` as needed. Verify with:

```bash
pytest tests/test_step3_etl.py -v
```

### Analytics API

The `analytics` package joins events to employees, aggregates usage by practice and level, summarizes tool and API error health, ranks peak hours (UTC) and weekdays, and fits scikit-learn linear regressions for 30-day cost forecasts (requires 14 distinct days with data per series; otherwise the message `Not enough data for forecasting` applies). Run:

```bash
pytest tests/test_step4_analytics.py -v
```

### Streamlit dashboard

From the repo root (with `pip install -e .` applied and a populated SQLite file at `PROVECTUS_DATABASE_PATH` or the default `data/analytics.db`):

```bash
streamlit run src/app.py
```

Use the sidebar to switch **Management** (KPIs, trends, forecasts, peak usage) and **Developer** (filters, event table, tool and API error summaries). Click **Refresh data** after reloading the database. Verify helpers with:

```bash
pytest tests/test_step5_app.py -v
```

---

## Other documentation

- [AGENTS.md](AGENTS.md): agent and evaluation rules
- [PLAN.md](PLAN.md): implementation plan
- [REPORTS.md](REPORTS.md): step verification reports

## Notes

- All user identifiers are synthetic
- Prompt contents are redacted
- Employee emails match the telemetry data when generated together
