"""Offline tests for src.catalog — gallery catalog management (Epoch 33)."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from src.catalog import (
    DEFAULT_SECTIONS,
    STATUS_TRANSITIONS,
    CatalogEntry,
    CatalogError,
    CatalogStore,
    GallerySection,
    artwork_key,
    build_entry_id,
    public_entries,
    public_gallery,
    seed_from_gallery_matrix,
    validate_entry,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _entry(**overrides) -> CatalogEntry:
    """Build a minimal valid CatalogEntry with overrides."""
    defaults = {
        "entry_id": "wa-clark-neon-basin-digital",
        "version": 1,
        "region": "Washington",
        "county": "Clark",
        "style": "neon-basin",
        "endpoint": "digital_image",
        "size": None,
        "rendered_at": "2026-09-29T12:00:00Z",
        "render_hash": "abc123",
        "sources": ("NHDPlus HR",),
        "status": "draft",
        "title": "Clark County Rivers",
        "description": "Neon river art of Clark County, WA",
        "tags": (),
        "section": None,
        "sort_order": 0,
        "deliverables": ("output/wa-clark.svg",),
        "thumbnail": None,
    }
    defaults.update(overrides)
    return CatalogEntry(**defaults)


def _store_with_entry(**overrides) -> tuple[CatalogStore, CatalogEntry]:
    """Return a store containing one entry."""
    store = CatalogStore()
    entry = _entry(**overrides)
    store.add(entry)
    return store, entry


# ===================================================================
# Group 1 — Data model & validation
# ===================================================================


class TestCatalogEntry:
    def test_construction(self):
        e = _entry()
        assert e.entry_id == "wa-clark-neon-basin-digital"
        assert e.version == 1
        assert e.status == "draft"

    def test_frozen(self):
        e = _entry()
        with pytest.raises(AttributeError):
            e.status = "published"  # type: ignore[misc]

    def test_artwork_key(self):
        e = _entry()
        assert artwork_key(e) == ("Washington", "Clark", "neon-basin", "digital_image", None)

    def test_artwork_key_with_size(self):
        e = _entry(endpoint="print_image", size="24x36")
        key = artwork_key(e)
        assert key == ("Washington", "Clark", "neon-basin", "print_image", "24x36")


class TestBuildEntryId:
    def test_basic(self):
        eid = build_entry_id("Washington", "Clark", "neon-basin", "digital_image", None)
        assert eid == "washington-clark-neon-basin-digital-image"

    def test_with_size(self):
        eid = build_entry_id("Washington", "Clark", "neon-basin", "print_image", "24x36")
        assert eid == "washington-clark-neon-basin-print-image-24x36"

    def test_no_county(self):
        eid = build_entry_id("Oregon", None, "elevation-tint", "digital_image", None)
        assert eid == "oregon-elevation-tint-digital-image"

    def test_deterministic(self):
        a = build_entry_id("California", "Shasta", "neon-basin", "animation", None)
        b = build_entry_id("California", "Shasta", "neon-basin", "animation", None)
        assert a == b

    def test_multi_word_region(self):
        eid = build_entry_id("New York", None, "neon-basin", "digital_image", None)
        assert eid.startswith("new-york-")


class TestGallerySection:
    def test_construction(self):
        s = GallerySection(
            section_id="featured",
            display_name="Featured",
            sort_order=0,
            description="Hero picks",
        )
        assert s.section_id == "featured"

    def test_default_sections_exist(self):
        ids = {s.section_id for s in DEFAULT_SECTIONS}
        assert "featured" in ids
        assert "by-region" in ids

    def test_default_sections_ordered(self):
        orders = [s.sort_order for s in DEFAULT_SECTIONS]
        assert orders == sorted(orders)


class TestValidateEntry:
    def test_valid_entry_passes(self):
        validate_entry(_entry())  # no exception

    def test_unknown_region_rejected(self):
        with pytest.raises(CatalogError, match="region"):
            validate_entry(_entry(region="Atlantis"))

    def test_unknown_style_rejected(self):
        with pytest.raises(CatalogError, match="style"):
            validate_entry(_entry(style="psychedelic"))

    def test_unknown_endpoint_rejected(self):
        with pytest.raises(CatalogError, match="endpoint"):
            validate_entry(_entry(endpoint="hologram"))

    def test_unknown_status_rejected(self):
        # Force via object.__setattr__ since frozen
        e = _entry()
        bad = CatalogEntry(**{**e.__dict__, "status": "magic"})
        with pytest.raises(CatalogError, match="status"):
            validate_entry(bad)


# ===================================================================
# Group 2 — CatalogStore CRUD
# ===================================================================


class TestCatalogStoreCRUD:
    def test_add_and_get(self):
        store, entry = _store_with_entry()
        assert store.get(entry.entry_id, entry.version) == entry

    def test_add_duplicate_raises(self):
        store, entry = _store_with_entry()
        with pytest.raises(CatalogError, match="already exists"):
            store.add(entry)

    def test_list_all(self):
        store = CatalogStore()
        store.add(_entry(entry_id="a", version=1))
        store.add(_entry(entry_id="b", version=1))
        assert len(store.list_entries()) == 2

    def test_list_by_status(self):
        store = CatalogStore()
        store.add(_entry(entry_id="a", version=1, status="draft"))
        store.add(_entry(entry_id="b", version=1, status="review"))
        drafts = store.list_entries(status="draft")
        assert len(drafts) == 1
        assert drafts[0].entry_id == "a"

    def test_list_by_region(self):
        store = CatalogStore()
        store.add(_entry(entry_id="a", version=1, region="Washington"))
        store.add(_entry(entry_id="b", version=1, region="Oregon"))
        wa = store.list_entries(region="Washington")
        assert len(wa) == 1

    def test_list_by_section(self):
        store = CatalogStore()
        store.add(_entry(entry_id="a", version=1, section="featured"))
        store.add(_entry(entry_id="b", version=1, section="by-region"))
        featured = store.list_entries(section="featured")
        assert len(featured) == 1

    def test_list_by_tag(self):
        store = CatalogStore()
        store.add(_entry(entry_id="a", version=1, tags=("hero", "washington")))
        store.add(_entry(entry_id="b", version=1, tags=("oregon",)))
        hero = store.list_entries(tag="hero")
        assert len(hero) == 1

    def test_json_roundtrip(self):
        store = CatalogStore()
        store.add(_entry(entry_id="a", version=1))
        store.add(_entry(entry_id="b", version=1, region="Oregon"))
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "catalog.json"
            store.save(path)
            loaded = CatalogStore.load(path)
        assert len(loaded.list_entries()) == 2
        assert loaded.get("a", 1) == store.get("a", 1)

    def test_json_deterministic(self):
        store = CatalogStore()
        store.add(_entry(entry_id="b", version=1))
        store.add(_entry(entry_id="a", version=1))
        with tempfile.TemporaryDirectory() as td:
            p1 = Path(td) / "c1.json"
            p2 = Path(td) / "c2.json"
            store.save(p1)
            store.save(p2)
            assert p1.read_text() == p2.read_text()


# ===================================================================
# Group 3 — Status transitions
# ===================================================================


class TestStatusTransitions:
    def test_draft_to_review(self):
        store, entry = _store_with_entry(status="draft")
        store.transition(entry.entry_id, entry.version, "review")
        assert store.get(entry.entry_id, entry.version).status == "review"

    def test_review_to_published(self):
        store, entry = _store_with_entry(status="review")
        store.transition(entry.entry_id, entry.version, "published")
        assert store.get(entry.entry_id, entry.version).status == "published"

    def test_published_to_archived(self):
        store, entry = _store_with_entry(status="published")
        store.transition(entry.entry_id, entry.version, "archived")
        assert store.get(entry.entry_id, entry.version).status == "archived"

    def test_archived_to_published(self):
        store, entry = _store_with_entry(status="archived")
        store.transition(entry.entry_id, entry.version, "published")
        assert store.get(entry.entry_id, entry.version).status == "published"

    def test_invalid_transition_raises(self):
        store, entry = _store_with_entry(status="draft")
        with pytest.raises(CatalogError, match="transition"):
            store.transition(entry.entry_id, entry.version, "published")

    def test_rejected_is_terminal(self):
        store, entry = _store_with_entry(status="rejected")
        with pytest.raises(CatalogError, match="transition"):
            store.transition(entry.entry_id, entry.version, "draft")

    def test_all_valid_transitions(self):
        """Every declared transition succeeds."""
        for from_status, to_set in STATUS_TRANSITIONS.items():
            for to_status in to_set:
                store, entry = _store_with_entry(status=from_status)
                store.transition(entry.entry_id, entry.version, to_status)
                assert store.get(entry.entry_id, entry.version).status == to_status


# ===================================================================
# Group 4 — Versioning
# ===================================================================


class TestVersioning:
    def test_first_version(self):
        store = CatalogStore()
        assert store.next_version(_entry()) == 1

    def test_increments(self):
        store = CatalogStore()
        store.add(_entry(version=1))
        assert store.next_version(_entry()) == 2

    def test_public_entries_latest_published(self):
        store = CatalogStore()
        store.add(_entry(version=1, status="archived"))
        store.add(_entry(version=2, status="published"))
        store.add(_entry(version=3, status="draft"))
        pub = public_entries(store)
        assert len(pub) == 1
        assert pub[0].version == 2

    def test_auto_archive_prior_on_version_add(self):
        store = CatalogStore()
        e1 = _entry(version=1, status="published")
        store.add(e1)
        e2 = _entry(version=2, status="draft")
        store.add(e2, auto_archive_prior=True)
        assert store.get(e1.entry_id, 1).status == "archived"


# ===================================================================
# Group 5 — Public export
# ===================================================================


class TestPublicExport:
    def test_groups_by_section(self):
        store = CatalogStore(sections=DEFAULT_SECTIONS)
        store.add(_entry(entry_id="a", version=1, status="published", section="featured"))
        store.add(_entry(entry_id="b", version=1, status="published", section="by-region", region="Oregon"))
        gallery = public_gallery(store)
        section_ids = [s["section_id"] for s in gallery["sections"]]
        assert "featured" in section_ids
        assert "by-region" in section_ids

    def test_sections_ordered(self):
        store = CatalogStore(sections=DEFAULT_SECTIONS)
        store.add(_entry(entry_id="a", version=1, status="published", section="by-region", region="Oregon"))
        store.add(_entry(entry_id="b", version=1, status="published", section="featured"))
        gallery = public_gallery(store)
        orders = [s["sort_order"] for s in gallery["sections"] if s["entries"]]
        assert orders == sorted(orders)

    def test_entries_ordered_within_section(self):
        store = CatalogStore(sections=DEFAULT_SECTIONS)
        store.add(_entry(entry_id="b", version=1, status="published", section="featured", sort_order=2))
        store.add(_entry(entry_id="a", version=1, status="published", section="featured", sort_order=1, region="Oregon"))
        gallery = public_gallery(store)
        featured = next(s for s in gallery["sections"] if s["section_id"] == "featured")
        ids = [e["entry_id"] for e in featured["entries"]]
        assert ids == ["a", "b"]

    def test_non_published_excluded(self):
        store = CatalogStore(sections=DEFAULT_SECTIONS)
        store.add(_entry(entry_id="a", version=1, status="draft", section="featured"))
        store.add(_entry(entry_id="b", version=1, status="published", section="featured", region="Oregon"))
        gallery = public_gallery(store)
        featured = next(s for s in gallery["sections"] if s["section_id"] == "featured")
        assert len(featured["entries"]) == 1
        assert featured["entries"][0]["entry_id"] == "b"

    def test_schema_field(self):
        store = CatalogStore(sections=DEFAULT_SECTIONS)
        gallery = public_gallery(store)
        assert gallery["schema"] == "hydro-art/catalog-public@1"

    def test_empty_catalog_valid_structure(self):
        store = CatalogStore(sections=DEFAULT_SECTIONS)
        gallery = public_gallery(store)
        assert "sections" in gallery
        assert "schema" in gallery
        assert isinstance(gallery["sections"], list)

    def test_export_json_deterministic(self):
        store = CatalogStore(sections=DEFAULT_SECTIONS)
        store.add(_entry(entry_id="b", version=1, status="published", section="featured", region="Oregon"))
        store.add(_entry(entry_id="a", version=1, status="published", section="featured"))
        g1 = json.dumps(public_gallery(store), sort_keys=True)
        g2 = json.dumps(public_gallery(store), sort_keys=True)
        assert g1 == g2


# ===================================================================
# Group 6 — Seed from GALLERY_MATRIX
# ===================================================================


class TestSeedFromGalleryMatrix:
    def test_seeds_all_items(self):
        from src.gallery import GALLERY_MATRIX
        store = CatalogStore()
        seed_from_gallery_matrix(store)
        assert len(store.list_entries()) == len(GALLERY_MATRIX)

    def test_seeded_status_is_draft(self):
        store = CatalogStore()
        seed_from_gallery_matrix(store)
        for entry in store.list_entries():
            assert entry.status == "draft"

    def test_seeded_preserves_item_id(self):
        from src.gallery import GALLERY_MATRIX
        store = CatalogStore()
        seed_from_gallery_matrix(store)
        entry_ids = {e.entry_id for e in store.list_entries()}
        gallery_ids = {s.item_id for s in GALLERY_MATRIX}
        assert gallery_ids == entry_ids

    def test_idempotent(self):
        store = CatalogStore()
        seed_from_gallery_matrix(store)
        count = len(store.list_entries())
        seed_from_gallery_matrix(store)  # second call should skip
        assert len(store.list_entries()) == count
