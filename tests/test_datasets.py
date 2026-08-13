"""Tests for the dataset registry and resolution (Item #2, Task Group 1)."""

from src.config import build_settings
from src.datasets import (
    DATASETS,
    REGION_HUC4,
    Dataset,
    resolve_required_files,
)


def _settings(*regions):
    return build_settings({"region": list(regions)})


def test_registry_priority_order_and_primary():
    priorities = [d.priority for d in DATASETS]
    assert priorities == sorted(priorities)
    primary = min(DATASETS, key=lambda d: d.priority)
    assert primary.id == "nhdplus_hr"
    assert primary.required is True


def test_only_required_datasets_are_resolved():
    files = resolve_required_files(_settings("Oregon"))
    dataset_ids = {f.dataset_id for f in files}
    required_ids = {d.id for d in DATASETS if d.required}
    assert dataset_ids == required_ids
    assert "nhd" not in dataset_ids  # fallback, not required


def test_region_resolves_expected_huc4s():
    files = resolve_required_files(_settings("Oregon"))
    hucs = {f.huc4 for f in files if f.dataset_id == "nhdplus_hr"}
    assert hucs == set(REGION_HUC4["Oregon"])


def test_idaho_resolves_region17_basins():
    files = resolve_required_files(_settings("Idaho"))
    nhd = {f.huc4 for f in files if f.dataset_id == "nhdplus_hr"}
    assert nhd == {"1701", "1704", "1705", "1706"}
    assert nhd == set(REGION_HUC4["Idaho"])
    # Every Idaho basin is in HU2 region 17, so WBD collapses to one archive.
    assert {f.huc4 for f in files if f.dataset_id == "wbd"} == {"17"}


def test_wbd_resolves_to_deduplicated_hu2():
    files = resolve_required_files(_settings("Oregon"))
    wbd = [f for f in files if f.dataset_id == "wbd"]
    # Oregon's HUC4s span HU2 regions 17 and 18; WBD is distributed per HU2,
    # so the six HUC4 codes collapse to two archives.
    assert {f.huc4 for f in wbd} == {"17", "18"}
    for f in wbd:
        assert "/WBD/HU2/GDB/" in f.url
        assert f.url.endswith(f"WBD_{f.huc4}_HU2_GDB.zip")
        assert f.filename == f"WBD_{f.huc4}_HU2_GDB.zip"


def test_shared_huc4_is_deduplicated_across_regions():
    files = resolve_required_files(_settings("Oregon", "Washington"))
    keys = [f.key for f in files]
    assert len(keys) == len(set(keys))  # no duplicate files
    # 1708 and 1710 are shared; each appears once per required dataset.
    nhd_1708 = [f for f in files if f.huc4 == "1708" and f.dataset_id == "nhdplus_hr"]
    assert len(nhd_1708) == 1


def test_descriptor_url_and_filename_are_derived():
    files = resolve_required_files(_settings("Washington"))
    sample = next(f for f in files if f.dataset_id == "nhdplus_hr")
    assert sample.url.endswith(f"NHDPLUS_H_{sample.huc4}_HU4_GDB.zip")
    assert sample.filename == f"NHDPLUS_H_{sample.huc4}_HU4_GDB.zip"
