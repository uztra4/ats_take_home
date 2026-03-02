from datetime import datetime
from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String, Text
from .database import Base


class ServiceCheck(Base):
    __tablename__ = "service_checks"

    id = Column(Integer, primary_key=True, index=True)
    service_name = Column(String(255), index=True, nullable=False)
    url = Column(Text, nullable=False)
    expected_version = Column(String(100), nullable=True)
    observed_version = Column(String(100), nullable=True)
    status = Column(String(50), nullable=False)  # healthy, degraded, down
    status_code = Column(Integer, nullable=True)
    latency_ms = Column(Float, nullable=True)
    version_drift = Column(Boolean, nullable=False, default=False)
    error_message = Column(Text, nullable=True)
    environment = Column(String, nullable=False)
    checked_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)