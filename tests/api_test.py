import httpx
import pytest

from src.api.async_client import AsyncLibraryClient
from src.api.sync_client import SyncLibraryClient
from src.exceptions import APIError


def _mock_transport(handler):
    return httpx.MockTransport(handler)


def test_sync_client_search_books_success():
    def handler(request):
        assert request.url.path == "/search.json"
        return httpx.Response(200, json={"docs": [{"title": "Dune"}]})

    client = SyncLibraryClient()
    client._client = httpx.Client(transport=_mock_transport(handler), base_url=client.base_url)
    result = client.search_books("dune")
    assert result["docs"][0]["title"] == "Dune"
    client.close()


def test_sync_client_raises_api_error_on_4xx():
    def handler(request):
        return httpx.Response(404, json={"error": "not found"})

    client = SyncLibraryClient()
    client._client = httpx.Client(transport=_mock_transport(handler), base_url=client.base_url)
    with pytest.raises(APIError):
        client.get_work("OL_missing")
    client.close()


def test_sync_client_retries_on_rate_limit(monkeypatch):
    calls = {"count": 0}

    def handler(request):
        calls["count"] += 1
        if calls["count"] < 2:
            return httpx.Response(429)
        return httpx.Response(200, json={"ok": True})

    client = SyncLibraryClient()
    client._client = httpx.Client(transport=_mock_transport(handler), base_url=client.base_url)
    monkeypatch.setattr("time.sleep", lambda *_: None)
    result = client.get_work("OL1W")
    assert result == {"ok": True}
    assert calls["count"] == 2
    client.close()


@pytest.mark.asyncio
async def test_async_client_get_subject_works_paged():
    def handler(request):
        return httpx.Response(200, json={"works": [{"key": "/works/OL1W", "title": "A"}]})

    client = AsyncLibraryClient()
    client._client = httpx.AsyncClient(transport=_mock_transport(handler), base_url=client.base_url)
    results = await client.get_subject_works_paged("fantasy", pages=3)
    assert len(results) == 3
    assert results[0]["works"][0]["title"] == "A"
    await client.aclose()


@pytest.mark.asyncio
async def test_async_client_raises_api_error_on_5xx():
    def handler(request):
        return httpx.Response(500, json={"error": "boom"})

    client = AsyncLibraryClient()
    client._client = httpx.AsyncClient(transport=_mock_transport(handler), base_url=client.base_url)
    with pytest.raises(APIError):
        await client.get_author_works("OL1A")
    await client.aclose()
