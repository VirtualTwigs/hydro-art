"""Tests for shipping address validation.

Offline — no GDAL, no network. Pure dataclass + validation.
"""

from __future__ import annotations

import pytest


def _valid_address(**overrides):
    base = {
        "name": "Jane Doe",
        "street": "123 Main St",
        "city": "Portland",
        "state": "OR",
        "zip": "97201",
    }
    base.update(overrides)
    return base


class TestValidateAddress:
    def test_valid_us_address_passes(self):
        from src.shipping import validate_address

        addr = validate_address(_valid_address())
        assert addr.name == "Jane Doe"
        assert addr.street == "123 Main St"
        assert addr.city == "Portland"
        assert addr.state == "OR"
        assert addr.zip == "97201"

    def test_missing_name_rejected(self):
        from src.shipping import validate_address, ShippingError

        with pytest.raises(ShippingError, match="[Nn]ame"):
            validate_address(_valid_address(name=""))

    def test_missing_street_rejected(self):
        from src.shipping import validate_address, ShippingError

        with pytest.raises(ShippingError, match="[Ss]treet"):
            validate_address(_valid_address(street=""))

    def test_missing_city_rejected(self):
        from src.shipping import validate_address, ShippingError

        with pytest.raises(ShippingError, match="[Cc]ity"):
            validate_address(_valid_address(city=""))

    def test_missing_state_rejected(self):
        from src.shipping import validate_address, ShippingError

        with pytest.raises(ShippingError, match="[Ss]tate"):
            validate_address(_valid_address(state=""))

    def test_missing_zip_rejected(self):
        from src.shipping import validate_address, ShippingError

        with pytest.raises(ShippingError, match="[Zz]ip"):
            validate_address(_valid_address(zip=""))

    def test_invalid_zip_format_rejected(self):
        from src.shipping import validate_address, ShippingError

        with pytest.raises(ShippingError, match="[Zz]ip"):
            validate_address(_valid_address(zip="ABCDE"))

    def test_zip_plus_four_accepted(self):
        from src.shipping import validate_address

        addr = validate_address(_valid_address(zip="97201-1234"))
        assert addr.zip == "97201-1234"

    def test_optional_line2(self):
        from src.shipping import validate_address

        addr = validate_address({**_valid_address(), "line2": "Apt 4B"})
        assert addr.line2 == "Apt 4B"

    def test_address_to_dict_roundtrip(self):
        from src.shipping import validate_address

        addr = validate_address(_valid_address())
        d = addr.to_dict()
        assert d["name"] == "Jane Doe"
        assert d["zip"] == "97201"
