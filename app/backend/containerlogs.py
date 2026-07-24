"""Read-only Docker container log access via a socket proxy.

The backend talks plain HTTP to a docker socket proxy sidecar (see
docker-compose.yml, service "socket-proxy"). Only the container-list and
container-logs GET endpoints are reachable through the proxy; the Docker
socket itself is never mounted into the backend container.

Services are discovered by the Docker label "easm.logs=enabled"; the public
service name comes from the "easm.service" label (fallback: first container
name). Log severity is a heuristic — EASM app logs are plain print() lines
without structured levels.
"""

import json
import os
import re
from collections.abc import Iterable, Iterator
from typing import Optional

import httpx

DOCKER_PROXY_URL = os.environ.get("DOCKER_PROXY_URL", "http://socket-proxy:2375")

LOG_LABEL = "easm.logs"
SERVICE_LABEL = "easm.service"

MAX_TAIL = 5000
LEVELS = ("info", "warning", "error")

# Heuristic severity classification. App logs are plain prints, so we match
# keywords; "error"-class keywords win over "warn" when both appear.
_ERROR_RE = re.compile(r"error|exception|traceback|fatal|failed", re.IGNORECASE)
_WARNING_RE = re.compile(r"warn", re.IGNORECASE)
_TS_PREFIX_RE = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}")

# Docker multiplexed stream: stream type byte in the 8-byte frame header.
_STREAM_NAMES = {1: "stdout", 2: "stderr"}


def make_client(
    timeout: Optional[float] = 10.0,
    transport: Optional[httpx.BaseTransport] = None,
) -> httpx.Client:
    """Sync client for the socket proxy. Transport is injectable for tests."""
    return httpx.Client(base_url=DOCKER_PROXY_URL, timeout=timeout, transport=transport)


def classify(line: str) -> str:
    """Heuristic log level: error keywords > warning keywords > info."""
    if _ERROR_RE.search(line):
        return "error"
    if _WARNING_RE.search(line):
        return "warning"
    return "info"


def service_name(container: dict) -> str:
    """Public service name: 'easm.service' label, fallback first container name."""
    labels = container.get("Labels") or {}
    if labels.get(SERVICE_LABEL):
        return labels[SERVICE_LABEL]
    names = container.get("Names") or []
    if names:
        return names[0].lstrip("/")
    return (container.get("Id") or "")[:12]


def _fetch_containers(client: httpx.Client) -> list[dict]:
    """All containers carrying the 'easm.logs=enabled' label."""
    filters = json.dumps({"label": [f"{LOG_LABEL}=enabled"]})
    resp = client.get("/containers/json", params={"filters": filters})
    resp.raise_for_status()
    return resp.json()


def list_services(client: Optional[httpx.Client] = None) -> list[dict]:
    """Public service list: [{"name", "container", "status"}, ...], sorted by name."""
    own = client is None
    client = client or make_client()
    try:
        services = [
            {
                "name": service_name(c),
                "container": (c.get("Names") or [""])[0].lstrip("/"),
                "status": c.get("State") or "unknown",
            }
            for c in _fetch_containers(client)
        ]
        return sorted(services, key=lambda s: s["name"])
    finally:
        if own:
            client.close()


def _resolve_container_id(service: str, client: httpx.Client) -> Optional[str]:
    for c in _fetch_containers(client):
        if service_name(c) == service:
            return c.get("Id")
    return None


def demux(chunks: Iterable[bytes]) -> Iterator[tuple[str, bytes]]:
    """Split Docker's multiplexed log stream into (stream, payload) frames.

    Frame layout (containers without TTY): 8-byte header — stream type byte,
    3 padding bytes, big-endian uint32 payload length — then the payload.
    Handles frames split arbitrarily across input chunks; an incomplete
    trailing frame is dropped.
    """
    buffer = bytearray()
    for chunk in chunks:
        buffer.extend(chunk)
        while len(buffer) >= 8:
            stream_type = buffer[0]
            size = int.from_bytes(buffer[4:8], "big")
            if len(buffer) < 8 + size:
                break
            payload = bytes(buffer[8 : 8 + size])
            del buffer[: 8 + size]
            yield _STREAM_NAMES.get(stream_type, "stdout"), payload


def _iter_log_lines(chunks: Iterable[bytes]) -> Iterator[tuple[str, str]]:
    """Yield (stream, line) — reassembles frame payloads into lines per stream."""
    pending: dict[str, bytearray] = {}
    for stream, payload in demux(chunks):
        buf = pending.setdefault(stream, bytearray())
        buf.extend(payload)
        while (idx := buf.find(b"\n")) != -1:
            line = bytes(buf[:idx])
            del buf[: idx + 1]
            if line:
                yield stream, line.decode("utf-8", errors="replace")
    for stream, buf in pending.items():
        if buf:
            yield stream, bytes(buf).decode("utf-8", errors="replace")


def _split_ts(line: str) -> tuple[Optional[str], str]:
    """Split the RFC3339Nano timestamp prefix (timestamps=1) from the message."""
    head, sep, rest = line.partition(" ")
    if sep and _TS_PREFIX_RE.match(head):
        return head, rest
    return None, line


def _log_params(tail: int, since: Optional[int], until: Optional[int]) -> dict:
    params: dict[str, object] = {
        "stdout": 1,
        "stderr": 1,
        "timestamps": 1,
        "tail": max(0, min(int(tail), MAX_TAIL)),
    }
    if since is not None:
        params["since"] = int(since)
    if until is not None:
        params["until"] = int(until)
    return params


def _parse_entry(stream: str, raw: str) -> dict:
    ts, text = _split_ts(raw)
    return {"ts": ts, "stream": stream, "line": text, "level": classify(text)}


def get_logs(
    service: str,
    tail: int = 200,
    since: Optional[int] = None,
    until: Optional[int] = None,
    lines: Optional[str] = None,
    level: Optional[str] = None,
    client: Optional[httpx.Client] = None,
) -> dict:
    """Fetch parsed log lines for a service. Raises KeyError for unknown services."""
    own = client is None
    client = client or make_client()
    try:
        container_id = _resolve_container_id(service, client)
        if container_id is None:
            raise KeyError(service)
        resp = client.get(
            f"/containers/{container_id}/logs",
            params=_log_params(tail, since, until),
        )
        resp.raise_for_status()
        min_level = LEVELS.index(level) if level in LEVELS else 0
        entries = []
        for stream, raw in _iter_log_lines(resp.iter_bytes()):
            entry = _parse_entry(stream, raw)
            if lines and lines not in entry["line"]:
                continue
            if LEVELS.index(entry["level"]) < min_level:
                continue
            entries.append(entry)
        return {"service": service, "lines": entries}
    finally:
        if own:
            client.close()


def stream_logs(
    service: str,
    tail: int = 100,
    since: Optional[int] = None,
    client: Optional[httpx.Client] = None,
) -> Iterator[dict]:
    """Blocking generator of parsed log entries in follow mode.

    Runs forever — intended for a background thread. Pass an externally owned
    client so the caller can close it to stop the stream (e.g. on websocket
    disconnect). Raises KeyError for unknown services.
    """
    own = client is None
    client = client or make_client(timeout=None)
    try:
        container_id = _resolve_container_id(service, client)
        if container_id is None:
            raise KeyError(service)
        params = _log_params(tail, since, None)
        params["follow"] = 1
        with client.stream("GET", f"/containers/{container_id}/logs", params=params) as resp:
            resp.raise_for_status()
            for stream, raw in _iter_log_lines(resp.iter_bytes()):
                yield _parse_entry(stream, raw)
    finally:
        if own:
            client.close()
