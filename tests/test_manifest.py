"""Tests for the portable cache manifest facility (roadmap #21, offline slice).

Offline and deterministic. Uses a real :class:`src.cache.Cache` in ``tmp_path``
(stdlib-only) plus hand-written archive files, so no network / GDAL / NAS is
touched. The module under test imports only stdlib + src.datasets/config/cache.
"""

from __future__ import annotations

import pytest

from src.cache import Cache
from src.config import build_settings
from src.datasets import FileDescriptor, resolve_required_files
from src.manifest import (
    CacheManifest,
    ManifestEntry,
    ManifestError,
    build_manifest,
    diff_manifests,
    manifest_for_settings,
    manifest_from_dict,
    manifest_to_dict,
    read_manifest,
    verify_manifest,
    write_manifest,
)


def _descriptor(dataset_id="nhdplus_hr", huc4="1708", filename="a.zip"):
    return FileDescriptor(
        dataset_id=dataset_id,
        huc4=huc4,
        filename=filename,
        url=f"https://example.test/{filename}",
    )


def _cache_with(tmp_path, *descriptors, payload=b"hydro"):
    """Build a Cache and record a payload file for each descriptor."""
    cache = Cache(tmp_path / "cache")
    for d in descriptors:
        path = cache.path_for(d)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
        cache.record(d)
    return cache


# ---- build_manifest ----------------------------------------------------------

def test_build_manifest_from_recorded_cache(tmp_path):
    d = _descriptor()
    cache = _cache_with(tmp_path, d)
    m = build_manifest(cache, [d])
    assert isinstance(m, CacheManifest)
    assert len(m.entries) == 1
    e = m.entries[0]
    assert e.key == d.key
    assert e.dataset_id == "nhdplus_hr" and e.huc4 == "1708"
    assert e.url == d.url
    assert e.size == len(b"hydro")
    assert e.relative_path == "nhdplus_hr/1708/a.zip"
    # checksum is the recorded sha256 of the payload
    assert e.checksum == cache.metadata(d)["checksum"]


def test_build_manifest_skips_unrecorded_but_strict_raises(tmp_path):
    recorded = _descriptor(filename="a.zip")
    missing = _descriptor(filename="b.zip")
    cache = _cache_with(tmp_path, recorded)  # only 'recorded' is in the index
    m = build_manifest(cache, [recorded, missing])
    assert [e.key for e in m.entries] == [recorded.key]
    with pytest.raises(ManifestError):
        build_manifest(cache, [recorded, missing], strict=True)


def test_build_manifest_entries_sorted_by_key(tmp_path):
    a = _descriptor(dataset_id="wbd", huc4="17", filename="z.zip")
    b = _descriptor(dataset_id="nhdplus_hr", huc4="1708", filename="a.zip")
    cache = _cache_with(tmp_path, a, b)
    m = build_manifest(cache, [a, b])  # inserted a-before-b
    assert [e.key for e in m.entries] == sorted([a.key, b.key])


# ---- (de)serialization -------------------------------------------------------

def test_dict_round_trip(tmp_path):
    d = _descriptor()
    m = build_manifest(_cache_with(tmp_path, d), [d])
    assert manifest_from_dict(manifest_to_dict(m)) == m


def test_write_read_round_trip(tmp_path):
    d = _descriptor()
    m = build_manifest(_cache_with(tmp_path, d), [d])
    out = tmp_path / "manifest.json"
    write_manifest(m, out)
    assert read_manifest(out) == m


def test_write_is_deterministic_and_order_independent(tmp_path):
    a = _descriptor(dataset_id="wbd", huc4="17", filename="z.zip")
    b = _descriptor(dataset_id="nhdplus_hr", huc4="1708", filename="a.zip")
    cache = _cache_with(tmp_path, a, b)
    m1 = build_manifest(cache, [a, b])
    m2 = build_manifest(cache, [b, a])  # reversed insertion order
    p1, p2 = tmp_path / "m1.json", tmp_path / "m2.json"
    write_manifest(m1, p1)
    write_manifest(m2, p2)
    assert p1.read_bytes() == p2.read_bytes()


def test_from_dict_malformed_raises():
    with pytest.raises(ManifestError):
        manifest_from_dict({"version": "1", "entries": "not-a-list"})
    with pytest.raises(ManifestError):
        manifest_from_dict({"version": "1", "entries": [{"key": "x"}]})  # missing fields


# ---- manifest_for_settings ---------------------------------------------------

def test_manifest_for_settings_covers_resolved_descriptors(tmp_path):
    settings = build_settings({"region": ["Oregon", "Washington"]})
    descriptors = resolve_required_files(settings)
    cache = _cache_with(tmp_path, *descriptors)
    m = manifest_for_settings(cache, settings)
    assert {e.key for e in m.entries} == {d.key for d in descriptors}


# ---- verify_manifest ---------------------------------------------------------

def test_verify_all_ok(tmp_path):
    d = _descriptor()
    cache = _cache_with(tmp_path, d)
    m = build_manifest(cache, [d])
    v = verify_manifest(m, cache.root)
    assert v.ok == (d.key,)
    assert v.missing == () and v.mismatched == ()
    assert v.is_complete is True


def test_verify_reports_missing_file(tmp_path):
    d = _descriptor()
    cache = _cache_with(tmp_path, d)
    m = build_manifest(cache, [d])
    cache.path_for(d).unlink()  # remove the cached file
    v = verify_manifest(m, cache.root)
    assert v.missing == (d.key,)
    assert v.is_complete is False


def test_verify_reports_mismatch_on_corruption(tmp_path):
    d = _descriptor()
    cache = _cache_with(tmp_path, d, payload=b"hydro")
    m = build_manifest(cache, [d])
    # same size, different bytes
    cache.path_for(d).write_bytes(b"HYDRO")
    v = verify_manifest(m, cache.root)
    assert v.mismatched == (d.key,)
    assert v.is_complete is False
    # different size (truncated) is also a mismatch
    cache.path_for(d).write_bytes(b"hy")
    assert verify_manifest(m, cache.root).mismatched == (d.key,)


# ---- diff_manifests ----------------------------------------------------------

def test_diff_classifies_added_removed_changed_unchanged(tmp_path):
    a = _descriptor(filename="a.zip")
    b = _descriptor(filename="b.zip")
    c = _descriptor(filename="c.zip")
    # old has a (v1), b (v1); new has a (v1, unchanged), b (v2, changed), c (added)
    old_cache = _cache_with(tmp_path / "old", a, b, payload=b"v1")
    old = build_manifest(old_cache, [a, b])
    new_cache = Cache(tmp_path / "new" / "cache")
    for desc, payload in ((a, b"v1"), (b, b"v2-changed"), (c, b"v1")):
        p = new_cache.path_for(desc)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(payload)
        new_cache.record(desc)
    new = build_manifest(new_cache, [a, b, c])

    diff = diff_manifests(old, new)
    assert diff.added == (c.key,)
    assert diff.removed == ()
    assert diff.changed == (b.key,)
    assert diff.unchanged == (a.key,)
    assert diff.is_synced is False


def test_diff_synced_when_identical(tmp_path):
    d = _descriptor()
    m = build_manifest(_cache_with(tmp_path, d), [d])
    diff = diff_manifests(m, m)
    assert diff.is_synced is True
    assert diff.unchanged == (d.key,)
