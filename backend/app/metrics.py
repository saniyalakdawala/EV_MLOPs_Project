"""Prometheus metrics shared across backend entry-point import modes."""

from prometheus_client import Counter, Histogram


HTTP_REQUESTS = Counter(
    "voltgrid_http_requests_total",
    "HTTP requests",
    ["method", "path", "status"],
)
HTTP_LATENCY = Histogram(
    "voltgrid_http_request_duration_seconds",
    "HTTP request duration",
    ["method", "path"],
)
