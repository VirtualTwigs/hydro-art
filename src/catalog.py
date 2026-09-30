"""Gallery catalog management — operational inventory layer (Epoch 33, #146–#153).

Tracks rendered artworks through a status lifecycle (draft → review → published →
archived/rejected), supports versioning on re-render, structured gallery sections,
and deterministic JSON persistence. The operator CLI lives in ``tools/catalog.py``;
this module is pure domain logic.

Pure and offline: imports only stdlib + :mod:`src.config` (``SUPPORTED_REGIONS``),
:mod:`src.fulfillment` (``ORDER_STYLES``), and :mod:`src.endpoints` (``ENDPOINTS``).
No GDAL / PIL / network / datasets. Nothing enters ``PIPELINE_STAGES``.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from src.config import SUPPORTED_REGIONS
from src.endpoints import ENDPOINTS
from src.fulfillment import ORDER_STYLES

__all__ = [
    "CATALOG_SCHEMA",
    "DEFAULT_SECTIONS",
    "ENTRY_STATUSES",
    "STATUS_TRANSITIONS",
    "CatalogEntry",
    "CatalogError",
    "CatalogStore",
    "GallerySection",
    "artwork_key",
    "build_entry_id",
    "public_entries",
    "public_gallery",
    "seed_from_gallery_matrix",
    "validate_entry",
]

CATALOG_SCHEMA = "hydro-art/catalog@1"
PUBLIC_SCHEMA = "hydro-art/catalog-public@1"

ENTRY_STATUSES: tuple[str, ...] = (
    "draft",
    "review",
    "published",
    "archived",
    "rejected",
)

STATUS_TRANSITIONS: dict[str, frozenset[str]] = {
    "draft": frozenset({"review", "rejected"}),
    "review": frozenset({"published", "rejected"}),
    "published": frozenset({"archived"}),
    "archived": frozenset({"published"}),
    "rejected": frozenset(),
}


class CatalogError(Exception):
    """Raised for invalid catalog operations."""


# ---------------------------------------------------------------------------
# Value objects
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CatalogEntry:
    """One artwork in the operator's inventory."""

    entry_id: str
    version: int

    # Render identity (the "same artwork" key)
    region: str
    county: str | None
    style: str
    endpoint: str
    size: str | None

    # Provenance
    rendered_at: str
    render_hash: str
    sources: tuple[str, ...]

    # Operator decisions
    status: str

    # Display metadata
    title: str
    description: str
    tags: tuple[str, ...]
    section: str | None
    sort_order: int

    # Files
    deliverables: tuple[str, ...]
    thumbnail: str | None


@dataclass(frozen=True)
class GallerySection:
    """A named section in the public gallery."""

    section_id: str
    display_name: str
    sort_order: int
    description: str


DEFAULT_SECTIONS: tuple[GallerySection, ...] = (
    GallerySection("featured", "Featured", 0, "Our best work, front and center."),
    GallerySection("by-region", "By Region", 10, "Explore river art by state."),
    GallerySection("seasonal", "Seasonal", 20, "Seasonal and time-limited editions."),
    GallerySection("limited-edition", "Limited Edition", 30, "Exclusive numbered runs."),
)


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------

def artwork_key(entry: CatalogEntry) -> tuple[str, str | None, str, str, str | None]:
    """The 5-tuple that identifies 'the same artwork' across versions."""
    return (entry.region, entry.county, entry.style, entry.endpoint, entry.size)


def build_entry_id(
    region: str,
    county: str | None,
    style: str,
    endpoint: str,
    size: str | None,
) -> str:
    """Deterministic slug from render identity."""
    parts = [region.lower().replace(" ", "-")]
    if county:
        parts.append(county.lower().replace(" ", "-"))
    parts.append(style)
    parts.append(endpoint.replace("_", "-"))
    if size:
        parts.append(size)
    return "-".join(parts)


