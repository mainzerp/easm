"""Notification handling for EASM Dashboard.

SMTP mail (primary channel), Discord and Slack webhooks.
Change detection (new assets/findings) comes from the DB trackers (ingest.py).
"""

import json
import smtplib
import urllib.request
from email.message import EmailMessage


def smtp_configured(cfg: dict) -> bool:
    return bool(cfg.get("smtp_host") and cfg.get("smtp_to"))


def send_mail(cfg: dict, subject: str, body: str) -> None:
    """Send a mail via the configured SMTP server. Raises on failure."""
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = cfg.get("smtp_from") or cfg.get("smtp_user") or "easm@localhost"
    recipients = [r.strip() for r in cfg.get("smtp_to", "").split(",") if r.strip()]
    msg["To"] = ", ".join(recipients)
    msg.set_content(body)

    host = cfg["smtp_host"]
    port = int(cfg.get("smtp_port", 587))
    tls_mode = cfg.get("smtp_tls", "starttls")
    user = cfg.get("smtp_user") or ""
    password = cfg.get("smtp_password") or ""

    if tls_mode == "ssl":
        server = smtplib.SMTP_SSL(host, port, timeout=30)
    else:
        server = smtplib.SMTP(host, port, timeout=30)
    try:
        if tls_mode == "starttls":
            server.starttls()
        if user:
            server.login(user, password)
        server.send_message(msg)
    finally:
        server.quit()


def send_discord(cfg: dict, content: str) -> None:
    url = cfg.get("discord_webhook", "")
    if not url:
        return
    data = json.dumps({"content": content}).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=15):
        pass


def send_slack(cfg: dict, text: str) -> None:
    url = cfg.get("slack_webhook", "")
    if not url:
        return
    data = json.dumps({"text": text}).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=15):
        pass


def _notify_channels(cfg: dict, subject: str, body: str) -> None:
    errors = []
    if smtp_configured(cfg):
        try:
            send_mail(cfg, subject, body)
            print(f"EASM Notify: Mail sent ({subject})", flush=True)
        except Exception as e:
            errors.append(f"SMTP: {e}")
    if cfg.get("discord_webhook"):
        try:
            send_discord(cfg, f"**{subject}**\n```\n{body}\n```")
            print(f"EASM Notify: Discord sent ({subject})", flush=True)
        except Exception as e:
            errors.append(f"Discord: {e}")
    if cfg.get("slack_webhook"):
        try:
            send_slack(cfg, f"*{subject}*\n```\n{body}\n```")
            print(f"EASM Notify: Slack sent ({subject})", flush=True)
        except Exception as e:
            errors.append(f"Slack: {e}")
    for err in errors:
        print(f"EASM Notify ERROR: {err}", flush=True)


def notify_scan_changes(cfg: dict, changes: dict, targets: list[str], date: str) -> None:
    """Notify about new assets/findings of a completed scan (from DB trackers)."""
    notify_on = cfg.get("notify_on", [])
    target_desc = ", ".join(targets) if targets else date

    if "new_asset" in notify_on and changes.get("new_assets"):
        new_assets = changes["new_assets"]
        body = "New assets discovered:\n\n" + "\n".join(new_assets)
        _notify_channels(cfg, f"[EASM] {len(new_assets)} new assets — {target_desc}", body)

    if "new_vuln" in notify_on and changes.get("new_findings"):
        new_vulns = changes["new_findings"]
        body = "New findings:\n\n" + "\n".join(new_vulns)
        _notify_channels(cfg, f"[EASM] {len(new_vulns)} new findings — {target_desc}", body)


def notify_scan_failed(cfg: dict, target_desc: str, reason: str) -> None:
    if "scan_failed" not in cfg.get("notify_on", []):
        return
    body = f"The scan failed.\n\nTarget: {target_desc}\nReason: {reason}"
    _notify_channels(cfg, f"[EASM] Scan failed — {target_desc}", body)


def send_test_mail(cfg: dict) -> None:
    send_mail(
        cfg,
        "[EASM] Test Notification",
        "This test email confirms the SMTP configuration is working.",
    )
