import pandas as pd

from src.processing.analytics import DataProcessor

SAMPLE_RECORDS = [
    {
        "work_id": "OL1W",
        "title": "A",
        "author_name": "Tolkien",
        "first_publish_year": 1937,
        "isbn": "123",
        "subject": "Fantasy",
        "language": "eng",
    },
    {
        "work_id": "OL2W",
        "title": "B",
        "author_name": "Tolkien",
        "first_publish_year": 1954,
        "isbn": "456",
        "subject": "Fantasy",
        "language": "eng",
    },
    {
        "work_id": "OL3W",
        "title": "C",
        "author_name": None,
        "first_publish_year": None,
        "isbn": None,
        "subject": None,
        "language": None,
    },
]


def test_handle_missing_values_fills_defaults():
    processor = DataProcessor(SAMPLE_RECORDS)
    df = processor.handle_missing_values()
    assert df.loc[2, "author_name"] == "Unknown"
    assert df.loc[2, "language"] == "und"
    assert df.loc[2, "subject"] == "Uncategorized"
    assert pd.isna(df.loc[2, "first_publish_year"])


def test_drop_duplicate_works_removes_duplicate_ids():
    records = SAMPLE_RECORDS + [SAMPLE_RECORDS[0]]
    processor = DataProcessor(records)
    df = processor.drop_duplicate_works()
    assert len(df) == 3


def test_author_productivity_counts_correctly():
    processor = DataProcessor(SAMPLE_RECORDS)
    processor.handle_missing_values()
    result = processor.author_productivity()
    tolkien_row = result[result["author_name"] == "Tolkien"].iloc[0]
    assert tolkien_row["work_count"] == 2


def test_subject_aggregation_groups_by_subject():
    processor = DataProcessor(SAMPLE_RECORDS)
    processor.handle_missing_values()
    result = processor.subject_aggregation()
    fantasy_row = result[result["subject"] == "Fantasy"].iloc[0]
    assert fantasy_row["work_count"] == 2
    assert fantasy_row["distinct_authors"] == 1


def test_summary_metrics_counts_distinct_values():
    processor = DataProcessor(SAMPLE_RECORDS)
    processor.handle_missing_values()
    summary = processor.summary_metrics()
    assert summary["total_works"] == 3
    assert summary["distinct_authors"] == 2
