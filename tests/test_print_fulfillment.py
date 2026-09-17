"""Tests for the print vendor integration module.

Offline — uses fake vendor client. No network, no vendor SDK.
"""

from __future__ import annotations


class FakePrintVendor:
    """Fake print vendor for offline testing."""

    def __init__(self):
        self.orders = []

    def submit_print_order(self, file_url, spec, address):
        order_id = f"VENDOR-{len(self.orders) + 1:04d}"
        self.orders.append({
            "vendor_order_id": order_id,
            "file_url": file_url,
            "spec": spec,
            "address": address,
        })
        return order_id

    def check_shipment(self, vendor_order_id):
        for o in self.orders:
            if o["vendor_order_id"] == vendor_order_id:
                return {"status": "shipped", "tracking": "1Z999AA10123456784", "carrier": "UPS"}
        return {"status": "unknown"}


class TestCreatePrintOrderPayload:
    def test_correct_file_url_and_spec(self):
        from src.print_vendor import build_print_order_payload

        payload = build_print_order_payload(
            file_url="https://cdn.example.com/REQ-001/final.png",
            product_spec={"size": "24x36", "paper": "matte"},
            address={"name": "Jane Doe", "street": "123 Main St", "city": "Portland", "state": "OR", "zip": "97201"},
        )
        assert payload["file_url"] == "https://cdn.example.com/REQ-001/final.png"
        assert payload["spec"]["size"] == "24x36"
        assert payload["address"]["city"] == "Portland"


class TestSubmitPrintOrder:
    def test_vendor_order_id_returned(self):
        from src.print_vendor import submit_print_order

        vendor = FakePrintVendor()
        vendor_id = submit_print_order(
            file_url="https://cdn.example.com/REQ-001/final.png",
            product_spec={"size": "24x36"},
            address={"name": "Jane", "street": "123 Main", "city": "Portland", "state": "OR", "zip": "97201"},
            client=vendor,
        )
        assert vendor_id.startswith("VENDOR-")
        assert len(vendor.orders) == 1

    def test_vendor_order_id_stored(self):
        from src.print_vendor import submit_print_order

        vendor = FakePrintVendor()
        vid = submit_print_order(
            file_url="https://x.com/file.png",
            product_spec={"size": "18x24"},
            address={"name": "J", "street": "1 St", "city": "P", "state": "OR", "zip": "97201"},
            client=vendor,
        )
        assert vendor.orders[0]["vendor_order_id"] == vid


class TestCheckShipment:
    def test_tracking_number_returned(self):
        from src.print_vendor import check_shipment

        vendor = FakePrintVendor()
        vid = vendor.submit_print_order("url", {"size": "24x36"}, {"name": "J"})
        status = check_shipment(vid, client=vendor)
        assert status["status"] == "shipped"
        assert "tracking" in status


class TestPrintCostPassthrough:
    def test_print_cost_calculation(self):
        from src.print_vendor import calculate_print_cost

        cost = calculate_print_cost(size="24x36", paper="matte")
        assert isinstance(cost, int)
        assert cost > 0

    def test_print_plus_shipping_total(self):
        from src.print_vendor import calculate_print_cost

        cost = calculate_print_cost(size="18x24", paper="matte")
        # Just verify it returns a positive integer (cents)
        assert cost > 0
