"""Route handlers for container log access and historical scan logs.

Written as FastAPI-ready handlers so main.py can register each with a single
line (app.get(...)(handler) / app.websocket(...)(handler)). Auth is inherited
from the /api/* middleware for REST routes; the websocket handler expects an
already-authenticated websocket (same cookie check as /ws/scan in main.py).
"""

import asyncio
import json
import os
import threading
import time
from typing import Optional

import httpx
from fastapi import HTTPException, Query, WebSocket, WebSocketDisconnect

import containerlogs
from db import Scan, SessionLocal
from scanqueue import log_key, redis_conn

RESULTS_DIR = os.environ.get("RESULTS_DIR", "/results")

_LEVELS = containerlogs.LEVELS


def service_log_message(service: str, entry: dict) -> dict:
    """Shape one parsed log entry into the /ws/logs wire message (pure)."""
    return {
        "type": "service_log",
        "service": service,
        "ts": entry.get("ts"),
        "line": entry.get("line"),
        "level": entry.get("level"),
    }


def list_log_services() -> list[dict]:
    """GET /api/logs/services"""
    try:
        return containerlogs.list_services()
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Log proxy unavailable: {e}")


def get_service_logs(
    service: str,
    tail: int = Query(default=200, ge=1, le=containerlogs.MAX_TAIL),
    since: Optional[int] = None,
    until: Optional[int] = None,
    lines: Optional[str] = None,
    level: Optional[str] = None,
) -> dict:
    """GET /api/logs/{service}"""
    if level is not None and level not in _LEVELS:
        raise HTTPException(status_code=400, detail=f"Invalid level '{level}' — use one of {_LEVELS}.")
    try:
        return containerlogs.get_logs(service, tail=tail, since=since, until=until, lines=lines, level=level)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Unknown service '{service}'.")
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Log proxy unavailable: {e}")


def get_scan_log(date: str) -> dict:
    """GET /api/scans/{date}/log — scan.log from disk, Redis backlog as fallback."""
    log_path = os.path.join(RESULTS_DIR, date, "scan.log")
    if os.path.isfile(log_path):
        with open(log_path, encoding="utf-8", errors="replace") as f:
            return {"date": date, "log": f.read()}

    session = SessionLocal()
    try:
        scan = session.query(Scan).filter_by(date=date).one_or_none()
    finally:
        session.close()
    if scan is None:
        raise HTTPException(status_code=404, detail=f"No log found for scan '{date}'.")

    lines = redis_conn.lrange(log_key(scan.id), 0, -1)
    text = "\n".join(line.decode(errors="replace") if isinstance(line, bytes) else line for line in lines)
    return {"date": date, "log": text}


def _follow_thread(
    service: str,
    since: int,
    queue: asyncio.Queue,
    loop: asyncio.AbstractEventLoop,
    stop: threading.Event,
    clients: list,
) -> None:
    """Blocking follow stream (own client) -> asyncio queue. Runs in a thread."""
    client = containerlogs.make_client(timeout=None)
    clients.append(client)
    try:
        for entry in containerlogs.stream_logs(service, tail=0, since=since, client=client):
            if stop.is_set():
                break
            loop.call_soon_threadsafe(queue.put_nowait, service_log_message(service, entry))
    except (httpx.HTTPError, KeyError, OSError):
        pass
    finally:
        client.close()


async def ws_logs(ws: WebSocket) -> None:
    """WS /ws/logs?services=a,b&tail=100 — merged live tail of service logs.

    Expects an already-authenticated websocket (caller performs the same cookie
    check as /ws/scan). Initial backlog = last `tail` lines per service,
    interleaved timestamp-ordered; then live follow streams merged via queue.
    """
    await ws.accept()
    query = ws.query_params
    requested = [s.strip() for s in query.get("services", "").split(",") if s.strip()]
    try:
        tail = max(0, min(int(query.get("tail", "100")), containerlogs.MAX_TAIL))
    except ValueError:
        tail = 100

    try:
        available = {s["name"] for s in containerlogs.list_services()}
    except httpx.HTTPError:
        await ws.close(code=1011)
        return
    names = [n for n in requested if n in available] if requested else sorted(available)
    if not names:
        await ws.close(code=1000)
        return

    # Backlog first; since-stamp taken before the fetch so the follow streams
    # (started after) don't leave a gap. Overlapping lines may repeat once.
    since = int(time.time())
    backlog: list[dict] = []
    for name in names:
        try:
            entries = containerlogs.get_logs(name, tail=tail)["lines"]
        except (httpx.HTTPError, KeyError):
            continue
        backlog.extend(service_log_message(name, e) for e in entries)
    backlog.sort(key=lambda m: (m["ts"] is None, m["ts"] or ""))

    queue: asyncio.Queue = asyncio.Queue()
    loop = asyncio.get_running_loop()
    stop = threading.Event()
    clients: list = []
    threads = [
        threading.Thread(
            target=_follow_thread,
            args=(name, since, queue, loop, stop, clients),
            daemon=True,
        )
        for name in names
    ]
    for t in threads:
        t.start()

    try:
        for msg in backlog:
            await ws.send_text(json.dumps(msg))
        get_task = asyncio.create_task(queue.get())
        recv_task = asyncio.create_task(ws.receive_text())
        try:
            while True:
                done, _ = await asyncio.wait({get_task, recv_task}, return_when=asyncio.FIRST_COMPLETED)
                if recv_task in done:
                    recv_task.result()  # raises WebSocketDisconnect on disconnect
                    recv_task = asyncio.create_task(ws.receive_text())
                if get_task in done:
                    await ws.send_text(json.dumps(get_task.result()))
                    get_task = asyncio.create_task(queue.get())
        finally:
            get_task.cancel()
            recv_task.cancel()
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        stop.set()
        for c in clients:
            try:
                c.close()
            except Exception:
                pass
        for t in threads:
            t.join(timeout=2)
