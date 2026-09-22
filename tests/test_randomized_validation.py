"""Randomized option-space exploration for the Python backend.

Exercises 100+ random combinations of regions, counties, styles, sizes,
config settings, and order payloads to surface edge cases in validation,
fulfillment, and config construction.

Seeded PRNG for reproducibility.
"""

from __future__ import annotations

import random
from itertools import product as cartesian

import pytest

from src.config import (
    SUPPORTED_COLOR_MODES,
    SUPPORTED_GLOW_MODES,
    SUPPORTED_HUC_LEVELS,
    SUPPORTED_PALETTES,
    SUPPORTED_REGIONS,
    SUPPORTED_WIDTH_MODES,
    ConfigError,
    Settings,
    build_settings,
)
from src.fulfillment import ORDER_STYLES, SIZES, TITLE_MAX, OrderError, build_order
from src.orders import OrderStore


# ── Seeded PRNG ──────────────────────────────────────────────────────────────
RNG = random.Random(20260921)

PRODUCTS = ["digital-image", "fine-art-print", "watershed-report", "year-in-motion"]
STYLES = list(ORDER_STYLES.keys())
SIZE_KEYS = list(SIZES.keys())
FORMAT_COMBOS = [["png"], ["pdf"], ["png", "pdf"]]
BACKGROUNDS = ["#000000", "#05060a", "#0a0a0a", "#ffffff", "#1a1a2e"]
SINGLE_COLORS = ["#00ffff", "#ff00ff", "#ff7a00", "#00ff5f", "#ffd700"]
OPTIONAL_TITLES = [None, "", "My River", "Clark Creek", "New York Watershed",
                   "St. Louis Basin", "A" * 80]
OPTIONAL_NAMES = [None, "", "Jane", "Neil Runde", "José García"]


def _random_order_payload(**overrides):
    """Build a random valid order payload."""
    region = RNG.choice(SUPPORTED_REGIONS)
    base = {
        "email": f"test{RNG.randint(1, 9999)}@example.com",
        "product": RNG.choice(PRODUCTS),
        "region": region,
        "county": "Test",  # county must be non-empty
        "style": RNG.choice(STYLES),
        "size": RNG.choice(SIZE_KEYS),
        "formats": RNG.choice(FORMAT_COMBOS),
    }
    # Randomly add optional fields
    title = RNG.choice(OPTIONAL_TITLES)
    if title is not None:
        base["title"] = title
    name = RNG.choice(OPTIONAL_NAMES)
    if name is not None:
        base["name"] = name
    base.update(overrides)
    return base


# ═════════════════════════════════════════════════════════════════════════════
# Block 1: 20 random valid order payloads — all must be accepted
# ═════════════════════════════════════════════════════════════════════════════


class TestRandomOrderPayloads:
    """20 random valid order payloads through OrderStore.create_request."""

    @pytest.mark.parametrize("trial", range(20))
    def test_random_valid_payload_accepted(self, tmp_path, trial):
        store = OrderStore(tmp_path / f"orders-{trial}")
        payload = _random_order_payload()
        req = store.create_request(payload)
        assert req.request_id.startswith("REQ-")
        assert req.order["region"] in SUPPORTED_REGIONS
        assert req.order["style"] in ORDER_STYLES
        assert req.order["size"] in SIZES


# ═════════════════════════════════════════════════════════════════════════════
# Block 2: Exhaustive style × size × format grid (all combos)
# ═════════════════════════════════════════════════════════════════════════════


class TestExhaustiveStyleSizeFormat:
    """Every style × size × format combination must validate."""

    @pytest.mark.parametrize(
        "style,size,formats",
        list(cartesian(STYLES, SIZE_KEYS, FORMAT_COMBOS)),
    )
    def test_combination_accepted(self, style, size, formats):
        order = build_order({
            "order_id": "REQ-TEST-0001",
            "region": "Washington",
            "county": "Clark",
            "style": style,
            "size": size,
            "formats": formats,
        })
        assert order.style == style
        assert order.size == size
        assert set(formats).issubset(set(order.formats))


# ═════════════════════════════════════════════════════════════════════════════
# Block 3: 20 random build_settings with varied options
# ═════════════════════════════════════════════════════════════════════════════


