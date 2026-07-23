"""Seed admin credentials from environment into settings table.

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-22
"""

import json
import os

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Check whether a credentials row already exists.
    conn = op.get_bind()
    row = conn.execute("SELECT key FROM settings WHERE key = 'credentials'").fetchone()
    if row:
        return

    hash_env = os.environ.get("EASM_ADMIN_PASSWORD_HASH", "").strip()
    pw_env = os.environ.get("EASM_ADMIN_PASSWORD", "").strip()
    totp_env = os.environ.get("EASM_TOTP_SECRET", "").strip()

    if hash_env:
        password_hash = hash_env
    elif pw_env:
        from argon2 import PasswordHasher

        password_hash = PasswordHasher().hash(pw_env)
    elif totp_env:
        # No password provided but a TOTP secret exists: create a random password
        # so the credentials row can be inserted. The user must set a password
        # via the UI or via env on the next startup.
        import secrets

        from argon2 import PasswordHasher

        generated = secrets.token_urlsafe(16)
        password_hash = PasswordHasher().hash(generated)
        print(f"EASM Migration: Kein Admin-Passwort gesetzt, generiert: {generated}", flush=True)
    else:
        # Nothing to seed.
        return

    value = {"password_hash": password_hash, "totp_secret": totp_env}
    conn.execute(
        "INSERT INTO settings (key, value) VALUES ('credentials', (:value)::jsonb)",
        {"value": json.dumps(value)},
    )


def downgrade() -> None:
    op.execute("DELETE FROM settings WHERE key = 'credentials'")
