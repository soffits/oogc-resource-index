from __future__ import annotations

import re
from urllib.parse import parse_qs, urljoin, urlparse

from bs4 import BeautifulSoup

from oogc_resource_index.constants import BASE_URL
from oogc_resource_index.models import ResourceRecord

FID_PATTERNS = (
    re.compile(r"[?&]fid=(\d+)", re.IGNORECASE),
    re.compile(r"(?:down|view|resource|mod)[-/](\d+)", re.IGNORECASE),
    re.compile(r"/(\d+)(?:\.html)?$", re.IGNORECASE),
)
TOTAL_PATTERN = re.compile(r"(?:共|total)\D{0,12}(\d+)\D{0,8}(?:条|items|records)?", re.IGNORECASE)


def parse_total_count(html: str) -> int | None:
    text = BeautifulSoup(html, "html.parser").get_text(" ", strip=True)
    match = TOTAL_PATTERN.search(text)
    return int(match.group(1)) if match else None


def parse_list_page(html: str, page_url: str) -> list[tuple[str, str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    entries: dict[str, tuple[str, str, str]] = {}
    for anchor in soup.find_all("a", href=True):
        href = str(anchor.get("href", ""))
        fid = extract_fid(href)
        if not fid:
            continue
        title = anchor.get_text(" ", strip=True)
        url = urljoin(_list_page_url_base(page_url), href)
        entries.setdefault(fid, (fid, title, url))
    return list(entries.values())


def _list_page_url_base(page_url: str) -> str:
    parsed = urlparse(urljoin(BASE_URL, page_url or ""))
    return f"{parsed.scheme}://{parsed.netloc}/"


def parse_detail_page(html: str, url: str, fid: str = "") -> ResourceRecord:
    soup = BeautifulSoup(html, "html.parser")
    resolved_fid = fid or extract_fid(url)
    title = _first_text(soup, ("h1", ".title", "title"))
    metadata = _metadata(soup)
    description = _description(soup)
    return ResourceRecord(
        fid=resolved_fid,
        title=title,
        url=url,
        category=metadata.get("category", ""),
        published_at=metadata.get("published_at", ""),
        updated_at=metadata.get("updated_at", ""),
        size=metadata.get("size", ""),
        downloads=metadata.get("downloads", ""),
        description=description,
        downUrl=_public_download_url(soup, url),
    )


def extract_fid(value: str) -> str:
    parsed = urlparse(value)
    fid_values = parse_qs(parsed.query).get("fid")
    if fid_values and fid_values[0].isdigit():
        return fid_values[0]
    for pattern in FID_PATTERNS:
        match = pattern.search(value)
        if match:
            return match.group(1)
    return ""


def _first_text(soup: BeautifulSoup, selectors: tuple[str, ...]) -> str:
    for selector in selectors:
        node = soup.select_one(selector)
        if node:
            text = node.get_text(" ", strip=True)
            if text:
                return text
    return ""


def _metadata(soup: BeautifulSoup) -> dict[str, str]:
    metadata: dict[str, str] = {}
    text = soup.get_text(" ", strip=True)
    for key, patterns in _metadata_patterns().items():
        for pattern in patterns:
            match = pattern.search(text)
            if match:
                metadata[key] = match.group(1).strip()
                break
    for label, value in _label_value_pairs(soup):
        key = _normalize_label(label)
        if key and value:
            metadata.setdefault(key, value)
    return metadata


def _metadata_patterns() -> dict[str, tuple[re.Pattern[str], ...]]:
    return {
        "category": (re.compile(r"(?:分类|category)[:： ]+([^ ]+)", re.IGNORECASE),),
        "published_at": (re.compile(r"(?:发布时间|发布|published)[:： ]+([0-9-]{8,10})", re.IGNORECASE),),
        "updated_at": (re.compile(r"(?:更新时间|更新|updated)[:： ]+([0-9-]{8,10})", re.IGNORECASE),),
        "size": (re.compile(r"(?:大小|size)[:： ]+([0-9.]+\s*[KMGT]?B)", re.IGNORECASE),),
        "downloads": (re.compile(r"(?:下载|downloads?)[:： ]+(\d+)", re.IGNORECASE),),
    }


def _label_value_pairs(soup: BeautifulSoup) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for row in soup.select("tr"):
        cells = [cell.get_text(" ", strip=True) for cell in row.select("th,td")]
        if len(cells) >= 2:
            pairs.append((cells[0], cells[1]))
    for item in soup.select("dl"):
        labels = [node.get_text(" ", strip=True) for node in item.select("dt")]
        values = [node.get_text(" ", strip=True) for node in item.select("dd")]
        pairs.extend(zip(labels, values, strict=False))
    return pairs


def _normalize_label(label: str) -> str:
    value = label.strip().strip(":：").lower()
    mapping = {
        "分类": "category",
        "category": "category",
        "发布时间": "published_at",
        "发布": "published_at",
        "published": "published_at",
        "更新时间": "updated_at",
        "更新": "updated_at",
        "updated": "updated_at",
        "大小": "size",
        "size": "size",
        "下载": "downloads",
        "下载次数": "downloads",
        "downloads": "downloads",
    }
    return mapping.get(value, "")


def _description(soup: BeautifulSoup) -> str:
    for selector in (".description", ".desc", ".content", "article"):
        node = soup.select_one(selector)
        if node:
            text = node.get_text(" ", strip=True)
            if text:
                return text[:5000]
    return ""


def _public_download_url(soup: BeautifulSoup, page_url: str) -> str:
    for anchor in soup.find_all("a", href=True):
        text = anchor.get_text(" ", strip=True).lower()
        href = str(anchor.get("href", ""))
        if "download" in text or "下载" in text or "down" in href.lower():
            return urljoin(page_url or BASE_URL, href)
    return ""
