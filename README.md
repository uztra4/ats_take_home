# Service Reliability Monitor

## Description 
Lightweight service monitoring app built with FastAPI, SQLite, and a minimal auto-refreshing dashboard. This refreshes the status of every services every 15s. Currently it sends alert via console if the status is down or degraded. It is also organized into environment namely Production, Sandbox and Staging

## Features
- Periodic service checks from JSON config
- Captures availability, latency, HTTP status, and observed version
- Persists all checks to SQLite, could be downloaded as csv
- Version drift detection
- Simple repeated-failure console alerting
- Docker and docker-compose support
- Addition of services (single or JSON file)
- Deletion of services at the side bar

## Quickstart (local)
1. Create a virtual environment:
   - `python -m venv .venv`
   - Linux/macOS: `source .venv/bin/activate`
   - Windows PowerShell: `.venv/bin/activate`
2. Install dependencies: `pip install -r requirements.txt`
3. Run the app: `uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`
4. Open `http://localhost:8000`

## Quickstart (Docker)
1. Build image: `docker build -t service-reliability-monitor .`
2. Run container: `docker run --rm -p 8000:8000 -v ${PWD}/data:/app/data service-reliability-monitor`
3. Open `http://localhost:8000`

## Deployment and Monitoring in Prod
A production deployment would package the FastAPI app as a container and run it behind a reverse proxy or load balancer that terminates HTTPS. FastAPI’s production guidance recommends using a production ASGI server and typically placing a termination proxy in front of the app. For a small single-server setup, I would deploy with Docker Compose using a production override file; Docker’s docs describe Compose as suitable for production deployments on a single server and for rebuilding/restarting only the updated service.

For persistence, I would move from local SQLite to a managed Postgres instance if multi-replica deployment or stricter durability were needed. I would keep environment variables and secrets outside the image, and use health checks plus rolling restarts during upgrades. For monitoring, I would expose application metrics such as check latency, service status counts, webhook alert counts, and background loop health, then scrape them with Prometheus. Prometheus is designed for numeric time-series monitoring in dynamic service environments, and Alertmanager can deduplicate, group, and route alerts to receivers such as email or on-call tools.

For deeper observability, I would instrument the FastAPI service with OpenTelemetry and export traces, metrics, and logs via OTLP to a collector/backend. OpenTelemetry’s Python docs support both manual instrumentation and zero-code/auto-instrumentation, which would make it straightforward to trace API requests, background polling, and outbound HTTP checks.

This gives a practical production stack: reverse proxy + containerized FastAPI service + managed database + Prometheus/Alertmanager + OpenTelemetry-backed tracing/logging.

## API
- GET /
- GET /api/health
- GET /api/config/services
- POST /api/services
- POST /api/services/import
- GET /api/services/latest
- GET /api/services/history/{service_name}
- DELETE /api/services/{service_name}
- GET /api/export/checks.csv
- GET /api/incidents/summary

## Persistence and why it is lightweight
- The app uses SQLite for persistence via SQLAlchemy ORM.
- The database file is created locally at `data/monitor.db`.
- There are no raw SQL files in the repo because SQLAlchemy generates the SQL from the Python models.
- Table creation is handled automatically on startup through `Base.metadata.create_all(bind=engine)`.
- Check results are inserted using ORM operations such as `db.add(...)` and `db.commit()`.
- This supports the lightweight design because it avoids running a separate database server while still giving persistent historical records for service checks.

## Improvements
- AI review summary 
- Filter on the tables

## AI usage
- Assist with the architecture brainstorm
- Debugging
- README summary

## Screenshot of the page
<img width="1167" height="500" alt="image" src="https://github.com/user-attachments/assets/a90596c9-741f-4220-bdcd-d56d5825fd7c" />

