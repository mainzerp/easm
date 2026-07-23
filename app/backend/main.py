import asyncio
import json
import os
import subprocess
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI, HTTPException, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy import func

import auth
import ingest
import notify
from db import (
    Asset,
    AssetTracker,
    Base,
    Finding,
    FindingTracker,
    Scan,
    SessionLocal,
    Setting,
    engine,
    utcnow,
)
from scanqueue import REDIS_URL, live_channel, log_key, redis_conn, scan_queue, stop_key

# ── Scheduler ────────────────────────────────────────────────────────────────

scheduler = AsyncIOScheduler()
SCHEDULED_JOB_ID = "scheduled-scan"


async def scheduled_scan():
    domains = load_config().get("targets", [])
    if not domains:
        return
    scan, overlap = _enqueue_scan(domains, "schedule")
    if scan is None:
        print("EASM Scheduler: A scan is already running — scheduled run skipped.", flush=True)
    else:
        print(f"EASM Scheduler: Scheduled scan enqueued ({scan.date}).", flush=True)


def apply_schedule():
    if scheduler.get_job(SCHEDULED_JOB_ID):
        scheduler.remove_job(SCHEDULED_JOB_ID)
    schedule = load_config().get("schedule", "").strip()
    if not schedule:
        return
    try:
        trigger = CronTrigger.from_crontab(schedule)
    except (ValueError, KeyError):
        print(f"EASM Scheduler: Invalid cron expression '{schedule}' — scheduler disabled.", flush=True)
        return
    scheduler.add_job(scheduled_scan, trigger, id=SCHEDULED_JOB_ID, replace_existing=True)


def next_scheduled_run() -> Optional[str]:
    if not scheduler.running:
        return None
    job = scheduler.get_job(SCHEDULED_JOB_ID)
    if job and job.next_run_time:
        return job.next_run_time.isoformat()
    return None


@asynccontextmanager
async def lifespan(app: FastAPI):
    # In Docker (WORKDIR /app) alembic migrations are available; in CI/tests
    # create tables directly from metadata to avoid hardcoded /app paths.
    if os.path.isfile("/app/alembic.ini"):
        subprocess.run(["alembic", "upgrade", "head"], cwd="/app", check=True)
    else:
        await asyncio.to_thread(Base.metadata.create_all, bind=engine)
    imported = await asyncio.to_thread(
        ingest.import_legacy_results, load_config().get("targets", [])
    )
    if imported:
        print(f"EASM DB: {imported} alte Scan-Ergebnisse importiert.", flush=True)
    await asyncio.to_thread(ingest.backfill_nuclei_enabled)
    await asyncio.to_thread(ingest.rebuild_trackers)
    await asyncio.to_thread(auth.load_credentials)
    scheduler.start()
    apply_schedule()
    yield
    scheduler.shutdown(wait=False)


app = FastAPI(title="EASM Dashboard", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Auth & Security Middleware ──────────────────────────────────────────────


@app.middleware("http")
async def auth_and_security_middleware(request: Request, call_next):
    path = request.url.path
    if path.startswith("/api/") and not path.startswith("/api/auth/"):
        if not auth.valid_session(request.cookies.get(auth.SESSION_COOKIE)):
            return JSONResponse({"detail": "Nicht authentifiziert."}, status_code=401)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com https://cdn.jsdelivr.net; "
        "img-src 'self' data:; "
        "connect-src 'self' ws: wss:"
    )
    return response


# ── Auth Endpoints ───────────────────────────────────────────────────────────


class LoginRequest(BaseModel):
    password: str
    code: str = ""


@app.post("/api/auth/login")
def login(req: LoginRequest, request: Request, response: Response):
    ip = request.client.host if request.client else "unknown"
    if auth.is_blocked(ip):
        raise HTTPException(
            status_code=429, detail="Too many attempts — please try again later."
        )
    if not auth.verify_password(req.password):
        auth.register_failure(ip)
        raise HTTPException(status_code=401, detail="Invalid credentials.")
    if auth.totp_enabled() and not auth.verify_totp(req.code):
        auth.register_failure(ip)
        raise HTTPException(
            status_code=401,
            detail="totp_required" if not req.code else "Invalid 2FA code.",
        )
    auth.clear_failures(ip)
    token = auth.create_session()
    response.set_cookie(
        auth.SESSION_COOKIE,
        token,
        httponly=True,
        samesite="strict",
        max_age=24 * 3600,
    )
    return {"status": "ok"}


