"""Tests for the local HTTP routing layer (roadmap #27, Task Group 2).

`handle_request` is a pure dispatcher, so these exercise it directly with a fake
runner and a temp web root — no sockets, network, or datasets.
"""

from __future__ import annotations

import json

import pytest

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
    assert resp.status == 201
    data = json.loads(resp.body)
    assert data["request_id"].startswith("REQ-")
    assert data["status"] == "submitted"
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
