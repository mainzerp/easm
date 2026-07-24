"""Tests for pipeline.runner.PipelineRunner (subprocess/Redis fully faked)."""

import io
import json
import os
import signal
import subprocess
import time
from pathlib import Path

from config import DEFAULT_CONFIG
from pipeline.events import RedisPublisher
from pipeline.runner import PipelineRunner
from pipeline.steps import StepDefinition


class _BlockingStream:
    def readline(self):
        time.sleep(3600)
        return ""


class FakeProc:
    def __init__(self, stdout_text="", returncode=0, block=False, ignore_term=False):
        self.stdout = _BlockingStream() if block else io.StringIO(stdout_text)
        self.returncode = None if block else returncode
        self._final_rc = returncode
        self._ignore_term = ignore_term
        self.pid = 4321

    def poll(self):
        return self.returncode

    def wait(self, timeout=None):
        if self._ignore_term and timeout is not None:
            raise subprocess.TimeoutExpired("fake", timeout)
        self.returncode = self._final_rc
        return self.returncode


class ListPublisher:
    def __init__(self):
        self.logs = []
        self.events = []

    def log(self, line):
        self.logs.append(line)

    def event(self, payload):
        self.events.append(payload)

    def done(self):
        pass


class FakeRedis:
    def __init__(self):
        self.lists = {}
        self.published = []

    def rpush(self, key, value):
        self.lists.setdefault(key, []).append(value)

    def expire(self, key, ttl):
        pass

    def publish(self, channel, message):
        self.published.append((channel, message))


def _patch_popen(monkeypatch, script):
    """script: {tool: {"output": str, "stdout": str, "rc": int, "block": bool,
    "ignore_term": bool}}. Returns the list of argv calls."""
    calls = []

    def fake_popen(argv, **kwargs):
        calls.append(argv)
        behavior = script.get(argv[0], {})
        for flag in ("-o", "-oN"):
            if flag in argv and "output" in behavior:
                Path(argv[argv.index(flag) + 1]).write_text(behavior["output"])
        return FakeProc(
            stdout_text=behavior.get("stdout", ""),
            returncode=behavior.get("rc", 0),
            block=behavior.get("block", False),
            ignore_term=behavior.get("ignore_term", False),
        )

    monkeypatch.setattr("pipeline.runner.subprocess.Popen", fake_popen)
    return calls


def _patch_killpg(monkeypatch):
    signals = []
    monkeypatch.setattr(os, "killpg", lambda pgid, sig: signals.append(sig), raising=False)
    monkeypatch.setattr(os, "getpgid", lambda pid: pid, raising=False)
    return signals


def _runner(tmp_path, publisher, cfg=None, stop_check=None):
    return PipelineRunner(
        scan_id=1,
        out_dir=str(tmp_path),
        domains=["example.com"],
        cfg=cfg or dict(DEFAULT_CONFIG),
        publisher=publisher,
        stop_check=stop_check or (lambda: False),
    )


def _phase_events(publisher, status=None):
    events = [e for e in publisher.events if e.get("type") == "phase"]
    if status is not None:
        events = [e for e in events if e["status"] == status]
    return events


HAPPY_SCRIPT = {
    "subfinder": {
        "output": "a.example.com\nb.example.com\n",
        "stdout": "subfinder stdout line\n",
    },
    "dnsx": {"output": "a.example.com\n"},
    "httpx-pd": {"output": "https://a.example.com [200] [Welcome] [nginx]\n"},
    "nmap": {"output": "Nmap scan report for a.example.com (192.0.2.1)\n80/tcp open http\n"},
    "nuclei": {"output": "[tpl] [http] [high] https://a.example.com/x\n"},
}


def test_happy_path_contract_events_counters_and_scanlog(monkeypatch, tmp_path):
    fake_redis = FakeRedis()
    monkeypatch.setattr("pipeline.events.redis_conn", fake_redis)
    _patch_popen(monkeypatch, HAPPY_SCRIPT)
    _patch_killpg(monkeypatch)
    publisher = RedisPublisher(scan_id=1, out_dir=str(tmp_path))

    outcome = _runner(tmp_path, publisher).run()

    assert outcome.status == "done"
    assert outcome.error is None
    assert outcome.warnings == []

    # six-file result contract (+ scan.log)
    for name in (
        "subdomains.txt",
        "resolved.txt",
        "http-results.txt",
        "urls.txt",
        "ports.txt",
        "vulns.txt",
        "scan.log",
    ):
        assert (tmp_path / name).exists(), name
    assert (tmp_path / "urls.txt").read_text() == "https://a.example.com\n"

    # Redis lists/channels
    assert "subfinder stdout line" in fake_redis.lists["scanlog:1"]
    structured = [m for _, m in fake_redis.published if m.startswith("{")]
    assert all(json.loads(m)["easm"] == 1 for m in structured)
    assert "scanphase:1" in fake_redis.lists

    # scan.log holds log lines + rendered events
    scan_log = (tmp_path / "scan.log").read_text()
    assert "subfinder stdout line" in scan_log
    assert "[phase] subfinder" in scan_log
    assert "[status] done" in scan_log


