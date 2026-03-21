# PLAN.md - Claude Code Analytics Platform

This plan implements `AGENTS.md` (in this `docs/` folder) for Provectus. Each numbered step is an **Important Step**: finish the step, run **pytest** as proof of work, then **git commit** with a descriptive message, then **append** to `REPORTS.md` in this folder using the exact format below.

---

## Mandatory protocol (every step)

1. **Git:** After the step is complete and pytest passes, commit all related changes. Use imperative, specific commit messages (for example: `Add SQLAlchemy models and SQLite bootstrap for Employees and Events`).
2. **Verification:** Run pytest from the project root (for example: `python -m pytest` or `pytest tests/ -q`). Fix failures before committing. Capture terminal output as proof of work when demonstrating the step.
3. **Reporting:** Append to `REPORTS.md` immediately after a green pytest run, using this **exact** format (two lines per step, blank line optional between entries):

```
**STEP [Number]:**
**REPORT:** [Clear explanation of what was done and how it was implemented]
```

4. **Markdown and UI style (project-wide):** Follow `AGENTS.md`: palette for Streamlit as specified; **no emojis** and **no em-dashes** in UI, code comments, or project Markdown (including `docs/README.md`, `docs/REPORTS.md`, and this plan where updated in-repo).

---

## Product decisions (locked)

| Topic | Decision |
| ----- | -------- |
| Data inputs | Canonical files: `output/employees.csv`, `output/telemetry_logs.jsonl`. Ingestion reads from a directory set by environment variable, defaulting to `output/`. |
| App shell | Single Streamlit app; **sidebar navigation or tabs** to switch Management vs Developer content. |
| Access control | No login in v1; **auth-ready** layout: Management and Developer content live in **separate functions** so a future role check can wrap them. |
| Forecasting | **Daily total cost** and **cost per Practice**; **30-day** horizon; require **at least 14 days** of history; otherwise show a clear **Not enough data for forecasting** message (no silent fallback). |
| Tests | **pytest** is the only standard for step verification. |
| Packaging | **`pyproject.toml`** as source of truth; optional **`requirements.txt`** generated or synced for deployment docs. |
| Audit trail | **Step 0** includes `git init` and the first `docs/REPORTS.md` entry (environment and repo initialization). |

---

## Target layout

```
provectus/
  pyproject.toml
  README.md                 # short landing page; links into docs/
  docs/
    README.md               # full operator documentation
    AGENTS.md
    PLAN.md
    REPORTS.md
  .gitignore
  output/                   # local only (gitignored); run generate_fake_data.py
    employees.csv
    telemetry_logs.jsonl
  generate_fake_data.py
  src/
    ingestion/
    database/
    analytics/
    app.py
  tests/
    fixtures/
    ...
```

---

## Step 0: Repository and Python project scaffold

**Goals**

- Initialize git history for the analytics platform work.
- Add `pyproject.toml` (Python 3.10+, dependencies: pandas, streamlit, sqlalchemy, plotly; dev: pytest and any typing/lint tools you choose minimally).
- Create `src/` package skeleton (`ingestion`, `database`, `analytics`) and `src/app.py` stub (or empty module with docstring only).
- Add `tests/` with a first pytest module that asserts repository layout and that core packages import (smoke test).
- Add `.gitignore` appropriate for Python, venvs, SQLite artifacts, and OS cruft.
- Create **`docs/REPORTS.md`** if it does not exist.

**Proof of work**

- Run pytest; all tests green.

**Git commit**

- Example message: `chore: initialize repo, pyproject, and test scaffold`

**docs/REPORTS.md**

- Append **STEP 0** documenting: Python version target, creation of `pyproject.toml`, directory layout, `git init`, and that pytest smoke tests passed.

---

## Step 1: Database layer (SQLite, SQLAlchemy, indexed tables)

**Goals**

- Define SQLAlchemy models for **`Employees`** and **`Events`** aligned with ingested fields (include columns needed for joins and analytics: at minimum employee identity, Practice, Level, and event fields for cost, duration, tokens, tool outcomes, timestamps, `user.email`, and raw error flags if present in telemetry).
- Provide a small **database API**: engine creation, session factory, and `create_all` (or equivalent) for SQLite.
- Store the SQLite file under a configurable path (environment variable with a sensible default under the project, for example `data/analytics.db`), and document it in `docs/README.md`.
- Add **indexes** on columns used for joins and common filters (for example: employee email, event timestamp, practice, level).
- Use **parameterized** SQLAlchemy queries only (no string-concatenated SQL).

**Proof of work**

- Pytest: create a temporary SQLite database, run schema creation, assert tables and expected indexes exist (inspect metadata or `PRAGMA index_list` via SQLAlchemy/SQL).

**Git commit**

- Example message: `feat(database): add Employees and Events models with SQLite indexes`

**docs/REPORTS.md**

- Append **STEP 1** describing schema, index choices, and how the DB path is configured.

---

## Step 2: Ingestion (CSV + JSONL, cleaning, configurable directory)

**Goals**

- Implement ingestion modules under `src/ingestion/`:
  - Load **`employees.csv`** from a base directory.
  - Load **`telemetry_logs.jsonl`**: for each line, parse structure and extract nested **`message` -> `attributes`** from **`logEvents`** as specified in `AGENTS.md`.
  - **Clean and coerce** `cost_usd` and `duration_ms` safely (nulls, bad strings, types).
- Resolve the data directory from an **environment variable** (for example `PROVECTUS_DATA_DIR`), defaulting to **`output/`** relative to project root when unset.
- Return typed structures (pandas DataFrames or pydantic/dataclass lists) suitable for loading; validate required columns exist with clear errors.

