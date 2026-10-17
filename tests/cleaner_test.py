from src.processing.cleaner import (
    clean_text,
    deduplicate_records,
    extract_isbn,
    normalize_catalog_record,
    validate_isbn10,
    validate_isbn13,
)


def test_clean_text_collapses_whitespace_and_strips_odd_chars():
    assert clean_text("  The   Hobbit!! \n") == "The Hobbit"


def test_clean_text_handles_empty_string():
    assert clean_text("") == ""


def test_extract_isbn_finds_isbn13():
    assert extract_isbn("ISBN: 978-0-261-10334-4 edition") == "9780261103344"


def test_validate_isbn10_valid():
    assert validate_isbn10("0-575-07953-3") is True


def test_validate_isbn10_invalid_checksum():
    assert validate_isbn10("0-575-07953-2") is False


def test_validate_isbn13_valid():
    assert validate_isbn13("9780261103344") is True


def test_validate_isbn13_invalid_checksum():
    assert validate_isbn13("9780261103345") is False


def test_normalize_catalog_record_maps_fields():
    raw = {
        "id": "OL1W",
        "title": " The Hobbit ",
        "author": "Tolkien",
        "year": 1937,
        "isbn": "978-0-261-10334-4",
    }
    record = normalize_catalog_record(raw)
    assert record["work_id"] == "OL1W"
    assert record["title"] == "The Hobbit"
    assert record["isbn"] == "9780261103344"


def test_deduplicate_records_removes_duplicate_isbn():
    records = [
        {"isbn": "123", "title": "A", "author_name": "X"},
        {"isbn": "123", "title": "A", "author_name": "X"},
        {"isbn": "456", "title": "B", "author_name": "Y"},
    ]
    deduped = deduplicate_records(records)
    assert len(deduped) == 2
