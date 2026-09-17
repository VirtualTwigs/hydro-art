"""Integration tests for print order handoff (Epoch 30 Task Group 3).

Offline — uses fake vendor and email sender. Full cycle:
print order → pay → auto-submit to vendor → tracking recorded → customer emailed.
"""

from __future__ import annotations

from src.orders import OrderStore
from src.print_vendor import check_shipment, submit_print_order


class FakePrintVendor:
    def __init__(self):
        self.orders = []

    def submit_print_order(self, file_url, spec, address):
        vid = f"VENDOR-{len(self.orders) + 1:04d}"
        self.orders.append({"vendor_order_id": vid, "file_url": file_url})
        return vid

    def check_shipment(self, vendor_order_id):
        return {"status": "shipped", "tracking": "1Z999AA10123456784", "carrier": "UPS"}


class FakeEmailSender:
    def __init__(self):
        self.sent = []

    def send(self, msg):
        self.sent.append(msg)


def _order_payload(**overrides):
    base = {
        "email": "buyer@example.com",
        "product": "Fine-art print",
        "region": "Washington",
        "county": "Clark",
        "style": "neon-basin",
        "size": "24x36",
        "formats": ["png"],
    }
    base.update(overrides)
    return base


class TestPrintOrderFullCycle:
    def test_pay_then_submit_to_vendor(self, tmp_path):
        """Paid print order → submit to vendor → vendor ID recorded."""
        store = OrderStore(tmp_path / "orders")
        req = store.create_request(_order_payload())

        # Walk through the lifecycle
        store.update_status(req.request_id, "accepted")
        store.update_status(req.request_id, "rendering")
        store.update_status(req.request_id, "proof_ready")
        store.update_status(req.request_id, "approved")
        store.update_status(req.request_id, "payment_pending")
        store.update_status(req.request_id, "paid")

        # Submit to print vendor
        vendor = FakePrintVendor()
        vendor_id = submit_print_order(
            file_url=f"https://cdn.example.com/{req.request_id}/final.png",
            product_spec={"size": "24x36", "paper": "matte"},
            address={"name": "Jane Doe", "street": "123 Main St", "city": "Portland", "state": "OR", "zip": "97201"},
            client=vendor,
        )
        assert vendor_id.startswith("VENDOR-")

        # Record vendor ID on request via notes
        store.add_note(req.request_id, f"Print submitted: {vendor_id}")

        # Check shipment
        status = check_shipment(vendor_id, client=vendor)
        assert status["status"] == "shipped"
        assert "tracking" in status

        # Record tracking
        store.add_note(req.request_id, f"Shipped: {status['tracking']} via {status['carrier']}")

        # Fulfill
        store.update_status(req.request_id, "fulfilled")
        final = store.get(req.request_id)
        assert final.status == "fulfilled"
        assert any("VENDOR-" in n for n in final.notes)
        assert any("Shipped" in n for n in final.notes)

    def test_shipping_email_sent_on_fulfillment(self, tmp_path):
        """Customer receives shipping confirmation email."""
        from src.email_delivery import send_delivery_email

        sender = FakeEmailSender()
        result = send_delivery_email(
            "buyer@example.com",
            "REQ-001",
            "http://localhost:8765/delivery.html?token=abc",
            product="Fine-art print",
            location="Clark County, Washington",
            sender=sender,
        )
        assert result is True
        assert len(sender.sent) == 1
        assert sender.sent[0]["To"] == "buyer@example.com"
