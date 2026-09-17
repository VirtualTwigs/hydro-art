"""Tests for order-fulfillment tooling (roadmap #56-#57, Epoch 11.5).

Fully offline and deterministic: the module under test imports only stdlib +
``src.config`` (for ``SUPPORTED_REGIONS``). Payloads are hand-built dicts; no
datasets, GDAL, or network. Injectable ``styles=`` / ``sizes=`` catalogs let the
Rights-gate guard be exercised with a fabricated PRISM-using style.
"""

from __future__ import annotations

import copy
import json

import pytest

from src.fulfillment import (
    ADD_ONS,
    DEFAULT_SOURCES,
    ORDER_STYLES,
    PRINT_FORMATS,
    SIZES,
    DataSource,
    Order,
    OrderError,
    StyleSpec,
    assert_sellable,
    attribution_line,
    build_order,
    deliverable_plan,
    fulfillment_manifest,
    title_block,
)


def _payload(**over):
    base = {
        "order_id": "ORD-1001",
        "region": "Washington",
        "county": "Clark",
        "style": "neon-basin",
        "size": "18x24",
        "formats": ["png", "pdf"],
        "add_ons": [],
        "title": None,
        "subtitle": None,
    }
    base.update(over)
    return base


# --- Group 1: order model & validation ------------------------------------

@pytest.mark.parametrize("region", ["Oregon", "Washington", "California", "Idaho"])
def test_build_order_accepts_supported_regions(region):
    order = build_order(_payload(region=region))
    assert isinstance(order, Order)
    assert order.region == region
    assert order.formats == ("png", "pdf")
    assert isinstance(order.formats, tuple)
    assert isinstance(order.add_ons, tuple)


def test_build_order_rejects_unsupported_region():
    with pytest.raises(OrderError):
        build_order(_payload(region="Atlantis"))


@pytest.mark.parametrize(
    "over",
    [
        {"county": "   "},
        {"county": ""},
        {"order_id": ""},
        {"formats": []},
        {"formats": ["gif"]},
        {"style": "no-such-style"},
        {"size": "99x99"},
        {"add_ons": ["poster-frame"]},
    ],
)
def test_build_order_rejects_bad_fields(over):
    with pytest.raises(OrderError):
        build_order(_payload(**over))


def test_title_and_subtitle_are_capped_and_stripped():
    order = build_order(_payload(title="  " + "T" * 200 + "  ", subtitle="S" * 200))
    assert len(order.title) <= 60
    assert not order.title.startswith(" ")
    assert len(order.subtitle) <= 80


def test_absent_title_subtitle_are_none():
    order = build_order(_payload())
    assert order.title is None
    assert order.subtitle is None


def test_build_order_does_not_mutate_payload_and_order_is_frozen():
    payload = _payload(formats=["png"], add_ons=["svg"])
    snapshot = copy.deepcopy(payload)
    order = build_order(payload)
    assert payload == snapshot  # no mutation of caller's dict
    with pytest.raises(AttributeError):
        order.region = "Oregon"  # frozen dataclass


def test_rights_gate_blocks_prism_style():
    prism_styles = {
        "prism-anim": StyleSpec(
            color_by="watershed",
            width_by="flow",
            glow=True,
            renderer="mono",
            uses_prism=True,
        )
    }
    payload = _payload(style="prism-anim")
    with pytest.raises(OrderError):
        build_order(payload, styles=prism_styles)
    # and the direct guard on an order whose style maps to a PRISM spec
    order = Order(
        order_id="ORD-X", region="Washington", county="Clark", style="prism-anim",
        size="18x24", formats=("png",), add_ons=(),
    )
    with pytest.raises(OrderError):
        assert_sellable(order, styles=prism_styles)


def test_catalogs_are_sane():
    assert set(PRINT_FORMATS) == {"png", "pdf"}
    assert set(ADD_ONS) == {"svg", "commercial_license"}
    assert "neon-basin" in ORDER_STYLES and "elevation-tint" in ORDER_STYLES
    assert all(not s.uses_prism for s in ORDER_STYLES.values())
    assert "18x24" in SIZES
    assert all(isinstance(s, DataSource) for s in DEFAULT_SOURCES)


# --- Group 2: title block & attribution -----------------------------------

def test_attribution_line_default_is_deterministic_and_nonempty():
    line = attribution_line()
    assert line
    assert line == attribution_line(DEFAULT_SOURCES)  # default == explicit

    def render(s):
        return f"{s.name} v{s.version}" if s.version else s.name

    expected = " · ".join(render(s) for s in sorted(DEFAULT_SOURCES, key=lambda s: s.name))
    assert line == expected