@app.post("/api/auth/logout")
def logout(request: Request, response: Response):
    auth.destroy_session(request.cookies.get(auth.SESSION_COOKIE))
    response.delete_cookie(auth.SESSION_COOKIE)
    return {"status": "ok"}


@app.get("/api/auth/check")
def auth_check(request: Request):
    return {
        "authenticated": auth.valid_session(request.cookies.get(auth.SESSION_COOKIE)),
        "totp_enabled": auth.totp_enabled(),
    }


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class TotpSetupRequest(BaseModel):
    current_password: str


class TotpVerifyRequest(BaseModel):
    current_password: str
    code: str


class TotpDisableRequest(BaseModel):
    current_password: str
    code: str = ""


@app.get("/api/auth/user")
def auth_user():
    return {"username": auth.DEFAULT_USERNAME, "totp_enabled": auth.totp_enabled()}


@app.post("/api/auth/change-password")
def change_password(req: ChangePasswordRequest, request: Request, response: Response):
    ip = request.client.host if request.client else "unknown"
    if not auth.verify_password(req.current_password):
        auth.register_failure(ip)
        raise HTTPException(status_code=401, detail="Invalid current password.")
    if not req.new_password:
        raise HTTPException(status_code=400, detail="Neues Passwort darf nicht leer sein.")
    auth.clear_failures(ip)
    auth.set_password_hash(auth.hash_password(req.new_password))
    auth.clear_all_sessions()
    response.delete_cookie(auth.SESSION_COOKIE)
    return {"success": True}


@app.post("/api/auth/totp/setup")
def totp_setup(req: TotpSetupRequest, request: Request):
    ip = request.client.host if request.client else "unknown"
    if not auth.verify_password(req.current_password):
        auth.register_failure(ip)
        raise HTTPException(status_code=401, detail="Invalid password.")
    if auth.totp_enabled():
        raise HTTPException(status_code=400, detail="2FA is already enabled.")
    auth.clear_failures(ip)
    return auth.generate_totp_setup()


@app.post("/api/auth/totp/verify")
def totp_verify(req: TotpVerifyRequest, request: Request):
    ip = request.client.host if request.client else "unknown"
    if not auth.verify_password(req.current_password):
        auth.register_failure(ip)
        auth.clear_pending_totp_secret()
        raise HTTPException(status_code=401, detail="Invalid password.")
    if not auth.verify_pending_totp(req.code):
        auth.register_failure(ip)
        auth.clear_pending_totp_secret()
        raise HTTPException(status_code=401, detail="Invalid 2FA code.")
    auth.clear_failures(ip)
    auth.commit_pending_totp_secret()
    return {"totp_enabled": True}


@app.post("/api/auth/totp/disable")
def totp_disable(req: TotpDisableRequest, request: Request):
    ip = request.client.host if request.client else "unknown"
    if not auth.verify_password(req.current_password):
        auth.register_failure(ip)
        raise HTTPException(status_code=401, detail="Invalid password.")
    if auth.totp_enabled() and req.code and not auth.verify_totp(req.code):
        auth.register_failure(ip)
        raise HTTPException(status_code=401, detail="Invalid 2FA code.")
    auth.clear_failures(ip)
    auth.clear_pending_totp_secret()
    auth.set_totp_secret(None)
    return {"totp_enabled": False}


CONFIG_FILE = "/data/config.json"
RESULTS_DIR = "/results"
SCRIPTS_DIR = "/scripts"

# ── Config ──────────────────────────────────────────────────────────────────

DEFAULT_CONFIG = {
    "targets": [],
    "discord_webhook": "",
    "slack_webhook": "",
    "schedule": "0 3 * * *",
    "nuclei_severity": ["critical", "high", "medium"],
    "ports": "80,443,8080,8443,22,21,3306,5432,6379,9200,27017",
    "notify_on": ["new_asset", "new_vuln", "scan_failed"],
    "smtp_host": "",
    "smtp_port": 587,
    "smtp_user": "",
    "smtp_password": "",
    "smtp_from": "",
    "smtp_to": "",
    "smtp_tls": "starttls",
    "enable_httpx": True,
    "enable_nmap": True,
    "enable_nuclei": True,
}


