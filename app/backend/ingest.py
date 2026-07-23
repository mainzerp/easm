"""Parse scan result files and write them into the database."""

import glob
import os
import re
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from db import (
    Asset,
    AssetTracker,
    Finding,
    FindingTracker,
    Scan,
    SessionLocal,
    utcnow,
)

RESULTS_DIR = "/results"


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


def _parse_httpx_line(line: str):
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


def _parse_nmap(path: str):
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


def _parse_finding_line(line: str, domains: list[str], scan_time):
    """Format: [template] [http] [severity] https://host/path ..."""
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
    return Finding(
        domain=attribute_domain(host, domains) if host else "",
        host=host,
        template=template,
        severity=severity,
        raw=line,
        first_seen=scan_time,
        last_seen=scan_time,
    )


def _finding_key(template: str | None, host: str | None, raw: str) -> tuple[str, str]:
    return (template or raw[:80], host or "")


def _apply_trackers(session: Session, scan: Scan) -> dict:
    """Upsert asset/finding trackers from a scan's DB rows. Returns changes."""
    scan_time = scan.finished_at or scan.started_at or utcnow()
    new_assets: list[str] = []
    new_findings: list[str] = []

    for asset in scan.assets:
        tr = session.query(AssetTracker).filter_by(host=asset.host).one_or_none()
        if tr:
            tr.last_seen = scan_time
            tr.last_scan_id = scan.id
        else:
            session.add(
                AssetTracker(
                    domain=asset.domain,
                    host=asset.host,
                    first_seen=scan_time,
                    last_seen=scan_time,
                    first_scan_id=scan.id,
                    last_scan_id=scan.id,
                )
            )
            new_assets.append(asset.host)

    if scan.nuclei_enabled:
        seen_keys: set[tuple[str, str]] = set()
        scanned_domains = {a.domain for a in scan.assets if a.domain}

        for f in scan.findings:
            key = _finding_key(f.template, f.host, f.raw)
            seen_keys.add(key)
            tr = session.query(FindingTracker).filter_by(template=key[0], host=key[1]).one_or_none()
            if tr:
                tr.last_seen = scan_time
                tr.last_scan_id = scan.id
                if tr.resolved:
                    tr.resolved = False
                    tr.resolved_scan_id = None
                    new_findings.append(f.raw)
            else:
                session.add(
                    FindingTracker(
                        domain=f.domain,
                        template=key[0],
                        host=key[1] or "",
                        severity=f.severity,
                        raw=f.raw,
                        first_seen=scan_time,
                        last_seen=scan_time,
                        first_scan_id=scan.id,
                        last_scan_id=scan.id,
                        resolved=False,
                    )
                )
                new_findings.append(f.raw)

        open_for_domains = (
            session.query(FindingTracker)
            .filter(FindingTracker.domain.in_(scanned_domains or {""}))
            .filter(FindingTracker.resolved.is_(False))
            .all()
        )
        for tr in open_for_domains:
            if (tr.template, tr.host) not in seen_keys:
                tr.resolved = True
                tr.resolved_scan_id = scan.id

    return {"new_assets": new_assets, "new_findings": new_findings}


def ingest_scan(
    session: Session,
    scan: Scan,
    out_dir: str,
    domains: list[str],
) -> dict:
    """Parse result files of one scan into assets/findings rows + trackers."""
    scan.assets.clear()
    scan.findings.clear()
    session.flush()

    scan_time = scan.finished_at or scan.started_at or utcnow()

    subdomains = _read_lines(os.path.join(out_dir, "subdomains.txt"))
    ports_map, ip_map = _parse_nmap(os.path.join(out_dir, "ports.txt"))

    http_map: dict[str, tuple] = {}
    for line in _read_lines(os.path.join(out_dir, "http-results.txt")):
        url, host, status, title, tech = _parse_httpx_line(line)
        http_map[host] = (status, title, tech)

    for host in subdomains:
        status, title, tech = http_map.get(host, (None, None, None))
        session.add(
            Asset(
                scan_id=scan.id,
                domain=attribute_domain(host, domains),
                host=host,
                ip=ip_map.get(host),
                http_status=status,
                title=title,
                tech=tech,
                ports=",".join(ports_map.get(host, [])) or None,
            )
        )

    for line in _read_lines(os.path.join(out_dir, "vulns.txt")):
        f = _parse_finding_line(line, domains, scan_time)
        f.scan_id = scan.id
        session.add(f)

    session.flush()
    changes = _apply_trackers(session, scan)
    session.commit()
    return changes


def import_legacy_results(domains: list[str]) -> int:
    """Import all /results/* scan folders not yet present in the DB."""
    imported = 0
    session = SessionLocal()
    try:
        for path in sorted(glob.glob(f"{RESULTS_DIR}/*/")):
            date = os.path.basename(path.rstrip("/"))
            if date == "previous":
                continue
            existing = session.query(Scan).filter_by(date=date).one_or_none()
            if existing:
                continue
            m = re.match(r"(\d{4})-(\d{2})-(\d{2})_(\d{2})-(\d{2})", date)
            started = utcnow()
            if m:
                started = datetime(
                    int(m.group(1)),
                    int(m.group(2)),
                    int(m.group(3)),
                    int(m.group(4)),
                    int(m.group(5)),
                    tzinfo=timezone.utc,
                )
            out_dir = path.rstrip("/")
            scan = Scan(
                date=date,
                started_at=started,
                finished_at=started,
                status="done",
                triggered_by="manual",
                nuclei_enabled=os.path.exists(os.path.join(out_dir, "vulns.txt")),
                target_desc="(import)",
                output_dir=out_dir,
            )
            session.add(scan)
            session.flush()
            ingest_scan(session, scan, out_dir, domains)
            imported += 1
        return imported
    finally:
        session.close()


def backfill_nuclei_enabled() -> None:
    """Derive nuclei_enabled for existing scans from vulns.txt presence."""
    session = SessionLocal()
    try:
        for scan in session.query(Scan).all():
            if scan.output_dir and os.path.isdir(scan.output_dir):
                scan.nuclei_enabled = os.path.exists(os.path.join(scan.output_dir, "vulns.txt"))
        session.commit()
    finally:
        session.close()


def rebuild_trackers() -> None:
    """Rebuild asset/finding trackers from all completed scans (idempotent)."""
    session = SessionLocal()
    try:
        session.query(FindingTracker).delete()
        session.query(AssetTracker).delete()
        session.commit()
        scans = session.query(Scan).filter_by(status="done").order_by(Scan.started_at.asc()).all()
        for scan in scans:
            _apply_trackers(session, scan)
        session.commit()
    finally:
        session.close()
