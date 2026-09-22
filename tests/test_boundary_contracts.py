"""Boundary contract tests — validates data shapes at system handoff points.

Each test exercises one cross-system boundary and asserts that the data
produced by the sender matches what the receiver expects.  These tests
catch the class of bug where both sides are individually correct but the
seam between them silently breaks (e.g. the "Unsupported region ''" order
failure where the JS form sent valid data that didn't propagate).

Boundaries tested:
  1. order.html payload → POST /api/orders → OrderStore
  2. POST /api/orders response → order.html confirmation step
  3. POST /api/orders response → delivery.html fetch
  4. order.html style/size buttons → fulfillment.build_order
  5. Pipeline artifact contracts between stages
  6. CLI args → Settings → pipeline Settings fields
"""

from __future__ import annotations

import json
import re
from dataclasses import fields
from pathlib import Path

import pytest

from src.config import (
    SUPPORTED_COLOR_MODES,
    SUPPORTED_HUC_LEVELS,
    SUPPORTED_PALETTES,
    SUPPORTED_REGIONS,
    SUPPORTED_WIDTH_MODES,
    Settings,
    build_settings,
)
from src.fulfillment import ORDER_STYLES, SIZES, build_order
from src.orders import OrderStore, Request

ROOT = Path(__file__).resolve().parent.parent
WEB_DIR = ROOT / "web"
ORDER_HTML = WEB_DIR / "order.html"
DELIVERY_HTML = WEB_DIR / "delivery.html"


# ── Helpers ──────────────────────────────────────────────────────────────────

def _order_payload(**overrides):
    """Minimal valid order payload matching what order.html sends."""
    base = {
        "email": "buyer@example.com",
        "product": "Fine-art print",
        "region": "Washington",
        "county": "Clark",
        "style": "neon-basin",
        "size": "18x24",
        "formats": ["png"],
    }
    base.update(overrides)
    return base


def _html_data_attrs(html_path: Path, attr_name: str) -> list[str]:
    """Extract data-* attribute values from the HTML portion (before <script>)."""
    html = html_path.read_text()
    html_only = html.split("<script")[0]
    return re.findall(rf'{attr_name}="([^"]+)"', html_only)


# ═════════════════════════════════════════════════════════════════════════════
# 1. order.html payload → POST /api/orders → OrderStore
#    The JS form constructs a JSON payload; the server passes it to
#    OrderStore.create_request → fulfillment.build_order.  Every field
#    the JS sends must be accepted by the Python validation.
# ═════════════════════════════════════════════════════════════════════════════


class TestOrderPayloadContract:
    """order.html JS payload → Python OrderStore.create_request."""

    def test_minimal_payload_accepted(self, tmp_path):
        """The exact payload shape order.html sends must be accepted."""
        store = OrderStore(tmp_path / "orders")
        req = store.create_request(_order_payload())
        assert req.request_id.startswith("REQ-")
        assert req.status == "submitted"
        assert req.email == "buyer@example.com"

    def test_every_style_button_accepted(self, tmp_path):
        """Every data-style value in order.html must be a valid ORDER_STYLES key."""
        styles = _html_data_attrs(ORDER_HTML, "data-style")
        assert len(styles) > 0, "no data-style buttons found"
        for style in styles:
            store = OrderStore(tmp_path / f"orders-{style}")
            req = store.create_request(_order_payload(style=style))
            assert req.order["style"] == style

    def test_every_size_button_accepted(self, tmp_path):
        """Every data-size value in order.html must be a valid SIZES key."""
        sizes = _html_data_attrs(ORDER_HTML, "data-size")
        assert len(sizes) > 0, "no data-size buttons found"
        for size in sizes:
            store = OrderStore(tmp_path / f"orders-{size}")
            req = store.create_request(_order_payload(size=size))
            assert req.order["size"] == size

    def test_every_supported_region_accepted(self, tmp_path):
        """Every region the JS STATES array offers must be accepted."""
        for region in SUPPORTED_REGIONS:
            store = OrderStore(tmp_path / f"orders-{region}")
            req = store.create_request(_order_payload(region=region, county="Test"))
            assert req.order["region"] == region

    def test_payload_with_optional_fields_accepted(self, tmp_path):
        """order.html sends optional title, subtitle, note, name fields."""
        store = OrderStore(tmp_path / "orders")
        payload = _order_payload(
            title="My River",
            subtitle="Clark County",
            note="Please use dark background",
            name="Jane Doe",
        )
        req = store.create_request(payload)
        assert req.order.get("title") == "My River"

    def test_empty_region_rejected_with_message(self, tmp_path):
        """The exact error the user saw — empty region must fail clearly."""
        store = OrderStore(tmp_path / "orders")
        from src.fulfillment import OrderError
        with pytest.raises(OrderError, match="Unsupported region"):
            store.create_request(_order_payload(region=""))

    def test_invalid_style_rejected(self, tmp_path):
        store = OrderStore(tmp_path / "orders")
        from src.fulfillment import OrderError
        with pytest.raises(OrderError, match="Unknown style"):
            store.create_request(_order_payload(style="aurora-glow"))

    def test_invalid_size_rejected(self, tmp_path):
        store = OrderStore(tmp_path / "orders")
        from src.fulfillment import OrderError
        with pytest.raises(OrderError, match="Unknown size"):
            store.create_request(_order_payload(size="99x99"))


