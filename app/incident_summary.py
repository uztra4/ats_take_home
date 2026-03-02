import json
import os
from datetime import datetime, timedelta

from openai import OpenAI
from sqlalchemy.orm import Session

from .models import ServiceCheck

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")


def build_recent_incident_payload(db: Session, hours: int = 1) -> dict:
    cutoff = datetime.utcnow() - timedelta(hours=hours)

    rows = (
        db.query(ServiceCheck)
        .filter(ServiceCheck.checked_at >= cutoff)
        .order_by(ServiceCheck.checked_at.desc())
        .all()
    )

    if not rows:
        return {
            "hours": hours,
            "total_checks": 0,
            "affected_checks": 0,
            "incidents": [],
        }

    affected = [
        row for row in rows
        if row.status != "healthy" or row.version_drift
    ]

    incidents = []
    for row in affected[:50]:
        incidents.append(
            {
                "service_name": row.service_name,
                "status": row.status,
                "status_code": row.status_code,
                "latency_ms": row.latency_ms,
                "expected_version": row.expected_version,
                "observed_version": row.observed_version,
                "version_drift": row.version_drift,
                "error_message": row.error_message,
                "checked_at": row.checked_at.isoformat() if row.checked_at else None,
                "url": row.url,
            }
        )

    return {
        "hours": hours,
        "total_checks": len(rows),
        "affected_checks": len(affected),
        "incidents": incidents,
    }


def generate_ai_incident_summary(db: Session, hours: int = 1) -> str:
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is not configured")

    payload = build_recent_incident_payload(db, hours=hours)

    client = OpenAI(api_key=OPENAI_API_KEY)

    prompt = f"""
        You are writing a service reliability dashboard summary.

        Summarize only the past {hours} hour of incident activity.
        Write exactly 3 to 4 short lines.
        Be factual, concise, and easy to scan.
        Mention:
        - how many services were affected
        - the most important failures or degraded services
        - whether any issue appears unresolved
        - version drift only if relevant

        Do not use bullets.
        Do not add a title.
        Do not mention missing data unless important.

        Incident data:
        {json.dumps(payload, indent=2)}
    """.strip()

    response = client.responses.create(
        model=OPENAI_MODEL,
        input=prompt,
    )
    
    print(response)

    return response.output_text.strip()