def load_config() -> dict:
    session = SessionLocal()
    try:
        row = session.get(Setting, "config")
        if row and row.value:
            return {**DEFAULT_CONFIG, **row.value}
        # one-time migration from legacy config.json
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE) as f:
                cfg = {**DEFAULT_CONFIG, **json.load(f)}
            session.add(Setting(key="config", value=cfg))
            session.commit()
            print("EASM DB: config.json in DB migriert.", flush=True)
            return cfg
        return DEFAULT_CONFIG
    finally:
        session.close()


def save_config(cfg: dict):
    session = SessionLocal()
    try:
        row = session.get(Setting, "config")
        if row:
            row.value = cfg
        else:
            session.add(Setting(key="config", value=cfg))
        session.commit()
    finally:
        session.close()


class Config(BaseModel):
    targets: list[str]
    discord_webhook: str = ""
    slack_webhook: str = ""
    schedule: str = "0 3 * * *"
    nuclei_severity: list[str] = ["critical", "high", "medium"]
    ports: str = "80,443,8080,8443,22,21,3306,5432,6379,9200,27017"
    notify_on: list[str] = ["new_asset", "new_vuln", "scan_failed"]
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    smtp_to: str = ""
    smtp_tls: str = "starttls"
    enable_httpx: bool = True
    enable_nmap: bool = True
    enable_nuclei: bool = True


@app.get("/api/config")
def get_config():
    return load_config()


@app.get("/api/domains")
def list_domains():
    return {"domains": load_config().get("targets", [])}


@app.post("/api/config")
def update_config(cfg: Config):
    save_config(cfg.dict())
    apply_schedule()
    return {"status": "saved"}


# ── Scan Results ─────────────────────────────────────────────────────────────


@app.get("/api/scans")
def list_scans(domain: Optional[str] = None):
    session = SessionLocal()
    try:
        q = session.query(Scan).order_by(Scan.started_at.desc()).limit(30)
        scans = []
        for s in q:
            assets_q = session.query(Asset).filter_by(scan_id=s.id)
            findings_q = session.query(Finding).filter_by(scan_id=s.id)
            if domain:
                assets_q = assets_q.filter_by(domain=domain)
                findings_q = findings_q.filter_by(domain=domain)
            assets = assets_q.all()
            scans.append(
                {
                    "date": s.date,
                    "status": s.status,
                    "triggered_by": s.triggered_by,
                    "target": s.target_desc,
                    "subdomains": len(assets),
                    "live_hosts": sum(1 for a in assets if a.http_status is not None),
                    "open_ports": sum(len(a.ports.split(",")) for a in assets if a.ports),
                    "findings": findings_q.count(),
                }
            )
        return scans
    finally:
        session.close()


@app.get("/api/scans/{date}")
def get_scan(date: str):
    base = f"{RESULTS_DIR}/{date}"
    result = {"date": date, "files": {}}
    for fname in ["subdomains.txt", "resolved.txt", "http-results.txt", "ports.txt", "vulns.txt"]:
        fp = os.path.join(base, fname)
        if os.path.exists(fp):
            with open(fp) as f:
                result["files"][fname] = f.read()
    return result


@app.get("/api/scans/{date}/findings")
def get_findings(date: str, severity: Optional[str] = None, domain: Optional[str] = None):
    session = SessionLocal()
    try:
        scan = session.query(Scan).filter_by(date=date).one_or_none()
        if not scan:
            return []
        q = session.query(Finding).filter_by(scan_id=scan.id)
        if severity:
            q = q.filter_by(severity=severity)
        if domain:
            q = q.filter_by(domain=domain)
        return [
            {
                "raw": f.raw,
                "severity": f.severity,
                "domain": f.domain,
                "host": f.host,
                "template": f.template,
            }
            for f in q.order_by(Finding.severity).all()
        ]
    finally:
        session.close()


# ── Scan Queue (RQ) ──────────────────────────────────────────────────────────