def test_happy_path_event_sequence_and_counters(monkeypatch, tmp_path):
    _patch_popen(monkeypatch, HAPPY_SCRIPT)
    _patch_killpg(monkeypatch)
    publisher = ListPublisher()

    outcome = _runner(tmp_path, publisher).run()

    assert outcome.status == "done"

    queued = _phase_events(publisher, "queued")
    assert [e["phase"] for e in queued] == [
        "subfinder",
        "dnsx",
        "httpx",
        "extract_urls",
        "nmap",
        "nuclei",
    ]
    assert [e["seq"] for e in queued] == [1, 2, 3, 4, 5, 6]
    assert all(e["total"] == 6 for e in queued)

    status_events = [e for e in publisher.events if e.get("type") == "status"]
    assert status_events[0]["status"] == "running"
    assert status_events[-1]["status"] == "done"

    done = _phase_events(publisher, "done")
    assert [e["phase"] for e in done] == [
        "subfinder",
        "dnsx",
        "httpx",
        "extract_urls",
        "nmap",
        "nuclei",
    ]
    assert all(e["elapsed_ms"] is not None for e in done)

    counter_events = [e for e in publisher.events if e.get("type") == "counter"]
    assert counter_events[0]["counters"] == {
        "subdomains": 0,
        "resolved": 0,
        "http": 0,
        "findings": 0,
    }
    assert counter_events[-1]["counters"] == {
        "subdomains": 2,
        "resolved": 1,
        "http": 1,
        "findings": 1,
    }
    assert outcome.counters == {"subdomains": 2, "resolved": 1, "http": 1, "findings": 1}

    # event order: queued batch -> status/running -> ... -> status/done
    types = [e.get("type") for e in publisher.events]
    assert types[:7] == ["phase"] * 6 + ["status"]
    assert types[-1] == "status"


def test_critical_subfinder_failure_aborts(monkeypatch, tmp_path):
    script = {**HAPPY_SCRIPT, "subfinder": {"rc": 1, "stdout": "boom\n"}}
    calls = _patch_popen(monkeypatch, script)
    _patch_killpg(monkeypatch)
    publisher = ListPublisher()

    outcome = _runner(tmp_path, publisher).run()

    assert outcome.status == "failed"
    assert outcome.error == "exit code 1"
    assert [c[0] for c in calls] == ["subfinder"]  # no later steps ran

    failed = _phase_events(publisher, "failed")
    assert [e["phase"] for e in failed] == ["subfinder"]
    assert failed[0]["error"] == "exit code 1"
    status_events = [e for e in publisher.events if e.get("type") == "status"]
    assert status_events[-1] == {"type": "status", "status": "failed", "error": "exit code 1"}


def test_noncritical_httpx_failure_continues_with_warning(monkeypatch, tmp_path):
    script = {**HAPPY_SCRIPT, "httpx-pd": {"rc": 2}}
    calls = _patch_popen(monkeypatch, script)
    _patch_killpg(monkeypatch)
    publisher = ListPublisher()

    outcome = _runner(tmp_path, publisher).run()

    assert outcome.status == "done"
    assert len(outcome.warnings) == 1
    assert "httpx failed: exit code 2" in outcome.warnings[0]

    tools = [c[0] for c in calls]
    assert "nmap" in tools  # pipeline continued past the failure
    assert "nuclei" not in tools  # skipped: urls.txt empty after httpx failure

    failed = _phase_events(publisher, "failed")
    assert [e["phase"] for e in failed] == ["httpx"]
    skipped = _phase_events(publisher, "skipped")
    assert [e["phase"] for e in skipped] == ["nuclei"]
    assert skipped[0]["reason"] == "urls.txt is empty"


def test_timeout_kills_process_group(monkeypatch, tmp_path):
    step = StepDefinition(
        key="slow",
        title="Slow Tool",
        kind="command",
        build=lambda ctx: ["slowtool", "-o", os.path.join(ctx["out_dir"], "slow.txt")],
        timeout_s=1,
        output_file="slow.txt",
        critical=True,
    )
    monkeypatch.setattr("pipeline.runner.build_steps", lambda cfg: [step])
    _patch_popen(monkeypatch, {"slowtool": {"block": True, "ignore_term": True}})
    signals = _patch_killpg(monkeypatch)
    publisher = ListPublisher()

    outcome = _runner(tmp_path, publisher).run()

    assert outcome.status == "failed"
    assert outcome.error == "timeout after 1s"
    assert signals == [signal.SIGTERM, getattr(signal, "SIGKILL", signal.SIGTERM)]


def test_cancel_mid_step_terminates_group(monkeypatch, tmp_path):
    script = {**HAPPY_SCRIPT, "subfinder": {"block": True}}
    calls = _patch_popen(monkeypatch, script)
    signals = _patch_killpg(monkeypatch)
    publisher = ListPublisher()

    checks = {"n": 0}

    def stop_check():
        checks["n"] += 1
        return checks["n"] > 2

    outcome = _runner(tmp_path, publisher, stop_check=stop_check).run()

    assert outcome.status == "canceled"
    assert signals == [signal.SIGTERM]  # process group killed
    assert [c[0] for c in calls] == ["subfinder"]  # later steps never ran

    status_events = [e for e in publisher.events if e.get("type") == "status"]
    assert status_events[-1]["status"] == "canceled"


def test_skip_when_input_empty(monkeypatch, tmp_path):
    script = {**HAPPY_SCRIPT, "subfinder": {"output": ""}}
    calls = _patch_popen(monkeypatch, script)
    _patch_killpg(monkeypatch)
    publisher = ListPublisher()

    outcome = _runner(tmp_path, publisher).run()

    assert outcome.status == "done"
    tools = [c[0] for c in calls]
    assert tools == ["subfinder"]  # dnsx skipped (empty subdomains.txt)

    skipped = _phase_events(publisher, "skipped")
    assert "dnsx" in [e["phase"] for e in skipped]
    assert skipped[0]["reason"] == "subdomains.txt is empty"
    # contract files still exist despite skips
    for name in ("subdomains.txt", "resolved.txt", "http-results.txt", "urls.txt", "ports.txt", "vulns.txt"):
        assert (tmp_path / name).exists(), name
