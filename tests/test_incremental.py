from __future__ import annotations

import asyncio

import httpx

from oogc_resource_index.incremental import IncrementalConfig, _update_records_incrementally
from oogc_resource_index.models import ResourceRecord


def test_incremental_update_skips_complete_existing_fids() -> None:
    detail_requests: list[str] = []
    responses = {
        "https://oogc.cc/zy/down-class": """
          <a href="https://oogc.cc/detail?fid=1">One</a>
          <a href="https://oogc.cc/detail?fid=2">Two</a>
        """,
        "https://oogc.cc/zy/down-class?page=2": """
          <a href="https://oogc.cc/detail?fid=1">One</a>
          <a href="https://oogc.cc/detail?fid=2">Two</a>
        """,
        "https://oogc.cc/detail?fid=2": """
          <h1>Two Detail</h1>
          <table><tr><th>分类</th><td>Maps</td></tr></table>
        """,
    }

    async def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url.startswith("https://oogc.cc/detail"):
            detail_requests.append(url)
        return httpx.Response(200, text=responses[url], request=request)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    existing = [
        ResourceRecord(
            fid="1",
            title="One Detail",
            url="https://oogc.cc/detail?fid=1",
            category="Maps",
        )
    ]

    result = asyncio.run(
        _update_records_incrementally(
            existing,
            IncrementalConfig(max_pages=5, download_links=False),
            client=client,
        )
    )
    asyncio.run(client.aclose())

    assert detail_requests == ["https://oogc.cc/detail?fid=2"]
    assert result.list_pages == 2
    assert result.metadata_fetches == 1
    assert result.new_fids == 1
    assert [(record.fid, record.title) for record in result.records] == [
        ("1", "One Detail"),
        ("2", "Two Detail"),
    ]
