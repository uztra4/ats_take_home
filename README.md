# Service Reliability Monitor

Lightweight service monitoring app built with FastAPI, SQLite, and a minimal auto-refreshing dashboard.

## Features
- Periodic service checks from JSON config
- Captures availability, latency, HTTP status, and observed version
- Persists all checks to SQLite, could be downloaded as csv
- Version drift detection
- Simple repeated-failure console alerting
- Docker and docker-compose support
- Addition of services (single or JSON file)

## Quickstart (local)
1. Create project folders exactly as shown in the structure.
2. Put the file contents into the matching files.
3. Create a virtual environment:
   - `python -m venv .venv`
   - Linux/macOS: `source .venv/bin/activate`
   - Windows PowerShell: `.venv\\Scripts\\Activate.ps1`
4. Install dependencies: `pip install -r requirements.txt`
5. Update `data/services.json` with real service URLs and expected versions.
6. Run the app: `uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`
7. Open `http://localhost:8000`

## Quickstart (Docker)
1. Build image: `docker build -t service-reliability-monitor .`
2. Run container: `docker run --rm -p 8000:8000 -v ${PWD}/data:/app/data service-reliability-monitor`
3. Open `http://localhost:8000`

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
- Mainly to assist with the architecture
- Debugging