# Claude Code Analytics Platform

## Project overview

The **Claude Code Analytics Platform** is a Provectus analytics stack that turns raw engineering telemetry into **actionable developer and management insights**. It ingests synthetic or real Claude Code style logs (JSONL batches with nested `logEvents`) and an employee directory (CSV), loads them into SQLite, and exposes **Management** and **Developer** views in a single Streamlit application. The goal is to move from opaque log files to clear signals on adoption, cost, operational health, and usage patterns over time.

---

## Tech stack

| Area | Technology |
| ---- | ---------- |
| Language | **Python 3.10+** |
| UI | **Streamlit** (sidebar navigation, cached data loads, Plotly charts) |
| Data processing | **Pandas** (ingestion outputs, analytics-friendly frames) |
| Visualization | **Plotly** (interactive bar charts and time-oriented views) |
| Storage | **SQLAlchemy 2.x** with **SQLite** (indexed `Employees` and `Events` tables) |
| Forecasting | **scikit-learn** `LinearRegression` (daily cost and per-practice series, gated by minimum history) |
| Packaging | **`pyproject.toml`** as source of truth; **`requirements.txt`** / **`requirements-dev.txt`** for flat installs |
| Tests | **pytest** (fixtures under `tests/fixtures/`, step-scoped test modules) |

---

## Architecture and data flow

The codebase under **`src/`** is split into four concerns:

1. **`ingestion/`**  
   Resolves the data directory (`PROVECTUS_DATA_DIR`, default **`output/`**). Loads **`employees.csv`** with required-column checks. Reads **`telemetry_logs.jsonl`** line by line; each line is a batch containing **`logEvents`**. For each event, the string field **`message`** is parsed as JSON. The parser expects an object with **`body`**, **`attributes`**, and **`resource`**. Fields used downstream (for example **`user.email`**, **`event.timestamp`**, **`cost_usd`**, **`duration_ms`**) are read from **`attributes`** (and related paths). Rows without a usable user email are skipped. Coercion and cleaning live in **`ingestion/cleaning.py`**.

2. **`database/`**  
   SQLAlchemy models for employees and events, session and engine helpers, schema creation, and **`load_database()`**: truncate-and-reload pattern, batch inserts, **`employee_id`** resolved from **`user_email`** using the employee directory.

3. **`analytics/`**  
   Read-only queries and pure functions: usage by practice and level, tool and API error summaries, peak hour and weekday aggregates (UTC), and cost forecasting helpers with explicit **insufficient history** handling.

4. **`app.py` (UI)**  
   Streamlit entrypoint: **`render_management_view()`** and **`render_developer_view()`** are separated for future auth. Data is read through the database and analytics layer, not by re-implementing parsers in the UI.

**ETL in one sentence:** JSONL batches become flattened event rows with cleaned numeric and timestamp fields; employees load from CSV; events load into SQLite with optional linkage to **`Employees`** via email.

---

## Key features

### Executive overview

Aggregated **events**, distinct **users**, and **cost** (USD) surface as KPI-style metrics in the Management view, backed by joined employee context where available.

### Adoption analytics

**Usage by Practice and Seniority Level:** token and cost totals (and related breakdowns) grouped by engineering practice and level, with Plotly visualizations for exploration.

### Temporal analysis

**Peak usage** summaries by **hour of day** and **day of week** (UTC) help identify when the organization concentrates activity.

### Predictive cost forecasting (linear regression)

**Daily total cost** and **cost per practice** are projected with **scikit-learn** linear regression over a **30-day** horizon when at least **14** distinct calendar days of history exist per series. Shorter histories return a clear **not enough data for forecasting** style outcome instead of silent or misleading charts.

### User interface and visualization (Visualization Expert palette)

The dashboard uses a **dark, minimal** Streamlit shell with **Plotly** charts styled to match. Colors are centralized in **`src/app.py`** as `COLOR_*` constants. The hex values below are the ones the app uses today:

