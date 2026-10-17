"""pandas-based transformations and aggregations over the works catalog."""

import pandas as pd


class DataProcessor:
    """Wraps a DataFrame of works and exposes cleaning/aggregation operations."""

    REQUIRED_COLUMNS = [
        "work_id",
        "title",
        "author_name",
        "first_publish_year",
        "isbn",
        "subject",
        "language",
    ]

    def __init__(self, records: list[dict]):
        self.df = pd.DataFrame(records, columns=self.REQUIRED_COLUMNS)

    def handle_missing_values(self) -> pd.DataFrame:
        self.df["author_name"] = self.df["author_name"].fillna("Unknown")
        self.df["language"] = self.df["language"].fillna("und")
        self.df["subject"] = self.df["subject"].fillna("Uncategorized")
        self.df["first_publish_year"] = pd.to_numeric(
            self.df["first_publish_year"], errors="coerce"
        ).astype("Int64")
        return self.df

    def drop_duplicate_works(self) -> pd.DataFrame:
        self.df = self.df.drop_duplicates(subset=["work_id"]).reset_index(drop=True)
        return self.df

    def top_publication_years(self, n: int = 10) -> pd.DataFrame:
        counts = (
            self.df.dropna(subset=["first_publish_year"])
            .groupby("first_publish_year", observed=True)
            .size()
            .sort_values(ascending=False)
            .head(n)
            .reset_index(name="work_count")
        )
        return counts

    def top_languages(self, n: int = 10) -> pd.DataFrame:
        counts = (
            self.df.groupby("language", observed=True)
            .size()
            .sort_values(ascending=False)
            .head(n)
            .reset_index(name="work_count")
        )
        return counts

    def author_productivity(self, n: int = 10) -> pd.DataFrame:
        counts = (
            self.df.groupby("author_name", observed=True)
            .agg(work_count=("work_id", "count"))
            .sort_values("work_count", ascending=False)
            .head(n)
            .reset_index()
        )
        return counts

    def subject_aggregation(self) -> pd.DataFrame:
        return (
            self.df.groupby("subject", observed=True)
            .agg(
                work_count=("work_id", "count"),
                distinct_authors=("author_name", "nunique"),
                earliest_year=("first_publish_year", "min"),
                latest_year=("first_publish_year", "max"),
            )
            .reset_index()
            .sort_values("work_count", ascending=False)
        )

    def summary_metrics(self) -> dict:
        return {
            "total_works": int(len(self.df)),
            "distinct_authors": int(self.df["author_name"].nunique()),
            "distinct_subjects": int(self.df["subject"].nunique()),
            "distinct_languages": int(self.df["language"].nunique()),
        }
