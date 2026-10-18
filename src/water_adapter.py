"""State source adapter protocol and registry helpers.

Defines the contract for state-level water-data adapters (API, bulk file,
ArcGIS service, HTML download, manual record request) and the adapter
manifest that records what was fetched, mapped, and unmapped.

Pure and offline: no database driver, no GIS, no network at module load.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol, runtime_checkable

from src.water_facility import StateSourceEntry, WaterFacilityError

__all__ = [
    "AdapterManifest",
    "StateSourceAdapter",
    "build_adapter_manifest",
    "validate_registry_entry",
]


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

_REQUIRED_STRING_FIELDS = (
    "jurisdiction",
    "program",
    "agency",
    "url",
    "coverage",
    "update_cadence",
    "license",
    "field_mapping_version",
)


def validate_registry_entry(entry: StateSourceEntry) -> bool:
    """Validate that a registry entry has all required fields populated.

    Raises :class:`WaterFacilityError` if any required string field is empty.
    Returns ``True`` on success.
    """
    for fname in _REQUIRED_STRING_FIELDS:
        val = getattr(entry, fname, "")
        if not val:
            raise WaterFacilityError(
                f"StateSourceEntry requires non-empty {fname}"
            )
    return True


# ---------------------------------------------------------------------------
# Adapter manifest
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AdapterManifest:
    """Records what an adapter fetched from one source pull."""

    jurisdiction: str
    program: str
    access_method: str
    snapshot_id: uuid.UUID
    record_count: int
    fields_mapped: tuple[str, ...]
    fields_unmapped: tuple[str, ...]
    source_url: str
    license: str
    field_mapping_version: str


def build_adapter_manifest(
    *,
    entry: StateSourceEntry,
    record_count: int,
    snapshot_id: uuid.UUID,
    fields_mapped: list[str],
    fields_unmapped: list[str],
) -> AdapterManifest:
    """Build a manifest from a registry entry and adapter pull results."""
    return AdapterManifest(
        jurisdiction=entry.jurisdiction,
        program=entry.program,
        access_method=entry.access_method,
        snapshot_id=snapshot_id,
        record_count=record_count,
        fields_mapped=tuple(fields_mapped),
        fields_unmapped=tuple(fields_unmapped),
        source_url=entry.url,
        license=entry.license,
        field_mapping_version=entry.field_mapping_version,
    )


# ---------------------------------------------------------------------------
# Adapter protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class StateSourceAdapter(Protocol):
    """Abstract adapter for fetching state-level water data."""

    def fetch(self, entry: StateSourceEntry) -> list[dict[str, Any]]:
        """Fetch raw records from the source. Returns a list of row dicts."""
        ...

    def normalize(
        self, rows: list[dict[str, Any]], *, snapshot_id: uuid.UUID
    ) -> list[Any]:
        """Normalize raw rows to the common contract."""
        ...