def _active_scans(session) -> list[Scan]:
    return session.query(Scan).filter(Scan.status.in_(["queued", "running"])).all()


def _enqueue_scan(domains: list[str], triggered_by: str):
    """Create a queued scan row + enqueue RQ job. Returns (scan, overlap_domains)."""
    cfg = load_config()
    session = SessionLocal()
    try:
        active = _active_scans(session)
        active_domains = {d for s in active for d in (s.domains or [])}
        overlap = sorted(set(domains) & active_domains)
        if overlap:
            return None, overlap

        now = datetime.now()
        date = now.strftime("%Y-%m-%d_%H-%M-%S") + f"-{now.microsecond // 1000:03d}"
        out = f"{RESULTS_DIR}/{date}"
        os.makedirs(out, exist_ok=True)
        scan = Scan(
            date=date,
            started_at=utcnow(),
            status="queued",
            triggered_by=triggered_by,
            nuclei_enabled=cfg.get("enable_nuclei", True),
            target_desc=domains[0] if len(domains) == 1 else f"{len(domains)} Targets",
            output_dir=out,
            domains=domains,
        )
        session.add(scan)
        session.commit()
        session.refresh(scan)

        job = scan_queue.enqueue("scanner.run_scan_job", scan.id, job_timeout=3600)
        scan.job_id = job.id
        session.commit()
        return scan, []
    finally:
        session.close()


class ScanRequest(BaseModel):
    target: Optional[str] = None


@app.post("/api/scan/trigger")
def trigger_scan(req: ScanRequest):
    domains = load_config().get("targets", []) if not req.target or req.target == "__all__" else [req.target]
    if not domains:
        raise HTTPException(status_code=400, detail="No targets configured.")
    scan, overlap = _enqueue_scan(domains, "manual")
    if scan is None:
        return {"status": "domain_conflict", "domains": overlap}
    return {"status": "queued", "date": scan.date, "target": scan.target_desc}


@app.post("/api/scan/cancel")
def cancel_scan():
    session = SessionLocal()
    try:
        active = _active_scans(session)
        if not active:
            return {"status": "nothing_running"}
        for scan in active:
            redis_conn.set(stop_key(scan.id), "1", ex=3600)
            if scan.status == "queued" and scan.job_id:
                try:
                    scan_queue.fetch_job(scan.job_id).cancel()
                except Exception:
                    pass
                scan.status = "canceled"
                scan.finished_at = utcnow()
                scan.error = "Abgebrochen (wartete in Queue)"
        session.commit()
        return {"status": "canceling", "count": len(active)}
    finally:
        session.close()


@app.get("/api/scan/status")
def scan_status():
    session = SessionLocal()
    try:
        active = _active_scans(session)
        latest_done = (
            session.query(Scan)
            .filter(Scan.status.in_(["done", "failed", "canceled"]))
            .order_by(Scan.started_at.desc())
            .first()
        )
        running = next((s for s in active if s.status == "running"), None)
        cur = running or (active[0] if active else None)
        return {
            "running": bool(active),
            "state": cur.status if cur else "idle",
            "target": cur.target_desc if cur else None,
            "started": cur.started_at.isoformat() if cur and cur.started_at else None,
            "queued": sum(1 for s in active if s.status == "queued"),
            "date": cur.date if cur else (latest_done.date if latest_done else None),
            "next_run": next_scheduled_run(),
            "schedule": load_config().get("schedule", ""),
        }
    finally:
        session.close()


@app.post("/api/notify/test")
def notify_test():
    cfg = load_config()
    if not notify.smtp_configured(cfg):
        raise HTTPException(
            status_code=400, detail="SMTP nicht konfiguriert (smtp_host/smtp_to fehlen)."
        )
    try:
        notify.send_test_mail(cfg)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Versand fehlgeschlagen: {e}")
    return {"status": "sent"}


