"""Tests for the production endpoint-contract layer (Epoch 19, #79-81).

Fully offline and deterministic: ``src.endpoints`` imports only stdlib +
``src.config`` + ``src.fulfillment``. Payloads are hand-built dicts; renderers are
injected fakes. No datasets, GDAL, numpy, or network.
"""

from __future__ import annotations

import copy
import json

import pytest

from src.endpoints import (
    ENDPOINT_CONTRACTS,
    ENDPOINTS,
    EndpointContract,
    EndpointError,
    EndpointRequest,
    EndpointResult,
    assert_sellable,
    build_endpoint_request,
    dispatch_endpoint,
    endpoint_manifest,
    endpoint_plan,
)
from src.fulfillment import ORDER_STYLES, StyleSpec


def _payload(**over):
    base = {
        "request_id": "REQ-1001",
        "region": "Washington",
        "county": "Wahkiakum",
        "endpoint": "digital_image",
        "style": "neon-basin",
    }
    base.update(over)
    return base


# --- Group 1: contracts + request validation ------------------------------

def test_all_four_endpoints_have_contracts():
    assert set(ENDPOINTS) == {"digital_image", "animation", "print_image", "report"}
    assert set(ENDPOINT_CONTRACTS) == set(ENDPOINTS)
    for name, c in ENDPOINT_CONTRACTS.items():
        assert isinstance(c, EndpointContract)
        assert c.endpoint == name
        assert c.format_names  # non-empty
        assert c.deliverable_kinds  # non-empty
        assert c.stem_suffix


@pytest.mark.parametrize(
    "endpoint,extra",
    [
        ("digital_image", {}),
        ("animation", {"year": 2015}),
        ("print_image", {"size": "18x24"}),
        ("report", {"huc": "17080003"}),
    ],
)
def test_build_accepts_valid_request_per_endpoint(endpoint, extra):
    req = build_endpoint_request(_payload(endpoint=endpoint, **extra))
    assert isinstance(req, EndpointRequest)
    assert req.endpoint == endpoint
    # formats default to the full contract set when unspecified
    assert req.formats == ENDPOINT_CONTRACTS[endpoint].format_names


@pytest.mark.parametrize(
    "over,frag",
    [
        ({"request_id": ""}, "request_id"),
        ({"region": "Atlantis"}, "region"),
        ({"endpoint": "hologram"}, "endpoint"),
        ({"style": "made-up"}, "style"),
        ({"endpoint": "digital_image", "formats": ["gif"]}, "format"),
        ({"endpoint": "print_image"}, "size"),  # print requires size
        ({"endpoint": "report"}, "huc"),  # report requires huc
        ({"endpoint": "animation"}, "year"),  # animation requires year/months
    ],
)
def test_build_rejects_invalid_request(over, frag):
    with pytest.raises(EndpointError) as exc:
        build_endpoint_request(_payload(**over))
    assert frag in str(exc.value).lower()


def test_build_does_not_mutate_payload():
    p = _payload(endpoint="print_image", size="18x24", formats=["png"])
    before = copy.deepcopy(p)
    build_endpoint_request(p)
    assert p == before


# --- Group 2: plan + manifest + rights gate -------------------------------

def test_plan_is_deterministic_and_order_independent():
    a = endpoint_plan(build_endpoint_request(_payload(formats=["png", "svg"])))
    b = endpoint_plan(build_endpoint_request(_payload(formats=["svg", "png"])))
    assert [d.filename for d in a.items] == [d.filename for d in b.items]
    # digital_image yields one vector (svg) + one raster (png)
    kinds = {d.kind for d in a.items}
    assert {"vector", "raster"} <= kinds


def test_print_plan_carries_pixel_dims():
    req = build_endpoint_request(
        _payload(endpoint="print_image", size="18x24", formats=["png"])
    )
    plan = endpoint_plan(req)
    png = next(d for d in plan.items if d.fmt == "png")
    assert (png.width_px, png.height_px) == (18 * 300, 24 * 300)


