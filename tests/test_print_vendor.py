"""Tests for print vendor integration (print cost, order payload, submission).

Offline — uses fakes for vendor client. No network, no SDK.
"""

from __future__ import annotations

import pytest

from src.print_vendor import (
    build_print_order_payload,
    calculate_print_cost,
    check_shipment,
    submit_print_order,
)


class FakeVendorClient:
    """Minimal fake satisfying PrintVendorLike."""

    def __init__(self):
        self.submitted: list[tuple] = []

    def submit_print_order(self, file_url, spec, address):
        self.submitted.append((file_url, spec, address))
        return f"VENDOR-{len(self.submitted):04d}"

    def check_shipment(self, vendor_order_id):
        return {"status": "shipped", "tracking": "1Z999", "carrier": "UPS"}


class TestBuildPrintOrderPayload:
    def test_returns_all_fields(self):
        result = build_print_order_payload(
            file_url="https://cdn.example.com/art.png",
            product_spec={"size": "24x36", "paper": "matte"},
            address={"name": "Test", "city": "Portland"},
        )
        assert result["file_url"] == "https://cdn.example.com/art.png"
        assert result["spec"] == {"size": "24x36", "paper": "matte"}
        assert result["address"] == {"name": "Test", "city": "Portland"}

    def test_copies_dicts_not_references(self):
        spec = {"size": "18x24"}
        addr = {"city": "Seattle"}
        result = build_print_order_payload(
            file_url="http://x", product_spec=spec, address=addr,
        )
        assert result["spec"] is not spec
        assert result["address"] is not addr


class TestSubmitPrintOrder:
    def test_delegates_to_client(self):
        client = FakeVendorClient()
        order_id = submit_print_order(
            file_url="http://cdn/art.png",
            product_spec={"size": "24x36"},
            address={"name": "Buyer"},
            client=client,
        )
        assert order_id == "VENDOR-0001"
        assert len(client.submitted) == 1

    def test_returns_vendor_order_id(self):
        client = FakeVendorClient()
        oid1 = submit_print_order(
            file_url="a", product_spec={}, address={}, client=client,
        )
        oid2 = submit_print_order(
            file_url="b", product_spec={}, address={}, client=client,
        )
        assert oid1 != oid2


class TestCheckShipment:
    def test_returns_status_dict(self):
        client = FakeVendorClient()
        result = check_shipment("VENDOR-0001", client=client)
        assert result["status"] == "shipped"
        assert "tracking" in result


class TestCalculatePrintCost:
    def test_known_size_matte(self):
        assert calculate_print_cost(size="12x16") == 2500
        assert calculate_print_cost(size="18x24") == 3500
        assert calculate_print_cost(size="24x36") == 5500

    def test_glossy_surcharge(self):
        assert calculate_print_cost(size="18x24", paper="glossy") == 4000

    def test_canvas_surcharge(self):
        assert calculate_print_cost(size="18x24", paper="canvas") == 5000

    def test_unknown_size_defaults_to_18x24(self):
        assert calculate_print_cost(size="30x40") == 3500

    def test_unknown_paper_no_surcharge(self):
        assert calculate_print_cost(size="18x24", paper="silk") == 3500
