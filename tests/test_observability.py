"""Slice 20 — /metrics exposition + X-Request-ID round-trip."""

from __future__ import annotations


def test_metrics_endpoint_exposes_prometheus_format(client) -> None:
    r = client.get("/metrics")
    assert r.status_code == 200
    ct = r.headers.get("content-type", "")
    assert ct.startswith("text/plain")
    body = r.text
    # Every counter/histogram we defined should have a HELP line.
    for name in ("requests_total", "battles_total", "summons_total", "request_duration_seconds"):
        assert f"# HELP {name}" in body, f"missing metric {name} in /metrics output"


def test_metrics_counter_increments_on_traffic(client) -> None:
    # Drive a well-known endpoint, then confirm the counter moved.
    client.get("/healthz")
    client.get("/healthz")
    body = client.get("/metrics").text
    # Line looks like: requests_total{method="GET",path="/healthz",status="200"} 2.0
    health_lines = [ln for ln in body.splitlines() if ln.startswith('requests_total{') and '"/healthz"' in ln]
    assert health_lines, f"no /healthz line in metrics:\n{body}"
    # At least one line should reflect a value >= 2.
    assert any(float(ln.rsplit(" ", 1)[-1]) >= 2 for ln in health_lines)


def test_request_id_is_generated_when_absent(client) -> None:
    r = client.get("/healthz")
    rid = r.headers.get("X-Request-ID", "")
    assert rid and len(rid) >= 8


def test_request_id_is_echoed_when_provided(client) -> None:
    r = client.get("/healthz", headers={"X-Request-ID": "test-rid-abc123"})
    assert r.headers.get("X-Request-ID") == "test-rid-abc123"


def test_root_redirects_to_static_app(client) -> None:
    r = client.get("/", follow_redirects=False)
    assert r.status_code in (302, 307)
    assert r.headers["location"].startswith("/app")


def test_static_html_client_is_served(client) -> None:
    r = client.get("/app/")
    assert r.status_code == 200
    body = r.text
    for marker in ("hero-proto", "heroproto_jwt", "/auth/register"):
        assert marker in body, f"missing marker: {marker!r}"


def test_request_id_overlong_input_is_replaced(client) -> None:
    junk = "x" * 500
    r = client.get("/healthz", headers={"X-Request-ID": junk})
    echoed = r.headers.get("X-Request-ID", "")
    assert echoed and echoed != junk and len(echoed) <= 128