def validate_entry(entry: CatalogEntry) -> None:
    """Validate a catalog entry against known allowlists. Raises CatalogError."""
    if entry.region not in SUPPORTED_REGIONS:
        raise CatalogError(
            f"Unknown region {entry.region!r}. "
            f"Valid: {', '.join(SUPPORTED_REGIONS[:5])}…"
        )
    if entry.style not in ORDER_STYLES:
        raise CatalogError(
            f"Unknown style {entry.style!r}. "
            f"Valid: {', '.join(ORDER_STYLES)}."
        )
    if entry.endpoint not in ENDPOINTS:
        raise CatalogError(
            f"Unknown endpoint {entry.endpoint!r}. "
            f"Valid: {', '.join(ENDPOINTS)}."
        )
    if entry.status not in ENTRY_STATUSES:
        raise CatalogError(
            f"Unknown status {entry.status!r}. "
            f"Valid: {', '.join(ENTRY_STATUSES)}."
        )


# ---------------------------------------------------------------------------
# CatalogStore
# ---------------------------------------------------------------------------

def _entry_sort_key(e: CatalogEntry) -> tuple:
    return (e.entry_id, -e.version)


def _entry_to_dict(entry: CatalogEntry) -> dict[str, Any]:
    d = asdict(entry)
    # Convert tuples to lists for JSON
    d["sources"] = list(entry.sources)
    d["tags"] = list(entry.tags)
    d["deliverables"] = list(entry.deliverables)
    return d


def _entry_from_dict(d: dict[str, Any]) -> CatalogEntry:
    d = dict(d)
    d["sources"] = tuple(d["sources"])
    d["tags"] = tuple(d["tags"])
    d["deliverables"] = tuple(d["deliverables"])
    return CatalogEntry(**d)


def _section_to_dict(s: GallerySection) -> dict[str, Any]:
    return asdict(s)


def _section_from_dict(d: dict[str, Any]) -> GallerySection:
    return GallerySection(**d)


