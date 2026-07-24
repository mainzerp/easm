"""Pure parsers for scan tool output. DB-free and Redis-free."""

import os
import re


def _read_lines(path: str) -> list[str]:
    if not os.path.exists(path):
        return []
    with open(path, errors="replace") as f:
        return [line.strip() for line in f if line.strip()]


def attribute_domain(host: str, domains: list[str]) -> str:
    for d in domains:
        if host == d or host.endswith("." + d):
            return d
    return ""


def parse_httpx_line(line: str):
    """Format: https://host [status] [title] [tech]  (title optional)."""
    parts = line.split(" [")
    url = parts[0].strip()
    host = re.sub(r"^https?://", "", url).split("/")[0].split(":")[0]
    status, title, tech = None, None, None
    tags = [p.rstrip("]").strip() for p in parts[1:]]
    rest = []
    for t in tags:
        if t.isdigit() and status is None:
            status = int(t)
        else:
            rest.append(t)
    if len(rest) >= 2:
        title, tech = rest[0], rest[1]
    elif len(rest) == 1:
        if "," in rest[0]:
            tech = rest[0]
        else:
            title = rest[0]
    return url, host, status, title, tech


def parse_nmap(path: str):
    """Returns (host->ports, host->ip) from nmap -oN output."""
    ports: dict[str, list[str]] = {}
    ips: dict[str, str] = {}
    current = None
    for line in _read_lines(path):
        m = re.match(r"Nmap scan report for (\S+?)(?: \((\S+)\))?$", line)
        if m:
            current = m.group(1)
            if m.group(2):
                ips[current] = m.group(2)
            elif re.match(r"^\d+\.\d+\.\d+\.\d+$", current):
                ips[current] = current
            ports.setdefault(current, [])
        elif current and "/tcp" in line and " open " in line:
            port = line.split("/")[0].strip()
            if port.isdigit():
                ports[current].append(port)
    return ports, ips


def parse_finding_line(line: str) -> tuple[str | None, str, str | None]:
    """Format: [template] [http] [severity] https://host/path ...

    Returns (template, severity, host); severity defaults to "info".
    """
    template = None
    severity = "info"
    host = None
    m = re.match(r"\[([^\]]+)\]", line)
    if m:
        template = m.group(1)
    for s in ["critical", "high", "medium", "low"]:
        if f"[{s}]" in line.lower():
            severity = s
            break
    um = re.search(r"https?://([^/\s]+)", line)
    if um:
        host = um.group(1).split(":")[0]
    return template, severity, host
