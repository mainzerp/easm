"""Shared Redis connection + RQ queue for scan jobs."""

import os

import redis
from rq import Queue

REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")

redis_conn = redis.Redis.from_url(REDIS_URL)
scan_queue = Queue("easm-scans", connection=redis_conn, default_timeout=3600)

LOG_TTL = 86400  # 24h


def log_key(scan_id: int) -> str:
    return f"scanlog:{scan_id}"


def live_channel(scan_id: int) -> str:
    return f"scanlive:{scan_id}"


def stop_key(scan_id: int) -> str:
    return f"scanstop:{scan_id}"
