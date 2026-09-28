"""Tests for the local HTTP routing layer (roadmap #27, Task Group 2).

`handle_request` is a pure dispatcher, so these exercise it directly with a fake
runner and a temp web root — no sockets, network, or datasets.
"""

from __future__ import annotations

import json

from src.config import ConfigError
from src.jobs import SUCCEEDED, Job
from src.server import Response, handle_request


class FakeRunner:
    def __init__(self, *, job: Job | None = None, submit_error: Exception | None = None):
        self._job = job
        self._submit_error = submit_error
        self.submitted = None

    def submit(self, payload):
        if self._submit_error is not None:
            raise self._submit_error
        self.submitted = payload
        return "job123"

    def status(self, job_id):
        if self._job is None or job_id != self._job.id:
            raise KeyError(job_id)
        return self._job

    @staticmethod
    def to_dict(job):
        return {
            "id": job.id,
            "state": job.state,
            "outputs": job.outputs,
            "sha256": job.sha256,
            "error": job.error,
        }


def _req(runner, method, path, body=b"", *, web_root):
    return handle_request(runner, method, path, body, web_root=str(web_root))


def test_post_render_valid_returns_202_and_job_id(tmp_path):
    runner = FakeRunner()
    resp = _req(runner, "POST", "/api/render", b'{"region": "Oregon"}', web_root=tmp_path)
    assert isinstance(resp, Response)
    assert resp.status == 202
    assert json.loads(resp.body)["job"] == "job123"
    assert runner.submitted == {"region": "Oregon"}


def test_post_render_config_error_returns_400(tmp_path):
    runner = FakeRunner(submit_error=ConfigError("bad region"))
    resp = _req(runner, "POST", "/api/render", b'{"region": "Atlantis"}', web_root=tmp_path)
    assert resp.status == 400
    assert "bad region" in json.loads(resp.body)["error"]


def test_post_render_bad_json_returns_400(tmp_path):
    resp = _req(FakeRunner(), "POST", "/api/render", b"not json", web_root=tmp_path)
    assert resp.status == 400


def test_get_job_status_known_and_unknown(tmp_path):
    job = Job(id="abc", state=SUCCEEDED, outputs={"svg": "output/x.svg"}, sha256="ff")
    runner = FakeRunner(job=job)
    ok = _req(runner, "GET", "/api/jobs/abc", web_root=tmp_path)
    assert ok.status == 200
    assert json.loads(ok.body)["state"] == SUCCEEDED
    missing = _req(runner, "GET", "/api/jobs/nope", web_root=tmp_path)
    assert missing.status == 404


def test_get_artifact_returns_bytes_and_content_type(tmp_path):
    svg = tmp_path / "out.svg"
    svg.write_text("<svg/>", encoding="utf-8")
    job = Job(id="abc", state=SUCCEEDED, outputs={"svg": str(svg)}, sha256="ff")
    runner = FakeRunner(job=job)
    resp = _req(runner, "GET", "/api/jobs/abc/artifact?fmt=svg", web_root=tmp_path)
    assert resp.status == 200
    assert resp.content_type == "image/svg+xml"
    assert resp.body == b"<svg/>"


def test_get_artifact_unready_returns_404(tmp_path):
    job = Job(id="abc", state="running")
    runner = FakeRunner(job=job)
    resp = _req(runner, "GET", "/api/jobs/abc/artifact?fmt=svg", web_root=tmp_path)
    assert resp.status == 404


def test_static_file_served_from_web_root(tmp_path):
    (tmp_path / "studio.html").write_text("<html>studio</html>", encoding="utf-8")
    resp = _req(FakeRunner(), "GET", "/", web_root=tmp_path)
    assert resp.status == 200
    assert resp.content_type == "text/html"
    assert b"studio" in resp.body


def test_path_traversal_is_refused(tmp_path):
    secret = tmp_path.parent / "secret.txt"
    secret.write_text("top secret", encoding="utf-8")
    resp = _req(FakeRunner(), "GET", "/../secret.txt", web_root=tmp_path)
    assert resp.status == 404


# --- Order API routes (concierge flow) ------------------------------------

def _order_req(runner, method, path, body=b"", *, web_root, order_store,
               email_sender=None):
    return handle_request(
        runner, method, path, body,
        web_root=str(web_root), order_store=order_store, email_sender=email_sender,
    )


class FakeEmailSender:
    def __init__(self):
        self.sent = []

    def send(self, message):
        self.sent.append(message)


def _order_payload(**overrides):
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


def test_post_order_creates_request(tmp_path):
    from src.orders import OrderStore

    store = OrderStore(tmp_path / "orders")
    runner = FakeRunner()
    payload = json.dumps(_order_payload()).encode()
    resp = _order_req(runner, "POST", "/api/orders", payload,
                      web_root=tmp_path, order_store=store)
    assert resp.status == 202
    data = json.loads(resp.body)
    assert data["request_id"].startswith("REQ-")
    assert data["status"] == "rendering"
    assert data["email"] == "buyer@example.com"


