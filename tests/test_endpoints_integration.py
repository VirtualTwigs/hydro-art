"""Offline integration tests for the four endpoint orchestrators (Epoch 20, #83).

Higher-level companion to ``tests/test_endpoints.py``: instead of exercising each
function in isolation, these drive the whole :func:`src.endpoints.dispatch_endpoint`
orchestrator end-of-path for every endpoint. The injected renderer behaves like a real
one — it writes REAL bytes to ``tmp_path`` for each planned filename, hashes them with
``hashlib.sha256``, and returns ``{filename: sha256}`` — so the full
``endpoint_plan -> renderer seam -> coverage check -> endpoint_manifest -> EndpointResult``
chain runs. Still fully offline: fakes + ``tmp_path`` only, no GDAL/network/datasets.
"""

from __future__ import annotations

import hashlib
import json

import pytest

from src.endpoints import (
    ENDPOINT_CONTRACTS,
    EndpointError,
    EndpointRequest,
    EndpointResult,
    build_endpoint_request,
    dispatch_endpoint,
)
from src.fulfillment import ORDER_STYLES, StyleSpec

# endpoint -> the extra request fields its contract requires.
ENDPOINT_EXTRAS = {
    "digital_image": {},
    "animation": {"year": 2015},
    "print_image": {"size": "18x24"},
    "report": {"huc": "17080003"},
}


def _payload(endpoint, **over):
    base = {
        "request_id": "REQ-INT-1",
        "region": "Washington",
        "county": "Wahkiakum",
        "endpoint": endpoint,
        "style": "neon-basin",
    }
    base.update(ENDPOINT_EXTRAS[endpoint])
    base.update(over)
    return base


def _disk_renderer(out_dir):
    """A realistic fake: write deterministic bytes per planned file, return sha256s."""

    def renderer(request, plan):
        out_dir.mkdir(parents=True, exist_ok=True)
        checksums = {}
        for d in plan.items:
            path = out_dir / d.filename
            payload = f"{request.endpoint}:{d.filename}".encode()
            path.write_bytes(payload)
            checksums[d.filename] = hashlib.sha256(path.read_bytes()).hexdigest()
        return checksums

    return renderer


@pytest.mark.parametrize("endpoint", list(ENDPOINT_CONTRACTS))
def test_endpoint_orchestrator_matches_contract(endpoint, tmp_path):
    req = build_endpoint_request(_payload(endpoint))
    result = dispatch_endpoint(req, renderers={endpoint: _disk_renderer(tmp_path)})

    assert isinstance(result, EndpointResult)
    assert result.ok and result.endpoint == endpoint

    contract = ENDPOINT_CONTRACTS[endpoint]
    # plan formats/kinds follow the contract, in canonical order.
    assert [d.fmt for d in result.plan.items] == list(contract.format_names)
    assert [d.kind for d in result.plan.items] == [
        contract.kind_for(f) for f in contract.format_names
    ]

    # manifest carries schema/endpoint/attribution + the real per-file sha256s.
    m = result.manifest
    assert m["schema"] == "hydro-art/endpoint-manifest@1"
    assert m["endpoint"] == endpoint
    assert m["attribution"]
    manifest_sums = {d["filename"]: d["sha256"] for d in m["deliverables"]}
    for d in result.plan.items:
        on_disk = hashlib.sha256((tmp_path / d.filename).read_bytes()).hexdigest()
        assert manifest_sums[d.filename] == on_disk


@pytest.mark.parametrize("endpoint", list(ENDPOINT_CONTRACTS))
def test_endpoint_orchestrator_is_byte_identical(endpoint, tmp_path):
    req = build_endpoint_request(_payload(endpoint))
    r1 = dispatch_endpoint(req, renderers={endpoint: _disk_renderer(tmp_path / "a")})
    r2 = dispatch_endpoint(req, renderers={endpoint: _disk_renderer(tmp_path / "b")})
    assert [d.filename for d in r1.plan.items] == [d.filename for d in r2.plan.items]
    assert json.dumps(r1.manifest, sort_keys=True) == json.dumps(
        r2.manifest, sort_keys=True
    )


def test_print_endpoint_carries_pixel_dims(tmp_path):
    req = build_endpoint_request(_payload("print_image", size="18x24", formats=["png"]))
    result = dispatch_endpoint(req, renderers={"print_image": _disk_renderer(tmp_path)})
    png = next(d for d in result.plan.items if d.fmt == "png")
    assert (png.width_px, png.height_px) == (18 * 300, 24 * 300)


def test_rights_gate_precedes_renderer_at_integration(tmp_path):
    styles = dict(ORDER_STYLES)
    styles["prism-x"] = StyleSpec(
        color_by="elevation", width_by="flow", glow=True,
        renderer="mono", uses_prism=True,
    )
    req = EndpointRequest(
        request_id="REQ-INT-9", region="Washington", county="Wahkiakum",
        endpoint="digital_image", style="prism-x",
        formats=ENDPOINT_CONTRACTS["digital_image"].format_names,
    )
    with pytest.raises(EndpointError):
        dispatch_endpoint(
            req, renderers={"digital_image": _disk_renderer(tmp_path)}, styles=styles
        )
    # renderer never ran -> no artifact bytes on disk.
    assert not list(tmp_path.iterdir())
