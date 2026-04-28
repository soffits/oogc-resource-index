from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urljoin

import httpx

from oogc_resource_index.constants import DEFAULT_ENV_FILE, DEFAULT_TIMEOUT_SECONDS


class SeafileConfigError(ValueError):
    pass


def upload_with_repo_token(file_path: Path, env_file: Path = DEFAULT_ENV_FILE) -> str:
    config = _load_env(env_file)
    server_url = _first(config, "SEAFILE_SERVER_URL", "SEAFILE_URL", "SERVER_URL")
    repo_token = _first(config, "SEAFILE_REPO_TOKEN", "REPO_TOKEN", "SEAFILE_VAULT_REPO_TOKEN")
    parent_dir = _first(config, "SEAFILE_PARENT_DIR", "PARENT_DIR", default="/")
    replace = _first(config, "SEAFILE_REPLACE", "REPLACE", default="1")
    if not server_url or not repo_token:
        raise SeafileConfigError(
            f"{env_file} must define SEAFILE_SERVER_URL and SEAFILE_REPO_TOKEN"
        )
    if not file_path.is_file():
        raise FileNotFoundError(file_path)
    base = server_url.rstrip("/") + "/"
    upload_link_url = urljoin(base, f"api/v2.1/repos/{repo_token}/upload-link/")
    with httpx.Client(timeout=DEFAULT_TIMEOUT_SECONDS) as client:
        upload_link = client.get(upload_link_url).raise_for_status().json()
        with file_path.open("rb") as file:
            response = client.post(
                str(upload_link),
                data={"parent_dir": parent_dir, "replace": replace},
                files={"file": (file_path.name, file)},
            )
        response.raise_for_status()
    return response.text


def _load_env(path: Path) -> dict[str, str]:
    values = dict(os.environ)
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _first(values: dict[str, str], *keys: str, default: str = "") -> str:
    for key in keys:
        value = values.get(key, "").strip()
        if value:
            return value
    return default
