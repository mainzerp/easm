"""RQ worker job: execute a scan end-to-end in the worker container."""

import os
import subprocess

import ingest
import notify
from db import Scan, SessionLocal, Setting, utcnow
from scanqueue import LOG_TTL, live_channel, log_key, redis_conn, stop_key

SCRIPT = "/scripts/run-easm.sh"
RESULTS_DIR = "/results"

DEFAULT_CONFIG_KEYS = {
    "discord_webhook": "",
    "nuclei_severity": ["critical", "high"],
    "ports": "80,443",
    "enable_httpx": True,
    "enable_nmap": True,
    "enable_nuclei": True,
}


def _load_config(session) -> dict:
    row = session.get(Setting, "config")
    return {**DEFAULT_CONFIG_KEYS, **(row.value if row and row.value else {})}


def _build_env(cfg: dict, domains: list[str], out: str) -> dict:
    return {
        **os.environ,
        "TARGET_DOMAIN": "\n".join(domains),
        "DISCORD_WEBHOOK": cfg.get("discord_webhook", ""),
        "NUCLEI_SEVERITY": ",".join(cfg.get("nuclei_severity", ["critical", "high"])),
        "PORTS": cfg.get("ports", "80,443"),
        "ENABLE_HTTPX": "true" if cfg.get("enable_httpx", True) else "false",
        "ENABLE_NMAP": "true" if cfg.get("enable_nmap", True) else "false",
        "ENABLE_NUCLEI": "true" if cfg.get("enable_nuclei", True) else "false",
        "OUTPUT_DIR": out,
    }


def _publish(line: str, scan_id: int) -> None:
    redis_conn.rpush(log_key(scan_id), line)
    redis_conn.expire(log_key(scan_id), LOG_TTL)
    redis_conn.publish(live_channel(scan_id), line)


def _finish(session, scan: Scan, status: str, error: str | None = None) -> None:
    scan.finished_at = utcnow()
    scan.status = status
    if error:
        scan.error = error
    session.commit()


def run_scan_job(scan_id: int) -> None:
    session = SessionLocal()
    try:
        scan = session.get(Scan, scan_id)
        if not scan:
            return
        if redis_conn.exists(stop_key(scan_id)):
            _finish(session, scan, "canceled", "Canceled before start")
            redis_conn.delete(stop_key(scan_id))
            redis_conn.publish(live_channel(scan_id), "__DONE__")
            return
        domains = scan.domains or []
        cfg = _load_config(session)
        out = scan.output_dir
        os.makedirs(out, exist_ok=True)

        scan.status = "running"
        scan.started_at = utcnow()
        session.commit()

        env = _build_env(cfg, domains, out)
        proc = subprocess.Popen(
            [SCRIPT],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=env,
        )

        canceled = False
        for raw in iter(proc.stdout.readline, b""):
            if redis_conn.exists(stop_key(scan_id)):
                canceled = True
                proc.terminate()
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    proc.kill()
                break
            _publish(raw.decode(errors="replace").rstrip(), scan_id)

        if not canceled:
            proc.wait()

        if canceled:
            _finish(session, scan, "canceled", "Canceled by user")
            _publish("[canceled] Scan canceled.", scan_id)
        elif proc.returncode == 0:
            _finish(session, scan, "done")
            changes = ingest.ingest_scan(session, scan, out, domains)
            notify.notify_scan_changes(cfg, changes, domains, scan.date)
        else:
            _finish(session, scan, "failed", f"Exit-Code {proc.returncode}")
            notify.notify_scan_failed(cfg, scan.target_desc, f"Exit-Code {proc.returncode}")
    except Exception as e:
        try:
            scan = session.get(Scan, scan_id)
            if scan:
                _finish(session, scan, "failed", str(e))
        except Exception:
            pass
        try:
            notify.notify_scan_failed(_load_config(session), "", str(e))
        except Exception:
            pass
    finally:
        redis_conn.delete(stop_key(scan_id))
        redis_conn.publish(live_channel(scan_id), "__DONE__")
        redis_conn.expire(log_key(scan_id), LOG_TTL)
        session.close()