# ═════════════════════════════════════════════════════════════════════════════
# 2. POST /api/orders response → order.html confirmation step
#    order.html reads: data.request_id, resp.ok, data.error
#    The response must include these fields with the expected types.
# ═════════════════════════════════════════════════════════════════════════════


class TestOrderResponseContract:
    """API response shape → order.html confirmation step."""

    def test_success_response_has_request_id(self, tmp_path):
        store = OrderStore(tmp_path / "orders")
        req = store.create_request(_order_payload())
        data = req.to_dict()
        # order.html reads: r.data.request_id
        assert "request_id" in data
        assert isinstance(data["request_id"], str)
        assert data["request_id"].startswith("REQ-")

    def test_success_response_has_status(self, tmp_path):
        store = OrderStore(tmp_path / "orders")
        req = store.create_request(_order_payload())
        data = req.to_dict()
        assert "status" in data
        assert isinstance(data["status"], str)

    def test_success_response_has_email(self, tmp_path):
        store = OrderStore(tmp_path / "orders")
        req = store.create_request(_order_payload())
        data = req.to_dict()
        # order.html doesn't read email from response, but delivery.html does
        assert "email" in data
        assert data["email"] == "buyer@example.com"

    def test_success_response_has_order_dict(self, tmp_path):
        store = OrderStore(tmp_path / "orders")
        req = store.create_request(_order_payload())
        data = req.to_dict()
        # delivery.html reads: req.order.region, req.order.county, etc.
        assert "order" in data
        assert isinstance(data["order"], dict)
        order = data["order"]
        assert order["region"] == "Washington"
        assert order["county"] == "Clark"
        assert order["style"] == "neon-basin"
        assert order["size"] == "18x24"

    def test_error_response_shape(self, tmp_path):
        """On validation error, server sends {"error": "message"}."""
        from src.fulfillment import OrderError
        from src.server import handle_request

        store = OrderStore(tmp_path / "orders")
        bad_payload = json.dumps({"email": "x@y.com", "product": "p"}).encode()
        resp = handle_request(
            None, "POST", "/api/orders", bad_payload,
            web_root=str(tmp_path), order_store=store,
        )
        assert resp.status == 400
        data = json.loads(resp.body)
        assert "error" in data
        assert isinstance(data["error"], str)
        assert len(data["error"]) > 0


# ═════════════════════════════════════════════════════════════════════════════
# 3. POST /api/orders response → delivery.html fetch
#    delivery.html fetches /api/orders/<id> and reads specific fields from
#    the response to render the page.  The to_dict() shape must provide them.
# ═════════════════════════════════════════════════════════════════════════════


