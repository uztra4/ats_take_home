import csv
import json
from io import StringIO
from pathlib import Path

SERVICES_FILE = Path("data/services.json")
REQUIRED_KEYS = {"name", "url", "expected_version", "environment"}


def normalize_service(service: dict) -> dict:
    return {
        "name": str(service["name"]).strip(),
        "url": str(service["url"]).strip(),
        "expected_version": str(service.get("expected_version", "")).strip(),
        "environment": str(service.get("environment", "default")).strip()
        }    


def validate_service(service: dict) -> dict:
    missing = REQUIRED_KEYS - set(service.keys())
    if missing:
        raise ValueError(f"Service config missing keys {missing}: {service}")

    normalized = normalize_service(service)

    if not normalized["name"]:
        raise ValueError("Service name cannot be empty")
    if not normalized["url"]:
        raise ValueError("Service URL cannot be empty")

    return normalized


def load_services() -> list[dict]:
    if not SERVICES_FILE.exists():
        SERVICES_FILE.parent.mkdir(parents=True, exist_ok=True)
        SERVICES_FILE.write_text("[]", encoding="utf-8")

    with SERVICES_FILE.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError("services.json must contain a list of services")

    return [validate_service(svc) for svc in data]


def save_services(services: list[dict]) -> None:
    SERVICES_FILE.parent.mkdir(parents=True, exist_ok=True)
    with SERVICES_FILE.open("w", encoding="utf-8") as f:
        json.dump(services, f, indent=2)


def add_service(service: dict) -> dict:
    validated = validate_service(service)
    services = load_services()

    for existing in services:
        if existing["name"].lower() == validated["name"].lower():
            raise ValueError(f"Service name already exists: {validated['name']}")
        if existing["url"].lower() == validated["url"].lower():
            raise ValueError(f"Service URL already exists: {validated['url']}")

    services.append(validated)
    save_services(services)
    return validated


def parse_uploaded_json(raw_bytes: bytes) -> list[dict]:
    data = json.loads(raw_bytes.decode("utf-8"))
    if not isinstance(data, list):
        raise ValueError("JSON upload must contain a list of services")
    return [validate_service(item) for item in data]


def parse_uploaded_csv(raw_bytes: bytes) -> list[dict]:
    text = raw_bytes.decode("utf-8-sig")
    reader = csv.DictReader(StringIO(text))

    required = {"name", "url", "expected_version"}
    headers = set(reader.fieldnames or [])
    missing = required - headers
    if missing:
        raise ValueError(f"CSV missing required columns: {missing}")

    services = []
    for row in reader:
        services.append(validate_service(row))
    return services


def import_services(new_services: list[dict]) -> int:
    services = load_services()
    existing_names = {s["name"].lower() for s in services}
    existing_urls = {s["url"].lower() for s in services}

    added = 0
    for svc in new_services:
        if svc["name"].lower() in existing_names:
            continue
        if svc["url"].lower() in existing_urls:
            continue
        services.append(svc)
        existing_names.add(svc["name"].lower())
        existing_urls.add(svc["url"].lower())
        added += 1

    save_services(services)
    return added