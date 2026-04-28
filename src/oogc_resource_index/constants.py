"""Shared constants for OOGC resource index tooling."""

from __future__ import annotations

from pathlib import Path

BASE_URL = "https://oogc.cc"
LIST_PATH = "/zy/down-class"
LIST_URL = f"{BASE_URL}{LIST_PATH}"
DOWNLOAD_AJAX_URL = f"{BASE_URL}/plugin.php?id=keke_down:ajax"
DEFAULT_VERIFY_FID = "326"
DEFAULT_TIMEOUT_SECONDS = 30.0
DEFAULT_USER_AGENT = "oogc-resource-index/0.1 (+metadata crawler)"
DEFAULT_BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
DEFAULT_OUTPUT = Path("oogc_resources.xlsx")
DEFAULT_ENV_FILE = Path("/opt/data/.secrets/seafile-vault.env")
FID_FIELD = "fid"
DOWN_URL_FIELD = "downUrl"
DATASET_FIELDS = (
    "fid",
    "title",
    "url",
    "category",
    "published_at",
    "updated_at",
    "size",
    "downloads",
    "description",
    "downUrl",
    "summary_status",
)


def detail_url(fid: str) -> str:
    return f"{BASE_URL}/zy/down-view-{fid}"
