import json
import struct

import containerlogs
from containerlogs import classify, demux, service_name


def frame(stream: int, payload: bytes) -> bytes:
    return bytes([stream, 0, 0, 0]) + struct.pack(">I", len(payload)) + payload


class TestDemux:
    def test_stdout_frame(self):
        data = frame(1, b"hello\n")
        assert list(demux([data])) == [("stdout", b"hello\n")]

    def test_stderr_frame(self):
        data = frame(2, b"boom\n")
        assert list(demux([data])) == [("stderr", b"boom\n")]

    def test_multiple_frames_one_chunk(self):
        data = frame(1, b"a\n") + frame(2, b"b\n") + frame(1, b"c\n")
        assert list(demux([data])) == [
            ("stdout", b"a\n"),
            ("stderr", b"b\n"),
            ("stdout", b"c\n"),
        ]

    def test_frame_split_across_chunks(self):
        data = frame(1, b"split-me\n")
        chunks = [data[:3], data[3:8], data[8:]]
        assert list(demux(chunks)) == [("stdout", b"split-me\n")]

    def test_partial_trailing_frame_dropped(self):
        data = frame(1, b"ok\n") + frame(1, b"truncated")[:10]
        assert list(demux([data])) == [("stdout", b"ok\n")]

    def test_empty_input(self):
        assert list(demux([])) == []
        assert list(demux([b""])) == []

    def test_unknown_stream_defaults_stdout(self):
        data = frame(9, b"x\n")
        assert list(demux([data])) == [("stdout", b"x\n")]


class TestClassify:
    def test_error_keywords(self):
        for line in [
            "something error happened",
            "ERROR: disk full",
            "ValueError exception raised",
            "Traceback (most recent call last):",
            "fatal: not a git repository",
            "scan failed after 3 retries",
        ]:
            assert classify(line) == "error", line

    def test_warning_keywords(self):
        assert classify("WARN: slow response") == "warning"
        assert classify("this is a warning") == "warning"

    def test_info_default(self):
        assert classify("scan started") == "info"
        assert classify("") == "info"

    def test_error_beats_warning(self):
        assert classify("warning: previous attempt failed") == "error"


class TestServiceName:
    def test_label_wins(self):
        c = {"Labels": {"easm.service": "backend"}, "Names": ["/easm-backend"]}
        assert service_name(c) == "backend"

    def test_fallback_first_name_stripped(self):
        c = {"Labels": {}, "Names": ["/easm-db"]}
        assert service_name(c) == "easm-db"

    def test_fallback_id_short(self):
        c = {"Labels": {}, "Names": [], "Id": "abcdef1234567890"}
        assert service_name(c) == "abcdef123456"


class TestListServices:
    def test_label_filter_and_mapping(self, monkeypatch):
        containers = [
            {
                "Id": "1" * 64,
                "Names": ["/easm-backend"],
                "State": "running",
                "Labels": {"easm.logs": "enabled", "easm.service": "backend"},
            },
            {
                "Id": "2" * 64,
                "Names": ["/other"],
                "State": "exited",
                "Labels": {"easm.logs": "enabled"},
            },
        ]
        seen = {}

        class FakeResponse:
            def raise_for_status(self):
                pass

            def json(self):
                return containers

        class FakeClient:
            def get(self, path, params=None):
                seen["path"] = path
                seen["params"] = params
                return FakeResponse()

            def close(self):
                pass

        services = containerlogs.list_services(client=FakeClient())

        assert seen["path"] == "/containers/json"
        assert json.loads(seen["params"]["filters"]) == {"label": ["easm.logs=enabled"]}
        assert services == [
            {"name": "backend", "container": "easm-backend", "status": "running"},
            {"name": "other", "container": "other", "status": "exited"},
        ]


class TestGetLogs:
    def _client(self, log_bytes: bytes):
        class FakeResponse:
            def raise_for_status(self):
                pass

            def json(self):
                return [
                    {
                        "Id": "abc123",
                        "Names": ["/easm-backend"],
                        "State": "running",
                        "Labels": {"easm.logs": "enabled", "easm.service": "backend"},
                    }
                ]

            def iter_bytes(self):
                yield log_bytes

        class FakeClient:
            def __init__(self):
                self.requests = []

            def get(self, path, params=None):
                self.requests.append((path, params))
                return FakeResponse()

            def close(self):
                pass

        return FakeClient()

    def test_fetch_parse_filter(self):
        payload = (
            b"2026-07-23T10:00:00.000000000Z starting up\n"
            b"2026-07-23T10:00:01.000000000Z WARN slow db\n"
            b"2026-07-23T10:00:02.000000000Z scan failed badly\n"
        )
        data = frame(1, payload)
        client = self._client(data)
        result = containerlogs.get_logs("backend", tail=50, client=client)

        assert result["service"] == "backend"
        lines = result["lines"]
        assert len(lines) == 3
        assert lines[0]["stream"] == "stdout"
        assert lines[0]["ts"] == "2026-07-23T10:00:00.000000000Z"
        assert lines[0]["line"] == "starting up"
        assert lines[0]["level"] == "info"
        assert lines[1]["level"] == "warning"
        assert lines[2]["level"] == "error"

        path, params = client.requests[1]
        assert path == "/containers/abc123/logs"
        assert params["tail"] == 50
        assert params["stdout"] == 1 and params["stderr"] == 1

    def test_level_minimum(self):
        payload = b"2026-07-23T10:00:00Z plain\n2026-07-23T10:00:01Z error here\n"
        client = self._client(frame(1, payload))
        result = containerlogs.get_logs("backend", level="error", client=client)
        assert [e["level"] for e in result["lines"]] == ["error"]

    def test_lines_substring(self):
        payload = b"2026-07-23T10:00:00Z apple\n2026-07-23T10:00:01Z banana\n"
        client = self._client(frame(1, payload))
        result = containerlogs.get_logs("backend", lines="banana", client=client)
        assert [e["line"] for e in result["lines"]] == ["banana"]

    def test_tail_clamped(self):
        client = self._client(frame(1, b"2026-07-23T10:00:00Z x\n"))
        containerlogs.get_logs("backend", tail=999999, client=client)
        assert client.requests[1][1]["tail"] == containerlogs.MAX_TAIL

    def test_unknown_service_raises(self):
        client = self._client(b"")
        try:
            containerlogs.get_logs("nope", client=client)
            raise AssertionError("expected KeyError")
        except KeyError:
            pass

    def test_stderr_lines_parsed(self):
        data = frame(2, b"2026-07-23T10:00:00Z oops error\n")
        client = self._client(data)
        result = containerlogs.get_logs("backend", client=client)
        assert result["lines"][0]["stream"] == "stderr"
        assert result["lines"][0]["level"] == "error"
