"""
app.py — RabTech Academy Internship, Task 06 Capstone
Cloud Infrastructure Deployment & Monitoring

A small, self-contained Flask service designed to be containerised and
deployed to a Docker hosting platform (e.g. Render).

Endpoints
---------
GET /         Service info JSON (name, environment, version, endpoints)
GET /health   Health check -> {"status": "ok"}   (used by Docker
              HEALTHCHECK, Render healthCheckPath and uptime monitors)
GET /metrics  Prometheus text exposition format:
                * http_requests_total  (counter, per method/endpoint/status)
                * process_uptime_seconds (gauge)

Configuration is read from environment variables (12-factor style):
    APP_NAME  service name        (default "rabtech-capstone")
    APP_ENV   environment label   (default "development")
    PORT      listen port for the built-in dev server (default 8000);
              in production gunicorn binds $PORT (see Dockerfile).
"""

import os
import threading
import time
from collections import defaultdict

from flask import Flask, jsonify, Response, request

# --------------------------------------------------------------------------
# Configuration (environment variables, with safe defaults)
# --------------------------------------------------------------------------
APP_NAME = os.environ.get("APP_NAME", "rabtech-capstone")
APP_ENV = os.environ.get("APP_ENV", "development")
VERSION = "1.0.0"

START_TIME = time.time()

app = Flask(__name__)

# --------------------------------------------------------------------------
# Metrics state — a simple in-process counter store, incremented in
# after_request so the final status code is known. /metrics itself is not
# counted, otherwise every Prometheus scrape would inflate the numbers.
# --------------------------------------------------------------------------
_lock = threading.Lock()
_request_counts = defaultdict(int)  # (method, endpoint, status) -> count


@app.after_request
def count_request(response):
    if request.path != "/metrics":
        key = (request.method, request.path, str(response.status_code))
        with _lock:
            _request_counts[key] += 1
    return response


# --------------------------------------------------------------------------
# Endpoints
# --------------------------------------------------------------------------
@app.get("/")
def index():
    return jsonify(
        service=APP_NAME,
        environment=APP_ENV,
        version=VERSION,
        status="running",
        endpoints={
            "health": "/health",
            "metrics": "/metrics",
        },
    )


@app.get("/health")
def health():
    return jsonify(status="ok")


@app.get("/metrics")
def metrics():
    uptime_seconds = time.time() - START_TIME

    lines = [
        "# HELP http_requests_total Total number of HTTP requests processed.",
        "# TYPE http_requests_total counter",
    ]
    with _lock:
        snapshot = dict(_request_counts)
    for (method, endpoint, status), count in sorted(snapshot.items()):
        lines.append(
            'http_requests_total{{method="{}",endpoint="{}",status="{}"}} {}'.format(
                method, endpoint, status, count
            )
        )

    lines += [
        "# HELP process_uptime_seconds Time in seconds since the service started.",
        "# TYPE process_uptime_seconds gauge",
        "process_uptime_seconds {:.3f}".format(uptime_seconds),
        "",
    ]

    return Response("\n".join(lines), mimetype="text/plain; version=0.0.4")


# --------------------------------------------------------------------------
# Local development entry point (production uses gunicorn — see Dockerfile)
# --------------------------------------------------------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    app.run(host="0.0.0.0", port=port)