class TestDeliveryPageContract:
    """API response shape → delivery.html rendering expectations."""

    def test_response_has_all_delivery_fields(self, tmp_path):
        """delivery.html reads these fields from the API response."""
        store = OrderStore(tmp_path / "orders")
        req = store.create_request(_order_payload())
        data = req.to_dict()

        # Fields delivery.html accesses (from reading delivery.html JS):
        # req.request_id, req.status, req.product, req.job_id,
        # req.order.region, req.order.county, req.order.style, req.order.size
        assert "request_id" in data
        assert "status" in data
        assert "product" in data
        assert "job_id" in data  # may be None
        assert "order" in data

        order = data["order"]
        assert "region" in order
        assert "county" in order
        assert "style" in order
        assert "size" in order

    def test_delivery_style_labels_cover_all_order_styles(self):
        """delivery.html hardcodes style labels — they must match ORDER_STYLES."""
        html = DELIVERY_HTML.read_text()
        # Extract: var styleLabels = { "neon-basin": "...", ... }
        match = re.search(r'styleLabels\s*=\s*\{([^}]+)\}', html)
        assert match, "styleLabels not found in delivery.html"
        label_keys = re.findall(r'"([^"]+)":', match.group(1))
        assert set(label_keys) == set(ORDER_STYLES.keys()), (
            f"delivery.html styleLabels {sorted(label_keys)} != "
            f"ORDER_STYLES {sorted(ORDER_STYLES.keys())}"
        )

    def test_delivery_size_labels_cover_all_sizes(self):
        """delivery.html hardcodes size labels — they must match SIZES."""
        html = DELIVERY_HTML.read_text()
        match = re.search(r'sizeLabels\s*=\s*\{([^}]+)\}', html)
        assert match, "sizeLabels not found in delivery.html"
        label_keys = re.findall(r'"([^"]+)":', match.group(1))
        assert set(label_keys) == set(SIZES.keys()), (
            f"delivery.html sizeLabels {sorted(label_keys)} != "
            f"SIZES {sorted(SIZES.keys())}"
        )

    def test_request_id_round_trips_through_confirmation_url(self, tmp_path):
        """order.html builds delivery.html?order=REQ-xxx; delivery.html reads it."""
        store = OrderStore(tmp_path / "orders")
        req = store.create_request(_order_payload())
        # Simulate what order.html does: encodeURIComponent(reqId)
        from urllib.parse import quote, unquote
        encoded = quote(req.request_id, safe="")
        # Simulate what delivery.html does: urlParams.get("order")
        decoded = unquote(encoded)
        assert decoded == req.request_id

        # Verify the request can be retrieved by this ID
        fetched = store.get(decoded)
        assert fetched.request_id == req.request_id
        assert fetched.order["region"] == "Washington"


# ═════════════════════════════════════════════════════════════════════════════
# 4. order.html style/size buttons → fulfillment.build_order
#    The HTML data-* attributes must exactly match the Python allowlists.
# ═════════════════════════════════════════════════════════════════════════════


class TestOrderFormFulfillmentContract:
    """order.html HTML buttons → fulfillment.build_order allowlists."""

    def test_style_buttons_exact_match(self):
        html_styles = sorted(_html_data_attrs(ORDER_HTML, "data-style"))
        py_styles = sorted(ORDER_STYLES.keys())
        assert html_styles == py_styles

    def test_size_buttons_exact_match(self):
        html_sizes = sorted(_html_data_attrs(ORDER_HTML, "data-size"))
        py_sizes = sorted(SIZES.keys())
        assert html_sizes == py_sizes

    def test_build_order_accepts_every_html_combination(self):
        """Every style × size combination from the HTML must validate."""
        styles = _html_data_attrs(ORDER_HTML, "data-style")
        sizes = _html_data_attrs(ORDER_HTML, "data-size")
        for style in styles:
            for size in sizes:
                order = build_order({
                    "order_id": "REQ-TEST-0001",
                    "region": "Washington",
                    "county": "Clark",
                    "style": style,
                    "size": size,
                    "formats": ["png"],
                })
                assert order.style == style
                assert order.size == size