@app.get("/api/assets")
def list_assets(
    type: Optional[str] = None,
    q: Optional[str] = None,
    domain: Optional[str] = None,
    page: int = 1,
    per_page: int = 25,
):
    """Asset inventory of the latest completed scan."""
    session = SessionLocal()
    try:
        latest = (
            session.query(Scan).filter_by(status="done").order_by(Scan.started_at.desc()).first()
        )
        if not latest:
            return {
                "total": 0,
                "page": 1,
                "per_page": per_page,
                "counts": {},
                "items": [],
                "scan": None,
            }

        base = session.query(Asset).filter_by(scan_id=latest.id)
        if domain:
            base = base.filter_by(domain=domain)
        if q:
            base = base.filter(Asset.host.ilike(f"%{q}%"))

        def type_filter(query, t):
            if t == "ipv4":
                return query.filter(Asset.ip.isnot(None))
            if t == "http":
                return query.filter(Asset.http_status.isnot(None))
            if t == "ports":
                return query.filter(Asset.ports.isnot(None))
            if t == "tech":
                return query.filter(Asset.tech.isnot(None))
            return query

        counts = {"all": base.count()}
        for t in ["ipv4", "http", "ports", "tech"]:
            counts[t] = type_filter(base, t).count()

        filtered = type_filter(base, type if type != "all" else None)
        total = filtered.count()
        items = (
            filtered.order_by(Asset.domain, Asset.host)
            .offset((max(page, 1) - 1) * per_page)
            .limit(min(per_page, 200))
            .all()
        )

        # open issues per host (from finding tracker)
        issue_rows = (
            session.query(FindingTracker.host, FindingTracker.severity, func.count())
            .filter(FindingTracker.resolved.is_(False))
            .group_by(FindingTracker.host, FindingTracker.severity)
            .all()
        )
        issues_map: dict[str, dict] = {}
        for host, sev_name, cnt in issue_rows:
            issues_map.setdefault(host, {})[sev_name] = cnt

        return {
            "total": total,
            "page": page,
            "per_page": per_page,
            "scan": latest.date,
            "counts": counts,
            "items": [
                {
                    "host": a.host,
                    "domain": a.domain,
                    "ip": a.ip,
                    "http_status": a.http_status,
                    "title": a.title,
                    "tech": a.tech,
                    "ports": a.ports,
                    "issues": issues_map.get(a.host, {}),
                }
                for a in items
            ],
        }
    finally:
        session.close()


