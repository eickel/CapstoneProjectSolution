"""Regex-based cleaning, normalization, and ISBN validation helpers."""

import csv
import json
import re
import unicodedata
from collections.abc import Generator
from pathlib import Path

from src.exceptions import CatalogFileError, DataValidationError

_ISBN_CHARS_RE = re.compile(r"[^0-9Xx]")
_WHITESPACE_RE = re.compile(r"\s+")
_NON_ALNUM_RE = re.compile(r"[^\w\s\-:,.'&]")


def clean_text(value: str) -> str:
    """Normalize UTF-8 text: collapse whitespace, strip stray control/odd characters."""
    if not value:
        return ""
    normalized = unicodedata.normalize("NFKC", value)
    normalized = _NON_ALNUM_RE.sub("", normalized)
    normalized = _WHITESPACE_RE.sub(" ", normalized).strip()
    return normalized


def extract_isbn(text: str) -> str | None:
    """Pull the first ISBN-10/13-looking token out of free text."""
    match = re.search(r"\b(97[89][-\s]?)?(?:\d[-\s]?){9}[\dXx]\b", text)
    return _ISBN_CHARS_RE.sub("", match.group(0)) if match else None


def validate_isbn10(isbn: str) -> bool:
    digits = _ISBN_CHARS_RE.sub("", isbn)
    if len(digits) != 10:
        return False
    total = 0
    for i, ch in enumerate(digits):
        value = 10 if ch.upper() == "X" else int(ch)
        total += (10 - i) * value
    return total % 11 == 0


def validate_isbn13(isbn: str) -> bool:
    digits = _ISBN_CHARS_RE.sub("", isbn)
    if len(digits) != 13 or not digits.isdigit():
        return False
    total = sum(int(d) * (1 if i % 2 == 0 else 3) for i, d in enumerate(digits))
    return total % 10 == 0


def validate_isbn(isbn: str) -> bool:
    digits = _ISBN_CHARS_RE.sub("", isbn)
    if len(digits) == 10:
        return validate_isbn10(digits)
    if len(digits) == 13:
        return validate_isbn13(digits)
    return False


def normalize_isbn_or_raise(isbn: str) -> str:
    digits = _ISBN_CHARS_RE.sub("", isbn)
    if not validate_isbn(digits):
        raise DataValidationError(f"Invalid ISBN checksum: {isbn!r}")
    return digits


def stream_catalog_records(path: str) -> Generator[dict]:
    """Stream rows from a dirty CSV or JSON catalog file one at a time."""
    file_path = Path(path)
    if not file_path.exists():
        raise CatalogFileError(f"Catalog file not found: {path}")

    suffix = file_path.suffix.lower()
    if suffix == ".csv":
        with file_path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            yield from reader
    elif suffix == ".json":
        with file_path.open(encoding="utf-8") as handle:
            data = json.load(handle)
        records = data if isinstance(data, list) else data.get("records", [])
        yield from records
    else:
        raise CatalogFileError(f"Unsupported catalog file type: {suffix}")


def normalize_catalog_record(record: dict) -> dict:
    """Clean and normalize a single raw catalog record's text fields."""
    return {
        "work_id": clean_text(str(record.get("work_id") or record.get("id") or "")),
        "title": clean_text(str(record.get("title", ""))),
        "author_name": clean_text(str(record.get("author_name") or record.get("author", ""))),
        "first_publish_year": record.get("first_publish_year") or record.get("year"),
        "isbn": _ISBN_CHARS_RE.sub("", str(record.get("isbn", ""))) or None,
        "subject": clean_text(str(record.get("subject", ""))),
        "language": clean_text(str(record.get("language", ""))),
    }


def deduplicate_records(records: list[dict]) -> list[dict]:
    """Deduplicate normalized catalog records using a set of seen identity keys."""
    seen: set[str] = set()
    deduped: list[dict] = []
    for record in records:
        title = record.get("title", "").lower()
        author = record.get("author_name", "").lower()
        key = record.get("isbn") or f"{title}|{author}"
        if key in seen:
            continue
        seen.add(key)
        deduped.append(record)
    return deduped
