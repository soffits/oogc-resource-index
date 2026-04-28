from __future__ import annotations

from pathlib import Path

from oogc_resource_index.dataset import merge_records, read_dataset, write_csv_copy, write_dataset
from oogc_resource_index.models import ResourceRecord


def test_merge_records_preserves_existing_fields_and_updates_download_url() -> None:
    existing = [ResourceRecord(fid="7", title="Title", url="https://oogc.cc/item/7")]
    updates = [ResourceRecord(fid="7", downUrl="https://download.test/7")]

    merged = merge_records(existing, updates)

    assert merged == [
        ResourceRecord(
            fid="7",
            title="Title",
            url="https://oogc.cc/item/7",
            downUrl="https://download.test/7",
        )
    ]


def test_write_and_read_xlsx_and_csv_copy(tmp_path: Path) -> None:
    output = tmp_path / "resources.xlsx"
    records = [ResourceRecord(fid="10", title="Name")]

    written = write_dataset(records, output)
    csv_path = write_csv_copy(records, output)

    assert written == output
    assert output.exists()
    assert csv_path.exists()
    assert read_dataset(output) == records
    assert read_dataset(csv_path) == records