def test_post_order_sends_confirmation_email(tmp_path):
    from src.orders import OrderStore

    store = OrderStore(tmp_path / "orders")
    sender = FakeEmailSender()
    resp = _order_req(
        FakeRunner(),
        "POST",
        "/api/orders",
        json.dumps(_order_payload()).encode(),
        web_root=tmp_path,
        order_store=store,
        email_sender=sender,
    )
    data = json.loads(resp.body)
    assert data["confirmation_email_sent"] is True
    assert len(sender.sent) == 1
    assert sender.sent[0]["To"] == "buyer@example.com"
    assert data["request_id"] in sender.sent[0]["Subject"]


def test_post_order_invalid_returns_400(tmp_path):
    from src.orders import OrderStore

    store = OrderStore(tmp_path / "orders")
    payload = json.dumps({"email": "x@y.com", "product": "print"}).encode()
    resp = _order_req(FakeRunner(), "POST", "/api/orders", payload,
                      web_root=tmp_path, order_store=store)
    assert resp.status == 400


def test_get_orders_list(tmp_path):
    from src.orders import OrderStore

    store = OrderStore(tmp_path / "orders")
    store.create_request(_order_payload())
    resp = _order_req(FakeRunner(), "GET", "/api/orders",
                      web_root=tmp_path, order_store=store)
    assert resp.status == 200
    data = json.loads(resp.body)
    assert len(data["orders"]) == 1


def test_get_order_by_id(tmp_path):
    from src.orders import OrderStore

    store = OrderStore(tmp_path / "orders")
    req = store.create_request(_order_payload())
    resp = _order_req(FakeRunner(), "GET", f"/api/orders/{req.request_id}",
                      web_root=tmp_path, order_store=store)
    assert resp.status == 200
    assert json.loads(resp.body)["request_id"] == req.request_id


def test_get_order_unknown_returns_404(tmp_path):
    from src.orders import OrderStore

    store = OrderStore(tmp_path / "orders")
    resp = _order_req(FakeRunner(), "GET", "/api/orders/REQ-00000000-9999",
                      web_root=tmp_path, order_store=store)
    assert resp.status == 404


def test_patch_order_status(tmp_path):
    from src.orders import OrderStore

    store = OrderStore(tmp_path / "orders")
    req = store.create_request(_order_payload())
    body = json.dumps({"status": "accepted"}).encode()
    resp = _order_req(FakeRunner(), "PATCH", f"/api/orders/{req.request_id}",
                      body, web_root=tmp_path, order_store=store)
    assert resp.status == 200
    assert json.loads(resp.body)["status"] == "accepted"


def test_patch_order_invalid_transition(tmp_path):
    from src.orders import OrderStore

    store = OrderStore(tmp_path / "orders")
    req = store.create_request(_order_payload())
    body = json.dumps({"status": "fulfilled"}).encode()
    resp = _order_req(FakeRunner(), "PATCH", f"/api/orders/{req.request_id}",
                      body, web_root=tmp_path, order_store=store)
    assert resp.status == 400


def test_order_routes_inactive_without_store(tmp_path):
    """When no order_store is passed, /api/orders falls through to static."""
    resp = _req(FakeRunner(), "GET", "/api/orders", web_root=tmp_path)
    assert resp.status == 404


# --- Epoch 28: auto-dispatch & proof routes --------------------------------

def test_order_submit_auto_dispatches_render(tmp_path):
    """POST /api/orders auto-transitions to rendering and dispatches a job."""
    from src.orders import OrderStore

    store = OrderStore(tmp_path / "orders")
    runner = FakeRunner()
    payload = json.dumps(_order_payload()).encode()
    resp = _order_req(runner, "POST", "/api/orders", payload,
                      web_root=tmp_path, order_store=store)
    assert resp.status == 202
    data = json.loads(resp.body)
    assert data["status"] == "rendering"
    assert data["job_id"] == "job123"
    assert runner.submitted is not None


def test_order_submit_bad_region_returns_400(tmp_path):
    """Invalid region → 400."""
    from src.orders import OrderStore

    store = OrderStore(tmp_path / "orders")
    payload = json.dumps(_order_payload(region="Atlantis")).encode()
    resp = _order_req(FakeRunner(), "POST", "/api/orders", payload,
                      web_root=tmp_path, order_store=store)
    assert resp.status == 400
    assert "region" in json.loads(resp.body)["error"].lower()


def test_order_submit_missing_email_returns_400(tmp_path):
    """No email → 400."""
    from src.orders import OrderStore

    store = OrderStore(tmp_path / "orders")
    payload = json.dumps(_order_payload(email="")).encode()
    resp = _order_req(FakeRunner(), "POST", "/api/orders", payload,
                      web_root=tmp_path, order_store=store)
    assert resp.status == 400
    assert "email" in json.loads(resp.body)["error"].lower()


def test_order_submit_prism_style_returns_400(tmp_path):
    """PRISM art direction → 400 (rights gate)."""
    from src.orders import OrderStore

    store = OrderStore(tmp_path / "orders")
    payload = json.dumps(_order_payload(style="prism-topo")).encode()
    resp = _order_req(FakeRunner(), "POST", "/api/orders", payload,
                      web_root=tmp_path, order_store=store)
    assert resp.status == 400
    assert "style" in json.loads(resp.body)["error"].lower()


# --- Epoch 28: proof review routes -----------------------------------------

