from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

import oogc_resource_index.cli as cli
from oogc_resource_index.crawler import CrawlConfig
from oogc_resource_index.incremental import IncrementalConfig, IncrementalResult
from oogc_resource_index.models import ResourceRecord


def test_crawl_updates_existing_output_incrementally(monkeypatch, tmp_path: Path) -> None:
    output = tmp_path / "oogc_resources.xlsx"
    output.touch()
    existing = [ResourceRecord(fid="1", title="Existing")]
    updated = [*existing, ResourceRecord(fid="2", title="New")]
    calls: dict[str, object] = {}

    def fake_read_dataset(path: Path) -> list[ResourceRecord]:
        calls["read_path"] = path
        return existing

    def fake_update_records_incrementally(
        records: list[ResourceRecord], config: IncrementalConfig
    ) -> IncrementalResult:
        calls["incremental_records"] = records
        calls["incremental_config"] = config
        return IncrementalResult(
            records=updated,
            list_pages=1,
            metadata_fetches=1,
            download_fetches=0,
            new_fids=1,
        )

    def fake_crawl_resources(config: CrawlConfig) -> list[ResourceRecord]:
        calls["crawl_config"] = config
        return []

    def fake_write_dataset(records: list[ResourceRecord], path: Path) -> Path:
        calls["written_records"] = records
        calls["written_path"] = path
        return path

    monkeypatch.setattr(cli, "read_dataset", fake_read_dataset)
    monkeypatch.setattr(cli, "update_records_incrementally", fake_update_records_incrementally)
    monkeypatch.setattr(cli, "crawl_resources", fake_crawl_resources)
    monkeypatch.setattr(cli, "write_dataset", fake_write_dataset)

    result = CliRunner().invoke(
        cli.app,
        ["crawl", "--output", str(output), "--max-pages", "3", "--no-download-links", "--no-csv-copy"],
    )

    assert result.exit_code == 0
    assert calls["read_path"] == output
    assert calls["incremental_records"] == existing
    assert calls["written_records"] == updated
    assert calls["written_path"] == output
    assert "crawl_config" not in calls
    config = calls["incremental_config"]
    assert isinstance(config, IncrementalConfig)
    assert config.max_pages == 3
    assert config.download_links is False
    assert "updated records=2 new_fids=1" in result.output


def test_crawl_full_forces_fresh_crawl_when_output_exists(monkeypatch, tmp_path: Path) -> None:
    output = tmp_path / "oogc_resources.csv"
    output.touch()
    crawled = [ResourceRecord(fid="2", title="Fresh")]
    calls: dict[str, object] = {}

    def fake_read_dataset(path: Path) -> list[ResourceRecord]:
        calls["read_path"] = path
        return []

    def fake_update_records_incrementally(
        records: list[ResourceRecord], config: IncrementalConfig
    ) -> IncrementalResult:
        calls["incremental_records"] = records
        calls["incremental_config"] = config
        return IncrementalResult([], 0, 0, 0, 0)

    def fake_crawl_resources(config: CrawlConfig) -> list[ResourceRecord]:
        calls["crawl_config"] = config
        return crawled

    def fake_write_dataset(records: list[ResourceRecord], path: Path) -> Path:
        calls["written_records"] = records
        calls["written_path"] = path
        return path

    monkeypatch.setattr(cli, "read_dataset", fake_read_dataset)
    monkeypatch.setattr(cli, "update_records_incrementally", fake_update_records_incrementally)
    monkeypatch.setattr(cli, "crawl_resources", fake_crawl_resources)
    monkeypatch.setattr(cli, "write_dataset", fake_write_dataset)

    result = CliRunner().invoke(cli.app, ["crawl", "--output", str(output), "--full", "--no-csv-copy"])

    assert result.exit_code == 0
    assert "read_path" not in calls
    assert "incremental_records" not in calls
    assert calls["written_records"] == crawled
    assert calls["written_path"] == output
    config = calls["crawl_config"]
    assert isinstance(config, CrawlConfig)
    assert result.output == f"wrote 1 records to {output}\n"