@app.get("/api/stats/overview")
def stats_overview():
    session = SessionLocal()
    try:
        done_scans = (
            session.query(Scan)
            .filter_by(status="done")
            .order_by(Scan.started_at.desc())
            .limit(30)
            .all()
        )
        latest = done_scans[0] if done_scans else None
        previous = done_scans[1] if len(done_scans) > 1 else None

        def scan_counts(scan):
            assets = session.query(Asset).filter_by(scan_id=scan.id).all()
            return {
                "assets": len(assets),
                "live_hosts": sum(1 for a in assets if a.http_status is not None),
                "open_ports": sum(len(a.ports.split(",")) for a in assets if a.ports),
            }

        open_q = session.query(FindingTracker).filter(FindingTracker.resolved.is_(False))
        sev = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
        for f in open_q.all():
            sev[f.severity] = sev.get(f.severity, 0) + 1
        open_total = sum(sev.values())

        score = 10.0 - (
            sev.get("critical", 0) * 2.0
            + sev.get("high", 0) * 1.0
            + sev.get("medium", 0) * 0.3
            + sev.get("low", 0) * 0.1
        )
        score = max(0.0, round(score, 1))

        cur = scan_counts(latest) if latest else {"assets": 0, "live_hosts": 0, "open_ports": 0}
        prev = scan_counts(previous) if previous else cur
        new_findings_latest = 0
        if latest:
            new_findings_latest = (
                session.query(FindingTracker)
                .filter_by(first_scan_id=latest.id, resolved=False)
                .count()
            )

        findings_by_scan = []
        for s in reversed(done_scans[:14]):
            row = {"date": s.date, "critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
            if s.nuclei_enabled:
                for f in session.query(Finding).filter_by(scan_id=s.id).all():
                    row[f.severity] = row.get(f.severity, 0) + 1
            findings_by_scan.append(row)

        return {
            "latest_scan": latest.date if latest else None,
            "totals": {
                "assets": cur["assets"],
                "live_hosts": cur["live_hosts"],
                "open_findings": open_total,
                "open_ports": cur["open_ports"],
                "domains": len(load_config().get("targets", [])),
            },
            "findings_by_severity": sev,
            "deltas": {
                "assets": cur["assets"] - prev["assets"],
                "live_hosts": cur["live_hosts"] - prev["live_hosts"],
                "new_findings": new_findings_latest,
            },
            "score": score,
            "findings_by_scan": findings_by_scan,
        }
    finally:
        session.close()


@app.get("/api/findings/open")
def open_findings(domain: Optional[str] = None, severity: Optional[str] = None):
    session = SessionLocal()
    try:
        q = session.query(FindingTracker).filter(FindingTracker.resolved.is_(False))
        if domain:
            q = q.filter_by(domain=domain)
        if severity:
            q = q.filter_by(severity=severity)
        order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
        rows = sorted(q.all(), key=lambda f: order.get(f.severity, 5))
        return [
            {
                "domain": f.domain,
                "template": f.template,
                "host": f.host,
                "severity": f.severity,
                "raw": f.raw,
                "first_seen": f.first_seen.isoformat(),
                "last_seen": f.last_seen.isoformat(),
            }
            for f in rows
        ]
    finally:
        session.close()


@app.get("/api/changes/latest")
def latest_changes():
    session = SessionLocal()
    try:
        latest = (
            session.query(Scan).filter_by(status="done").order_by(Scan.started_at.desc()).first()
        )
        if not latest:
            return {"scan": None, "new_assets": [], "new_findings": []}
        new_assets = session.query(AssetTracker).filter_by(first_scan_id=latest.id).all()
        new_findings = (
            session.query(FindingTracker).filter_by(first_scan_id=latest.id, resolved=False).all()
        )
        return {
            "scan": latest.date,
            "new_assets": [{"domain": a.domain, "host": a.host} for a in new_assets],
            "new_findings": [
                {
                    "domain": f.domain,
                    "severity": f.severity,
                    "host": f.host,
                    "template": f.template,
                }
                for f in new_findings
            ],
        }
    finally:
        session.close()


@app.websocket("/ws/scan")
async def ws_scan(ws: WebSocket):
    if not auth.valid_session(ws.cookies.get(auth.SESSION_COOKIE)):
        await ws.close(code=4401)
        return
    await ws.accept()
    import redis.asyncio as aioredis

    session = SessionLocal()
    try:
        scan = (
            session.query(Scan)
            .filter(Scan.status.in_(["queued", "running"]))
            .order_by(Scan.started_at.desc())
            .first()
        ) or session.query(Scan).order_by(Scan.started_at.desc()).first()
        scan_id = scan.id if scan else None
        scan_state_val = scan.status if scan else None
        scan_date = scan.date if scan else None
    finally:
        session.close()

    if scan_id is None:
        await ws.send_text(json.dumps({"type": "done", "date": ""}))
        await ws.close()
        return

    r = aioredis.from_url(REDIS_URL)
    try:
        lines = await r.lrange(log_key(scan_id), 0, -1)
        for line in lines:
            if isinstance(line, bytes):
                line = line.decode(errors="replace")
            await ws.send_text(json.dumps({"type": "log", "line": line}))

        if scan_state_val in ("queued", "running"):
            pubsub = r.pubsub()
            await pubsub.subscribe(live_channel(scan_id))
            try:
                async for msg in pubsub.listen():
                    if msg.get("type") != "message":
                        continue
                    data = msg["data"]
                    if isinstance(data, bytes):
                        data = data.decode(errors="replace")
                    if data == "__DONE__":
                        await ws.send_text(json.dumps({"type": "done", "date": scan_date}))
                        break
                    await ws.send_text(json.dumps({"type": "log", "line": data}))
            except WebSocketDisconnect:
                pass
            finally:
                try:
                    await pubsub.unsubscribe(live_channel(scan_id))
                    await pubsub.close()
                except Exception:
                    pass
        else:
            await ws.send_text(json.dumps({"type": "done", "date": scan_date}))
    finally:
        await r.aclose()
    try:
        await ws.close()
    except Exception:
        pass


# ── Static Frontend ──────────────────────────────────────────────────────────

if os.path.exists("/app/static"):
    app.mount("/", StaticFiles(directory="/app/static", html=True), name="static")
