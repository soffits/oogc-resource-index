from __future__ import annotations

from dataclasses import dataclass

from oogc_resource_index.constants import DATASET_FIELDS


@dataclass(frozen=True, slots=True)
class ResourceRecord:
    fid: str
    title: str = ""
    url: str = ""
    category: str = ""
    published_at: str = ""
    updated_at: str = ""
    size: str = ""
    downloads: str = ""
    description: str = ""
    downUrl: str = ""
    summary_status: str = ""

    def as_row(self) -> dict[str, str]:
        return {field: str(getattr(self, field, "") or "") for field in DATASET_FIELDS}

    @classmethod
    def from_row(cls, row: dict[str, object]) -> "ResourceRecord":
        values = {field: _string_value(row.get(field)) for field in DATASET_FIELDS}
        return cls(**values)


def _string_value(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()
