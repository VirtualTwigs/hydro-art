"""Flagship end-to-end proof — one region, one path, all four endpoints (Epoch 21).

Fully offline: builds four requests from a shared base (Washington/Wahkiakum/neon-basin),
dispatches each through the real ``src.endpoints.dispatch_endpoint`` with a fake renderer
that writes real bytes to ``tmp_path`` and hashes them, and aggregates via
``combined_manifest`` — proving the four endpoints on a single path with contract +
determinism assertions. No GDAL/network/datasets; the real-artifact run is the opt-in
``tools/render_all_endpoints.py`` harness (deferred to the GDAL+NAS machine).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from src.endpoints import (
    ENDPOINT_CONTRACTS,
    ENDPOINTS,
    FLAGSHIP_E2E,
    EndpointError,
    build_endpoint_request,
    combined_manifest,
    dispatch_endpoint,
    e2e_contract_digest,
    flagship_e2e_requests,
)

GOLDEN = Path(__file__).parent / "fixtures" / "golden" / "e2e" / "washington-wahkiakum.json"

# Single source of truth for the flagship path (also used by the Epoch 23 release gate).
ENDPOINT_EXTRAS = FLAGSHIP_E2E["extras"]


def _payload(endpoint, **over):
    base = {
        "request_id": FLAGSHIP_E2E["request_id"],
        "region": FLAGSHIP_E2E["region"],
        "county": FLAGSHIP_E2E["county"],
        "endpoint": endpoint,
        "style": FLAGSHIP_E2E["style"],
    }
    base.update(ENDPOINT_EXTRAS[endpoint])
    base.update(over)
    return base


def _disk_renderer(out_dir):
    def renderer(request, plan):
        out_dir.mkdir(parents=True, exist_ok=True)
        checksums = {}
        for d in plan.items:
            path = out_dir / d.filename
            path.write_bytes(f"{request.endpoint}:{d.filename}".encode())
            checksums[d.filename] = hashlib.sha256(path.read_bytes()).hexdigest()
        return checksums

    return renderer


def _all_requests():
    return flagship_e2e_requests()


def _dispatch_all(out_root):
    results = []
    for req in _all_requests():
        results.append(
            dispatch_endpoint(
                req, renderers={req.endpoint: _disk_renderer(out_root / req.endpoint)}
            )
        )
    return results


# --- Group 1: combined provenance core ------------------------------------

def test_combined_manifest_aggregates_all_four(tmp_path):
    m = combined_manifest(_dispatch_all(tmp_path))
    assert m["schema"] == "hydro-art/e2e-manifest@1"
    assert set(m["endpoints"]) == set(ENDPOINTS)
    assert m["region"] == "Washington" and m["county"] == "Wahkiakum"
    assert m["attribution"]
    # each endpoint's sub-manifest is its own per-file manifest.
    for ep in ENDPOINTS:
        assert m["endpoints"][ep]["endpoint"] == ep


def test_combined_manifest_is_byte_identical(tmp_path):
    m1 = combined_manifest(_dispatch_all(tmp_path / "a"))
    # reversed result order must not change the serialized bytes.
    m2 = combined_manifest(list(reversed(_dispatch_all(tmp_path / "b"))))
    assert json.dumps(m1, sort_keys=True) == json.dumps(m2, sort_keys=True)


def test_combined_manifest_rejects_inconsistent_identity(tmp_path):
    results = _dispatch_all(tmp_path)
    odd = dispatch_endpoint(
        build_endpoint_request(_payload("digital_image", county="Clark")),
        renderers={"digital_image": _disk_renderer(tmp_path / "odd")},
    )
    with pytest.raises(EndpointError):
        combined_manifest(results[1:] + [odd])  # two digital_image + mismatched county


def test_e2e_contract_digest_is_render_independent_and_byte_identical():
    d1 = e2e_contract_digest(_all_requests())
    d2 = e2e_contract_digest(list(reversed(_all_requests())))
    assert d1["schema"] == "hydro-art/e2e-contract@1"
    assert set(d1["endpoints"]) == set(ENDPOINTS)
    # no checksums in the render-independent skeleton.
    blob = json.dumps(d1)
    assert "sha256" not in blob
    assert json.dumps(d1, sort_keys=True) == json.dumps(d2, sort_keys=True)
    # each endpoint lists its contract formats.
    for ep in ENDPOINTS:
        fmts = [d["fmt"] for d in d1["endpoints"][ep]]
        assert fmts == list(ENDPOINT_CONTRACTS[ep].format_names)


# --- Group 2: flagship single-flow e2e (#85) ------------------------------

def test_one_flow_proves_all_four_endpoints(tmp_path):
    """The headline: one region walked to every endpoint, contract + determinism."""
    results = _dispatch_all(tmp_path / "run1")

    # every endpoint ran and satisfied its contract.
    assert {r.endpoint for r in results} == set(ENDPOINTS)
    for r in results:
        assert r.ok
        contract = ENDPOINT_CONTRACTS[r.endpoint]
        assert [d.fmt for d in r.plan.items] == list(contract.format_names)

    manifest = combined_manifest(results)
    # combined manifest carries every planned deliverable for every endpoint.
    for r in results:
        delivered = {d["filename"] for d in manifest["endpoints"][r.endpoint]["deliverables"]}
        assert delivered == {d.filename for d in r.plan.items}
    assert manifest["attribution"]

    # whole-flow determinism: an independent second walk is byte-identical.
    manifest2 = combined_manifest(_dispatch_all(tmp_path / "run2"))
    assert json.dumps(manifest, sort_keys=True) == json.dumps(manifest2, sort_keys=True)


# --- Group 4: e2e golden fixture (#87) ------------------------------------

def test_e2e_contract_digest_matches_committed_golden():
    """Regression-guard the render-independent flagship path against the golden."""
    digest = e2e_contract_digest(_all_requests())
    committed = json.loads(GOLDEN.read_text())
    assert digest == committed
