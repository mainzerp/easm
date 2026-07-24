"""Event publishing for scan runs: Redis lists/channels + on-disk scan.log.

Wire format (scanqueue.py convention):
- scanlog:{id}   — list of plain log lines (TTL LOG_TTL)
- scanlive:{id}  — pub/sub channel: plain log lines, "__DONE__" sentinel,
                   and structured events as single-line JSON {"easm": 1, ...}
- scanphase:{id} — list of structured event JSON for late-joiner replay
- <out_dir>/scan.log — every log line + rendered events, appended live
"""

import json
import os
from typing import Protocol

from scanqueue import LOG_TTL, live_channel, log_key, redis_conn

DONE_SENTINEL = "__DONE__"


def phase_key(scan_id: int) -> str:
    return f"scanphase:{scan_id}"


class EventPublisher(Protocol):
    def log(self, line: str) -> None: ...

    def event(self, payload: dict) -> None: ...

    def done(self) -> None: ...


def render_event(payload: dict) -> str:
    """Human-readable one-line rendering of a structured event for scan.log."""
    etype = payload.get("type")
    if etype == "phase":
        text = f"[phase] {payload.get('phase')} — {payload.get('title')}: {payload.get('status')}"
        extras = []
        if payload.get("elapsed_ms") is not None:
            extras.append(f"{payload['elapsed_ms']} ms")
        if payload.get("reason"):
            extras.append(str(payload["reason"]))
        if payload.get("error"):
            extras.append(str(payload["error"]))
        if extras:
            text += " (" + "; ".join(extras) + ")"
        return text
    if etype == "counter":
        counters = payload.get("counters", {})
        return "[counters] " + ", ".join(f"{k}={v}" for k, v in counters.items())
    if etype == "status":
        text = f"[status] {payload.get('status')}"
        if payload.get("error"):
            text += f" — {payload['error']}"
        return text
    return "[event] " + json.dumps(payload, separators=(",", ":"), sort_keys=True)


class RedisPublisher:
    """Publishes scan log lines and structured events to Redis and scan.log."""

    def __init__(self, scan_id: int, out_dir: str):
        self.scan_id = scan_id
        self.out_dir = out_dir
        self._log_path = os.path.join(out_dir, "scan.log")

    def _append_file(self, line: str) -> None:
        try:
            os.makedirs(self.out_dir, exist_ok=True)
            with open(self._log_path, "a", errors="replace") as f:
                f.write(line + "\n")
        except OSError:
            pass

    def log(self, line: str) -> None:
        redis_conn.rpush(log_key(self.scan_id), line)
        redis_conn.expire(log_key(self.scan_id), LOG_TTL)
        redis_conn.publish(live_channel(self.scan_id), line)
        self._append_file(line)

    def event(self, payload: dict) -> None:
        payload = {"easm": 1, **payload}
        line = json.dumps(payload, separators=(",", ":"))
        redis_conn.rpush(phase_key(self.scan_id), line)
        redis_conn.expire(phase_key(self.scan_id), LOG_TTL)
        redis_conn.publish(live_channel(self.scan_id), line)
        self._append_file(render_event(payload))

    def done(self) -> None:
        redis_conn.publish(live_channel(self.scan_id), DONE_SENTINEL)
