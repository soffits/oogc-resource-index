# oogc-resource-index

`oogc-resource-index` is a focused Python CLI for building a clean, spreadsheet-ready index of OOGC resource metadata. It crawls resource list and detail pages, enriches records with authenticated download URLs when a cookie is provided, writes XLSX/CSV exports, and can upload finished files to Seafile.

Designed as a practical Phase 1 automation tool, the project keeps the workflow small, auditable, and easy to rerun for incremental updates.

## Highlights

- Crawls OOGC resource pages asynchronously with configurable concurrency and timeouts.
- Exports normalized records to XLSX, with a CSV copy by default.
- Updates existing CSV/XLSX datasets incrementally unless `--full` is requested.
- Optionally resolves authenticated `downUrl` values from a cookie supplied at runtime.
- Uploads completed exports to Seafile through repository-token configuration outside the repo.

## Setup

```bash
uv sync
```

## Commands

```bash
uv run pytest
uv run oogc-resource-index --help
uv run oogc-resource-index verify-cookie --cookie-file cookie.txt
uv run oogc-resource-index crawl --cookie-file cookie.txt --output exports/oogc_resources.xlsx
uv run oogc-resource-index crawl --cookie-file cookie.txt --output exports/oogc_resources.xlsx --full
uv run oogc-resource-index incremental-update --dataset exports/oogc_resources.xlsx --output exports/oogc_resources.xlsx --cookie-file cookie.txt
uv run oogc-resource-index upload-seafile exports/oogc_resources.xlsx
```

`crawl` creates a new dataset when the output file does not exist. Later runs against the same output update it incrementally by default. Use `--no-download-links` for metadata-only exports and `--no-csv-copy` to skip the CSV companion file.

`upload-seafile` reads `/opt/data/.secrets/seafile-vault.env` by default. It expects `SEAFILE_SERVER_URL` and `SEAFILE_REPO_TOKEN`; optional keys are `SEAFILE_PARENT_DIR` and `SEAFILE_REPLACE`.

## Security

Do not commit cookies, account credentials, Seafile tokens, generated exports, or local environment files. Runtime secrets should stay in ignored files such as `cookie.txt` or external paths such as `/opt/data/.secrets/seafile-vault.env`.

## License

GNU Affero General Public License v3.0 only. See [LICENSE](LICENSE).
