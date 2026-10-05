"""Tests for tools/import_legacy.py — legacy data import (offline, fake repository).

All tests use a fake OrderRepository and in-memory data structures.
No database, no filesystem, no network.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

# ---------------------------------------------------------------------------
# Import the tool module (it's under tools/, outside the package)
# ---------------------------------------------------------------------------

TOOL_PATH = Path(__file__).resolve().parent.parent / "tools" / "import_legacy.py"


def _load_tool():
    """Import tools/import_legacy.py as a module."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("import_legacy", TOOL_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Fake repository
# ---------------------------------------------------------------------------


class FakeRepository:
    """Minimal OrderRepository fake for import testing."""

    def __init__(self):
        self.requests: dict[str, dict] = {}
        self.assets: dict[str, dict] = {}
        self.events: list[dict] = []

    def create_request(self, payload: dict[str, Any]) -> Any:
        rid = payload.get("order_id", payload.get("request_id", ""))
        self.requests[rid] = payload
        return type("Req", (), {"request_id": rid, "to_dict": lambda s: payload})()

    def get(self, request_id: str) -> Any:
        if request_id not in self.requests:
            raise KeyError(request_id)
        p = self.requests[request_id]
        return type("Req", (), {"request_id": request_id, "to_dict": lambda s: p})()

    def list_all(self) -> list:
        return list(self.requests.values())

    def record_asset(self, asset) -> None:
        self.assets[asset.asset_id] = asset

    def add_event(self, request_id, event, detail=None):
        self.events.append({"request_id": request_id, "event": event, "detail": detail})

    def update_status(self, request_id, new_status):
        if request_id in self.requests:
            self.requests[request_id]["status"] = new_status

    def set_job_id(self, request_id, job_id):
        if request_id in self.requests:
            self.requests[request_id]["job_id"] = job_id

    def add_note(self, request_id, note):
        self.events.append({"request_id": request_id, "event": "note", "detail": note})


# ---------------------------------------------------------------------------
# Sample data builders
# ---------------------------------------------------------------------------


def _sample_request_json(request_id="REQ-20260901-0001"):
    return {
        "request_id": request_id,
        "status": "fulfilled",
        "email": "customer@example.com",
        "product": "neon-basin 18x24",
        "created_at": "2026-09-01T00:00:00Z",
        "updated_at": "2026-09-01T12:00:00Z",
        "order": {
            "region": "Washington",
            "county": "Clark",
            "style": "neon-basin",
            "size": "18x24",
            "formats": ["png"],
        },
        "events": [
            {"timestamp": "2026-09-01T00:00:00Z", "event": "submitted", "detail": {}},
        ],
        "notes": [],
    }


def _sample_manifest(order_id="REQ-20260901-0001"):
    return {
        "schema": "hydro-art/fulfillment-manifest@1",
        "order": {
            "order_id": order_id,
            "region": "Washington",
            "county": "Clark",
            "style": "neon-basin",
            "size": "18x24",
            "formats": ["png"],
            "add_ons": [],
        },
        "attribution": "USGS NHD · USGS NHDPlus HR · USGS WBD",
        "deliverables": [
            {
                "filename": f"{order_id}_washington-clark_neon-basin_18x24.png",
                "kind": "print",
                "fmt": "png",
                "sha256": "abc123deadbeef",
                "width_px": 5400,
                "height_px": 7200,
            },
        ],
    }


def _sample_catalog_entry(entry_id="wa-clark-neon-basin-county-print-18x24"):
    return {
        "entry_id": entry_id,
        "version": 1,
        "region": "Washington",
        "county": "Clark",
        "style": "neon-basin",
        "endpoint": "county_print",
        "size": "18x24",
        "rendered_at": "2026-09-01T00:00:00Z",
        "render_hash": "abc123",
        "sources": ["USGS NHDPlus HR"],
        "status": "draft",
        "title": "Clark County Watersheds",
        "description": "Neon river art",
        "tags": ["washington", "clark"],
        "section": "by-region",
        "sort_order": 0,
        "deliverables": ["clark.png"],
        "thumbnail": None,
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestToolSyntax:
    def test_tool_file_exists(self):
        assert TOOL_PATH.is_file()

    def test_tool_is_syntactically_valid(self):
        source = TOOL_PATH.read_text("utf-8")
        compile(source, str(TOOL_PATH), "exec")


class TestImportRequests:
    def test_imports_request_json(self):
        """import_requests creates a ledger record from a Request JSON."""
        mod = _load_tool()
        repo = FakeRepository()
        req = _sample_request_json()
        result = mod.import_request(repo, req, dry_run=False)
        assert result["action"] == "created"
        assert "REQ-20260901-0001" in repo.requests

    def test_dry_run_no_mutations(self):
        """Dry-run mode produces counts without creating records."""
        mod = _load_tool()
        repo = FakeRepository()
        req = _sample_request_json()
        result = mod.import_request(repo, req, dry_run=True)
        assert result["action"] == "would_create"
        assert len(repo.requests) == 0

    def test_idempotent_reimport(self):
        """Re-importing the same request produces a skip, not a duplicate."""
        mod = _load_tool()
        repo = FakeRepository()
        req = _sample_request_json()
        mod.import_request(repo, req, dry_run=False)
        result = mod.import_request(repo, req, dry_run=False)
        assert result["action"] == "skipped"


class TestImportAssets:
    def test_imports_manifest_assets(self):
        """import_manifest_assets creates Asset records from a manifest."""
        mod = _load_tool()
        repo = FakeRepository()
        manifest = _sample_manifest()
        result = mod.import_manifest_assets(repo, manifest, dry_run=False)
        assert result["created"] >= 1
        assert len(repo.assets) >= 1

    def test_dry_run_no_asset_mutations(self):
        mod = _load_tool()
        repo = FakeRepository()
        manifest = _sample_manifest()
        result = mod.import_manifest_assets(repo, manifest, dry_run=True)
        assert result["would_create"] >= 1
        assert len(repo.assets) == 0


class TestRightsGate:
    def test_refuses_public_without_cleared_rights(self):
        """Cannot set approved_public visibility without rights_status=cleared."""
        mod = _load_tool()
        repo = FakeRepository()
        manifest = _sample_manifest()
        # Try to force public visibility
        with pytest.raises(mod.ImportError):
            mod.import_manifest_assets(
                repo, manifest, dry_run=False,
                force_visibility="approved_public",
                force_rights_status="pending",
            )


class TestCatalogImport:
    def test_imports_catalog_entry(self):
        """import_catalog_entry creates asset record from CatalogStore entry."""
        mod = _load_tool()
        repo = FakeRepository()
        entry = _sample_catalog_entry()
        result = mod.import_catalog_entry(repo, entry, dry_run=False)
        assert result["action"] in ("created", "skipped")
