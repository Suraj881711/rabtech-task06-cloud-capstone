# Monitoring Guide — Task 06 Capstone

How the deployed service is watched: **Prometheus** scrapes application
metrics, **Grafana** visualises them, and a **free uptime checker** probes
the public `/health` endpoint from outside and sends alert notifications
if the service goes down.

```
                        scrape /metrics (every 15s)
  ┌────────────┐  ───────────────────────────►  ┌──────────────────┐
  │  Capstone  │                                 │   Prometheus     │
  │  Flask app │  ◄───────────────────────────   │   :9090          │
  │  /health   │        up == 0 → ServiceDown    │   + alert rules  │
  │  /metrics  │        alert (alert-rules.yml)  └────────┬─────────┘
  └─────▲──────┘                                          │ query
        │ GET /health every 5 min                         ▼
  ┌─────┴───────────────┐                          ┌────────────┐
  │  Uptime checker     │   email alert on DOWN    │  Grafana   │
  │  (e.g. UptimeRobot) ├──────────────────►  you  │ dashboards │
  └─────────────────────┘                          └────────────┘
```

---

## 1. What the application exposes

| Endpoint   | Content |
|------------|---------|
| `/health`  | `{"status": "ok"}` — liveness probe used by Docker, Render and the uptime checker. |
| `/metrics` | Prometheus text format: `http_requests_total` counter (labels: method, endpoint, status) and `process_uptime_seconds` gauge. |

## 2. Prometheus scrape

Configuration: [`prometheus.yml`](prometheus.yml) — job `rabtech-capstone`,
path `/metrics`, 15-second interval. Alert rules:
[`alert-rules.yml`](alert-rules.yml).

Run Prometheus locally (Docker) against a locally running app:

```bash
# 1. Start the app
docker build -t rabtech-capstone ..
docker run -d --name capstone -p 8000:8000 rabtech-capstone

# 2. Start Prometheus with this folder's config mounted in
docker run -d --name prometheus -p 9090:9090 \
  -v "$PWD/prometheus.yml:/etc/prometheus/prometheus.yml" \
  -v "$PWD/alert-rules.yml:/etc/prometheus/alert-rules.yml" \
  prom/prometheus

# 3. Open http://localhost:9090/targets — job "rabtech-capstone" must be UP
```

Useful queries (PromQL):

```promql
up{job="rabtech-capstone"}                        # 1 = reachable, 0 = down
rate(http_requests_total[5m])                      # requests per second
sum by (status) (rate(http_requests_total[5m]))    # traffic by HTTP status
process_uptime_seconds                             # seconds since start
```

### Alerts

| Alert | Condition | Severity |
|-------|-----------|----------|
| `ServiceDown` | `up == 0` for 1 minute (target unreachable) | critical |
| `MetricsMissing` | `http_requests_total` absent for 2 minutes | warning |

With an Alertmanager target configured in `prometheus.yml`, Prometheus
forwards firing alerts for email/Slack delivery. For this capstone the
hosted uptime checker (section 4) is the primary notification channel, so
no self-hosted Alertmanager is required.

## 3. Grafana dashboard notes

1. Run Grafana: `docker run -d -p 3000:3000 grafana/grafana`
   (default login `admin` / `admin`).
2. **Connections → Data sources → Add Prometheus** → URL
   `http://host.docker.internal:9090` → Save & test.
3. **Dashboards → New → Import** (or build manually) with these panels:
   - **Uptime status** — Stat panel, query `up{job="rabtech-capstone"}`,
     value mapping 1 = UP (green), 0 = DOWN (red).
   - **Request rate** — Time series, `sum(rate(http_requests_total[5m]))`.
   - **Requests by status** — Time series,
     `sum by (status) (rate(http_requests_total[5m]))` — watch the 5xx line.
   - **Process uptime** — Stat, `process_uptime_seconds` (unit: seconds →
     duration). A sudden drop to ~0 means the service restarted.
4. Save the dashboard as **"Capstone — Service Overview"**.

## 4. Uptime monitoring & health-check alerts (external)

Prometheus watches from inside; an external checker watches the public
URL the way a real user would see it — including DNS, TLS and the hosting
platform itself. Setup with a free checker (UptimeRobot free plan shown;
any equivalent works):

1. Sign up at <https://uptimerobot.com> (free plan: 50 monitors, 5-minute
   interval — sufficient here).
2. **Add New Monitor**
   - Monitor Type: **HTTP(s)**
   - Friendly Name: `RabTech Capstone`
   - URL: `https://<your-app>.onrender.com/health`
   - Monitoring Interval: 5 minutes
3. **Alert Contacts** → add your email address and tick it on the monitor.
   You now get an email when the monitor goes **DOWN** and another when it
   recovers (**UP**).
4. Optional keyword check: switch the monitor type to **Keyword**, point it
   at `/health` and require the keyword `"ok"` — this catches a service
   that responds 200 but returns the wrong body.
5. Note: free Render services spin down after inactivity, so the first
   probe after idle may be slow (cold start ~30–60 s) — set the monitor
   timeout accordingly and expect an occasional slow-response reading,
   not necessarily a real outage.

## 5. Who alerts whom — summary

| Layer | Tool | Signal | Notification |
|-------|------|--------|--------------|
| Container | Docker `HEALTHCHECK` | `/health` inside the container | Container marked unhealthy |
| Platform | Render `healthCheckPath: /health` | Deploy/runtime health | Failed deploys don't go live |
| Metrics | Prometheus + alert rules | `up == 0`, missing metrics | Alertmanager (optional) |
| External | UptimeRobot (free) | Public `/health` every 5 min | **Email on down/recovery** |