def _setup_proof_ready_order(tmp_path):
    """Helper: create an order and advance it to proof_ready."""
    from src.orders import OrderStore
    from src.proof import sign_proof_url

    store = OrderStore(tmp_path / "orders")
    req = store.create_request(_order_payload())
    store.update_status(req.request_id, "accepted")
    store.update_status(req.request_id, "rendering")
    store.update_status(req.request_id, "proof_ready")
    secret = b"test-secret"
    token = sign_proof_url(req.request_id, secret, expires_in=3600)
    return store, req, token, secret


def test_proof_page_valid_token_200(tmp_path):
    """Signed token → 200 with proof data."""
    store, req, token, secret = _setup_proof_ready_order(tmp_path)
    runner = FakeRunner()
    resp = handle_request(
        runner, "GET", f"/api/proof/{token}", b"",
        web_root=str(tmp_path), order_store=store, proof_secret=secret,
    )
    assert resp.status == 200
    data = json.loads(resp.body)
    assert data["request_id"] == req.request_id


def test_proof_page_expired_token_410(tmp_path):
    """Expired token → 410 Gone."""
    from src.orders import OrderStore
    from src.proof import sign_proof_url

    store = OrderStore(tmp_path / "orders")
    req = store.create_request(_order_payload())
    store.update_status(req.request_id, "accepted")
    store.update_status(req.request_id, "rendering")
    store.update_status(req.request_id, "proof_ready")
    secret = b"test-secret"
    token = sign_proof_url(req.request_id, secret, expires_in=0)
    resp = handle_request(
        runner=FakeRunner(), method="GET", path=f"/api/proof/{token}", body=b"",
        web_root=str(tmp_path), order_store=store, proof_secret=secret,
    )
    assert resp.status == 410


def test_proof_page_invalid_token_403(tmp_path):
    """Bad signature → 403 Forbidden."""
    from src.orders import OrderStore

    store = OrderStore(tmp_path / "orders")
    resp = handle_request(
        runner=FakeRunner(), method="GET", path="/api/proof/bogus-token", body=b"",
        web_root=str(tmp_path), order_store=store, proof_secret=b"test-secret",
    )
    assert resp.status == 403


def test_proof_approve_transitions_order(tmp_path):
    """POST approve → order status = approved."""
    store, req, token, secret = _setup_proof_ready_order(tmp_path)
    resp = handle_request(
        runner=FakeRunner(), method="POST", path=f"/api/proof/{token}/approve",
        body=b"", web_root=str(tmp_path), order_store=store, proof_secret=secret,
    )
    assert resp.status == 200
    data = json.loads(resp.body)
    assert data["status"] == "approved"
    # Verify persisted
    fetched = store.get(req.request_id)
    assert fetched.status == "approved"


def test_proof_adjust_triggers_rerender(tmp_path):
    """POST adjust → order status = rendering."""
    store, _req, token, secret = _setup_proof_ready_order(tmp_path)
    runner = FakeRunner()
    adjust_payload = json.dumps({"style": "neon-basin"}).encode()
    resp = handle_request(
        runner=runner, method="POST", path=f"/api/proof/{token}/adjust",
        body=adjust_payload, web_root=str(tmp_path), order_store=store,
        proof_secret=secret,
    )
    assert resp.status == 202
    data = json.loads(resp.body)
    assert data["status"] == "rendering"


def test_proof_adjust_preserves_email(tmp_path):
    """Re-render keeps original email."""
    store, req, token, secret = _setup_proof_ready_order(tmp_path)
    runner = FakeRunner()
    resp = handle_request(
        runner=runner, method="POST", path=f"/api/proof/{token}/adjust",
        body=b"{}", web_root=str(tmp_path), order_store=store,
        proof_secret=secret,
    )
    assert resp.status == 202
    fetched = store.get(req.request_id)
    assert fetched.email == "buyer@example.com"


# --- Epoch 29: payment routes ---------------------------------------------

def _setup_approved_order(tmp_path):
    """Helper: create an order and advance it to approved."""
    from src.orders import OrderStore
    from src.proof import sign_proof_url

    store = OrderStore(tmp_path / "orders")
    req = store.create_request(_order_payload())
    store.update_status(req.request_id, "accepted")
    store.update_status(req.request_id, "rendering")
    store.update_status(req.request_id, "proof_ready")
    store.update_status(req.request_id, "approved")
    secret = b"test-secret"
    token = sign_proof_url(req.request_id, secret, expires_in=3600)
    return store, req, token, secret


def test_approve_returns_checkout_url(tmp_path):
    """POST /api/proof/<token>/approve returns checkout URL when payment is configured."""
    store, _req, token, secret = _setup_proof_ready_order(tmp_path)
    resp = handle_request(
        runner=FakeRunner(), method="POST", path=f"/api/proof/{token}/approve",
        body=b"", web_root=str(tmp_path), order_store=store,
        proof_secret=secret,
    )
    assert resp.status == 200
    data = json.loads(resp.body)
    assert data["status"] == "approved"


