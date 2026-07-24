"""Database layer for EASM Dashboard (PostgreSQL via SQLAlchemy 2)."""

import os
from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
    sessionmaker,
)

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+psycopg://easm:easm@db:5432/easm",
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[dict] = mapped_column(JSONB, default=dict)


class Scan(Base):
    __tablename__ = "scans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[str] = mapped_column(String, unique=True, index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String, default="running")  # queued | running | done | failed | canceled
    triggered_by: Mapped[str] = mapped_column(String, default="manual")  # manual | schedule
    nuclei_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    job_id: Mapped[str | None] = mapped_column(String, nullable=True)
    domains: Mapped[list] = mapped_column(JSONB, default=list)
    target_desc: Mapped[str] = mapped_column(String, default="")
    output_dir: Mapped[str] = mapped_column(String, default="")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    assets: Mapped[list["Asset"]] = relationship(
        back_populates="scan", cascade="all, delete-orphan"
    )
    findings: Mapped[list["Finding"]] = relationship(
        back_populates="scan", cascade="all, delete-orphan"
    )


class Asset(Base):
    __tablename__ = "assets"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    scan_id: Mapped[int] = mapped_column(ForeignKey("scans.id", ondelete="CASCADE"), index=True)
    domain: Mapped[str] = mapped_column(String, index=True)
    host: Mapped[str] = mapped_column(String)
    ip: Mapped[str | None] = mapped_column(String, nullable=True)
    http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    tech: Mapped[str | None] = mapped_column(Text, nullable=True)
    ports: Mapped[str | None] = mapped_column(Text, nullable=True)  # "22,80,443"

    scan: Mapped[Scan] = relationship(back_populates="assets")


class Finding(Base):
    __tablename__ = "findings"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    scan_id: Mapped[int] = mapped_column(ForeignKey("scans.id", ondelete="CASCADE"), index=True)
    domain: Mapped[str] = mapped_column(String, index=True)
    host: Mapped[str | None] = mapped_column(String, nullable=True)
    template: Mapped[str | None] = mapped_column(String, nullable=True)
    severity: Mapped[str] = mapped_column(String, index=True)
    raw: Mapped[str] = mapped_column(Text)
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    scan: Mapped[Scan] = relationship(back_populates="findings")


class AssetTracker(Base):
    """Cross-scan view: when was each host first/last seen."""

    __tablename__ = "asset_tracker"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    domain: Mapped[str] = mapped_column(String, index=True)
    host: Mapped[str] = mapped_column(String, unique=True, index=True)
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    first_scan_id: Mapped[int] = mapped_column(Integer)
    last_scan_id: Mapped[int] = mapped_column(Integer)


class FindingTracker(Base):
    """Cross-scan view: open vs resolved findings over time."""

    __tablename__ = "finding_tracker"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    domain: Mapped[str] = mapped_column(String, index=True)
    template: Mapped[str] = mapped_column(String)
    host: Mapped[str] = mapped_column(String)
    severity: Mapped[str] = mapped_column(String, index=True)
    raw: Mapped[str] = mapped_column(Text)
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    first_scan_id: Mapped[int] = mapped_column(Integer)
    last_scan_id: Mapped[int] = mapped_column(Integer)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    resolved_scan_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
