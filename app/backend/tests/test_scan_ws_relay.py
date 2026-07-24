"""Unit tests for the /ws/scan envelope relay helper in main.py (spec E)."""

import json

from main import _scan_ws_message


class TestScanWsMessage:
    def test_easm_event_forwarded_typed_without_marker(self):
        data = json.dumps(
            {
                "easm": 1,
                "type": "phase",
                "phase": "subfinder",
                "title": "Subdomain Discovery",
                "status": "running",
                "seq": 1,
                "total": 7,
                "elapsed_ms": None,
                "reason": None,
                "error": None,
            }
        )
        out = json.loads(_scan_ws_message(data))
        assert out["type"] == "phase"
        assert out["phase"] == "subfinder"
        assert "easm" not in out

    def test_counter_and_status_events(self):
        counter = json.loads(
            _scan_ws_message(json.dumps({"easm": 1, "type": "counter", "counters": {"subdomains": 3}}))
        )
        assert counter == {"type": "counter", "counters": {"subdomains": 3}}
        status = json.loads(
            _scan_ws_message(json.dumps({"easm": 1, "type": "status", "status": "done", "error": None}))
        )
        assert status == {"type": "status", "status": "done", "error": None}

    def test_plain_line_becomes_log_message(self):
        out = json.loads(_scan_ws_message("subfinder output line"))
        assert out == {"type": "log", "line": "subfinder output line"}

    def test_json_without_marker_becomes_log_message(self):
        data = json.dumps({"type": "phase", "phase": "dnsx"})
        out = json.loads(_scan_ws_message(data))
        assert out == {"type": "log", "line": data}

    def test_non_dict_json_becomes_log_message(self):
        out = json.loads(_scan_ws_message("[1, 2, 3]"))
        assert out == {"type": "log", "line": "[1, 2, 3]"}