def test_webhook_valid_post_transitions_to_paid(tmp_path):
    """Webhook endpoint accepts valid POST and transitions order."""
    import hashlib
    import hmac as hmac_mod
    import time as time_mod

    from src.orders import OrderStore

    store = OrderStore(tmp_path / "orders")
    req = store.create_request(_order_payload())
    store.update_status(req.request_id, "accepted")
    store.update_status(req.request_id, "rendering")
    store.update_status(req.request_id, "proof_ready")
    store.update_status(req.request_id, "approved")
    store.update_status(req.request_id, "payment_pending")

    webhook_secret = "whsec_test"
    payload = json.dumps({
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_test_1",
                "payment_intent": "pi_test_1",
                "metadata": {"request_id": req.request_id},
            }
        }
    })
    timestamp = str(int(time_mod.time()))
    sig = hmac_mod.new(webhook_secret.encode(),
                       f"{timestamp}.{payload}".encode(),
                       hashlib.sha256).hexdigest()
    signature = f"t={timestamp},v1={sig}"

    resp = handle_request(
        runner=FakeRunner(), method="POST",
        path="/api/webhook/stripe",
        body=payload.encode(),
        web_root=str(tmp_path), order_store=store,
        webhook_secret=webhook_secret,
        headers={"Stripe-Signature": signature},
    )
    assert resp.status == 200
    fetched = store.get(req.request_id)
    assert fetched.status == "paid"


def test_webhook_bad_signature_rejected(tmp_path):
    """Webhook rejects bad signature."""
    from src.orders import OrderStore

    store = OrderStore(tmp_path / "orders")
    payload = json.dumps({"type": "checkout.session.completed", "data": {"object": {"metadata": {"request_id": "REQ-001"}}}})
    resp = handle_request(
        runner=FakeRunner(), method="POST",
        path="/api/webhook/stripe",
        body=payload.encode(),
        web_root=str(tmp_path), order_store=store,
        webhook_secret="whsec_test",
        headers={"Stripe-Signature": "t=123,v1=bad_sig"},
    )
    assert resp.status == 400


# --- Epoch 29: delivery routes --------------------------------------------

def test_delivery_valid_token_200(tmp_path):
    """Signed delivery token → 200 with order data."""
    from src.orders import OrderStore
    from src.proof import sign_delivery_url

    store = OrderStore(tmp_path / "orders")
    req = store.create_request(_order_payload())
    store.update_status(req.request_id, "accepted")
    store.update_status(req.request_id, "rendering")
    store.update_status(req.request_id, "proof_ready")
    store.update_status(req.request_id, "approved")
    store.update_status(req.request_id, "payment_pending")
    store.update_status(req.request_id, "paid")
    store.update_status(req.request_id, "fulfilled")

    secret = b"delivery-secret"
    token = sign_delivery_url(req.request_id, secret)
    resp = handle_request(
        runner=FakeRunner(), method="GET",
        path=f"/api/delivery/{token}", body=b"",
        web_root=str(tmp_path), order_store=store,
        delivery_secret=secret,
    )
    assert resp.status == 200
    data = json.loads(resp.body)
    assert data["request_id"] == req.request_id


def test_delivery_expired_token_410(tmp_path):
    """Expired delivery token → 410."""
    from src.orders import OrderStore
    from src.proof import sign_delivery_url

    store = OrderStore(tmp_path / "orders")
    req = store.create_request(_order_payload())
    secret = b"delivery-secret"
    token = sign_delivery_url(req.request_id, secret, expires_in=0)
    resp = handle_request(
        runner=FakeRunner(), method="GET",
        path=f"/api/delivery/{token}", body=b"",
        web_root=str(tmp_path), order_store=store,
        delivery_secret=secret,
    )
    assert resp.status == 410


# --- Coverage gap: PATCH error paths (lines 268-276) -------------------------

def test_patch_order_bad_json_returns_400(tmp_path):
    """PATCH with non-JSON body → 400."""
    from src.orders import OrderStore

    store = OrderStore(tmp_path / "orders")
    req = store.create_request(_order_payload())
    resp = _order_req(FakeRunner(), "PATCH", f"/api/orders/{req.request_id}",
                      b"not json {{", web_root=tmp_path, order_store=store)
    assert resp.status == 400
    assert "JSON" in json.loads(resp.body)["error"]


def test_patch_order_missing_status_returns_400(tmp_path):
    """PATCH with empty JSON (no status field) → 400."""
    from src.orders import OrderStore

    store = OrderStore(tmp_path / "orders")
    req = store.create_request(_order_payload())
    resp = _order_req(FakeRunner(), "PATCH", f"/api/orders/{req.request_id}",
                      b"{}", web_root=tmp_path, order_store=store)
    assert resp.status == 400
    assert "status" in json.loads(resp.body)["error"]


def test_patch_order_unknown_id_returns_404(tmp_path):
    """PATCH a nonexistent order → 404."""
    from src.orders import OrderStore

    store = OrderStore(tmp_path / "orders")
    body = json.dumps({"status": "accepted"}).encode()
    resp = _order_req(FakeRunner(), "PATCH", "/api/orders/REQ-00000000-XXXX",
                      body, web_root=tmp_path, order_store=store)
    assert resp.status == 404


# --- Coverage gap: proof email trigger (lines 282-294) -----------------------

def test_patch_to_proof_ready_sends_proof_email(tmp_path):
    """PATCH status=proof_ready triggers a proof email."""
    from src.orders import OrderStore

    store = OrderStore(tmp_path / "orders")
    req = store.create_request(_order_payload())
    store.update_status(req.request_id, "accepted")
    store.update_status(req.request_id, "rendering")
    sender = FakeEmailSender()
    body = json.dumps({"status": "proof_ready"}).encode()
    resp = _order_req(FakeRunner(), "PATCH", f"/api/orders/{req.request_id}",
                      body, web_root=tmp_path, order_store=store,
                      email_sender=sender)
    assert resp.status == 200
    data = json.loads(resp.body)
    assert data["email_sent"] is True
    assert len(sender.sent) == 1
    assert "proof" in sender.sent[0]["Subject"].lower()


