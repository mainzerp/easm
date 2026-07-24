import struct

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import containerlogs
import logroutes
from db import Scan, SessionLocal, utcnow


def frame(stream: int, payload: bytes) -> bytes:
    return bytes([stream, 0, 0, 0]) + struct.pack(">I", len(payload)) + payload


CONTAINERS = [
    {
        "Id": "a" * 64,
        "Names": ["/easm-backend"],
        "State": "running",
        "Labels": {"easm.logs": "enabled", "easm.service": "backend"},
    },
    {
        "Id": "b" * 64,
        "Names": ["/easm-db"],
        "State": "running",
        "Labels": {"easm.logs": "enabled", "easm.service": "db"},
    },
]

LOG_PAYLOAD = frame(
    1,
    b"2026-07-23T10:00:00.000000000Z starting up\n"
    b"2026-07-23T10:00:01.000000000Z WARN slow query\n"
    b"2026-07-23T10:00:02.000000000Z scan failed hard\n",
)


def proxy_handler(request: httpx.Request) -> httpx.Response:
    if request.url.path == "/containers/json":
        assert "easm.logs" in request.url.params["filters"]
        return httpx.Response(200, json=CONTAINERS)
    if request.url.path.endswith("/logs"):
        return httpx.Response(200, content=LOG_PAYLOAD)
    return httpx.Response(404)


@pytest.fixture
def logs_app(monkeypatch):
    def make_mock_client(timeout=10.0, transport=None):
        return httpx.Client(base_url="http://proxy", transport=httpx.MockTransport(proxy_handler))

    monkeypatch.setattr(containerlogs, "make_client", make_mock_client)

    app = FastAPI()
    app.get("/api/logs/services")(logroutes.list_log_services)
    app.get("/api/logs/{service}")(logroutes.get_service_logs)
    app.get("/api/scans/{date}/log")(logroutes.get_scan_log)
    with TestClient(app) as c:
        yield c


class TestServicesEndpoint:
    def test_lists_labeled_services(self, logs_app):
        resp = logs_app.get("/api/logs/services")
        assert resp.status_code == 200
        assert resp.json() == [
            {"name": "backend", "container": "easm-backend", "status": "running"},
            {"name": "db", "container": "easm-db", "status": "running"},
        ]


class TestServiceLogsEndpoint:
    def test_returns_parsed_lines(self, logs_app):
        resp = logs_app.get("/api/logs/backend")
        assert resp.status_code == 200
        data = resp.json()
        assert data["service"] == "backend"
        assert len(data["lines"]) == 3
        first = data["lines"][0]
        assert first["ts"] == "2026-07-23T10:00:00.000000000Z"
        assert first["stream"] == "stdout"
        assert first["line"] == "starting up"
        assert first["level"] == "info"

    def test_level_filter(self, logs_app):
        resp = logs_app.get("/api/logs/backend", params={"level": "warning"})
        assert [e["level"] for e in resp.json()["lines"]] == ["warning", "error"]

    def test_lines_filter(self, logs_app):
        resp = logs_app.get("/api/logs/backend", params={"lines": "slow"})
        lines = resp.json()["lines"]
        assert len(lines) == 1
        assert lines[0]["line"] == "WARN slow query"

    def test_tail_out_of_range_rejected(self, logs_app):
        assert logs_app.get("/api/logs/backend", params={"tail": 0}).status_code == 422
        assert logs_app.get("/api/logs/backend", params={"tail": 5001}).status_code == 422

    def test_invalid_level_rejected(self, logs_app):
        assert logs_app.get("/api/logs/backend", params={"level": "debug"}).status_code == 400

    def test_unknown_service_404(self, logs_app):
        assert logs_app.get("/api/logs/ghost").status_code == 404


class TestScanLogEndpoint:
    def test_log_from_results_file(self, logs_app, monkeypatch, tmp_path):
        scan_dir = tmp_path / "2026-07-23_01-02-03-000"
        scan_dir.mkdir()
        (scan_dir / "scan.log").write_text("line one\nline two\n")
        monkeypatch.setattr(logroutes, "RESULTS_DIR", str(tmp_path))

        resp = logs_app.get("/api/scans/2026-07-23_01-02-03-000/log")
        assert resp.status_code == 200
        assert resp.json() == {
            "date": "2026-07-23_01-02-03-000",
            "log": "line one\nline two\n",
        }

    def test_redis_fallback(self, logs_app, monkeypatch, tmp_path):
        monkeypatch.setattr(logroutes, "RESULTS_DIR", str(tmp_path))  # no file here
        date = "2026-07-23_04-05-06-000"

        session = SessionLocal()
        try:
            scan = Scan(date=date, started_at=utcnow(), status="done", triggered_by="manual")
            session.add(scan)
            session.commit()
            scan_id = scan.id
        finally:
            session.close()

        class FakeRedis:
            def lrange(self, key, start, end):
                assert key == f"scanlog:{scan_id}"
                return [b"redis line 1", b"redis line 2"]

        monkeypatch.setattr(logroutes, "redis_conn", FakeRedis())
        try:
            resp = logs_app.get(f"/api/scans/{date}/log")
            assert resp.status_code == 200
            assert resp.json() == {"date": date, "log": "redis line 1\nredis line 2"}
        finally:
            session = SessionLocal()
            try:
                row = session.get(Scan, scan_id)
                if row:
                    session.delete(row)
                    session.commit()
            finally:
                session.close()

    def test_unknown_scan_404(self, logs_app, monkeypatch, tmp_path):
        monkeypatch.setattr(logroutes, "RESULTS_DIR", str(tmp_path))
        resp = logs_app.get("/api/scans/1999-01-01_00-00-00-000/log")
        assert resp.status_code == 404


class TestWsMessageShaping:
    def test_service_log_message(self):
        entry = {
            "ts": "2026-07-23T10:00:00Z",
            "stream": "stderr",
            "line": "boom error",
            "level": "error",
        }
        msg = logroutes.service_log_message("backend", entry)
        assert msg == {
            "type": "service_log",
            "service": "backend",
            "ts": "2026-07-23T10:00:00Z",
            "line": "boom error",
            "level": "error",
        }
