"""Dataset registry and region -> required-file resolution.

USGS distributes NHDPlus HR and NHD as per-HU4 archives and the Watershed
Boundary Dataset (WBD) as per-HU2 archives. This module declares the supported
datasets and the HUC4 codes covering each region, and resolves the concrete
list of archive files a given :class:`~src.config.Settings` needs (truncating
each HUC4 to the dataset's own granularity via ``Dataset.code_digits``).

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
        url_template: URL with a ``{code}`` placeholder for the archive's HUC
            unit (see ``code_digits``).
        required: Whether this dataset is fetched by default. Fallback and
            optional sources are declared but not required this release.
        code_digits: Number of leading HUC4 digits identifying this dataset's
            distribution unit: 4 for per-HU4 archives (NHDPlus HR, NHD), 2 for
            per-HU2 archives (WBD).
    """

    id: str
    name: str
    priority: int
    url_template: str
    required: bool
    code_digits: int = 4


#: Supported datasets in priority order (PRD section 5.2). URLs point at the
#: USGS The National Map staged-products S3 bucket.
DATASETS: tuple[Dataset, ...] = (
    Dataset(
        id="nhdplus_hr",
        name="USGS NHDPlus HR",
        priority=1,
        url_template=(
            "https://prd-tnm.s3.amazonaws.com/StagedProducts/Hydrography/"
            "NHDPlusHR/Beta/GDB/NHDPLUS_H_{code}_HU4_GDB.zip"
        ),
        required=True,
    ),
    Dataset(
        id="wbd",
        name="Watershed Boundary Dataset",
        priority=2,
        # USGS distributes WBD per 2-digit HU2, not per HU4.
        url_template=(
            "https://prd-tnm.s3.amazonaws.com/StagedProducts/Hydrography/"
            "WBD/HU2/GDB/WBD_{code}_HU2_GDB.zip"
        ),
        required=True,
        code_digits=2,
    ),
    Dataset(
        id="nhd",
        name="USGS National Hydrography Dataset",
        priority=3,
        url_template=(
            "https://prd-tnm.s3.amazonaws.com/StagedProducts/Hydrography/"
            "NHD/HU4/HighResolution/GDB/NHD_H_{code}_HU4_GDB.zip"
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
    # California: HU2 region 18 is the California hydrologic region (all of
    # 1801-1810 tag CA in WBD's ``states`` attribute); 1710/1712 are the region-17
    # OR/CA border basins. Derived from ``tools/derive_state_huc4.py`` against local
    # WBD. The far-eastern desert fringes in HU2 15 (Lower Colorado) / 16 (Great
    # Basin) are omitted pending those archives; re-run the deriver with the
    # national WBD GDB to add them if needed.
    "California": (
        "1710", "1712",
        "1801", "1802", "1803", "1804", "1805",
        "1806", "1807", "1808", "1809", "1810",
    ),
    # Idaho: the Snake River system + panhandle, all in HU2 region 17. Derived
    # from local WBD via ``tools/derive_state_huc4.py Idaho --min-overlap-frac
    # 0.01``: 1701 (panhandle), 1704 (Upper Snake), 1705 (Middle Snake), 1706
    # (Salmon/Clearwater/Lower Snake). The far-SE Bear River corner is in HU2 15
    # (Lower Colorado) / 16 (Great Basin) and is omitted pending those archives —
    # re-run the deriver with the national WBD GDB to add them if needed.
    "Idaho": ("1701", "1704", "1705", "1706"),
}


@dataclass(frozen=True)
class FileDescriptor:
    """A single archive file required for a run.

    Attributes:
        dataset_id: The owning :class:`Dataset` id.
        huc4: The HUC unit code this archive covers, at the dataset's own
            granularity (HU4 for NHDPlus HR/NHD, HU2 for WBD).
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
                code = huc4[: ds.code_digits]
                url = ds.url_template.format(code=code)
                filename = url.rsplit("/", 1)[-1]
                descriptor = FileDescriptor(
                    dataset_id=ds.id,
                    huc4=code,
                    filename=filename,
                    url=url,
                )
                seen.setdefault(descriptor.key, descriptor)
    return tuple(seen.values())