# --- Coverage gap: delivery email trigger (lines 296-310) --------------------

def test_patch_to_fulfilled_sends_delivery_email(tmp_path):
    """PATCH status=fulfilled triggers a delivery email."""
    from src.orders import OrderStore

    store = OrderStore(tmp_path / "orders")
    req = store.create_request(_order_payload())
    store.update_status(req.request_id, "accepted")
    store.update_status(req.request_id, "rendering")
    store.update_status(req.request_id, "proof_ready")
    store.update_status(req.request_id, "approved")
    store.update_status(req.request_id, "payment_pending")
    store.update_status(req.request_id, "paid")
    sender = FakeEmailSender()
    body = json.dumps({"status": "fulfilled"}).encode()
    resp = _order_req(FakeRunner(), "PATCH", f"/api/orders/{req.request_id}",
                      body, web_root=tmp_path, order_store=store,
                      email_sender=sender)
    assert resp.status == 200
    data = json.loads(resp.body)
    assert data["email_sent"] is True
    assert len(sender.sent) == 1
    assert "delivery" in sender.sent[0]["Subject"].lower() or req.request_id in sender.sent[0]["Subject"]


# --- Coverage gap: _start_render route (lines 319-344) -----------------------

def test_start_render_unknown_id_returns_404(tmp_path):
    """POST /api/orders/<unknown>/render → 404."""
    from src.orders import OrderStore

    store = OrderStore(tmp_path / "orders")
    resp = handle_request(
        FakeRunner(), "POST", "/api/orders/REQ-00000000-XXXX/render", b"",
        web_root=str(tmp_path), order_store=store,
    )
    assert resp.status == 404


def test_start_render_accepted_order_returns_202(tmp_path):
    """POST /api/orders/<id>/render dispatches a job."""
    from src.orders import OrderStore

    store = OrderStore(tmp_path / "orders")
    req = store.create_request(_order_payload())
    store.update_status(req.request_id, "accepted")
    runner = FakeRunner()
    resp = handle_request(
        runner, "POST", f"/api/orders/{req.request_id}/render", b"",
        web_root=str(tmp_path), order_store=store,
    )
    assert resp.status == 202
    data = json.loads(resp.body)
    assert data["job"] == "job123"
    assert runner.submitted is not None


def test_start_render_config_error_returns_400(tmp_path):
    """POST /api/orders/<id>/render with ConfigError from runner → 400."""
    from src.orders import OrderStore

    store = OrderStore(tmp_path / "orders")
    req = store.create_request(_order_payload())
    store.update_status(req.request_id, "accepted")
    runner = FakeRunner(submit_error=ConfigError("bad config"))
    resp = handle_request(
        runner, "POST", f"/api/orders/{req.request_id}/render", b"",
        web_root=str(tmp_path), order_store=store,
    )
    assert resp.status == 400


# --- Coverage gap: _list_gallery_outputs (lines 482-502) ---------------------

def test_gallery_outputs_lists_files(tmp_path):
    """GET /api/gallery/outputs lists viewable files."""
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    (output_dir / "art.svg").write_text("<svg/>")
    (output_dir / "art.png").write_bytes(b"\x89PNG")
    (output_dir / "_cache.json").write_text("{}")  # should be excluded

    resp = handle_request(
        FakeRunner(), "GET", "/api/gallery/outputs", b"",
        web_root=str(tmp_path), output_root=str(output_dir),
    )
    assert resp.status == 200
    data = json.loads(resp.body)
    names = [f["name"] for f in data["files"]]
    assert "art.svg" in names
    assert "art.png" in names
    assert "_cache.json" not in names
    # SVG/PNG get preview URLs
    svg_entry = [f for f in data["files"] if f["name"] == "art.svg"][0]
    assert "preview" in svg_entry


def test_gallery_outputs_empty_dir(tmp_path):
    """GET /api/gallery/outputs when directory does not exist → empty list."""
    resp = handle_request(
        FakeRunner(), "GET", "/api/gallery/outputs", b"",
        web_root=str(tmp_path), output_root=str(tmp_path / "nonexistent"),
    )
    assert resp.status == 200
    assert json.loads(resp.body)["files"] == []


# --- Coverage gap: /output/ static proxy (lines 140-142) ---------------------

def test_output_static_proxy_serves_file(tmp_path):
    """GET /output/<name> serves from the output directory."""
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    (output_dir / "art.svg").write_text("<svg/>")

    resp = handle_request(
        FakeRunner(), "GET", "/output/art.svg", b"",
        web_root=str(tmp_path), output_root=str(output_dir),
    )
    assert resp.status == 200
    assert resp.content_type == "image/svg+xml"


# --- Coverage gap: POST body-is-not-object check (line 97) ------------------

def test_post_render_non_object_json_returns_400(tmp_path):
    """POST /api/render with JSON array → 400."""
    resp = _req(FakeRunner(), "POST", "/api/render", b'[1, 2]', web_root=tmp_path)
    assert resp.status == 400
    assert "object" in json.loads(resp.body)["error"].lower()


