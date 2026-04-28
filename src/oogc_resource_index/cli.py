from __future__ import annotations

from pathlib import Path

import typer

from oogc_resource_index.auth_downloader import read_cookie_value, verify_cookie
from oogc_resource_index.constants import (
    DEFAULT_ENV_FILE,
    DEFAULT_OUTPUT,
    DEFAULT_TIMEOUT_SECONDS,
    DEFAULT_VERIFY_FID,
    LIST_URL,
    detail_url,
)
from oogc_resource_index.crawler import CrawlConfig, crawl_resources
from oogc_resource_index.dataset import read_dataset, write_csv_copy, write_dataset
from oogc_resource_index.incremental import IncrementalConfig, update_records_incrementally
from oogc_resource_index.seafile import upload_with_repo_token

app = typer.Typer(no_args_is_help=True, help="OOGC resource index tools.")


@app.command()
def crawl(
    output: Path = typer.Option(DEFAULT_OUTPUT, "--output", "-o"),
    start_url: str = typer.Option(LIST_URL, "--start-url"),
    max_pages: int = typer.Option(0, "--max-pages", min=0),
    concurrency: int = typer.Option(8, "--concurrency", min=1),
    timeout: float = typer.Option(DEFAULT_TIMEOUT_SECONDS, "--timeout", min=0.1),
    cookie: str | None = typer.Option(None, "--cookie", help="Cookie header value; prefer --cookie-file."),
    cookie_file: Path | None = typer.Option(None, "--cookie-file", exists=True, readable=True),
    full: bool = typer.Option(False, "--full", help="Force a full crawl even when --output exists."),
    download_links: bool = typer.Option(True, "--download-links/--no-download-links"),
    csv_copy: bool = typer.Option(True, "--csv-copy/--no-csv-copy"),
) -> None:
    cookie_value = read_cookie_value(cookie, cookie_file)
    if output.exists() and not full:
        existing = read_dataset(output)
        result = update_records_incrementally(
            existing,
            IncrementalConfig(
                start_url=start_url,
                max_pages=max_pages,
                concurrency=concurrency,
                timeout_seconds=timeout,
                download_links=download_links,
                cookie=cookie_value,
            ),
        )
        written = write_dataset(result.records, output)
        typer.echo(
            "updated "
            f"records={len(result.records)} new_fids={result.new_fids} "
            f"list_pages={result.list_pages} metadata_fetches={result.metadata_fetches} "
            f"download_fetches={result.download_fetches}"
        )
        typer.echo(f"wrote {len(result.records)} records to {written}")
        if csv_copy:
            csv_path = write_csv_copy(result.records, output)
            typer.echo(f"wrote csv copy to {csv_path}")
        return

    records = crawl_resources(
        CrawlConfig(
            start_url=start_url,
            max_pages=max_pages,
            concurrency=concurrency,
            timeout_seconds=timeout,
            cookie=cookie_value,
            download_links=download_links,
        )
    )
    written = write_dataset(records, output)
    typer.echo(f"wrote {len(records)} records to {written}")
    if csv_copy:
        csv_path = write_csv_copy(records, output)
        typer.echo(f"wrote csv copy to {csv_path}")

@app.command("verify-cookie")
def verify_cookie_command(
    fid: str = typer.Option(DEFAULT_VERIFY_FID, "--fid"),
    target_url: str | None = typer.Option(None, "--target-url"),
    cookie: str | None = typer.Option(None, "--cookie", help="Cookie header value; prefer --cookie-file."),
    cookie_file: Path | None = typer.Option(None, "--cookie-file", exists=True, readable=True),
    timeout: float = typer.Option(DEFAULT_TIMEOUT_SECONDS, "--timeout", min=0.1),
) -> None:
    result = verify_cookie(
        detail_url=target_url or detail_url(fid),
        fid=fid,
        cookie=cookie,
        cookie_file=cookie_file,
        timeout_seconds=timeout,
    )
    typer.echo(f"status={result.status_code}")
    typer.echo(f"state={result.state}")
    typer.echo(f"downUrl-present={str(result.down_url_present).lower()}")


@app.command("incremental-update")
def incremental_update(
    dataset: Path = typer.Option(..., "--dataset", exists=True, readable=True),
    output: Path = typer.Option(DEFAULT_OUTPUT, "--output", "-o"),
    cookie_file: Path | None = typer.Option(None, "--cookie-file", exists=True, readable=True),
    max_pages: int = typer.Option(0, "--max-pages", min=0),
    concurrency: int = typer.Option(8, "--concurrency", min=1),
    timeout: float = typer.Option(DEFAULT_TIMEOUT_SECONDS, "--timeout", min=0.1),
    refresh_existing: bool = typer.Option(False, "--refresh-existing"),
    download_links: bool = typer.Option(True, "--download-links/--no-download-links"),
) -> None:
    existing = read_dataset(dataset)
    result = update_records_incrementally(
        existing,
        IncrementalConfig(
            max_pages=max_pages,
            concurrency=concurrency,
            timeout_seconds=timeout,
            refresh_existing=refresh_existing,
            download_links=download_links,
            cookie=read_cookie_value(cookie_file=cookie_file) if cookie_file else "",
        ),
    )
    xlsx_output = output if output.suffix.lower() == ".xlsx" else output.with_suffix(".xlsx")
    written = write_dataset(result.records, xlsx_output)
    csv_path = write_csv_copy(result.records, xlsx_output)
    typer.echo(
        "updated "
        f"records={len(result.records)} new_fids={result.new_fids} "
        f"list_pages={result.list_pages} metadata_fetches={result.metadata_fetches} "
        f"download_fetches={result.download_fetches}"
    )
    typer.echo(f"wrote xlsx to {written}")
    typer.echo(f"wrote csv copy to {csv_path}")


@app.command("upload-seafile")
def upload_seafile(
    file_path: Path = typer.Argument(..., exists=True, readable=True),
    env_file: Path = typer.Option(DEFAULT_ENV_FILE, "--env-file"),
) -> None:
    response_text = upload_with_repo_token(file_path, env_file=env_file)
    typer.echo(response_text)


if __name__ == "__main__":
    app()
