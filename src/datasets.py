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
    # All HUC4 mappings derived via ``tools/derive_state_huc4.py --all --wbd-hu4
    # /Volumes/home/data/incoming/WBD_National_GDB/WBD_National_GDB.gdb
    # --min-overlap-frac 0.01`` against the national WBD GDB (2026-09-14).
    #
    # --- Northeast ---
    "Maine": ("0101", "0102", "0103", "0104", "0105", "0106"),
    "New Hampshire": ("0104", "0106", "0107", "0108"),
    "Vermont": ("0108", "0202", "0430"),
    "Massachusetts": ("0107", "0108", "0109", "0110", "0202"),
    "Rhode Island": ("0109", "0110"),
    "Connecticut": ("0108", "0110"),
    "New York": (
        "0110", "0202", "0203", "0204", "0205",
        "0412", "0413", "0414", "0427", "0429", "0430", "0501",
    ),
    "New Jersey": ("0202", "0203", "0204"),
    "Pennsylvania": (
        "0204", "0205", "0206", "0207",
        "0412", "0413", "0501", "0502", "0503",
    ),
    "Delaware": ("0204", "0206", "0208"),
    "Maryland": ("0204", "0205", "0206", "0207", "0208", "0502"),
    # --- Southeast ---
    "Virginia": ("0204", "0207", "0208", "0301", "0505", "0507", "0601"),
    "West Virginia": ("0207", "0502", "0503", "0505", "0507", "0509"),
    "North Carolina": (
        "0301", "0302", "0303", "0304", "0305", "0306",
        "0505", "0601", "0602",
    ),
    "South Carolina": ("0304", "0305", "0306"),
    "Georgia": ("0306", "0307", "0311", "0312", "0313", "0315", "0602"),
    "Florida": ("0307", "0308", "0309", "0310", "0311", "0312", "0313", "0314"),
    "Alabama": ("0313", "0314", "0315", "0316", "0317", "0602", "0603"),
    "Mississippi": (
        "0316", "0317", "0318", "0603",
        "0801", "0802", "0803", "0806", "0807",
    ),
    "Tennessee": ("0511", "0513", "0601", "0602", "0603", "0604", "0801"),
    "Kentucky": ("0507", "0509", "0510", "0511", "0513", "0514", "0604", "0801"),
    # --- Great Lakes / Midwest ---
    "Ohio": (
        "0410", "0411", "0412", "0503", "0504", "0506", "0508", "0509", "0512",
    ),
    "Indiana": ("0404", "0405", "0410", "0508", "0509", "0512", "0514", "0712"),
    "Illinois": (
        "0404", "0512", "0514", "0706", "0708",
        "0709", "0711", "0712", "0713", "0714",
    ),
    "Michigan": (
        "0401", "0402", "0403", "0404", "0405", "0406", "0407", "0408",
        "0409", "0410", "0418", "0420", "0424",
    ),
    "Wisconsin": (
        "0401", "0402", "0403", "0404",
        "0703", "0704", "0705", "0706", "0707", "0709", "0712",
    ),
    "Minnesota": (
        "0401", "0701", "0702", "0703", "0704", "0706", "0708", "0710",
        "0902", "0903", "1017", "1023",
    ),
    # --- Plains ---
    "Iowa": ("0702", "0706", "0708", "0710", "0711", "1017", "1023", "1024", "1028"),
    "Missouri": (
        "0711", "0714", "0801", "0802", "1024", "1028", "1029", "1030",
        "1101", "1107",
    ),
    "Arkansas": (
        "0801", "0802", "0803", "0804", "0805",
        "1101", "1107", "1111", "1114",
    ),
    "Louisiana": (
        "0318", "0803", "0804", "0805", "0806", "0807", "0808", "0809",
        "1114", "1201", "1204",
    ),
    "North Dakota": ("0901", "0902", "1006", "1010", "1011", "1013", "1016"),
    "South Dakota": (
        "0702", "0902", "1011", "1012", "1013", "1014", "1015", "1016", "1017",
    ),
    "Nebraska": (
        "1012", "1014", "1015", "1017", "1018", "1019", "1020", "1021",
        "1022", "1023", "1024", "1025", "1027",
    ),
    "Kansas": (
        "1024", "1025", "1026", "1027", "1029", "1030",
        "1103", "1104", "1106", "1107",
    ),
    "Oklahoma": (
        "1104", "1105", "1106", "1107", "1109", "1110",
        "1111", "1112", "1113", "1114",
    ),
    "Texas": (
        "1109", "1110", "1112", "1113", "1114",
        "1201", "1202", "1203", "1204", "1205", "1206", "1207",
        "1208", "1209", "1210", "1211",
        "1304", "1305", "1307", "1308", "1309",
    ),
    # --- Mountain ---
    "Montana": (
        "0904", "1002", "1003", "1004", "1005", "1006", "1007", "1008",
        "1009", "1010", "1011", "1701",
    ),
    "Idaho": ("1601", "1602", "1701", "1704", "1705", "1706"),
    "Wyoming": (
        "1002", "1007", "1008", "1009", "1011", "1012", "1015", "1018", "1019",
        "1404", "1405", "1601", "1704",
    ),
    "Nevada": (
        "1501", "1503", "1602", "1604", "1605", "1606",
        "1704", "1705", "1712", "1808", "1809",
    ),
    "Utah": (
        "1403", "1404", "1405", "1406", "1407", "1408",
        "1501", "1601", "1602", "1603", "1704",
    ),
    "Colorado": (
        "1018", "1019", "1025", "1026", "1102", "1103", "1104",
        "1301", "1401", "1402", "1403", "1404", "1405", "1408",
    ),
    "Arizona": (
        "1407", "1408", "1501", "1502", "1503", "1504",
        "1505", "1506", "1507", "1508",
    ),
    "New Mexico": (
        "1104", "1108", "1109", "1110", "1112", "1205", "1208",
        "1301", "1302", "1303", "1305", "1306", "1307",
        "1408", "1502", "1504",
    ),
    # --- Pacific ---
    "Oregon": (
        "1604", "1705", "1706", "1707", "1708", "1709", "1710", "1712",
        "1801", "1802",
    ),
    "Washington": ("1701", "1702", "1703", "1706", "1707", "1708", "1710", "1711"),
    "California": (
        "1503", "1605", "1606",
        "1801", "1802", "1803", "1804", "1805",
        "1806", "1807", "1808", "1809", "1810",
    ),
    "Hawaii": ("2001", "2002", "2003", "2004", "2005", "2006", "2007", "2008"),
    "Alaska": ("1901", "1902", "1903", "1905", "1906", "1907", "1908", "1909"),
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