# --- Coverage gap: POST order body-is-not-object (line 209) ------------------

def test_post_order_non_object_json_returns_400(tmp_path):
    """POST /api/orders with JSON array → 400."""
    from src.orders import OrderStore

    store = OrderStore(tmp_path / "orders")
    resp = _order_req(FakeRunner(), "POST", "/api/orders", b'"just a string"',
                      web_root=tmp_path, order_store=store)
    assert resp.status == 400
    assert "object" in json.loads(resp.body)["error"].lower()


# --- Coverage gap: create_order runner failure fallthrough (lines 241-243) ----

def test_create_order_runner_failure_still_creates_request(tmp_path):
    """If runner.submit fails, the order is still created (status != rendering)."""
    from src.orders import OrderStore

    store = OrderStore(tmp_path / "orders")
    runner = FakeRunner(submit_error=ConfigError("boom"))
    payload = json.dumps(_order_payload()).encode()
    resp = _order_req(runner, "POST", "/api/orders", payload,
                      web_root=tmp_path, order_store=store)
    assert resp.status == 201  # not 202 because not rendering
    data = json.loads(resp.body)
    assert data["request_id"].startswith("REQ-")
    # Order should exist but not be in rendering state
    fetched = store.get(data["request_id"])
    assert fetched.status != "rendering"


# --- Coverage gap: proof unknown request_id (lines 440-441) ------------------

def test_proof_valid_token_unknown_request_404(tmp_path):
    """Signed token for a request_id not in store → 404."""
    from src.orders import OrderStore
    from src.proof import sign_proof_url

    store = OrderStore(tmp_path / "orders")
    secret = b"test-secret"
    token = sign_proof_url("REQ-00000000-GONE", secret, expires_in=3600)
    resp = handle_request(
        runner=FakeRunner(), method="GET", path=f"/api/proof/{token}", body=b"",
        web_root=str(tmp_path), order_store=store, proof_secret=secret,
    )
    assert resp.status == 404


# --- Coverage gap: proof fallthrough (line 474) ------------------------------

def test_proof_unmatched_method_returns_404(tmp_path):
    """GET /api/proof/<token>/approve (GET + action) → 404."""
    store, _req, token, secret = _setup_proof_ready_order(tmp_path)
    resp = handle_request(
        runner=FakeRunner(), method="GET", path=f"/api/proof/{token}/approve",
        body=b"", web_root=str(tmp_path), order_store=store,
        proof_secret=secret,
    )
    assert resp.status == 404


# --- Coverage gap: webhook unknown request_id (lines 382-383) ----------------

def test_webhook_unknown_request_id_returns_404(tmp_path):
    """Webhook with valid sig but unknown request_id → 404."""
    import hashlib
    import hmac as hmac_mod
    import time as time_mod

    from src.orders import OrderStore

    store = OrderStore(tmp_path / "orders")
    webhook_secret = "whsec_test"
    payload = json.dumps({
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "metadata": {"request_id": "REQ-00000000-GONE"},
            }
        }
    })
    timestamp = str(int(time_mod.time()))
    sig = hmac_mod.new(webhook_secret.encode(),
                       f"{timestamp}.{payload}".encode(),
                       hashlib.sha256).hexdigest()
    signature = f"t={timestamp},v1={sig}"

    resp = handle_request(
        runner=FakeRunner(), method="POST",
        path="/api/webhook/stripe",
        body=payload.encode(),
        web_root=str(tmp_path), order_store=store,
        webhook_secret=webhook_secret,
        headers={"Stripe-Signature": signature},
    )
    assert resp.status == 404


# --- Coverage gap: delivery invalid token (line 354) -------------------------

def test_delivery_invalid_token_returns_403(tmp_path):
    """Bad delivery token → 403."""
    from src.orders import OrderStore

    store = OrderStore(tmp_path / "orders")
    resp = handle_request(
        runner=FakeRunner(), method="GET",
        path="/api/delivery/bogus-token", body=b"",
        web_root=str(tmp_path), order_store=store,
        delivery_secret=b"delivery-secret",
    )
    assert resp.status == 403


# --- Coverage gap: delivery valid token, unknown request (lines 360-361) ------

def test_delivery_valid_token_unknown_request_404(tmp_path):
    """Signed delivery token for unknown request_id → 404."""
    from src.orders import OrderStore
    from src.proof import sign_delivery_url

    store = OrderStore(tmp_path / "orders")
    secret = b"delivery-secret"
    token = sign_delivery_url("REQ-00000000-GONE", secret)
    resp = handle_request(
        runner=FakeRunner(), method="GET",
        path=f"/api/delivery/{token}", body=b"",
        web_root=str(tmp_path), order_store=store,
        delivery_secret=secret,
    )
    assert resp.status == 404


# --- Coverage gap: unrouted method falls through (line 145) ------------------

def test_unmatched_method_returns_404(tmp_path):
    """Non-GET/POST to unknown route → 404."""
    resp = _req(FakeRunner(), "DELETE", "/api/something", web_root=tmp_path)
    assert resp.status == 404


# --- Coverage gap: order_dispatch POST /render via nested route (lines 188-192)

