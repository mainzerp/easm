"""Tests for pipeline.parsers (pure, DB-free)."""

from pipeline.parsers import (
    attribute_domain,
    parse_finding_line,
    parse_httpx_line,
    parse_nmap,
)


def test_parse_httpx_line_status_only():
    url, host, status, title, tech = parse_httpx_line("https://a.example.com [200]")
    assert url == "https://a.example.com"
    assert host == "a.example.com"
    assert status == 200
    assert title is None
    assert tech is None


def test_parse_httpx_line_title():
    url, host, status, title, tech = parse_httpx_line("https://a.example.com [200] [Welcome]")
    assert status == 200
    assert title == "Welcome"
    assert tech is None


def test_parse_httpx_line_tech():
    url, host, status, title, tech = parse_httpx_line("https://a.example.com [200] [nginx,PHP]")
    assert status == 200
    assert title is None
    assert tech == "nginx,PHP"


def test_parse_httpx_line_full():
    url, host, status, title, tech = parse_httpx_line("https://a.example.com [200] [Welcome] [nginx,PHP]")
    assert status == 200
    assert title == "Welcome"
    assert tech == "nginx,PHP"


def test_parse_httpx_line_host_with_port_and_path():
    url, host, status, title, tech = parse_httpx_line("http://a.example.com:8443/login [301]")
    assert host == "a.example.com"
    assert status == 301


def test_parse_httpx_line_no_status():
    url, host, status, title, tech = parse_httpx_line("https://a.example.com [Welcome]")
    assert status is None
    assert title == "Welcome"


def test_parse_nmap(tmp_path):
    out = tmp_path / "ports.txt"
    out.write_text(
        "# Nmap 7.94 scan initiated\n"
        "Nmap scan report for web.example.com (192.0.2.10)\n"
        "PORT     STATE SERVICE\n"
        "80/tcp   open  http\n"
        "443/tcp  open  https\n"
        "22/tcp   closed ssh\n"
        "Nmap scan report for 192.0.2.20\n"
        "PORT     STATE SERVICE\n"
        "8080/tcp open  http-proxy\n"
        "Nmap done\n"
    )
    ports, ips = parse_nmap(str(out))
    assert ports == {"web.example.com": ["80", "443"], "192.0.2.20": ["8080"]}
    assert ips == {"web.example.com": "192.0.2.10", "192.0.2.20": "192.0.2.20"}


def test_parse_nmap_missing_file(tmp_path):
    ports, ips = parse_nmap(str(tmp_path / "nope.txt"))
    assert ports == {}
    assert ips == {}


def test_parse_finding_line_full():
    template, severity, host = parse_finding_line("[cve-2021-1234] [http] [high] https://sub.example.com/path")
    assert template == "cve-2021-1234"
    assert severity == "high"
    assert host == "sub.example.com"


def test_parse_finding_line_defaults():
    template, severity, host = parse_finding_line("some unparsed output line")
    assert template is None
    assert severity == "info"
    assert host is None


def test_parse_finding_line_severity_case_insensitive_and_port_stripped():
    template, severity, host = parse_finding_line("[tpl] [http] [CRITICAL] https://h.example.com:8443/x")
    assert template == "tpl"
    assert severity == "critical"
    assert host == "h.example.com"


def test_attribute_domain():
    domains = ["example.com", "example.org"]
    assert attribute_domain("example.com", domains) == "example.com"
    assert attribute_domain("a.b.example.com", domains) == "example.com"
    assert attribute_domain("example.org", domains) == "example.org"
    assert attribute_domain("notexample.com", domains) == ""
    assert attribute_domain("other.net", domains) == ""
