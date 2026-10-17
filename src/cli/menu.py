"""Functional menu controller and terminal UI (CLIApp)."""

import asyncio
import re
import subprocess
import sys
import time

from src.api.async_client import AsyncLibraryClient
from src.api.sync_client import SyncLibraryClient
from src.db.manager import DatabaseManager
from src.exceptions import APIError, CatalogFileError, DataValidationError, LibraryProjectError
from src.logger import get_logger
from src.processing.analytics import DataProcessor
from src.processing.cleaner import (
    clean_text,
    deduplicate_records,
    normalize_catalog_record,
    stream_catalog_records,
    validate_isbn,
)
from src.reporting.generator import ReportGenerator

logger = get_logger(__name__)

BANNER = "=" * 70
SUBJECT_RE = re.compile(r"[^a-zA-Z0-9\s\-]")
SEARCH_RE = re.compile(r"[^a-zA-Z0-9\s\-:'.]")


def _work_from_subject_entry(entry: dict, subject: str) -> dict:
    authors = entry.get("authors") or [{}]
    first_author = authors[0] if authors else {}
    return {
        "work_id": entry.get("key", "").replace("/works/", ""),
        "title": entry.get("title", ""),
        "author_name": first_author.get("name"),
        "author_id": (first_author.get("key") or "").replace("/authors/", "") or None,
        "first_publish_year": entry.get("first_publish_year"),
        "isbn": None,
        "subject": subject,
        "language": (entry.get("language") or [None])[0] if entry.get("language") else None,
        "raw": entry,
    }


