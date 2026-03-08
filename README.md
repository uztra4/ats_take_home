# Service Reliability Monitor (ATS Take-Home)

A lightweight service reliability solution that periodically checks multiple service endpoints, detects availability/version issues, and displays the latest health information in a simple auto-refreshing dashboard.

---

## What this app does (mapped to requirements)

1. **Accept a list/configuration of services** (`name`, `url`, `expected_version`)
   - Add a single service via API/UI: `POST /api/services`
   - Bulk import via JSON/CSV upload: `POST /api/services/import`
   - Config stored in `data/services.json`

2. **Periodically ping each service and record status, latency, version (if available)**
   - Background monitor task starts on app startup (`lifespan()`)
   - Polls every `CHECK_INTERVAL_SECONDS` (defined in `checker.py`)
   - Persists each check with:
     - status (`healthy` / `degraded` / `down`)
     - latency (ms)
     - HTTP status code
     - observed version (headers/JSON fields when available)
     - version drift flag

3. **Store results persistently**
   - Uses SQLite via SQLAlchemy ORM
   - Database file: `data/monitor.db`
   - Tables created automatically on startup (`Base.metadata.create_all(...)`)

4. **Expose results through a minimal API and dashboard**
   - Dashboard: `GET /` (HTML)
   - API endpoints listed below
   - Dashboard auto-refreshes using JS polling of `/api/services/latest`

5. **Provide Docker support**
   - Dockerfile and docker-compose included

---

## Stretch goals included

- Environment field per service (stored in config and returned in API)
- Simple alerting (console/webhook) on repeated failures (implemented in `checker.py`)
- AI-generated incident summary (past hour): `GET /api/incidents/summary`

---

## Configuration

### Required fields (core)
- `name`
- `url`
- `expected_version`

### Optional
- `environment`

### Example `data/services.json`
```json
[
  {
    "name": "orders-api",
    "url": "https://example.com/orders/health",
    "expected_version": "1.2.0",
    "environment": "production"
  }
]
```

CSV import must contain headers:

* `name,url,expected_version` (and optional `environment`)

---

## AI + Environment Variables

This project uses environment variables for:

* AI incident summary
* alerting mode/webhook

### Option A (recommended): `.env` file in project root

Example `.env`:

```env
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4.1-mini
ALERT_MODE=webhook
ALERT_WEBHOOK_URL=https://your-webhook-url
```

`main.py` loads this automatically:

* `load_dotenv()` is called at startup.

**Security**: add `.env` to `.gitignore` so secrets are not committed.

---

## Quickstart (Local)

1. Create and activate venv:

   * `python -m venv .venv`
   * Linux/macOS: `source .venv/bin/activate`
   * Windows PowerShell: `.venv\Scripts\Activate.ps1`

2. Install dependencies:

   * `pip install -r requirements.txt`

3. Ensure `data/services.json` exists (example: `[]`).

4. Create `.env` (recommended) or export env vars.

5. Run:

   * `uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`

6. Open:

   * `http://localhost:8000`

---

## Quickstart (Docker)

Build:

* `docker build -t service-reliability-monitor .`

Run (Linux/macOS):

```bash
docker run --rm -p 8000:8000 \
  --env-file .env \
  -v $(pwd)/data:/app/data \
  service-reliability-monitor
```

Run (Windows PowerShell):

```powershell
docker run --rm -p 8000:8000 `
  --env-file .env `
  -v ${PWD}/data:/app/data `
  service-reliability-monitor
```

Open:

* `http://localhost:8000`

---

## Quickstart (docker-compose)

Recommended for reviewers:

* `docker compose up --build`
* Open: `http://localhost:8000`
* Stop: `docker compose down`

Ensure your `docker-compose.yml` includes:

```yaml
env_file:
  - .env
volumes:
  - ./data:/app/data
```

---

## API Endpoints

### UI

* `GET /` — Dashboard HTML

### Health

* `GET /api/health` — App health check

### Configuration

* `GET /api/config/services` — List configured services from `services.json`
* `POST /api/services` — Add a single service (multipart form fields: `name`, `url`, `expected_version`, `environment`)
* `POST /api/services/import` — Import services from JSON/CSV upload (`file`)
* `DELETE /api/services/{service_name}` — Remove a service from configuration

### Monitoring results

* `GET /api/services/latest` — Latest status snapshot and summary

  * Returns: `{ summary, services, timestamp }`
* `GET /api/services/history/{service_name}` — Last 50 checks for a service

### Export

* `GET /api/export/checks.csv` — Export all persisted check records to CSV

### AI Incident Summary

* `GET /api/incidents/summary` — AI summary for past hour

  * Returns JSON: `{ "summary": "..." }`
  * On failure returns JSON error: `{ "detail": "..." }` (HTTP 500)

---

## Notes / Known limitations

* `/api/services/latest` currently selects the first row per service after ordering by `service_name`, which may not always represent the most recent check if the DB contains multiple records per service. A more correct implementation would order by `checked_at DESC` and pick the first record per service.
* CSV export currently exports the full dataset; time-range filters can be added as an enhancement.
* AI incident summary requires `OPENAI_API_KEY` and compatible dependency versions.

---

## Infrastructure Note (≤300 words)

In production, I would containerize the FastAPI app and run it behind a reverse proxy/load balancer that terminates TLS (e.g., Nginx/ALB). For a single-node deployment, Docker Compose is sufficient; for higher availability, I would run it on ECS or Kubernetes. If scaling beyond a small number of endpoints, I would split the background checker into a dedicated worker (separate deployment) so API/UI performance remains predictable.

SQLite is appropriate for a single-node demo; for production multi-replica deployments I would migrate to managed Postgres and add retention (e.g., keep raw checks for N days) plus indexes on `(service_name, checked_at)`. For observability, I would emit structured logs (service_name, status, latency, error type) and export metrics (checks run, failures by status, latency histograms, webhook alert counts, and a monitor-loop heartbeat) to Prometheus. Alerting would cover “service down for X minutes”, “high latency p95”, “monitor loop stopped”, and webhook delivery failures. This provides clear operational visibility while keeping the system minimal and maintainable.

---

## AI usage

AI was used to assist with architecture/scaffolding, debugging dependency issues, and documentation.