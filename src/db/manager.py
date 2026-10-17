"""SQLite database manager: schema, CRUD, upserts, and TTL-based API cache."""

import json
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path

from src.config import settings
from src.exceptions import DatabaseError
from src.logger import get_logger

logger = get_logger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS works (
    work_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    author_name TEXT,
    first_publish_year INTEGER,
    isbn TEXT,
    subject TEXT,
    language TEXT,
    raw_json TEXT,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS authors (
    author_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    raw_json TEXT,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS api_cache (
    cache_key TEXT PRIMARY KEY,
    response_json TEXT NOT NULL,
    created_at REAL NOT NULL,
    expires_at REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_works_isbn ON works(isbn);
CREATE INDEX IF NOT EXISTS idx_works_subject ON works(subject);
CREATE INDEX IF NOT EXISTS idx_authors_name ON authors(name);
"""


class DatabaseManager:
    """Owns the SQLite connection and all CRUD / cache operations for the application."""

    def __init__(self, db_path: str | None = None):
        self.db_path = db_path or settings.database_path
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        except sqlite3.Error as exc:
            conn.rollback()
            raise DatabaseError(f"SQLite operation failed: {exc}") from exc
        finally:
            conn.close()

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(SCHEMA)

    # -- Works -----------------------------------------------------------

    def upsert_work(self, work: dict) -> None:
        now = time.time()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO works (work_id, title, author_name, first_publish_year,
                                    isbn, subject, language, raw_json, created_at, updated_at)
                VALUES (:work_id, :title, :author_name, :first_publish_year,
                        :isbn, :subject, :language, :raw_json, :created_at, :updated_at)
                ON CONFLICT(work_id) DO UPDATE SET
                    title=excluded.title,
                    author_name=excluded.author_name,
                    first_publish_year=excluded.first_publish_year,
                    isbn=excluded.isbn,
                    subject=excluded.subject,
                    language=excluded.language,
                    raw_json=excluded.raw_json,
                    updated_at=excluded.updated_at
                """,
                {
                    "work_id": work["work_id"],
                    "title": work.get("title"),
                    "author_name": work.get("author_name"),
                    "first_publish_year": work.get("first_publish_year"),
                    "isbn": work.get("isbn"),
                    "subject": work.get("subject"),
                    "language": work.get("language"),
                    "raw_json": json.dumps(work.get("raw", {})),
                    "created_at": now,
                    "updated_at": now,
                },
            )

    def upsert_works_batch(self, works: list[dict]) -> int:
        count = 0
        with self._connect() as conn:
            now = time.time()
            for work in works:
                conn.execute(
                    """
                    INSERT INTO works (work_id, title, author_name, first_publish_year,
                                        isbn, subject, language, raw_json, created_at, updated_at)
                    VALUES (:work_id, :title, :author_name, :first_publish_year,
                            :isbn, :subject, :language, :raw_json, :created_at, :updated_at)
                    ON CONFLICT(work_id) DO UPDATE SET
                        title=excluded.title,
                        author_name=excluded.author_name,
                        first_publish_year=excluded.first_publish_year,
                        isbn=excluded.isbn,
                        subject=excluded.subject,
                        language=excluded.language,
                        raw_json=excluded.raw_json,
                        updated_at=excluded.updated_at
                    """,
                    {
                        "work_id": work["work_id"],
                        "title": work.get("title"),
                        "author_name": work.get("author_name"),
                        "first_publish_year": work.get("first_publish_year"),
                        "isbn": work.get("isbn"),
                        "subject": work.get("subject"),
                        "language": work.get("language"),
                        "raw_json": json.dumps(work.get("raw", {})),
                        "created_at": now,
                        "updated_at": now,
                    },
                )
                count += 1
        return count

    def search_works(
        self, *, title: str | None = None, author: str | None = None, isbn: str | None = None
    ) -> list[sqlite3.Row]:
        clauses, params = [], {}
        if title:
            clauses.append("title LIKE :title")
            params["title"] = f"%{title}%"
        if author:
            clauses.append("author_name LIKE :author")
            params["author"] = f"%{author}%"
        if isbn:
            clauses.append("isbn = :isbn")
            params["isbn"] = isbn
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._connect() as conn:
            rows = conn.execute(f"SELECT * FROM works {where}", params).fetchall()
        return rows

    # -- Cache -------------------------------------------------------------

    def get_cached(self, cache_key: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT response_json, expires_at FROM api_cache WHERE cache_key = ?",
                (cache_key,),
            ).fetchone()
        if row is None:
            return None
        if row["expires_at"] < time.time():
            return None
        return json.loads(row["response_json"])

    def set_cached(self, cache_key: str, response: dict, ttl_seconds: int | None = None) -> None:
        now = time.time()
        ttl = ttl_seconds if ttl_seconds is not None else settings.cache_ttl_seconds
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO api_cache (cache_key, response_json, created_at, expires_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(cache_key) DO UPDATE SET
                    response_json=excluded.response_json,
                    created_at=excluded.created_at,
                    expires_at=excluded.expires_at
                """,
                (cache_key, json.dumps(response), now, now + ttl),
            )

    def purge_expired_cache(self) -> int:
        with self._connect() as conn:
            cursor = conn.execute("DELETE FROM api_cache WHERE expires_at < ?", (time.time(),))
            return cursor.rowcount

    # -- Diagnostics ---------------------------------------------------------

    def get_metrics(self) -> dict:
        with self._connect() as conn:
            works_count = conn.execute("SELECT COUNT(*) FROM works").fetchone()[0]
            authors_count = conn.execute("SELECT COUNT(*) FROM authors").fetchone()[0]
            cache_total = conn.execute("SELECT COUNT(*) FROM api_cache").fetchone()[0]
            cache_valid = conn.execute(
                "SELECT COUNT(*) FROM api_cache WHERE expires_at >= ?", (time.time(),)
            ).fetchone()[0]
        db_size_bytes = Path(self.db_path).stat().st_size if Path(self.db_path).exists() else 0
        hit_ratio = (cache_valid / cache_total) if cache_total else 0.0
        return {
            "works_count": works_count,
            "authors_count": authors_count,
            "cache_entries": cache_total,
            "cache_valid_entries": cache_valid,
            "cache_hit_ratio": round(hit_ratio, 4),
            "database_size_bytes": db_size_bytes,
        }