**Proof of work**

- Pytest: use **fixture files** in `tests/fixtures/` (tiny CSV + JSONL snippets) to assert parsing, attribute flattening, and type coercion behavior including edge cases.

**Git commit**

- Example message: `feat(ingestion): parse employees CSV and telemetry JSONL with env data dir`

**docs/REPORTS.md**

- Append **STEP 2** describing parsers, cleaning rules, and the env default to `output/`.

---

## Step 3: ETL load into SQLite and employee linkage

**Goals**

- Implement an idempotent or repeatable load strategy (document choice: for example truncate-and-load for assignment-sized data, or upsert by natural keys if you prefer).
- Insert **Employees** and **Events** into SQLite.
- **Join logic:** link telemetry to employees via **`user.email`** (store `employee_id` on events or resolve at query time; choose one approach and stay consistent in analytics queries).
- CLI or Python entrypoint function `load_database()` (or similar) callable from tests and optionally from README.

**Proof of work**

- Pytest: run full load against a **temporary** SQLite DB using fixture data; assert row counts, foreign key or email resolution, and that a sample joined query returns expected rows.

**Git commit**

- Example message: `feat(etl): load employees and events into SQLite with email join`

**docs/REPORTS.md**

- Append **STEP 3** describing load order, join strategy, and how to rebuild the database.

---

## Step 4: Analytics (trends, health, time patterns, forecasting)

**Goals**

- Under `src/analytics/`, implement pure functions (pandas and/or SQLAlchemy) that power:
  - **Usage trends:** aggregate tokens and costs by **Practice** and **Level**.
  - **Operational health:** tool success rates and **`api_error`** patterns.
  - **Temporal analysis:** peak usage by hour-of-day and day-of-week (or equivalent clear summaries).
  - **Forecasting (bonus, required in this plan):** simple **linear regression** (for example `sklearn.linear_model.LinearRegression` or closed-form numpy) for:
    - **Daily total cost** (one series).
    - **Cost per Practice** (one series per practice present in history).
  - **Forecast rules:** horizon **30 days** ahead; require **at least 14 distinct days** of history per series; if not met, return a structured result that the UI can map to **Not enough data for forecasting** (no chart or a single message).

**Proof of work**

- Pytest: build small deterministic time series in tests; assert aggregates match expected numbers; assert forecasting returns the insufficient-data path below 14 days and returns 30 projected points when data is sufficient.

**Git commit**

- Example message: `feat(analytics): aggregates, operational health, temporal peaks, cost forecasts`

**docs/REPORTS.md**

- Append **STEP 4** summarizing metrics, forecasting method, and the 14-day / 30-day rules.

---

## Step 5: Streamlit application (Management vs Developer, auth-ready)

**Goals**

- Implement `src/app.py` as the Streamlit entry.
- **Navigation:** use **sidebar** or **tabs** to switch **Management** vs **Developer** experiences in one unified app.
- **Auth-ready structure:** implement `render_management_view()` and `render_developer_view()` (names may vary but keep the separation explicit). A future `require_role("management")` wrapper should be able to call only the right function without rewriting the UI tree.
- **Management:** high-level KPI-style summaries, trends by Practice and Level, cost forecasts (with insufficient-data handling), peak usage insights.
- **Developer:** technical tables and filters: recent events, tool success, `api_error` drilldowns, optional raw attribute inspection where useful.
- **Strict styling:** background **#FBF3D1**, primary text **#1B211A**, secondary surfaces **#F9F8F6** (Streamlit theme and/or `st.markdown` with `unsafe_allow_html` only if needed; keep consistent).
- Read data via the database and analytics layer (no duplicate parsing logic inside the UI beyond light formatting).

**Proof of work**

- Pytest: test **non-UI** pieces (analytics functions, query builders) already covered in Step 4; add tests that **import** app helpers, confirm view functions exist, and run lightweight tests with **mocked** Streamlit session or by extracting dataframe-building code into testable functions. Minimum bar: no import errors; view functions callable without Streamlit runtime if you refactor thin wrappers.

**Git commit**

- Example message: `feat(app): Streamlit dashboard with management and developer views`

**docs/REPORTS.md**

- Append **STEP 5** describing navigation, view split, styling, and how the app loads from SQLite.

---

## Step 6: Documentation, optional requirements export, full regression

**Goals**

- Update **`docs/README.md`**: how to install (`pip install -e .` or `pip install .`), set `PROVECTUS_DATA_DIR`, run pytest, run `streamlit run src/app.py` (or module path you configure in `pyproject.toml`).
- Generate or maintain **`requirements.txt`** from `pyproject.toml` (for example `pip freeze` after install, or `pip-compile`, or documented export command) so deployment instructions stay simple.
- Run the **full** pytest suite; fix any flakiness (temp paths, Windows path separators).

**Proof of work**

- Pytest: full suite green on a clean install from `pyproject.toml`.

**Git commit**

- Example message: `docs: README, optional requirements.txt, and test suite hardening`

**docs/REPORTS.md**

- Append **STEP 6** documenting operator runbook, env vars, and final verification.

---

## Definition of done

- All steps **0 through 6** completed in order.
- Each step has a **git commit**, a **green pytest** run, and a matching **`docs/REPORTS.md`** entry in the required format.
- Running the app against default `output/` data produces Management and Developer views without login, with forecasts obeying the **14-day minimum** and **30-day** horizon rules.
- Codebase respects `docs/AGENTS.md` structure, frameworks, typing, and style constraints.

---

## Optional follow-ups (out of scope unless requested)

- Docker image for Streamlit.
- Real authentication and role mapping.
- Incremental ETL and scheduled jobs.
