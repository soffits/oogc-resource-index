# AGENTS.md

## Project Purpose

`oogc-resource-index` is a Python CLI that builds and maintains a spreadsheet-ready index of OOGC resource metadata. It crawls list and detail pages, parses resource fields, optionally resolves authenticated download URLs from a runtime cookie, writes XLSX/CSV datasets, and can upload generated exports to Seafile.

## Architecture

- `src/oogc_resource_index/cli.py`: Typer command surface.
- `src/oogc_resource_index/crawler.py`: asynchronous full crawl flow.
- `src/oogc_resource_index/incremental.py`: incremental dataset update flow.
- `src/oogc_resource_index/parser.py`: HTML parsing and field extraction.
- `src/oogc_resource_index/auth_downloader.py`: authenticated download URL verification and resolution.
- `src/oogc_resource_index/dataset.py`: CSV/XLSX read, merge, sort, and write helpers.
- `src/oogc_resource_index/seafile.py`: Seafile upload via repository token configuration.
- `src/oogc_resource_index/constants.py`: shared URLs, defaults, and dataset field names.
- `tests/`: pytest coverage for parser, crawler, CLI, incremental updates, dataset import, and authenticated download helpers.
- `exports/`: generated data output; ignored by Git.

## Package Manager

Use `uv`. Do not switch to `pip`, Poetry, or another package manager unless explicitly requested.

## Commands

```bash
uv sync
uv run pytest
uv run oogc-resource-index --help
uv run oogc-resource-index verify-cookie --cookie-file cookie.txt
uv run oogc-resource-index crawl --cookie-file cookie.txt --output exports/oogc_resources.xlsx
uv run oogc-resource-index crawl --cookie-file cookie.txt --output exports/oogc_resources.xlsx --full
uv run oogc-resource-index incremental-update --dataset exports/oogc_resources.xlsx --output exports/oogc_resources.xlsx --cookie-file cookie.txt
uv run oogc-resource-index upload-seafile exports/oogc_resources.xlsx
```

## Coding Rules

- Keep repository prose and documentation in English only.
- Keep runtime behavior unchanged unless the user explicitly asks for code changes.
- Prefer small, direct changes over broad refactors.
- Preserve the Typer CLI interface unless the task requires changing it.
- Keep generated exports, caches, virtual environments, cookies, and local environment files out of Git.
- Add or update tests when changing runtime behavior.
- Use ASCII for new text unless an existing file requires otherwise.

## Security Boundaries

- Never add cookies, account credentials, Seafile tokens, `.env` files, generated exports, or secret paths containing real values.
- `cookie.txt`, `*cookie*.txt`, `.env`, `.env.*`, `.venv/`, `.pytest_cache/`, `__pycache__/`, and `exports/` are ignored intentionally.
- Seafile configuration is expected at `/opt/data/.secrets/seafile-vault.env` by default or supplied through environment variables.
- Treat authenticated download URLs and exported datasets as sensitive operational data.

## Commits

Use Conventional Commits when committing, for example:

```text
docs: update contributor agent guidance
fix: preserve csv copy during incremental crawl
test: cover authenticated download parser states
```

Do not commit unless the user explicitly asks. Do not amend commits unless the user explicitly asks.

## License

This repository is licensed under GNU AGPL-3.0-only. Keep license references accurate and preserve the `LICENSE` file.
