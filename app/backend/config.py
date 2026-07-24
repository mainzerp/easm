"""Shared scan/notification configuration (DB-backed, legacy JSON migration)."""

import json
import os

from pydantic import BaseModel

from db import SessionLocal, Setting

CONFIG_FILE = "/data/config.json"

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
    "enable_alterx": False,
}


def _load_config(session) -> dict:
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


def load_config(session=None) -> dict:
    """Load config using the given session, or open a short-lived one."""
    if session is not None:
        return _load_config(session)
    own = SessionLocal()
    try:
        return _load_config(own)
    finally:
        own.close()


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
    enable_alterx: bool = False
