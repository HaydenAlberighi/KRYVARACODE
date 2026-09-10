from src.core.metrics import render_metrics


def test_metrics_endpoint_reports_prometheus(client, auth_headers):
    client.get("/health")
    r = client.get("/api/v1/metrics", headers=auth_headers)
    assert r.status_code == 200
    assert "text/plain" in r.headers["content-type"]
    assert "kryvaracode_requests_total" in r.text


def test_render_metrics_available():
    assert render_metrics() is not None
