from __future__ import annotations

import asyncio

import httpx

import oogc_resource_index.crawler as crawler
from oogc_resource_index.crawler import CrawlConfig, _crawl_with_client


def test_crawler_stops_on_no_new_fids() -> None:
    responses = {
        "https://oogc.cc/zy/down-class": """
          <div>共 2 条</div>
          <a href="https://oogc.cc/detail?fid=1">One</a>
          <a href="https://oogc.cc/detail?fid=2">Two</a>
        """,
        "https://oogc.cc/zy/down-class?page=2": """
          <a href="https://oogc.cc/detail?fid=1">One</a>
          <a href="https://oogc.cc/detail?fid=2">Two</a>
        """,
        "https://oogc.cc/detail?fid=1": "<h1>One</h1>",
        "https://oogc.cc/detail?fid=2": "<h1>Two</h1>",
    }

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=responses[str(request.url)])

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))

    records = asyncio.run(_crawl_with_client(CrawlConfig(), client=client))
    asyncio.run(client.aclose())

    assert [record.fid for record in records] == ["1", "2"]
    assert [record.title for record in records] == ["One", "Two"]


def test_crawler_bounds_detail_concurrency_and_reports_progress(capsys) -> None:
    active_details = 0
    max_active_details = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal active_details, max_active_details
        url = str(request.url)
        if url == "https://oogc.cc/zy/down-class":
            links = "".join(
                f'<a href="https://oogc.cc/detail?fid={fid}">Title {fid}</a>' for fid in range(1, 56)
            )
            return httpx.Response(200, text=f"<div>共 55 条</div>{links}")

        active_details += 1
        max_active_details = max(max_active_details, active_details)
        await asyncio.sleep(0.001)
        active_details -= 1
        fid = request.url.params["fid"]
        return httpx.Response(200, text=f"<h1>Detail {fid}</h1>")

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))

    records = asyncio.run(_crawl_with_client(CrawlConfig(concurrency=3), client=client))
    asyncio.run(client.aclose())

    assert [record.fid for record in records] == [str(fid) for fid in range(1, 56)]
    assert max_active_details <= 3
    stderr = capsys.readouterr().err
    assert "page 1: 55 entries, 55 first-seen this run, 55 unique fids" in stderr
    assert "details fetched: 50" in stderr


def test_detail_timeout_returns_fallback_record(monkeypatch, capsys) -> None:
    monkeypatch.setattr(crawler, "DETAIL_FETCH_RETRY_COUNT", 1)
    monkeypatch.setattr(crawler, "DETAIL_FETCH_RETRY_BACKOFF_SECONDS", 0)
    detail_attempts = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal detail_attempts
        if str(request.url) == "https://oogc.cc/zy/down-class":
            return httpx.Response(
                200,
                text='<div>共 1 条</div><a href="https://oogc.cc/detail?fid=9">List Title</a>',
            )

        detail_attempts += 1
        raise httpx.ReadTimeout("timed out", request=request)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))

    records = asyncio.run(_crawl_with_client(CrawlConfig(), client=client))
    asyncio.run(client.aclose())

    assert detail_attempts == 2
    assert records == [
        crawler.ResourceRecord(
            fid="9",
            title="List Title",
            url="https://oogc.cc/detail?fid=9",
            summary_status="detail_fetch_error: ReadTimeout: timed out",
        )
    ]
    stderr = capsys.readouterr().err
    assert "detail failed after 2 attempts: fid=9" in stderr
    assert "Traceback" not in stderr


def test_detail_http_failure_returns_fallback_record(monkeypatch, capsys) -> None:
    monkeypatch.setattr(crawler, "DETAIL_FETCH_RETRY_COUNT", 1)
    monkeypatch.setattr(crawler, "DETAIL_FETCH_RETRY_BACKOFF_SECONDS", 0)
    detail_attempts = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal detail_attempts
        if str(request.url) == "https://oogc.cc/zy/down-class":
            return httpx.Response(
                200,
                text='<div>共 1 条</div><a href="https://oogc.cc/detail?fid=10">Broken Detail</a>',
            )

        detail_attempts += 1
        return httpx.Response(503, request=request)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))

    records = asyncio.run(_crawl_with_client(CrawlConfig(), client=client))
    asyncio.run(client.aclose())

    assert detail_attempts == 2
    assert records[0].fid == "10"
    assert records[0].title == "Broken Detail"
    assert records[0].url == "https://oogc.cc/detail?fid=10"
    assert records[0].summary_status.startswith("detail_fetch_error: HTTPStatusError:")
    stderr = capsys.readouterr().err
    assert "detail failed after 2 attempts: fid=10" in stderr
    assert "Traceback" not in stderr


def test_crawler_fills_missing_download_url_with_cookie() -> None:
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        url = str(request.url)
        if url == "https://oogc.cc/zy/down-class":
            return httpx.Response(
                200,
                text='<div>共 1 条</div><a href="https://oogc.cc/detail?fid=7">Seven</a>',
                request=request,
            )
        if request.method == "POST":
            return httpx.Response(200, json={"state": "success", "downUrl": "/files/7.zip"}, request=request)
        return httpx.Response(
            200,
            text='<h1>Seven</h1><input type="hidden" name="formhash" value="abc123">',
            request=request,
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))

    records = asyncio.run(_crawl_with_client(CrawlConfig(cookie="session=redacted"), client=client))
    asyncio.run(client.aclose())

    assert records[0].downUrl == "https://oogc.cc/files/7.zip"
    assert [request.method for request in requests] == ["GET", "GET", "POST"]
    assert requests[2].headers["Cookie"] == "session=redacted"
    assert requests[2].content == b"ac=getdown&fid=7&formhash=abc123"


def test_crawler_does_not_post_for_download_url_without_cookie() -> None:
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if str(request.url) == "https://oogc.cc/zy/down-class":
            return httpx.Response(
                200,
                text='<div>共 1 条</div><a href="https://oogc.cc/detail?fid=8">Eight</a>',
                request=request,
            )
        return httpx.Response(
            200,
            text='<h1>Eight</h1><input type="hidden" name="formhash" value="abc123">',
            request=request,
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))

    records = asyncio.run(_crawl_with_client(CrawlConfig(), client=client))
    asyncio.run(client.aclose())

    assert records[0].downUrl == ""
    assert [request.method for request in requests] == ["GET", "GET"]


def test_crawler_does_not_post_for_download_url_when_disabled() -> None:
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if str(request.url) == "https://oogc.cc/zy/down-class":
            return httpx.Response(
                200,
                text='<div>共 1 条</div><a href="https://oogc.cc/detail?fid=9">Nine</a>',
                request=request,
            )
        return httpx.Response(
            200,
            text='<h1>Nine</h1><input type="hidden" name="formhash" value="abc123">',
            request=request,
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))

    records = asyncio.run(
        _crawl_with_client(CrawlConfig(cookie="session=redacted", download_links=False), client=client)
    )
    asyncio.run(client.aclose())

    assert records[0].downUrl == ""
    assert [request.method for request in requests] == ["GET", "GET"]
