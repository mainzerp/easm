# Pinned Versions

All build-critical versions are pinned in one place:
`app/backend/Dockerfile` (ARG block), `app/backend/requirements.txt`, `app/frontend/Dockerfile`.

## Scanner Tools (app/backend/Dockerfile ARG)

| Tool | Version |
|------|---------|
| Go toolchain | 1.26.4 (`golang:1.26.4-bookworm`) |
| subfinder | v2.14.0 |
| dnsx | v1.2.3 |
| httpx | v1.9.0 |
| nuclei | v3.9.0 |
| alterx | v0.1.0 |

## Python (app/backend/requirements.txt)

| Package | Version |
|---------|---------|
| fastapi | 0.138.1 |
| uvicorn[standard] | 0.49.0 |
| pydantic | 2.13.4 |
| argon2-cffi | 25.1.0 |
| pyotp | 2.10.0 |
| apscheduler | 3.11.3 |
| sqlalchemy | 2.0.51 |
| alembic | 1.18.5 |
| psycopg[binary] | 3.3.4 |
| rq | 2.10.0 |
| redis | 8.0.1 |
| qrcode | 8.2 |

## Services (docker-compose.yml / docker-compose.local.yml)

| Image | Tag |
|-------|-----|
| PostgreSQL | `postgres:18-alpine` |
| Redis | `redis:8-alpine` |

## Base Images

| Image | Tag |
|-------|-----|
| Backend runtime | `python:3.12-slim-bookworm` |
| Frontend builder | `node:22-alpine` |
| Frontend runtime | `nginx:1.31-alpine` |

## Update Policy

- **Go tools**: update deliberately (individually, with a test scan), bump version in the ARG block. Never use `@latest` — a tool update already caused a build break once (subfinder v2.14.0 requires Go >= 1.24).
- **Python packages**: bump as needed, test locally with `pip install`.
- **nuclei-templates**: intentional floating (security tool needs fresh templates). Downloaded during build via `nuclei -update-templates`.
- **apt packages** (nmap, curl, ca-certificates, bash): float within Debian Bookworm.
- **Base images**: distro codename pinned (`bookworm`), patch level floats.
