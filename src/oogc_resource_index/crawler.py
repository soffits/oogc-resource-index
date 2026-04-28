from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass
from urllib.parse import urlencode

import httpx

from oogc_resource_index.auth_downloader import browser_headers, fetch_download_url
from oogc_resource_index.constants import DEFAULT_TIMEOUT_SECONDS, DEFAULT_USER_AGENT, LIST_URL
from oogc_resource_index.models import ResourceRecord
from oogc_resource_index.parser import parse_detail_page, parse_list_page, parse_total_count

DETAIL_FETCH_RETRY_COUNT = 2
DETAIL_FETCH_RETRY_BACKOFF_SECONDS = 0.2


@dataclass(frozen=True, slots=True)
class CrawlConfig:
    start_url: str = LIST_URL
    max_pages: int = 0
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
    concurrency: int = 8
    user_agent: str = DEFAULT_USER_AGENT
    cookie: str = ""
    download_links: bool = True


def crawl_resources(config: CrawlConfig) -> list[ResourceRecord]:
    headers = browser_headers(config.cookie) if config.cookie else {"User-Agent": config.user_agent}
    return asyncio.run(_crawl_with_client(config, headers=headers))


async def _crawl_with_client(
    config: CrawlConfig,
    *,
    client: httpx.AsyncClient | None = None,
    headers: dict[str, str] | None = None,
) -> list[ResourceRecord]:
    if client is None:
        async with httpx.AsyncClient(
            headers=headers,
            follow_redirects=True,
            timeout=config.timeout_seconds,
        ) as owned_client:
            return await _crawl_with_client(config, client=owned_client)

    records: list[ResourceRecord] = []
    seen_fids: set[str] = set()
    total_count: int | None = None
    detail_count = 0
    page = 1
    while config.max_pages <= 0 or page <= config.max_pages:
        page_url = _page_url(config.start_url, page)
        response = await client.get(page_url)
        response.raise_for_status()
        if total_count is None:
            total_count = parse_total_count(response.text)
        entries = parse_list_page(response.text, page_url)
        new_entries = []
        for entry in entries:
            fid = entry[0]
            if fid not in seen_fids:
                seen_fids.add(fid)
                new_entries.append(entry)

        _print_progress(
            f"page {page}: {len(entries)} entries, {len(new_entries)} first-seen this run, "
            f"{len(seen_fids)} unique fids"
        )
        if not new_entries:
            break

        page_records, detail_count = await _fetch_details(
            client,
            config,
            new_entries,
            completed=detail_count,
        )
        records.extend(page_records)
        if total_count is not None and len(seen_fids) >= total_count:
            break
        page += 1
    _print_progress(f"crawl complete: {len(records)} records")
    return records


async def _fetch_details(
    client: httpx.AsyncClient,
    config: CrawlConfig,
    entries: list[tuple[str, str, str]],
    *,
    completed: int,
) -> tuple[list[ResourceRecord], int]:
    semaphore = asyncio.Semaphore(max(1, config.concurrency))
    results: list[ResourceRecord | None] = [None] * len(entries)

    async def fetch_one(index: int, fid: str, list_title: str, detail_url: str) -> tuple[int, ResourceRecord]:
        async with semaphore:
            detail_response, error = await _get_detail_with_retries(client, fid, detail_url)
        if error is not None:
            return index, _failed_detail_record(fid, list_title, detail_url, error)
        record = parse_detail_page(detail_response.text, detail_url, fid=fid)
        if not record.title and list_title:
            record = ResourceRecord.from_row({**record.as_row(), "title": list_title})
        if _should_fetch_download(record, config):
            download = await fetch_download_url(
                detail_url=record.url or detail_url,
                fid=fid,
                cookie=config.cookie,
                timeout_seconds=config.timeout_seconds,
                client=client,
                detail_html=detail_response.text,
                detail_status_code=detail_response.status_code,
            )
            if download.down_url:
                record = ResourceRecord.from_row({**record.as_row(), "downUrl": download.down_url})
        return index, record

    tasks = [asyncio.create_task(fetch_one(index, *entry)) for index, entry in enumerate(entries)]
    for task in asyncio.as_completed(tasks):
        index, record = await task
        results[index] = record
        completed += 1
        if completed % 50 == 0:
            _print_progress(f"details fetched: {completed}")

    return [record for record in results if record is not None], completed


async def _get_detail_with_retries(
    client: httpx.AsyncClient, fid: str, detail_url: str
) -> tuple[httpx.Response | None, httpx.HTTPError | None]:
    attempts = DETAIL_FETCH_RETRY_COUNT + 1
    last_error: httpx.HTTPError | None = None
    for attempt in range(1, attempts + 1):
        try:
            response = await client.get(detail_url)
            response.raise_for_status()
            return response, None
        except httpx.HTTPError as exc:
            last_error = exc
            if attempt < attempts:
                await asyncio.sleep(DETAIL_FETCH_RETRY_BACKOFF_SECONDS * attempt)

    assert last_error is not None
    _print_progress(
        f"detail failed after {attempts} attempts: fid={fid} url={detail_url} error={_brief_error(last_error)}"
    )
    return None, last_error


def _failed_detail_record(fid: str, list_title: str, detail_url: str, error: httpx.HTTPError) -> ResourceRecord:
    return ResourceRecord(
        fid=fid,
        title=list_title,
        url=detail_url,
        summary_status=f"detail_fetch_error: {_brief_error(error)}",
    )


def _brief_error(error: httpx.HTTPError) -> str:
    return f"{type(error).__name__}: {error}"


def _should_fetch_download(record: ResourceRecord, config: CrawlConfig) -> bool:
    return bool(config.download_links and config.cookie and not record.downUrl)


def _print_progress(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def _page_url(start_url: str, page: int) -> str:
    if page <= 1:
        return start_url
    separator = "&" if "?" in start_url else "?"
    return f"{start_url}{separator}{urlencode({'page': page})}"
