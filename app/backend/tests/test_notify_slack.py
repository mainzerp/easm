"""Tests for notify.send_slack and the Slack branch of _notify_channels."""

import json

import notify


class _FakeResponse:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def test_send_slack_posts_payload(monkeypatch):
    calls = []

    def fake_urlopen(req, timeout=None):
        calls.append((req, timeout))
        return _FakeResponse()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    notify.send_slack({"slack_webhook": "https://hooks.slack.test/x"}, "hello")

    assert len(calls) == 1
    req, timeout = calls[0]
    assert req.full_url == "https://hooks.slack.test/x"
    assert json.loads(req.data) == {"text": "hello"}
    assert timeout == 15


def test_send_slack_no_url_is_noop(monkeypatch):
    calls = []
    monkeypatch.setattr("urllib.request.urlopen", lambda *a, **k: calls.append(1))
    notify.send_slack({"slack_webhook": ""}, "hello")
    assert calls == []


def test_slack_only_config_sends(monkeypatch):
    calls = []

    def fake_urlopen(req, timeout=None):
        calls.append(req)
        return _FakeResponse()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    cfg = {"slack_webhook": "https://hooks.slack.test/x"}
    notify._notify_channels(cfg, "[EASM] Subject", "body")

    assert len(calls) == 1
    assert json.loads(calls[0].data) == {"text": "*[EASM] Subject*\n```\nbody\n```"}


def test_failing_slack_collected_without_raising(monkeypatch, capsys):
    def boom(req, timeout=None):
        raise OSError("connection refused")

    monkeypatch.setattr("urllib.request.urlopen", boom)
    cfg = {"slack_webhook": "https://hooks.slack.test/x"}
    notify._notify_channels(cfg, "[EASM] Subject", "body")

    out = capsys.readouterr().out
    assert "EASM Notify ERROR: Slack: connection refused" in out
