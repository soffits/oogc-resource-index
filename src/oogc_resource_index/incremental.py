from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass
from urllib.parse import urlencode

import httpx

from oogc_resource_index.auth_downloader import browser_headers, fetch_download_url
from oogc_resource_index.constants import DEFAULT_TIMEOUT_SECONDS, DEFAULT_USER_AGENT, LIST_URL
from oogc_resource_index.dataset import merge_records
from oogc_resource_index.models import ResourceRecord
from oogc_resource_index.parser import parse_detail_page, parse_list_page


@dataclass(frozen=True, slots=True)
class IncrementalConfig:
    start_url: str = LIST_URL
    max_pages: int = 0
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
    concurrency: int = 8
    refresh_existing: bool = False
    download_links: bool = True
    cookie: str = ""


@dataclass(frozen=True, slots=True)
class IncrementalResult:
    records: list[ResourceRecord]
    list_pages: int
    metadata_fetches: int
    download_fetches: int
    new_fids: int


def update_records_incrementally(
    existing: list[ResourceRecord],
    config: IncrementalConfig,
) -> IncrementalResult:
    return asyncio.run(_update_records_incrementally(existing, config))


async def _update_records_incrementally(
    existing: list[ResourceRecord],
    config: IncrementalConfig,
    *,
    client: httpx.AsyncClient | None = None,
) -> IncrementalResult:
    if client is None:
        headers = browser_headers(config.cookie) if config.cookie else {"User-Agent": DEFAULT_USER_AGENT}
        async with httpx.AsyncClient(
            headers=headers,
            follow_redirects=True,
            timeout=config.timeout_seconds,
        ) as owned_client:
            return await _update_records_incrementally(existing, config, client=owned_client)

    existing_by_fid = {record.fid: record for record in existing if record.fid}
    seen_list_fids: set[str] = set()
    candidates: dict[str, tuple[str, str, str]] = {}
    new_fids: set[str] = set()
    page = 1
    list_pages = 0
    while config.max_pages <= 0 or page <= config.max_pages:
        page_url = _page_url(config.start_url, page)
        response = await client.get(page_url)
        response.raise_for_status()
        list_pages += 1
        entries = parse_list_page(response.text, page_url)
        page_new_fids = 0
        for fid, title, detail_url in entries:
            if fid in seen_list_fids:
                continue
            seen_list_fids.add(fid)
            record = existing_by_fid.get(fid)
            if record is None:
                page_new_fids += 1
                new_fids.add(fid)
            if _should_fetch_metadata(record, config.refresh_existing):
                candidates[fid] = (fid, title, detail_url)
            elif _should_fetch_download(record, config):
                candidates[fid] = (fid, title, detail_url)

        _print_progress(
            f"page {page}: {len(entries)} entries, {page_new_fids} new fids, {len(candidates)} queued updates"
        )
        if page_new_fids == 0:
            break
        page += 1

    updates, metadata_fetches, download_fetches = await _fetch_updates(
        client,
        list(candidates.values()),
        existing_by_fid,
        config,
    )
    return IncrementalResult(
        records=merge_records(existing, updates),
        list_pages=list_pages,
        metadata_fetches=metadata_fetches,
        download_fetches=download_fetches,
        new_fids=len(new_fids),
    )


async def _fetch_updates(
    client: httpx.AsyncClient,
    entries: list[tuple[str, str, str]],
    existing_by_fid: dict[str, ResourceRecord],
    config: IncrementalConfig,
) -> tuple[list[ResourceRecord], int, int]:
    semaphore = asyncio.Semaphore(max(1, config.concurrency))
    results: list[ResourceRecord | None] = [None] * len(entries)
    metadata_fetches = 0
    download_fetches = 0

    async def fetch_one(index: int, fid: str, list_title: str, detail_url: str) -> tuple[int, ResourceRecord, bool, bool]:
        existing = existing_by_fid.get(fid)
        should_fetch_metadata = _should_fetch_metadata(existing, config.refresh_existing)
        async with semaphore:
            record = existing or ResourceRecord(fid=fid, title=list_title, url=detail_url)
            if should_fetch_metadata:
                detail_response = await client.get(detail_url)
                detail_response.raise_for_status()
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
                )
                if download.down_url:
                    record = ResourceRecord.from_row({**record.as_row(), "downUrl": download.down_url})
                return index, record, should_fetch_metadata, True
        return index, record, should_fetch_metadata, False

    tasks = [asyncio.create_task(fetch_one(index, *entry)) for index, entry in enumerate(entries)]
    for task in asyncio.as_completed(tasks):
        index, record, fetched_metadata, fetched_download = await task
        results[index] = record
        metadata_fetches += int(fetched_metadata)
        download_fetches += int(fetched_download)

    return [record for record in results if record is not None], metadata_fetches, download_fetches


def _should_fetch_metadata(record: ResourceRecord | None, refresh_existing: bool) -> bool:
    if record is None or refresh_existing:
        return True
    return not record.title or not record.url or _metadata_missing(record)


def _should_fetch_download(record: ResourceRecord | None, config: IncrementalConfig) -> bool:
    return bool(config.download_links and config.cookie and record is not None and not record.downUrl)


def _metadata_missing(record: ResourceRecord) -> bool:
    return not any((record.category, record.published_at, record.updated_at, record.size, record.downloads, record.description))


def _page_url(start_url: str, page: int) -> str:
    if page <= 1:
        return start_url
    separator = "&" if "?" in start_url else "?"
    return f"{start_url}{separator}{urlencode({'page': page})}"


def _print_progress(message: str) -> None:
    print(message, file=sys.stderr, flush=True)