| Role | Hex | Constant |
| ---- | --- | -------- |
| Page background | `#0D1117` | `COLOR_BG` |
| Sidebar and main surfaces | `#161B22` | `COLOR_SURFACE` |
| Elevated panels and chart plot background | `#21262D` | `COLOR_ELEVATED` |
| Primary text | `#F0F6FC` | `COLOR_TEXT` |
| Muted text, axis ticks, legend | `#8B949E` | `COLOR_MUTED` |
| Borders | `#30363D` | `COLOR_BORDER` |
| Primary accent (bars, highlights) | `#58A6FF` | `COLOR_ACCENT` |
| Secondary accent | `#79B8FF` | `COLOR_ACCENT_MUTED` |

**Note:** Older planning docs mentioned a light cream palette (`#FBF3D1`, `#1B211A`, `#F9F8F6`). The shipped UI does **not** use those values; trust **`src/app.py`** and the table above.

---

## Setup and installation

### 1. Clone the repository

```bash
git clone <your-remote-url>
cd provectus
```

### 2. Create and activate a virtual environment

**Linux or macOS:**

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
```

**Windows (PowerShell):**

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
```

### 3. Install dependencies

**Option A (recommended for development):** editable install from **`pyproject.toml`**

```bash
pip install -e .
```

Include dev tools (pytest, mypy):

```bash
pip install -e ".[dev]"
```

**Option B:** flat requirements files

```bash
pip install -r requirements.txt
```

For tests and mypy:

```bash
pip install -r requirements-dev.txt
```

### 4. Generate local data under `output/`

The **`output/`** directory is **gitignored** (large JSONL). After clone, generate CSV and JSONL:

```bash
python generate_fake_data.py
```

Optional larger dataset:

```bash
python generate_fake_data.py --num-users 100 --num-sessions 5000 --days 60
```

### 5. Initialize the database and load data

Default SQLite path: **`data/analytics.db`**. Override with **`PROVECTUS_DATABASE_PATH`** if needed. Data directory defaults to **`output/`**; override with **`PROVECTUS_DATA_DIR`**.

From the repository root (with **`src`** on **`PYTHONPATH`**, satisfied by editable install):

```bash
python -c "from database.session import create_engine_instance, init_schema; from database.load import load_database; init_schema(create_engine_instance()); print(load_database())"
```

### 6. Launch the dashboard

```bash
streamlit run src/app.py
```

Use the sidebar to switch **Management** vs **Developer** and **Refresh data** after reloading the database.

---

## Technical implementation details

**Malformed or unexpected JSON:** Each `logEvents[].message` string is parsed with **`json.loads`**. Invalid JSON raises a **`ValueError`** with context. Parsed values must be objects; **`attributes`** and **`resource`** are validated as objects when present. Wrong types on **`message`** surface as **`TypeError`**. This fails fast on structural corruption instead of silently producing bad rows.

**Validation and type casting:** Telemetry fields such as **`cost_usd`** and **`duration_ms`** are normalized through dedicated parsers: blanks and non-numeric strings become **`None`**; NaNs are dropped; integers and floats are handled consistently; timestamps accept ISO strings (including **`Z`**) and normalize to UTC-aware datetimes where possible. Employee CSV loading checks required columns before ingest. Together, this keeps SQLite loads and analytics from being skewed by loose string types in the source logs.

---

## LLM orchestration note

This project was developed with an **AI-first workflow** using **Cursor** and large language models to speed up implementation while keeping structure, tests, and reviews disciplined. Three Markdown artifacts in **`docs/`** acted as the control plane:

- **`docs/AGENTS.md`** defined roles (data architecture, analytics, UI), quality bars (typing, safety, palette rules aligned with **`src/app.py`** colors), and how code should be organized. It gave the assistant standing instructions so generated modules stayed aligned with product intent.

- **`docs/PLAN.md`** broke work into numbered steps (scaffold, database, ingestion, ETL, analytics, Streamlit, documentation). Each step had explicit goals, pytest proof, git commit expectations, and a **`docs/REPORTS.md`** entry format. That turned an open-ended build into a verifiable sequence.