class CLIApp:
    """Interactive, loop-driven terminal menu for the library automation system."""

    def __init__(self):
        self.db = DatabaseManager()

    # -- Input helpers ---------------------------------------------------

    @staticmethod
    def _prompt_int(message: str, default: int, minimum: int = 1, maximum: int = 100) -> int:
        raw = input(f"{message} [{default}]: ").strip()
        if not raw:
            return default
        try:
            value = int(raw)
        except ValueError:
            print(f"  Invalid number, using default ({default}).")
            return default
        return max(minimum, min(maximum, value))

    @staticmethod
    def _prompt_nonempty(message: str) -> str:
        while True:
            raw = input(message).strip()
            if raw:
                return raw
            print("  Input cannot be empty. Please try again.")

    # -- Menu loop ---------------------------------------------------------

    def run(self) -> None:
        actions = {
            "1": self.ingest_works_by_subject,
            "2": self.search_books,
            "3": self.process_catalog_file,
            "4": self.generate_reports,
            "5": self.system_health,
            "6": self.run_quality_checks,
        }
        while True:
            self._print_menu()
            choice = input("Select an option: ").strip()
            if choice == "0":
                print("Goodbye!")
                break
            action = actions.get(choice)
            if action is None:
                print("  Invalid option. Please choose a number from the menu.\n")
                continue
            try:
                action()
            except LibraryProjectError as exc:
                logger.error("Handled application error: %s", exc)
                print(f"  [ERROR] {exc}")
            except Exception as exc:  # unexpected failure, keep the menu alive
                logger.exception("Unexpected error in menu action")
                print(f"  [UNEXPECTED ERROR] {exc}")
            print()

    @staticmethod
    def _print_menu() -> None:
        print(BANNER)
        print("OPEN LIBRARY INTELLIGENCE & CATALOG AUTOMATION SYSTEM")
        print(BANNER)
        print("[1] Ingest Works by Subject")
        print("[2] Search Books by Author/Title/ISBN")
        print("[3] Process & Deduplicate Local Catalog File")
        print("[4] Generate Analytical Reports")
        print("[5] System Health, Cache Maintenance & Database Administration")
        print("[6] Run Quality Checks & Test Suite Diagnostic")
        print("[0] Exit")
        print(BANNER)

    # -- Option 1 ------------------------------------------------------------

    def ingest_works_by_subject(self) -> None:
        raw_subject = self._prompt_nonempty("Enter a subject: ")
        subject = SUBJECT_RE.sub("", raw_subject).strip().lower().replace(" ", "_")
        if not subject:
            raise DataValidationError("Subject contains no valid characters after cleaning.")
        pages = self._prompt_int("Enter page depth", default=2, minimum=1, maximum=10)

        print(f"\nFetching '{subject}' ({pages} page(s)) synchronously...")
        start = time.perf_counter()
        sync_results = []
        with SyncLibraryClient() as client:
            for page in range(pages):
                data = client.get_subject_works(subject, limit=20, offset=page * 20)
                sync_results.append(data)
        sync_elapsed = time.perf_counter() - start

        print(f"Fetching '{subject}' ({pages} page(s)) asynchronously...")
        start = time.perf_counter()

        async def _fetch_async():
            async with AsyncLibraryClient() as client:
                return await client.get_subject_works_paged(subject, pages=pages, limit=20)

        async_results = asyncio.run(_fetch_async())
        async_elapsed = time.perf_counter() - start

        works = []
        for page_data in async_results:
            for entry in page_data.get("works", []):
                works.append(_work_from_subject_entry(entry, subject))

        inserted = self.db.upsert_works_batch(works)

        print("\n--- Runtime Comparison ---")
        print(f"  Sync:  {sync_elapsed:.3f}s")
        print(f"  Async: {async_elapsed:.3f}s")
        if async_elapsed > 0:
            print(f"  Speedup: {sync_elapsed / async_elapsed:.2f}x")
        print(f"Cached {inserted} work(s) into SQLite under subject '{subject}'.")

    # -- Option 2 ------------------------------------------------------------

    def search_books(self) -> None:
        raw_query = self._prompt_nonempty("Enter author name, title, or ISBN: ")
        query = SEARCH_RE.sub("", raw_query).strip()
        if not query:
            raise DataValidationError("Query contains no valid characters after cleaning.")

        isbn_candidate = re.sub(r"[^0-9Xx]", "", query)
        is_isbn_like = len(isbn_candidate) in (10, 13)
        if is_isbn_like and not validate_isbn(isbn_candidate):
            print(f"  Warning: '{query}' looks like an ISBN but failed checksum validation.")

        if is_isbn_like and validate_isbn(isbn_candidate):
            rows = self.db.search_works(isbn=isbn_candidate)
        else:
            rows = self.db.search_works(title=query) or self.db.search_works(author=query)

        if not rows:
            print("No local match found. Querying Open Library API...")
            with SyncLibraryClient() as client:
                try:
                    data = client.search_books(query)
                except APIError as exc:
                    print(f"  API search failed: {exc}")
                    return
            docs = data.get("docs", [])[:10]
            if not docs:
                print("No results found via API either.")
                return
            self._print_table(
                ["Title", "Author", "First Published", "Key"],
                [
                    [
                        d.get("title", ""),
                        ", ".join(d.get("author_name", []) or []),
                        d.get("first_publish_year", ""),
                        d.get("key", ""),
                    ]
                    for d in docs
                ],
            )
            return

        self._print_table(
            ["Work ID", "Title", "Author", "Year", "ISBN"],
            [
                [r["work_id"], r["title"], r["author_name"], r["first_publish_year"], r["isbn"]]
                for r in rows
            ],
        )

    @staticmethod
    def _print_table(headers: list[str], rows: list[list]) -> None:
        widths = [len(h) for h in headers]
        str_rows = [[str(cell) if cell is not None else "" for cell in row] for row in rows]
        for row in str_rows:
            for i, cell in enumerate(row):
                widths[i] = max(widths[i], len(cell))
        header_line = " | ".join(h.ljust(widths[i]) for i, h in enumerate(headers))
        print(header_line)
        print("-" * len(header_line))
        for row in str_rows:
            print(" | ".join(cell.ljust(widths[i]) for i, cell in enumerate(row)))

    # -- Option 3 ------------------------------------------------------------

    def process_catalog_file(self) -> None:
        path = self._prompt_nonempty("Enter path to catalog file (CSV/JSON): ")
        try:
            raw_records = list(stream_catalog_records(path))
        except CatalogFileError as exc:
            print(f"  {exc}")
            return

        print(f"Streamed {len(raw_records)} raw record(s). Normalizing...")
        normalized = [normalize_catalog_record(r) for r in raw_records if r]
        deduped = deduplicate_records(normalized)
        removed = len(normalized) - len(deduped)
        print(f"Deduplicated to {len(deduped)} unique record(s) (removed {removed}).")

        for record in deduped:
            if not record.get("work_id"):
                title_slug = clean_text(record.get("title", ""))[:40]
                record["work_id"] = f"local-{title_slug}-{record.get('isbn') or ''}"
            record["raw"] = dict(record)

        inserted = self.db.upsert_works_batch(deduped)
        print(f"Upserted {inserted} record(s) into the SQLite catalog.")

    # -- Option 4 ------------------------------------------------------------

    def generate_reports(self) -> None:
        rows = self.db.search_works()
        if not rows:
            print("No works in the database yet. Ingest or process a catalog first.")
            return

        records = [dict(row) for row in rows]
        processor = DataProcessor(records)
        processor.handle_missing_values()
        processor.drop_duplicate_works()

        generator = ReportGenerator(processor)
        paths = generator.generate_all()

        print("Reports generated:")
        for fmt, path in paths.items():
            print(f"  [{fmt.upper()}] {path}")

    # -- Option 5 ------------------------------------------------------------

    def system_health(self) -> None:
        metrics = self.db.get_metrics()
        print("--- Database Metrics ---")
        print(f"  Works:              {metrics['works_count']}")
        print(f"  Authors:            {metrics['authors_count']}")
        valid = metrics["cache_valid_entries"]
        print(f"  Cache entries:      {metrics['cache_entries']} (valid: {valid})")
        print(f"  Cache hit ratio:    {metrics['cache_hit_ratio']:.2%}")
        print(f"  Database size:      {metrics['database_size_bytes']} bytes")

        purge = input("\nPurge expired cache entries? [y/N]: ").strip().lower()
        if purge == "y":
            purged = self.db.purge_expired_cache()
            print(f"  Purged {purged} expired cache entries.")

    # -- Option 6 ------------------------------------------------------------

    def run_quality_checks(self) -> None:
        commands = [
            ("ruff check", [sys.executable, "-m", "ruff", "check", "."]),
            ("ruff format --check", [sys.executable, "-m", "ruff", "format", "--check", "."]),
            ("pytest", [sys.executable, "-m", "pytest", "-q"]),
        ]
        for label, cmd in commands:
            print(f"\n--- Running: {label} ---")
            result = subprocess.run(cmd, capture_output=True, text=True)
            print(result.stdout)
            if result.stderr:
                print(result.stderr)
            status = "PASSED" if result.returncode == 0 else "FAILED"
            print(f"[{label}] {status} (exit code {result.returncode})")