class TestRandomBuildSettings:
    """20 random config dictionaries through build_settings."""

    @pytest.mark.parametrize("trial", range(20))
    def test_random_valid_settings(self, trial):
        region = RNG.choice(SUPPORTED_REGIONS)
        cfg = {"region": [region]}

        # Randomly add optional config fields
        if RNG.random() > 0.5:
            cfg["palette"] = RNG.choice(SUPPORTED_PALETTES)
        if RNG.random() > 0.5:
            cfg["color_by"] = RNG.choice(SUPPORTED_COLOR_MODES)
        if RNG.random() > 0.5:
            cfg["width_by"] = RNG.choice(SUPPORTED_WIDTH_MODES)
        if RNG.random() > 0.5:
            cfg["huc_level"] = RNG.choice(SUPPORTED_HUC_LEVELS)
        if RNG.random() > 0.5:
            cfg["glow"] = RNG.choice([True, False])
        if RNG.random() > 0.5:
            cfg["background"] = RNG.choice(BACKGROUNDS)
        if RNG.random() > 0.5:
            cfg["line_width"] = round(RNG.uniform(0.3, 3.0), 1)
        if RNG.random() > 0.5:
            cfg["single_color"] = RNG.choice(SINGLE_COLORS)

        settings = build_settings(cfg)
        assert isinstance(settings, Settings)
        assert region in settings.regions


# ═════════════════════════════════════════════════════════════════════════════
# Block 4: 10 random invalid payloads — all must be rejected with clear errors
# ═════════════════════════════════════════════════════════════════════════════


class TestRandomInvalidPayloads:
    """10 random invalid payloads — each corrupts one field."""

    CORRUPTIONS = [
        ("region", ["", "Atlantis", "new york", "  ", None, 42]),
        ("style", ["aurora-glow", "", "NEON-BASIN", None, 42]),
        ("size", ["99x99", "", "18X24", None, "small"]),
        ("county", ["", "   ", None]),
        ("formats", [[], ["bmp"], "png", None]),
    ]

    @pytest.mark.parametrize("trial", range(10))
    def test_random_corruption_rejected(self, tmp_path, trial):
        field, bad_values = RNG.choice(self.CORRUPTIONS)
        bad_value = RNG.choice(bad_values)
        payload = _random_order_payload(**{field: bad_value})
        store = OrderStore(tmp_path / f"orders-bad-{trial}")
        with pytest.raises(OrderError):
            store.create_request(payload)


# ═════════════════════════════════════════════════════════════════════════════
# Block 5: 10 random region × county order round-trips through store
# ═════════════════════════════════════════════════════════════════════════════


class TestRandomRegionCountyRoundTrip:
    """10 random region/county combos — create, persist, retrieve."""

    @pytest.mark.parametrize("trial", range(10))
    def test_round_trip(self, tmp_path, trial):
        region = RNG.choice(SUPPORTED_REGIONS)
        payload = _random_order_payload(region=region)
        store = OrderStore(tmp_path / f"orders-rt-{trial}")

        req = store.create_request(payload)
        assert req.order["region"] == region

        # Retrieve and verify persistence
        fetched = store.get(req.request_id)
        assert fetched.request_id == req.request_id
        assert fetched.order["region"] == region
        assert fetched.order["style"] == payload["style"]
        assert fetched.order["size"] == payload["size"]
        assert fetched.email == payload["email"]


# ═════════════════════════════════════════════════════════════════════════════
# Block 6: 10 random multi-region builds (2–5 states)
# ═════════════════════════════════════════════════════════════════════════════


class TestRandomMultiRegionSettings:
    """10 random multi-state build_settings calls."""

    @pytest.mark.parametrize("trial", range(10))
    def test_multi_region_valid(self, trial):
        n = RNG.randint(2, 5)
        regions = RNG.sample(list(SUPPORTED_REGIONS), n)
        settings = build_settings({"region": regions})
        assert isinstance(settings, Settings)
        for r in regions:
            assert r in settings.regions


# ═════════════════════════════════════════════════════════════════════════════
# Block 7: Edge case names — special characters in titles/counties
# ═════════════════════════════════════════════════════════════════════════════


class TestSpecialCharacterEdgeCases:
    """Order payloads with special characters in string fields."""

    SPECIAL_TITLES = [
        "Clark's Creek",
        "Río Grande",
        "Lac qui Parle",
        "Coeur d'Alene",
        "Prince George's",
        'Title with "quotes"',
        "Line1\nLine2",
        "  Leading/trailing spaces  ",
        "",
        "A" * 200,
    ]

    @pytest.mark.parametrize("title", SPECIAL_TITLES)
    def test_special_title_accepted(self, tmp_path, title):
        store = OrderStore(tmp_path / "orders-special")
        payload = _random_order_payload(title=title)
        req = store.create_request(payload)
        # _clean_text collapses whitespace, strips, and caps at TITLE_MAX
        cleaned = " ".join(title.split())
        if cleaned:
            assert req.order.get("title") == cleaned[:TITLE_MAX]
        else:
            assert req.order.get("title") is None
