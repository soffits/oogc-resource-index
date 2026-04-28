from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from oogc_resource_index.constants import (
    BASE_URL,
    DEFAULT_BROWSER_USER_AGENT,
    DEFAULT_TIMEOUT_SECONDS,
    DOWNLOAD_AJAX_URL,
)

FORMHASH_PATTERN = re.compile(r"formhash[\"']?\s*[:=]\s*[\"']?([A-Za-z0-9]+)", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class DownloadResult:
    fid: str
    status_code: int
    state: str
    down_url: str = ""

    @property
    def has_down_url(self) -> bool:
        return bool(self.down_url)


@dataclass(frozen=True, slots=True)
class AuthVerifyResult:
    status_code: int
    state: str
    down_url_present: bool


def read_cookie_value(cookie: str | None = None, cookie_file: Path | None = None) -> str:
    if cookie:
        return cookie.strip()
    if cookie_file is None:
        return ""
    return cookie_file.read_text(encoding="utf-8").strip()


def verify_cookie(
    *,
    detail_url: str,
    fid: str,
    cookie: str | None = None,
    cookie_file: Path | None = None,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> AuthVerifyResult:
    result = asyncio.run(
        fetch_download_url(
            detail_url=detail_url,
            fid=fid,
            cookie=read_cookie_value(cookie, cookie_file),
            timeout_seconds=timeout_seconds,
        )
    )
    return AuthVerifyResult(
        status_code=result.status_code,
        state=result.state,
        down_url_present=result.has_down_url,
    )


async def fetch_download_url(
    *,
    detail_url: str,
    fid: str,
    cookie: str,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    client: httpx.AsyncClient | None = None,
    detail_html: str | None = None,
    detail_status_code: int = 200,
) -> DownloadResult:
    if client is None:
        async with httpx.AsyncClient(
            headers=browser_headers(cookie),
            follow_redirects=True,
            timeout=timeout_seconds,
        ) as owned_client:
            return await fetch_download_url(
                detail_url=detail_url,
                fid=fid,
                cookie=cookie,
                timeout_seconds=timeout_seconds,
                client=owned_client,
                detail_html=detail_html,
                detail_status_code=detail_status_code,
            )

    status_code = detail_status_code
    if detail_html is None:
        detail_response = await client.get(detail_url, headers=browser_headers(cookie))
        status_code = detail_response.status_code
        if detail_response.is_error:
            return DownloadResult(fid=fid, status_code=status_code, state="detail_http_error")
        detail_html = detail_response.text

    formhash = extract_formhash(detail_html)
    if not formhash:
        return DownloadResult(fid=fid, status_code=status_code, state="formhash_missing")

    ajax_response = await client.post(
        DOWNLOAD_AJAX_URL,
        content=f"ac=getdown&fid={fid}&formhash={formhash}",
        headers=post_headers(detail_url, cookie),
    )
    state, down_url = parse_download_response(ajax_response.text)
    return DownloadResult(
        fid=fid,
        status_code=ajax_response.status_code,
        state=state or ("ok" if down_url else "down_url_missing"),
        down_url=down_url,
    )


def browser_headers(cookie: str) -> dict[str, str]:
    headers = {
        "User-Agent": DEFAULT_BROWSER_USER_AGENT,
        "Accept": "*/*",
        "Accept-Language": "en;q=0.8",
        "DNT": "1",
        "Sec-GPC": "1",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
    }
    if cookie:
        headers["Cookie"] = cookie
    return headers


def post_headers(detail_url: str, cookie: str) -> dict[str, str]:
    headers = browser_headers(cookie)
    headers.update(
        {
            "Accept": "application/json,text/javascript,*/*;q=0.01",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Origin": BASE_URL,
            "Referer": detail_url,
            "X-Requested-With": "XMLHttpRequest",
        }
    )
    return headers


def extract_formhash(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    formhash_input = soup.find("input", attrs={"name": "formhash"})
    if formhash_input:
        value = str(formhash_input.get("value", "") or "").strip()
        if value:
            return value
    match = FORMHASH_PATTERN.search(html)
    if match:
        return match.group(1).strip()
    return ""


def parse_download_response(text: str) -> tuple[str, str]:
    payload = _json_payload(text)
    if isinstance(payload, dict):
        state = str(payload.get("state", "") or payload.get("status", "") or "").strip()
        down_url = str(payload.get("downUrl", "") or payload.get("down_url", "") or "").strip()
        return state, urljoin(BASE_URL + "/", down_url) if down_url else ""
    return "invalid_response", ""


def _json_payload(text: str) -> object:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None