def test_attribution_line_versioned_and_order_stable():
    a = DataSource("USGS WBD", version="2024")
    b = DataSource("USGS NHD", version=None)
    line1 = attribution_line((a, b))
    line2 = attribution_line((b, a))  # shuffled input
    assert line1 == line2  # sort-stable
    assert "USGS WBD v2024" in line1
    assert "USGS NHD" in line1 and "USGS NHD v" not in line1  # no version -> bare name


def test_title_block_uses_explicit_text_collapsed_and_capped():
    order = build_order(_payload(title="  Clark   Rivers  ", subtitle="  My  Sub  "))
    tb = title_block(order)
    assert tb["title"] == "Clark Rivers"  # whitespace collapsed
    assert tb["subtitle"] == "My Sub"
    assert tb["credit"] == attribution_line()


def test_title_block_defaults_from_county_and_region():
    tb = title_block(build_order(_payload(title=None, subtitle=None)))
    assert "Clark" in tb["title"]
    assert "Washington" in tb["subtitle"]
    # deterministic
    assert tb == title_block(build_order(_payload(title=None, subtitle=None)))


# --- Group 3: deliverable plan --------------------------------------------

def test_plan_print_items_have_correct_px_and_deterministic_names():
    plan = deliverable_plan(build_order(_payload(formats=["png", "pdf"], size="18x24")))
    prints = [d for d in plan.items if d.fmt in ("png", "pdf")]
    assert len(prints) == 2
    for d in prints:
        assert (d.width_px, d.height_px) == (5400, 7200)
    # deterministic filenames, stable across a re-plan
    plan2 = deliverable_plan(build_order(_payload(formats=["png", "pdf"], size="18x24")))
    assert [d.filename for d in plan.items] == [d.filename for d in plan2.items]
    assert plan.includes_editable_svg is False
    assert plan.requires_license_doc is False


def test_svg_addon_adds_editable_vector():
    plan = deliverable_plan(build_order(_payload(add_ons=["svg"])))
    assert plan.includes_editable_svg is True
    assert any(d.fmt == "svg" for d in plan.items)


def test_license_addon_adds_license_doc():
    plan = deliverable_plan(build_order(_payload(add_ons=["commercial_license"])))
    assert plan.requires_license_doc is True
    assert any(d.kind == "license" for d in plan.items)


def test_plan_is_addon_order_independent():
    a = deliverable_plan(build_order(_payload(add_ons=["svg", "commercial_license"])))
    b = deliverable_plan(build_order(_payload(add_ons=["commercial_license", "svg"])))
    assert [d.filename for d in a.items] == [d.filename for d in b.items]


# --- Group 4: fulfillment manifest ----------------------------------------

def _checksums_for(plan, value="00"):
    return {d.filename: value * 32 for d in plan.items}


def test_manifest_carries_order_titleblock_attribution_and_checksums():
    order = build_order(_payload(add_ons=["svg"]))
    plan = deliverable_plan(order)
    cks = _checksums_for(plan)
    m = fulfillment_manifest(order, plan, checksums=cks)
    assert m["order"]["order_id"] == "ORD-1001"
    assert m["title_block"]["credit"] == attribution_line()
    assert m["attribution"] == attribution_line()
    assert {s["name"] for s in m["sources"]} == {s.name for s in DEFAULT_SOURCES}
    got = {d["filename"]: d["sha256"] for d in m["deliverables"]}
    assert got == cks


def test_manifest_is_byte_identical_for_equal_inputs():
    order = build_order(_payload())
    plan = deliverable_plan(order)
    cks = _checksums_for(plan)
    j1 = json.dumps(fulfillment_manifest(order, plan, checksums=cks), sort_keys=True)
    j2 = json.dumps(fulfillment_manifest(order, plan, checksums=cks), sort_keys=True)
    assert j1 == j2


def test_manifest_rejects_checksum_coverage_mismatch():
    order = build_order(_payload())
    plan = deliverable_plan(order)
    missing = _checksums_for(plan)
    missing.pop(plan.items[0].filename)  # drop one -> incomplete
    with pytest.raises(OrderError):
        fulfillment_manifest(order, plan, checksums=missing)
    extra = _checksums_for(plan)
    extra["stranger.png"] = "ab" * 32  # not in the plan
    with pytest.raises(OrderError):
        fulfillment_manifest(order, plan, checksums=extra)