class CatalogStore:
    """JSON-file-backed catalog with status lifecycle and versioning."""

    def __init__(self, sections: tuple[GallerySection, ...] | None = None) -> None:
        self._entries: dict[tuple[str, int], CatalogEntry] = {}
        self._sections: list[GallerySection] = list(sections or ())

    # -- CRUD ---------------------------------------------------------------

    def add(self, entry: CatalogEntry, *, auto_archive_prior: bool = False) -> None:
        """Add an entry. Raises CatalogError if (entry_id, version) already exists."""
        key = (entry.entry_id, entry.version)
        if key in self._entries:
            raise CatalogError(
                f"Entry {entry.entry_id!r} v{entry.version} already exists."
            )
        if auto_archive_prior:
            ak = artwork_key(entry)
            for existing in list(self._entries.values()):
                if artwork_key(existing) == ak and existing.status == "published":
                    self._entries[(existing.entry_id, existing.version)] = CatalogEntry(
                        **{**existing.__dict__, "status": "archived"}
                    )
        self._entries[key] = entry

    def get(self, entry_id: str, version: int) -> CatalogEntry:
        """Retrieve by (entry_id, version). Raises CatalogError if not found."""
        key = (entry_id, version)
        if key not in self._entries:
            raise CatalogError(f"Entry {entry_id!r} v{version} not found.")
        return self._entries[key]

    def list_entries(
        self,
        *,
        status: str | None = None,
        region: str | None = None,
        section: str | None = None,
        tag: str | None = None,
    ) -> list[CatalogEntry]:
        """List entries with optional filters."""
        result = list(self._entries.values())
        if status is not None:
            result = [e for e in result if e.status == status]
        if region is not None:
            result = [e for e in result if e.region == region]
        if section is not None:
            result = [e for e in result if e.section == section]
        if tag is not None:
            result = [e for e in result if tag in e.tags]
        result.sort(key=_entry_sort_key)
        return result

    # -- Transitions --------------------------------------------------------

    def transition(self, entry_id: str, version: int, to_status: str) -> None:
        """Move an entry to a new status. Raises CatalogError on invalid transition."""
        entry = self.get(entry_id, version)
        allowed = STATUS_TRANSITIONS.get(entry.status, frozenset())
        if to_status not in allowed:
            raise CatalogError(
                f"Invalid transition {entry.status!r} → {to_status!r}. "
                f"Allowed: {', '.join(sorted(allowed)) or '(none — terminal)'}."
            )
        updated = CatalogEntry(**{**entry.__dict__, "status": to_status})
        self._entries[(entry_id, version)] = updated

    # -- Versioning ---------------------------------------------------------

    def next_version(self, entry: CatalogEntry) -> int:
        """Return the next version number for this artwork key."""
        ak = artwork_key(entry)
        versions = [
            e.version for e in self._entries.values() if artwork_key(e) == ak
        ]
        return max(versions, default=0) + 1

    # -- Persistence --------------------------------------------------------

    def save(self, path: Path) -> None:
        """Write the catalog to a JSON file (deterministic)."""
        entries = sorted(self._entries.values(), key=_entry_sort_key)
        sections = sorted(self._sections, key=lambda s: s.sort_order)
        data = {
            "schema": CATALOG_SCHEMA,
            "sections": [_section_to_dict(s) for s in sections],
            "entries": [_entry_to_dict(e) for e in entries],
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")

    @classmethod
    def load(cls, path: Path) -> CatalogStore:
        """Load a catalog from a JSON file."""
        data = json.loads(path.read_text())
        sections = tuple(_section_from_dict(d) for d in data.get("sections", []))
        store = cls(sections=sections)
        for d in data.get("entries", []):
            store.add(_entry_from_dict(d))
        return store


# ---------------------------------------------------------------------------
# Public gallery export
# ---------------------------------------------------------------------------

def public_entries(store: CatalogStore) -> list[CatalogEntry]:
    """Return the latest published version of each artwork."""
    published = store.list_entries(status="published")
    best: dict[tuple, CatalogEntry] = {}
    for e in published:
        ak = artwork_key(e)
        if ak not in best or e.version > best[ak].version:
            best[ak] = e
    return sorted(best.values(), key=_entry_sort_key)


def public_gallery(store: CatalogStore) -> dict[str, Any]:
    """Build the structured public gallery export."""
    entries = public_entries(store)
    section_map: dict[str, list[dict]] = {}
    for e in entries:
        sid = e.section or "uncategorized"
        section_map.setdefault(sid, []).append(_entry_to_dict(e))

    # Sort entries within each section
    for entries_list in section_map.values():
        entries_list.sort(key=lambda d: (d["sort_order"], d["entry_id"]))

    # Build section output
    known_sections = {s.section_id: s for s in store._sections}
    sections_out = []
    for sid in sorted(section_map, key=lambda s: known_sections.get(s, GallerySection(s, s, 999, "")).sort_order):
        sec = known_sections.get(sid)
        sections_out.append({
            "section_id": sid,
            "display_name": sec.display_name if sec else sid.replace("-", " ").title(),
            "sort_order": sec.sort_order if sec else 999,
            "description": sec.description if sec else "",
            "entries": section_map[sid],
        })

    return {
        "schema": PUBLIC_SCHEMA,
        "sections": sections_out,
    }


# ---------------------------------------------------------------------------
# Seed from GALLERY_MATRIX
# ---------------------------------------------------------------------------

def seed_from_gallery_matrix(store: CatalogStore) -> None:
    """Import existing GALLERY_MATRIX selections as draft catalog entries."""
    from src.gallery import GALLERY_MATRIX

    existing_ids = {e.entry_id for e in store.list_entries()}
    for sel in GALLERY_MATRIX:
        if sel.item_id in existing_ids:
            continue
        entry = CatalogEntry(
            entry_id=sel.item_id,
            version=1,
            region=sel.region,
            county=sel.county,
            style=sel.style,
            endpoint=sel.endpoint,
            size=sel.size,
            rendered_at="",
            render_hash="",
            sources=(),
            status="draft",
            title=sel.rationale.split("—")[0].strip() if "—" in sel.rationale else sel.rationale,
            description=sel.rationale,
            tags=(),
            section=None,
            sort_order=0,
            deliverables=(),
            thumbnail=None,
        )
        store.add(entry)
