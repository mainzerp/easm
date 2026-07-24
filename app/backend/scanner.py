"""RQ worker job: execute a scan end-to-end in the worker container."""

import os

import ingest
import notify
from config import load_config
from db import Scan, SessionLocal, utcnow
from pipeline.events import RedisPublisher
from pipeline.runner import PipelineRunner
from scanqueue import LOG_TTL, live_channel, log_key, redis_conn, stop_key

RESULTS_DIR = "/results"


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
        cfg = load_config(session)
        out = scan.output_dir
        os.makedirs(out, exist_ok=True)

        scan.status = "running"
        scan.started_at = utcnow()
        session.commit()

        publisher = RedisPublisher(scan_id, out)

        def stop_check() -> bool:
            return bool(redis_conn.exists(stop_key(scan_id)))

        outcome = PipelineRunner(
            scan_id=scan_id,
            out_dir=out,
            domains=domains,
            cfg=cfg,
            publisher=publisher,
            stop_check=stop_check,
        ).run()

        if outcome.status == "canceled":
            _finish(session, scan, "canceled", "Canceled by user")
            publisher.log("[canceled] Scan canceled.")
        elif outcome.status == "failed":
            _finish(session, scan, "failed", outcome.error)
            notify.notify_scan_failed(cfg, scan.target_desc, outcome.error or "unknown error")
        else:
            _finish(session, scan, "done")
            if outcome.warnings:
                scan.error = "; ".join(outcome.warnings)
                session.commit()
            changes = ingest.ingest_scan(session, scan, out, domains)
            notify.notify_scan_changes(cfg, changes, domains, scan.date)
    except Exception as e:
        try:
            scan = session.get(Scan, scan_id)
            if scan:
                _finish(session, scan, "failed", str(e))
        except Exception:
            pass
        try:
            notify.notify_scan_failed(load_config(session), "", str(e))
        except Exception:
            pass
    finally:
        redis_conn.delete(stop_key(scan_id))
        redis_conn.publish(live_channel(scan_id), "__DONE__")
        redis_conn.expire(log_key(scan_id), LOG_TTL)
        session.close()
