# Open Library Intelligence & Catalog Automation System

A CLI-driven Python automation tool that interacts with the public [Open Library](https://openlibrary.org) REST API. It provides an asynchronous/synchronous API client, a SQLite local cache, a pandas data-transformation pipeline, a multi-format report generator, and an interactive terminal menu for book research, subject aggregation, author analytics, catalog deduplication, and sync/async performance benchmarking.

## Features

- **Subject ingestion** — fetches works by subject both synchronously and asynchronously, comparing runtime and caching results into SQLite.
- **Search** — looks up books by author, title, or ISBN (with ISBN-10/13 checksum validation) against the local cache first, falling back to the live API on a miss.
- **Catalog processing** — streams a dirty CSV/JSON catalog file via a generator, normalizes UTF-8 text, deduplicates records, and upserts them into SQLite.
- **Reporting** — generates an Excel workbook, a CSV summary, and a JSON export of key catalog metrics using pandas and openpyxl.
- **System health** — reports database metrics (row counts, size, cache hit ratio) and purges expired cache entries.
- **Quality checks** — runs `ruff check`, `ruff format --check`, and `pytest` from inside the menu.

## Requirements

- [uv](https://docs.astral.sh/uv/) (manages the Python interpreter and dependencies)

## Setup

```bash
uv sync
cp .env.example .env
```

## Usage

```bash
uv run python main.py
```

This launches the interactive menu:

```
======================================================================
OPEN LIBRARY INTELLIGENCE & CATALOG AUTOMATION SYSTEM
======================================================================
[1] Ingest Works by Subject
[2] Search Books by Author/Title/ISBN
[3] Process & Deduplicate Local Catalog File
[4] Generate Analytical Reports
[5] System Health, Cache Maintenance & Database Administration
[6] Run Quality Checks & Test Suite Diagnostic
[0] Exit
======================================================================
```

## Configuration

Runtime settings are loaded from `.env` (see `.env.example`) via `src/config.py`, including API timeout/retry/rate-limit behavior, the SQLite database path, cache TTL, and the reports output directory.

## Development

```bash
uv run ruff check .
uv run ruff format --check .
uv run pytest -q
```

## Project structure

```
src/
├── config.py          # Environment & settings loader
├── exceptions.py       # Custom exception hierarchy
├── logger.py            # Logging setup
├── api/                  # Sync & async Open Library clients
├── db/                    # SQLite CRUD & cache management
├── processing/            # Regex cleaning & pandas analytics
├── reporting/              # Multi-format report generator
└── cli/                     # Interactive menu controller
```

## CI

GitHub Actions (`.github/workflows/ci.yml`) runs `ruff check`, `ruff format --check`, and `pytest` on every push and pull request.