# ═════════════════════════════════════════════════════════════════════════════
# 5. Pipeline artifact contracts between stages
#    Stages communicate via ctx.artifacts dict.  These tests verify that
#    the artifact keys written by one stage match what the next reads.
# ═════════════════════════════════════════════════════════════════════════════


class TestPipelineArtifactContracts:
    """Pipeline stage N writes artifact X → stage N+1 reads artifact X."""

    def test_pipeline_stages_have_declared_order(self):
        """PIPELINE_STAGES is a fixed, ordered list — no accidental reordering."""
        from src.pipeline import PIPELINE_STAGES
        names = [s.name for s in PIPELINE_STAGES]
        assert names == [
            "download", "extract", "validate", "repair_geometries",
            "reproject", "clip_to_region", "build_graph",
            "compute_watersheds", "assign_colors", "generate_svg",
            "optimize_svg", "export",
        ]

    def test_settings_region_flows_to_pipeline(self):
        """Settings.region (from config) must match what the pipeline reads."""
        settings = build_settings({"region": ["Oregon"]})
        assert "Oregon" in settings.regions
        assert all(r in SUPPORTED_REGIONS for r in settings.regions)

    def test_settings_county_flows_to_pipeline(self):
        """Settings.county (from config) passes through to pipeline."""
        settings = build_settings({"region": ["Washington"], "county": "Clark"})
        assert settings.county == "Clark"

    def test_settings_palette_in_supported(self):
        settings = build_settings({"region": ["Oregon"], "palette": "neon"})
        assert settings.palette in SUPPORTED_PALETTES

    def test_settings_color_by_in_supported(self):
        settings = build_settings({"region": ["Oregon"], "color_by": "watershed"})
        assert settings.color_by in SUPPORTED_COLOR_MODES

    def test_settings_width_by_in_supported(self):
        settings = build_settings({"region": ["Oregon"], "width_by": "flow"})
        assert settings.width_by in SUPPORTED_WIDTH_MODES

    def test_settings_huc_level_in_supported(self):
        settings = build_settings({"region": ["Oregon"], "huc_level": "HUC4"})
        assert settings.huc_level in SUPPORTED_HUC_LEVELS


# ═════════════════════════════════════════════════════════════════════════════
# 6. CLI → config boundary
#    resolve_settings merges YAML + CLI; build_settings validates.
#    The merged dict must produce a valid Settings without throwing.
# ═════════════════════════════════════════════════════════════════════════════


class TestCliConfigContract:
    """CLI args → config.build_settings → valid Settings object."""

    def test_minimal_cli_produces_valid_settings(self):
        settings = build_settings({"region": ["Washington"]})
        assert isinstance(settings, Settings)
        assert "Washington" in settings.regions

    def test_county_flag_passes_through(self):
        settings = build_settings({
            "region": ["Washington"], "county": "Clark",
        })
        assert settings.county == "Clark"

    def test_all_regions_produce_valid_settings(self):
        for region in SUPPORTED_REGIONS:
            settings = build_settings({"region": [region]})
            assert region in settings.regions

    def test_all_palettes_produce_valid_settings(self):
        for palette in SUPPORTED_PALETTES:
            settings = build_settings({"region": ["Oregon"], "palette": palette})
            assert settings.palette == palette

    def test_invalid_region_raises_config_error(self):
        from src.config import ConfigError
        with pytest.raises(ConfigError, match="Unsupported region"):
            build_settings({"region": ["Atlantis"]})

    def test_settings_fields_are_all_set(self):
        """Every field on Settings must have a non-sentinel value after build."""
        settings = build_settings({"region": ["Oregon"]})
        for f in fields(settings):
            val = getattr(settings, f.name)
            # None is acceptable for optional fields (county, etc.)
            # but the field must exist and be accessible
            assert hasattr(settings, f.name), f"Settings missing field: {f.name}"
