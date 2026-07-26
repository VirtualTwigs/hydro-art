"""Dataset registry and region -> required-file resolution.

USGS distributes NHDPlus HR, NHD, and the Watershed Boundary Dataset (WBD) as
per-HUC4 archives. This module declares the supported datasets and the HUC4
codes covering each region, and resolves the concrete list of archive files a
given :class:`~src.config.Settings` needs.

The registry and the region->HUC4 map are the single extension points: adding
a region or dataset means editing the data here, not the resolution logic.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.config import Settings

__all__ = [
    "AcquisitionError",
    "Dataset",
    "FileDescriptor",
    "DATASETS",
    "REGION_HUC4",
    "resolve_required_files",
]


class AcquisitionError(Exception):
    """Raised when datasets cannot be resolved, downloaded, or extracted.

    The message is intended to be shown directly to the user.
    """


@dataclass(frozen=True)
class Dataset:
    """A public hydrography dataset source.

    Attributes:
        id: Short stable identifier (used in cache keys and paths).
        name: Human-readable name.
        priority: Lower numbers are higher priority (1 = primary source).
        url_template: URL with a ``{huc4}`` placeholder for the archive.
        required: Whether this dataset is fetched by default. Fallback and
            optional sources are declared but not required this release.
    """

    id: str
    name: str
    priority: int
    url_template: str
    required: bool


#: Supported datasets in priority order (PRD section 5.2). URLs point at the
#: USGS The National Map staged-products S3 bucket.
DATASETS: tuple[Dataset, ...] = (
    Dataset(
        id="nhdplus_hr",
        name="USGS NHDPlus HR",
        priority=1,
        url_template=(
            "https://prd-tnm.s3.amazonaws.com/StagedProducts/Hydrography/"
            "NHDPlusHR/Beta/GDB/NHDPLUS_H_{huc4}_HU4_GDB.zip"
        ),
        required=True,
    ),
    Dataset(
        id="wbd",
        name="Watershed Boundary Dataset",
        priority=2,
        url_template=(
            "https://prd-tnm.s3.amazonaws.com/StagedProducts/Hydrography/"
            "WBD/HU4/GDB/WBD_{huc4}_HU4_GDB.zip"
        ),
        required=True,
    ),
    Dataset(
        id="nhd",
        name="USGS National Hydrography Dataset",
        priority=3,
        url_template=(
            "https://prd-tnm.s3.amazonaws.com/StagedProducts/Hydrography/"
            "NHD/HU4/HighResolution/GDB/NHD_H_{huc4}_HU4_GDB.zip"
        ),
        required=False,  # fallback for NHDPlus HR
    ),
    # Optional global sources, declared for completeness (not fetched here).
    Dataset(
        id="hydrosheds",
        name="HydroSHEDS",
        priority=4,
        url_template="",
        required=False,
    ),
    Dataset(
        id="merit_hydro",
        name="MERIT Hydro",
        priority=5,
        url_template="",
        required=False,
    ),
)

#: HUC4 subregions covering each supported region. Curated for the initial
#: release; approximate at region borders and intended to be edited here as
#: coverage is refined. Shared codes (e.g. 1708/1710 span OR and WA) are
#: deduplicated during resolution.
REGION_HUC4: dict[str, tuple[str, ...]] = {
    "Oregon": ("1707", "1708", "1709", "1710", "1712", "1801"),
    "Washington": ("1701", "1702", "1703", "1708", "1710", "1711"),
}


@dataclass(frozen=True)
class FileDescriptor:
    """A single archive file required for a run.

    Attributes:
        dataset_id: The owning :class:`Dataset` id.
        huc4: The HUC4 code this archive covers.
        filename: Basename of the archive (derived from the URL).
        url: Fully resolved download URL.
        expected_sha256: Known checksum, if the registry provides one.
    """

    dataset_id: str
    huc4: str
    filename: str
    url: str
    expected_sha256: str | None = None

    @property
    def key(self) -> str:
        """Stable cache/dedup key for this file."""
        return f"{self.dataset_id}/{self.huc4}/{self.filename}"


def _dataset(dataset_id: str) -> Dataset:
    for ds in DATASETS:
        if ds.id == dataset_id:
            return ds
    raise AcquisitionError(f"Unknown dataset id: {dataset_id!r}.")


def resolve_required_files(settings: Settings) -> tuple[FileDescriptor, ...]:
    """Resolve the archive files needed for ``settings``.

    Iterates the required datasets over the HUC4 codes covering the configured
    regions, deduplicating files shared across regions.

    Raises:
        AcquisitionError: If a region has no known HUC4 mapping.
    """
    seen: dict[str, FileDescriptor] = {}
    for region in settings.regions:
        huc4s = REGION_HUC4.get(region)
        if not huc4s:
            raise AcquisitionError(
                f"No HUC4 mapping for region {region!r}; add it to REGION_HUC4."
            )
        for ds in DATASETS:
            if not ds.required:
                continue
            for huc4 in huc4s:
                url = ds.url_template.format(huc4=huc4)
                filename = url.rsplit("/", 1)[-1]
                descriptor = FileDescriptor(
                    dataset_id=ds.id,
                    huc4=huc4,
                    filename=filename,
                    url=url,
                )
                seen.setdefault(descriptor.key, descriptor)
    return tuple(seen.values())
