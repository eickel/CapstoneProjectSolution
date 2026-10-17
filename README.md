# Open Library Intelligence & Catalog Automation System

A CLI-driven Python automation tool that interacts with the public [Open Library REST API](https://openlibrary.org) to research books, aggregate subjects, analyze author productivity, deduplicate catalog files, and generate multi-format analytical reports.

Built as the capstone project for **SOFT-753: Automation with Python** (CENFOTEC University).

## Features

- Asynchronous and synchronous REST API clients (`httpx`) with retry, backoff, and rate-limit handling
- SQLite local caching database with TTL-based expiry and batch upserts
- pandas-based data cleaning, deduplication, and aggregation pipeline
- Multi-format report generator (Excel, CSV, JSON)
- Interactive, loop-driven terminal menu with input validation
- Regex-based text cleaning and ISBN-10/13 checksum validation
- GitHub Actions CI (ruff + pytest)

## Project Structure

```
library-project/
├── .github/workflows/ci.yml   # GitHub Actions workflow (ruff + pytest)
├── data/
│   ├── sample_catalog.csv     # Dirty test data for file automation
│   └── outputs/                # Default folder for generated reports
├── src/
│   ├── config.py                # Environment & settings loader (pydantic + dotenv)
│   ├── exceptions.py            # Custom exception hierarchy
│   ├── logger.py                 # Logging setup (console + rotating file handler)
│   ├── api/                      # Sync/async Open Library REST API clients
│   ├── db/                       # SQLite database manager
│   ├── processing/               # Regex cleaning & pandas analytics
│   ├── reporting/                # Multi-format report generator
│   └── cli/                      # Interactive terminal menu controller
├── tests/                        # pytest unit tests (mocked API, DB, analytics, cleaning)
├── .env.example
├── pyproject.toml
└── main.py
```

## Setup

```bash
uv sync
```

Optionally copy `.env.example` to `.env` to override default settings (API timeouts, cache TTL, database path).

## Usage

```bash
uv run python main.py
```

This launches the interactive menu:

```
[1] Ingest Works by Subject
[2] Search Books by Author/Title/ISBN
[3] Process & Deduplicate Local Catalog File
[4] Generate Analytical Reports
[5] System Health, Cache Maintenance & Database Administration
[6] Run Quality Checks & Test Suite Diagnostic
[0] Exit
```

## Development

```bash
uv run ruff check .
uv run ruff format .
uv run pytest -q
```

## Notes

- API clients use the `truststore` package to validate TLS certificates against the operating system's trust store, which is necessary on networks with TLS-inspecting proxies.
- Generated reports and the SQLite database are written to `data/outputs/` and are gitignored.