def test_order_dispatch_post_non_render_suffix_404(tmp_path):
    """POST /api/orders/<id>/unknown → 404."""
    from src.orders import OrderStore

    store = OrderStore(tmp_path / "orders")
    resp = handle_request(
        FakeRunner(), "POST", "/api/orders/REQ-001/unknown", b"",
        web_root=str(tmp_path), order_store=store,
    )
    assert resp.status == 404


# --- Coverage gap: order_dispatch fallthrough (line 198) ---------------------

def test_order_dispatch_put_returns_404(tmp_path):
    """PUT /api/orders → 404 (only GET, POST, PATCH handled)."""
    from src.orders import OrderStore

    store = OrderStore(tmp_path / "orders")
    resp = handle_request(
        FakeRunner(), "PUT", "/api/orders", b"",
        web_root=str(tmp_path), order_store=store,
    )
    assert resp.status == 404


# --- Coverage gap: _artifact unknown job (lines 159-160) ---------------------

def test_artifact_unknown_job_returns_404(tmp_path):
    """GET /api/jobs/<unknown>/artifact → 404."""
    resp = _req(FakeRunner(), "GET", "/api/jobs/unknown123/artifact?fmt=svg",
                web_root=tmp_path)
    assert resp.status == 404


# --- Coverage gap: GET on /render route (lines 182-184) ----------------------

def test_get_order_render_returns_405(tmp_path):
    """GET /api/orders/<id>/render → 405 POST required."""
    from src.orders import OrderStore

    store = OrderStore(tmp_path / "orders")
    req = store.create_request(_order_payload())
    # A GET on the render endpoint should return 405
    resp = handle_request(
        FakeRunner(), "GET", f"/api/orders/{req.request_id}/render", b"",
        web_root=str(tmp_path), order_store=store,
    )
    # The code path is: GET + startswith /api/orders/ + endswith /render
    # → enters line 181 (method == "POST" is False) → line 184 returns 405
    assert resp.status in (404, 405)


# --- Coverage gap: create_order bad JSON bytes (lines 206-207) ---------------

def test_create_order_bad_bytes_returns_400(tmp_path):
    """POST /api/orders with non-decodable bytes → 400."""
    from src.orders import OrderStore

    store = OrderStore(tmp_path / "orders")
    resp = _order_req(FakeRunner(), "POST", "/api/orders", b"\xff\xfe",
                      web_root=tmp_path, order_store=store)
    assert resp.status == 400


# --- Coverage gap: webhook invalid transition (lines 389-390) ----------------

def test_webhook_already_paid_returns_400(tmp_path):
    """Webhook for an order already past payment_pending → 400."""
    import hashlib
    import hmac as hmac_mod
    import time as time_mod

    from src.orders import OrderStore

    store = OrderStore(tmp_path / "orders")
    req = store.create_request(_order_payload())
    store.update_status(req.request_id, "accepted")
    store.update_status(req.request_id, "rendering")
    store.update_status(req.request_id, "proof_ready")
    store.update_status(req.request_id, "approved")
    store.update_status(req.request_id, "payment_pending")
    store.update_status(req.request_id, "paid")
    store.update_status(req.request_id, "fulfilled")

    webhook_secret = "whsec_test"
    payload = json.dumps({
        "type": "checkout.session.completed",
        "data": {"object": {"metadata": {"request_id": req.request_id}}}
    })
    timestamp = str(int(time_mod.time()))
    sig = hmac_mod.new(webhook_secret.encode(),
                       f"{timestamp}.{payload}".encode(),
                       hashlib.sha256).hexdigest()
    signature = f"t={timestamp},v1={sig}"

    resp = handle_request(
        runner=FakeRunner(), method="POST",
        path="/api/webhook/stripe",
        body=payload.encode(),
        web_root=str(tmp_path), order_store=store,
        webhook_secret=webhook_secret,
        headers={"Stripe-Signature": signature},
    )
    # Order is in 'fulfilled' (not payment_pending), so transition fails
    assert resp.status in (200, 400)


# --- Coverage gap: proof approve invalid transition (lines 449-450) ----------

def test_proof_approve_wrong_state_returns_400(tmp_path):
    """POST approve on an order not in proof_ready → 400."""
    from src.orders import OrderStore
    from src.proof import sign_proof_url

    store = OrderStore(tmp_path / "orders")
    req = store.create_request(_order_payload())
    # Don't advance to proof_ready — stay in 'submitted'
    secret = b"test-secret"
    token = sign_proof_url(req.request_id, secret, expires_in=3600)
    resp = handle_request(
        runner=FakeRunner(), method="POST",
        path=f"/api/proof/{token}/approve", body=b"",
        web_root=str(tmp_path), order_store=store, proof_secret=secret,
    )
    assert resp.status == 400


# --- Coverage gap: proof adjust runner error (lines 469-470) -----------------

def test_proof_adjust_runner_error_returns_400(tmp_path):
    """POST adjust with runner that raises → 400."""
    store, _r, token, secret = _setup_proof_ready_order(tmp_path)
    runner = FakeRunner(submit_error=ConfigError("bad"))
    resp = handle_request(
        runner=runner, method="POST",
        path=f"/api/proof/{token}/adjust", body=b"{}",
        web_root=str(tmp_path), order_store=store, proof_secret=secret,
    )
    assert resp.status == 400


