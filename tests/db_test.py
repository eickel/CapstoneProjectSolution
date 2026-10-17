import pytest

from src.db.manager import DatabaseManager


@pytest.fixture
def db(tmp_path):
    return DatabaseManager(db_path=str(tmp_path / "test.db"))


def test_upsert_and_search_work(db):
    db.upsert_work(
        {
            "work_id": "OL1W",
            "title": "The Hobbit",
            "author_name": "J.R.R. Tolkien",
            "first_publish_year": 1937,
            "isbn": "9780261103344",
            "subject": "Fantasy",
            "language": "eng",
        }
    )
    rows = db.search_works(title="Hobbit")
    assert len(rows) == 1
    assert rows[0]["work_id"] == "OL1W"


def test_upsert_work_updates_existing_row(db):
    base = {
        "work_id": "OL1W",
        "title": "Old Title",
        "author_name": "A",
        "first_publish_year": 2000,
        "isbn": None,
        "subject": "X",
        "language": "eng",
    }
    db.upsert_work(base)
    base["title"] = "New Title"
    db.upsert_work(base)
    rows = db.search_works(title="New Title")
    assert len(rows) == 1
    assert len(db.search_works()) == 1


def test_upsert_works_batch_returns_count(db):
    works = [
        {
            "work_id": f"OL{i}W",
            "title": f"Book {i}",
            "author_name": "A",
            "first_publish_year": 2000,
            "isbn": None,
            "subject": "X",
            "language": "eng",
        }
        for i in range(5)
    ]
    assert db.upsert_works_batch(works) == 5
    assert len(db.search_works()) == 5


def test_cache_round_trip(db):
    assert db.get_cached("missing") is None
    db.set_cached("key1", {"hello": "world"}, ttl_seconds=100)
    assert db.get_cached("key1") == {"hello": "world"}


def test_cache_expired_returns_none(db):
    db.set_cached("key1", {"hello": "world"}, ttl_seconds=-1)
    assert db.get_cached("key1") is None


def test_purge_expired_cache(db):
    db.set_cached("expired", {"a": 1}, ttl_seconds=-1)
    db.set_cached("valid", {"b": 2}, ttl_seconds=1000)
    purged = db.purge_expired_cache()
    assert purged == 1
    assert db.get_cached("valid") == {"b": 2}


def test_get_metrics_reports_counts(db):
    db.upsert_work(
        {
            "work_id": "OL1W",
            "title": "T",
            "author_name": "A",
            "first_publish_year": 2000,
            "isbn": None,
            "subject": "X",
            "language": "eng",
        }
    )
    metrics = db.get_metrics()
    assert metrics["works_count"] == 1
    assert metrics["authors_count"] == 1


def test_upsert_work_also_upserts_author_with_real_id(db):
    db.upsert_work(
        {
            "work_id": "OL1W",
            "title": "The Hobbit",
            "author_name": "J.R.R. Tolkien",
            "author_id": "OL123A",
            "first_publish_year": 1937,
            "isbn": None,
            "subject": "Fantasy",
            "language": "eng",
        }
    )
    with db._connect() as conn:
        row = conn.execute("SELECT * FROM authors").fetchone()
    assert row["author_id"] == "OL123A"
    assert row["name"] == "J.R.R. Tolkien"


def test_upsert_work_without_author_id_falls_back_to_slug(db):
    db.upsert_work(
        {
            "work_id": "OL2W",
            "title": "Dirty Catalog Entry",
            "author_name": "Jane Q. Author",
            "first_publish_year": 2001,
            "isbn": None,
            "subject": "X",
            "language": "eng",
        }
    )
    with db._connect() as conn:
        row = conn.execute("SELECT * FROM authors").fetchone()
    assert row["author_id"] == "jane-q-author"
    assert row["name"] == "Jane Q. Author"


def test_upsert_works_batch_dedupes_same_author(db):
    works = [
        {
            "work_id": f"OL{i}W",
            "title": f"Book {i}",
            "author_name": "Shared Author",
            "first_publish_year": 2000,
            "isbn": None,
            "subject": "X",
            "language": "eng",
        }
        for i in range(3)
    ]
    db.upsert_works_batch(works)
    metrics = db.get_metrics()
    assert metrics["works_count"] == 3
    assert metrics["authors_count"] == 1


def test_upsert_work_without_author_name_skips_author_row(db):
    db.upsert_work(
        {
            "work_id": "OL3W",
            "title": "No Author Book",
            "author_name": None,
            "first_publish_year": 2000,
            "isbn": None,
            "subject": "X",
            "language": "eng",
        }
    )
    metrics = db.get_metrics()
    assert metrics["authors_count"] == 0
