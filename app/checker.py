import asyncio
import logging
import os
import time
from datetime import datetime

import httpx
from sqlalchemy.orm import Session

from .config_loader import load_services
from .models import ServiceCheck

logger = logging.getLogger(__name__)

CHECK_INTERVAL_SECONDS = 30
REQUEST_TIMEOUT_SECONDS = 10
FAILURE_ALERT_THRESHOLD = 3
ALERT_MODE=os.getenv("ALERT_MODE", "")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

_failure_streaks: dict[str, int] = {}
_alert_sent: dict[str, bool] = {}

_failure_streaks: dict[str, int] = {}


def derive_status(status_code: int | None, error_message: str | None) -> str:
    if error_message:
        return "down"
    if status_code is None:
        return "down"
    if 200 <= status_code < 300:
        return "healthy"
    if 300 <= status_code < 500:
        return "degraded"
    return "down"


def extract_version(response: httpx.Response) -> str | None:
    # Check common version headers
    version_headers = [
        "X-App-Version",
        "X-API-Version",
        "API-Version",
        "X-Powered-By",
        "X-AspNet-Version",
        "Server",
    ]
    
    for header in version_headers:
        version = response.headers.get(header)
        if version:
            if header == "Server":
                version = version.split("/")[-1] if "/" in version else version
            return version

    # Check JSON body for version fields
    content_type = response.headers.get("content-type", "")
    if "application/json" in content_type:
        try:
            body = response.json()
            if isinstance(body, dict):
                version_fields = ["version", "app_version", "api_version", "appVersion"]
                for field in version_fields:
                    if field in body:
                        return str(body[field])
        except Exception:
            pass
    
    return None


async def check_service(client: httpx.AsyncClient, service: dict) -> dict:
    try:
        response = await client.get(service["url"], timeout=REQUEST_TIMEOUT_SECONDS)
        latency_ms = response.elapsed.total_seconds() * 1000
        status = derive_status(response.status_code, None)
        version = extract_version(response)
        
        return {
            "service_name": service["name"],
            "url": service["url"],
            "expected_version": service["expected_version"],
            "observed_version": version,
            "status": status,
            "status_code": response.status_code,
            "latency_ms": latency_ms,
            "version_drift": version and version != service["expected_version"],
            "error_message": None,
            "environment": service.get("environment", "default"),
            "checked_at": datetime.utcnow(),
        }
    except Exception as e:
        return {
            "service_name": service["name"],
            "url": service["url"],
            "expected_version": service["expected_version"],
            "observed_version": None,
            "status": "down",
            "status_code": None,
            "latency_ms": 0,
            "version_drift": False,
            "error_message": str(e),
            "environment": service.get("environment", "default"),
            "checked_at": datetime.utcnow(),
        }
    
def persist_result(db: Session, result: dict) -> None:
    row = ServiceCheck(**result)
    db.add(row)
    db.commit()

async def send_console_alert(service_name: str, result: dict, failures: int):
    logger.warning(
        "ALERT: service=%s status=%s failures=%s url=%s latency_ms=%s error=%s checked_at=%s",
        service_name,
        result["status"],
        failures,
        result["url"],
        result["latency_ms"],
        result["error_message"],
        result["checked_at"],
    )


async def send_telegram_alert(client: httpx.AsyncClient, service_name: str, result: dict, failures: int):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning("Telegram alert skipped: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID missing")
        return

    text = (
        f"🚨 Service Alert\n"
        f"Service: {service_name}\n"
        f"Status: {result['status']} (failures={failures})\n"
        f"URL: {result['url']}\n"
        f"HTTP: {result.get('status_code')}\n"
        f"Latency: {result.get('latency_ms')} ms\n"
        f"Expected: {result.get('expected_version')}\n"
        f"Observed: {result.get('observed_version')}\n"
        f"Drift: {result.get('version_drift')}\n"
        f"Error: {result.get('error_message')}\n"
        f"Time: {result.get('checked_at')}\n"
    )

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "disable_web_page_preview": True,
    }

    resp = await client.post(url, json=payload, timeout=10)
    resp.raise_for_status()


async def trigger_alert(client: httpx.AsyncClient, service_name: str, result: dict, failures: int):
    if ALERT_MODE == "none":
        return
    if ALERT_MODE == "webhook":
        await send_telegram_alert(client, service_name, result, failures)
        return

    await send_console_alert(service_name, result, failures)

async def process_alerts(client: httpx.AsyncClient, result: dict):
    service_name = result["service_name"]

    if result["status"] == "healthy":
        if _failure_streaks.get(service_name, 0) > 0:
            logger.info("RECOVERY: service=%s is healthy again", service_name)
        _failure_streaks[service_name] = 0
        _alert_sent[service_name] = False
        return

    _failure_streaks[service_name] = _failure_streaks.get(service_name, 0) + 1
    failures = _failure_streaks[service_name]

    if failures >= FAILURE_ALERT_THRESHOLD and not _alert_sent.get(service_name, False):
        await trigger_alert(client, service_name, result, failures)
        _alert_sent[service_name] = True

async def monitor_loop(session_factory):
    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS, follow_redirects=True) as client:
        while True:
            try:
                services = load_services()
            except Exception as exc:
                logger.exception("Failed to load services config: %s", exc)
                services = []

            for service in services:
                db = session_factory()
                try:
                    result = await check_service(client, service)
                    persist_result(db, result)
                    await process_alerts(client, result)
                except Exception as exc:
                    logger.exception("Unexpected monitor error for %s: %s", service.get("name"), exc)
                finally:
                    db.close()

            await asyncio.sleep(CHECK_INTERVAL_SECONDS)