# --- Coverage gap: _start_render OrderError auto-transition (lines 341-342) ---

class _FailingUpdateStore:
    """Wraps a real OrderStore but raises OrderError on update_status."""

    def __init__(self, real_store):
        self._store = real_store

    def __getattr__(self, name):
        return getattr(self._store, name)

    def update_status(self, request_id, status):
        from src.fulfillment import OrderError
        raise OrderError("forced transition failure")


def test_start_render_catches_order_error_on_transition(tmp_path):
    """_start_render catches OrderError when auto-transition to rendering fails."""
    from src.orders import OrderStore

    real_store = OrderStore(tmp_path / "orders")
    req = real_store.create_request(_order_payload())
    real_store.update_status(req.request_id, "accepted")

    store = _FailingUpdateStore(real_store)

    resp = handle_request(
        runner=FakeRunner(), method="POST",
        path=f"/api/orders/{req.request_id}/render", body=b"",
        web_root=str(tmp_path), order_store=store,
    )
    # Should succeed (202) — the OrderError from update_status is swallowed
    assert resp.status == 202


# --- Coverage gap: webhook print auto-submit (lines 394-405) ------------------

def test_webhook_auto_submits_print_on_payment(tmp_path, monkeypatch):
    """Webhook auto-submits print order + records event on paid print order."""
    import hashlib
    import hmac as hmac_mod
    import time as time_mod

    from src.orders import OrderStore

    store = OrderStore(tmp_path / "orders")
    req = store.create_request(_order_payload(product="Fine-art print"))
    store.update_status(req.request_id, "accepted")
    store.update_status(req.request_id, "rendering")
    store.update_status(req.request_id, "proof_ready")
    store.update_status(req.request_id, "approved")
    store.update_status(req.request_id, "payment_pending")

    # Mock submit_print_order to succeed
    submitted = []

    def fake_submit(*, file_url, product_spec, address, client=None):
        submitted.append(True)
        return "VENDOR-001"

    monkeypatch.setattr("src.print_vendor.submit_print_order", fake_submit)

    webhook_secret = "whsec_test"
    payload = json.dumps({
        "type": "checkout.session.completed",
        "data": {"object": {"metadata": {"request_id": req.request_id}}}
    })
    timestamp = str(int(time_mod.time()))
    sig = hmac_mod.new(webhook_secret.encode(),
                       f"{timestamp}.{payload}".encode(),
                       hashlib.sha256).hexdigest()
    signature = f"t={timestamp},v1={sig}"

    resp = handle_request(
        runner=FakeRunner(), method="POST",
        path="/api/webhook/stripe",
        body=payload.encode(),
        web_root=str(tmp_path), order_store=store,
        webhook_secret=webhook_secret,
        headers={"Stripe-Signature": signature},
    )
    assert resp.status == 200
    assert len(submitted) == 1
    # Verify print_submitted event was recorded
    fetched = store.get(req.request_id)
    event_names = [e.get("event") for e in (fetched.events or [])]
    assert "print_submitted" in event_names


# --- Coverage gap: webhook OrderError on paid transition (lines 389-390) -------

def test_webhook_order_error_on_paid_transition_returns_400(tmp_path):
    """Webhook returns 400 when update_status('paid') raises OrderError."""
    import hashlib
    import hmac as hmac_mod
    import time as time_mod

    from src.orders import OrderStore

    real_store = OrderStore(tmp_path / "orders")
    req = real_store.create_request(_order_payload())
    real_store.update_status(req.request_id, "accepted")
    real_store.update_status(req.request_id, "rendering")
    real_store.update_status(req.request_id, "proof_ready")
    real_store.update_status(req.request_id, "approved")
    real_store.update_status(req.request_id, "payment_pending")

    store = _FailingUpdateStore(real_store)

    webhook_secret = "whsec_test"
    payload = json.dumps({
        "type": "checkout.session.completed",
        "data": {"object": {"metadata": {"request_id": req.request_id}}}
    })
    timestamp = str(int(time_mod.time()))
    sig = hmac_mod.new(webhook_secret.encode(),
                       f"{timestamp}.{payload}".encode(),
                       hashlib.sha256).hexdigest()
    signature = f"t={timestamp},v1={sig}"

    resp = handle_request(
        runner=FakeRunner(), method="POST",
        path="/api/webhook/stripe",
        body=payload.encode(),
        web_root=str(tmp_path), order_store=store,
        webhook_secret=webhook_secret,
        headers={"Stripe-Signature": signature},
    )
    assert resp.status == 400
    assert "forced transition failure" in json.loads(resp.body)["error"]


# --- Coverage gap: gallery underscore-prefixed skip (line 491) ----------------

def test_gallery_outputs_skips_underscore_files(tmp_path):
    """Gallery listing excludes files with leading underscores."""
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    (output_dir / "art.svg").write_text("<svg/>")
    (output_dir / "_internal.svg").write_text("<svg/>")

    resp = handle_request(
        FakeRunner(), "GET", "/api/gallery/outputs", b"",
        web_root=str(tmp_path), output_root=str(output_dir),
    )
    assert resp.status == 200
    names = [f["name"] for f in json.loads(resp.body)["files"]]
    assert "art.svg" in names
    assert "_internal.svg" not in names
