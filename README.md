# Claude Code Analytics Platform

Provectus telemetry pipeline: synthetic data generation, SQLite ETL, analytics package, and Streamlit dashboard.

## Documentation

| Doc | Purpose |
|-----|---------|
| [docs/README.md](docs/README.md) | Full setup, ETL, tests, Streamlit |
| [docs/AGENTS.md](docs/AGENTS.md) | Agent and evaluation rules |
| [docs/PLAN.md](docs/PLAN.md) | Implementation plan |
| [docs/REPORTS.md](docs/REPORTS.md) | Step verification reports |

## Data after clone

The **`output/`** folder is **not** in Git (large generated files). Create it locally:

```bash
python generate_fake_data.py
```

Optional larger run: `python generate_fake_data.py --num-users 100 --num-sessions 5000 --days 60`

## Quick start

```bash
pip install -e ".[dev]"
python -c "from database.session import create_engine_instance, init_schema; from database.load import load_database; init_schema(create_engine_instance()); print(load_database())"
streamlit run src/app.py
```

Set `PROVECTUS_DATA_DIR` and `PROVECTUS_DATABASE_PATH` if you need non-default paths. Details: **[docs/README.md](docs/README.md)**.

## Agent tooling

If a tool expects `AGENTS.md` at the repository root, use **[docs/AGENTS.md](docs/AGENTS.md)** or see the short pointer in the root `AGENTS.md` file.