def test_manifest_versioned_and_byte_identical():
    req = build_endpoint_request(_payload(formats=["svg", "png"]))
    plan = endpoint_plan(req)
    checksums = {d.filename: "0" * 64 for d in plan.items}
    m1 = endpoint_manifest(req, plan, checksums=checksums)
    m2 = endpoint_manifest(req, plan, checksums=dict(reversed(list(checksums.items()))))
    assert m1["schema"] == "hydro-art/endpoint-manifest@1"
    assert m1["endpoint"] == "digital_image"
    assert m1.get("attribution")
    assert json.dumps(m1, sort_keys=True) == json.dumps(m2, sort_keys=True)


def test_manifest_enforces_exact_checksum_coverage():
    req = build_endpoint_request(_payload(formats=["svg", "png"]))
    plan = endpoint_plan(req)
    with pytest.raises(EndpointError):
        endpoint_manifest(req, plan, checksums={plan.items[0].filename: "0" * 64})


def test_rights_gate_refuses_prism_style():
    styles = dict(ORDER_STYLES)
    styles["prism-x"] = StyleSpec(
        color_by="elevation", width_by="flow", glow=True,
        renderer="mono", uses_prism=True,
    )
    req = EndpointRequest(
        request_id="REQ-9", region="Washington", county="Wahkiakum",
        endpoint="digital_image", style="prism-x",
        formats=ENDPOINT_CONTRACTS["digital_image"].format_names,
    )
    with pytest.raises(EndpointError):
        assert_sellable(req, styles=styles)


# --- Group 3: dispatch seam -----------------------------------------------

def _sha_renderer(request, plan):
    """A fake renderer: returns a checksum for every planned file."""
    return {d.filename: f"{i:064d}" for i, d in enumerate(plan.items)}


def test_dispatch_routes_to_correct_renderer():
    called = {}

    def make(tag):
        def r(request, plan):
            called["tag"] = tag
            return _sha_renderer(request, plan)
        return r

    renderers = {ep: make(ep) for ep in ENDPOINTS}
    req = build_endpoint_request(_payload(endpoint="report", huc="17080003"))
    result = dispatch_endpoint(req, renderers=renderers)
    assert isinstance(result, EndpointResult)
    assert result.ok and result.endpoint == "report"
    assert called["tag"] == "report"
    assert result.manifest["endpoint"] == "report"


def test_dispatch_runs_rights_gate_before_renderer():
    styles = dict(ORDER_STYLES)
    styles["prism-x"] = StyleSpec(
        color_by="elevation", width_by="flow", glow=True,
        renderer="mono", uses_prism=True,
    )
    calls = []

    def recording(request, plan):
        calls.append(request.endpoint)
        return _sha_renderer(request, plan)

    req = EndpointRequest(
        request_id="REQ-9", region="Washington", county="Wahkiakum",
        endpoint="digital_image", style="prism-x",
        formats=ENDPOINT_CONTRACTS["digital_image"].format_names,
    )
    with pytest.raises(EndpointError):
        dispatch_endpoint(req, renderers={"digital_image": recording}, styles=styles)
    assert calls == []  # renderer never called


def test_dispatch_enforces_checksum_coverage():
    def short_renderer(request, plan):
        return {plan.items[0].filename: "0" * 64}  # misses the rest

    req = build_endpoint_request(_payload(formats=["svg", "png"]))
    with pytest.raises(EndpointError):
        dispatch_endpoint(req, renderers={"digital_image": short_renderer})


# --- Group 4: gap-filling gate --------------------------------------------

def test_every_contract_round_trips_build_plan_manifest():
    extras = {
        "digital_image": {},
        "animation": {"year": 2015},
        "print_image": {"size": "12x16"},
        "report": {"huc": "17080003"},
    }
    for endpoint in ENDPOINTS:
        req = build_endpoint_request(_payload(endpoint=endpoint, **extras[endpoint]))
        plan = endpoint_plan(req)
        checksums = {d.filename: "0" * 64 for d in plan.items}
        m = endpoint_manifest(req, plan, checksums=checksums)
        assert m["endpoint"] == endpoint
        # stems are filesystem-safe (no spaces) and deterministic
        for d in plan.items:
            assert " " not in d.filename
        assert plan.items == endpoint_plan(req).items


