"""Custom exception hierarchy for the Open Library automation system."""


class LibraryProjectError(Exception):
    """Base exception for all application-specific errors."""


class APIError(LibraryProjectError):
    """Raised when a request to the Open Library API fails or returns an error status."""

    def __init__(self, message: str, status_code: int | None = None, url: str | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.url = url


class RateLimitError(APIError):
    """Raised when the Open Library API responds with a rate-limit (429) status."""


class DataValidationError(LibraryProjectError):
    """Raised when incoming or outgoing data fails validation (e.g. bad ISBN, malformed record)."""


class DatabaseError(LibraryProjectError):
    """Raised when a SQLite operation fails unexpectedly."""


class CatalogFileError(LibraryProjectError):
    """Raised when a catalog file (CSV/JSON) cannot be read, parsed, or streamed."""


class ReportGenerationError(LibraryProjectError):
    """Raised when report generation (Excel/CSV/JSON export) fails."""