- **`docs/REPORTS.md`** recorded what was completed per step. It worked as **context engineering**: after each milestone, appending a short report preserved decisions and outcomes so later sessions did not re-litigate finished work.

The human operator asked for **validation after each step** (run **`pytest`**, fix failures, then commit). That loop kept the assistant honest: generated code had to pass the suite and match the plan before moving on. Root **`README.md`** (this file) is the public front door; **`docs/README.md`** carries extended operator notes, fixture paths, and per-step pytest commands.

---

## LLM usage log

This subsection records **how** AI assistance was used on this repository, not every chat turn. It is meant for reviewers who want transparency on tooling, prompting style, and verification.

### AI tools

| Tool | Role |
| ---- | ---- |
| **Cursor** | Primary IDE; repository-wide search, edits, and terminal commands coordinated in one workspace. |
| **Cursor Agent / automated sessions** | Multi-file implementation passes (for example full PLAN steps, refactors, and test fixes) with the model proposing patches and running commands the operator approved. |
| **Inline chat** | Targeted questions, small diffs, and clarifications on a single file or error message. |

Exact model names and versions change with Cursor releases; the important part is that **all** merged code was re-run through **`pytest`** and human review before commit.

### Example prompts (representative)

These are **paraphrased** from the real workflow; wording varied per session.

1. **Plan execution:** “Execute **`docs/PLAN.md`** in order. After each step, run **`pytest`**, fix failures, commit, and append **`docs/REPORTS.md`** in the required format.”

2. **Domain implementation:** “Implement JSONL ingestion: walk **`logEvents`**, parse each **`message`** as JSON, read **`attributes`** and **`resource`**, coerce **`cost_usd`** and **`duration_ms`**, and validate required CSV columns for employees.”

3. **UI iteration:** “Modern dark Streamlit layout: fix sidebar contrast, align Plotly styling with app colors, and remove stray **undefined** labels above charts.”

4. **Repository hygiene:** “Move Markdown under **`docs/`**, stop tracking **`output/`**, document **`generate_fake_data.py`** for clones, and add **`requirements.txt`** synced with **`pyproject.toml`**.”

5. **Documentation accuracy:** “Expand root **`README.md`** with architecture, setup, and technical detail; then verify Visualization Expert colors against **`src/app.py`**.”

### How AI-generated output was validated

| Layer | What we did |
| ----- | ----------- |
| **Automated tests** | Full suite: **`python -m pytest tests/ -q`**. Step-scoped modules (**`test_step0_scaffold.py`** through **`test_step5_app.py`**) cover layout, database schema, ingestion, ETL, analytics, and app helpers (including mocked Streamlit for view smoke tests). |
| **PLAN gate** | **`docs/PLAN.md`** required a green **`pytest`** run before treating a step as done and before the associated git commit. |
| **Audit trail** | **`docs/REPORTS.md`** records each completed step so later sessions and reviewers can see what was already verified. |
| **Manual UI check** | **`streamlit run src/app.py`** against a populated SQLite file: Management vs Developer navigation, KPIs, charts, forecast insufficient-data messaging, and **Refresh data** after reloads. |

Generated code was **not** trusted on first paste: failing tests or obvious runtime errors were fed back into the assistant until the suite passed and the UI matched expectations.

---

## Further reading

| Document | Purpose |
| -------- | ------- |
| [docs/README.md](docs/README.md) | Extended setup, environment variables, and per-module test commands |
| [docs/AGENTS.md](docs/AGENTS.md) | Full agent and evaluation rules |
| [docs/PLAN.md](docs/PLAN.md) | Implementation plan and definition of done |
| [docs/REPORTS.md](docs/REPORTS.md) | Step-by-step verification log |

Root **`AGENTS.md`** is a short pointer for tools that only look at the repository root; authoritative content is **`docs/AGENTS.md`**.
