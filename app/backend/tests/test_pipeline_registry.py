"""Tests for pipeline.registry.build_steps (order, enable flags, critical flags)."""

from config import DEFAULT_CONFIG
from pipeline.registry import build_steps


def test_default_cfg_six_steps_in_spec_order():
    steps = build_steps(dict(DEFAULT_CONFIG))
    assert [s.key for s in steps] == [
        "subfinder",
        "dnsx",
        "httpx",
        "extract_urls",
        "nmap",
        "nuclei",
    ]


def test_alterx_included_at_position_two_when_enabled():
    cfg = {**DEFAULT_CONFIG, "enable_alterx": True}
    steps = build_steps(cfg)
    assert [s.key for s in steps] == [
        "subfinder",
        "alterx",
        "dnsx",
        "httpx",
        "extract_urls",
        "nmap",
        "nuclei",
    ]


def test_enable_flags_exclude_steps():
    cfg = {
        **DEFAULT_CONFIG,
        "enable_httpx": False,
        "enable_nmap": False,
        "enable_nuclei": False,
    }
    steps = build_steps(cfg)
    assert [s.key for s in steps] == ["subfinder", "dnsx", "extract_urls"]


def test_extract_urls_always_present():
    cfg = {
        **DEFAULT_CONFIG,
        "enable_alterx": False,
        "enable_httpx": False,
        "enable_nmap": False,
        "enable_nuclei": False,
    }
    assert "extract_urls" in [s.key for s in build_steps(cfg)]


def test_critical_flags_exactly_subfinder_and_dnsx():
    cfg = {**DEFAULT_CONFIG, "enable_alterx": True}
    steps = build_steps(cfg)
    assert {s.key for s in steps if s.critical} == {"subfinder", "dnsx"}


def test_counter_keys():
    steps = {s.key: s for s in build_steps(DEFAULT_CONFIG)}
    assert steps["subfinder"].counter_key == "subdomains"
    assert steps["dnsx"].counter_key == "resolved"
    assert steps["httpx"].counter_key == "http"
    assert steps["nuclei"].counter_key == "findings"
    assert steps["nmap"].counter_key is None
    assert steps["extract_urls"].counter_key is None