# --- Group 5: CONUS region support (Item #111) ----------------------------

def test_conus_request_accepted_without_county():
    """CONUS region accepts None/empty county — no county clip for continental."""
    req = build_endpoint_request(_payload(region="CONUS", county=None))
    assert isinstance(req, EndpointRequest)
    assert req.region == "CONUS"
    assert req.county == ""


def test_supported_state_accepts_empty_county():
    """Supported states accept county=None for state-level renders."""
    req = build_endpoint_request(_payload(region="Oregon", county=None))
    assert isinstance(req, EndpointRequest)
    assert req.region == "Oregon"
    assert req.county == ""


def test_state_level_stem_has_no_double_dash():
    """State-level request stem is clean (no empty county segment)."""
    req = build_endpoint_request(_payload(region="Oregon", county=None))
    plan = endpoint_plan(req)
    for d in plan.items:
        assert "--" not in d.filename
        assert "oregon" in d.filename.lower()


def test_conus_stem_has_no_double_dash():
    """The filename stem for a CONUS request is clean (no empty county segment)."""
    req = build_endpoint_request(_payload(region="CONUS", county=None))
    plan = endpoint_plan(req)
    for d in plan.items:
        assert "--" not in d.filename
        assert "conus" in d.filename.lower()


def test_conus_request_passes_rights_gate():
    """CONUS + neon-basin is public domain — sellable."""
    req = build_endpoint_request(_payload(region="CONUS", county=None))
    assert_sellable(req)


# --- Coverage gap: kind_for KeyError (line 96) --------------------------------

def test_kind_for_unknown_format_raises():
    """EndpointContract.kind_for raises KeyError for unknown format."""
    contract = next(iter(ENDPOINT_CONTRACTS.values()))
    with pytest.raises(KeyError):
        contract.kind_for("nonexistent_format")


# --- Coverage gap: dispatch_endpoint unknown renderer (line 340) --------------

def test_dispatch_no_renderer_raises():
    """dispatch_endpoint raises when no renderer registered."""
    req = build_endpoint_request(_payload())
    with pytest.raises(EndpointError, match="No renderer"):
        dispatch_endpoint(req, renderers={})  # empty registry


# --- Coverage gap: combined_manifest edge cases (lines 378, 381) --------------

def test_combined_manifest_empty_raises():
    """combined_manifest with empty results raises."""
    from src.endpoints import combined_manifest

    with pytest.raises(EndpointError, match="at least one"):
        combined_manifest([])


def test_combined_manifest_duplicate_endpoint_raises():
    """combined_manifest with duplicate endpoints raises."""
    from src.endpoints import combined_manifest

    req = build_endpoint_request(_payload())
    plan = endpoint_plan(req)
    checksums = {item.filename: "abc123" * 10 + "ab" for item in plan.items}
    result = EndpointResult(
        endpoint=req.endpoint,
        plan=plan,
        manifest=endpoint_manifest(req, plan, checksums=checksums),
    )
    with pytest.raises(EndpointError, match="Duplicate"):
        combined_manifest([result, result])


# --- Coverage gap: e2e_contract_digest edge cases (lines 410, 413) ------------

def test_e2e_digest_empty_raises():
    """e2e_contract_digest with empty requests raises."""
    from src.endpoints import e2e_contract_digest

    with pytest.raises(EndpointError, match="at least one"):
        e2e_contract_digest([])


def test_e2e_digest_duplicate_endpoint_raises():
    """e2e_contract_digest with duplicate endpoints raises."""
    from src.endpoints import e2e_contract_digest

    req = build_endpoint_request(_payload())
    with pytest.raises(EndpointError, match="Duplicate"):
        e2e_contract_digest([req, req])
