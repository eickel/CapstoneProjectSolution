"""Asynchronous Open Library REST API client (httpx + asyncio)."""

import asyncio
import time

import httpx

from src.config import settings
from src.exceptions import APIError, RateLimitError
from src.logger import get_logger

logger = get_logger(__name__)


class AsyncLibraryClient:
    """Asynchronous client for the Open Library REST API with retry and rate-limit handling."""

    def __init__(self, base_url: str | None = None):
        self.base_url = base_url or settings.openlibrary_base_url
        self._min_interval = 1.0 / settings.rate_limit_requests_per_second
        self._last_request_time = 0.0
        self._throttle_lock = asyncio.Lock()
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=settings.request_timeout_seconds,
            headers={"User-Agent": "library-project-capstone/1.0"},
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> "AsyncLibraryClient":
        return self

    async def __aexit__(self, *exc_info) -> None:
        await self.aclose()

    async def _throttle(self) -> None:
        async with self._throttle_lock:
            elapsed = time.monotonic() - self._last_request_time
            if elapsed < self._min_interval:
                await asyncio.sleep(self._min_interval - elapsed)
            self._last_request_time = time.monotonic()

    async def _get(self, path: str, params: dict | None = None) -> dict:
        last_error: Exception | None = None
        for attempt in range(1, settings.max_retries + 1):
            await self._throttle()
            try:
                response = await self._client.get(path, params=params)
                if response.status_code == 429:
                    raise RateLimitError(
                        "Rate limit exceeded", status_code=429, url=str(response.url)
                    )
                response.raise_for_status()
                return response.json()
            except (httpx.TransportError, RateLimitError) as exc:
                last_error = exc
                backoff = settings.retry_backoff_seconds * attempt
                logger.warning(
                    "Request to %s failed (attempt %s/%s): %s. Retrying in %.1fs",
                    path,
                    attempt,
                    settings.max_retries,
                    exc,
                    backoff,
                )
                await asyncio.sleep(backoff)
            except httpx.HTTPStatusError as exc:
                raise APIError(
                    f"API request failed: {exc}",
                    status_code=exc.response.status_code,
                    url=str(exc.response.url),
                ) from exc

        msg = f"API request to {path} failed after {settings.max_retries} attempts"
        raise APIError(msg) from last_error

    async def search_books(self, query: str, page: int = 1) -> dict:
        return await self._get("/search.json", params={"q": query, "page": page})

    async def get_work(self, work_id: str) -> dict:
        return await self._get(f"/works/{work_id}.json")

    async def get_author_works(self, author_id: str) -> dict:
        return await self._get(f"/authors/{author_id}/works.json")

    async def get_subject_works(self, subject: str, limit: int = 20, offset: int = 0) -> dict:
        return await self._get(
            f"/subjects/{subject}.json", params={"limit": limit, "offset": offset}
        )

    async def get_subject_works_paged(
        self, subject: str, pages: int, limit: int = 20
    ) -> list[dict]:
        """Fetch multiple pages of subject works concurrently."""
        tasks = [
            self.get_subject_works(subject, limit=limit, offset=page * limit)
            for page in range(pages)
        ]
        return await asyncio.gather(*tasks)
