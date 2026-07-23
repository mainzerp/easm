# Pinned Versions

Alle Build-relevanten Versionen sind an genau einer Stelle gepinnt:
`app/backend/Dockerfile` (ARG-Block), `app/backend/requirements.txt`, `app/frontend/Dockerfile`.

## Scanner-Tools (app/backend/Dockerfile ARG)

| Tool | Version |
|------|---------|
| Go toolchain | 1.26.4 (`golang:1.26.4-bookworm`) |
| subfinder | v2.14.0 |
| dnsx | v1.2.3 |
| httpx | v1.9.0 |
| nuclei | v3.9.0 |
| alterx | v0.1.0 |

## Python (app/backend/requirements.txt)

| Paket | Version |
|-------|---------|
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

## Services (docker-compose.yml)

| Image | Tag |
|-------|-----|
| PostgreSQL | `postgres:18-alpine` |
| Redis | `redis:8-alpine` |

## Basisimages

| Image | Tag |
|-------|-----|
| Backend runtime | `python:3.12-slim-bookworm` |
| Frontend builder | `node:22-alpine` |
| Frontend runtime | `nginx:1.31-alpine` |

## Update-Policy

- **Go-Tools**: bewusst aktualisieren (einzeln, mit Test-Scan), Version im ARG-Block erhöhen. Niemals `@latest` verwenden — ein Tool-Update hat bereits einen Build-Bruch verursacht (subfinder v2.14.0 benötigt Go >= 1.24).
- **Python-Pakete**: bei Bedarf erhöhen, `pip install` lokal testen.
- **nuclei-templates**: floaten absichtlich (Security-Tool braucht frische Templates). Werden beim Build via `nuclei -update-templates` geladen.
- **apt-Pakete** (nmap, curl, ca-certificates, bash): floaten innerhalb Debian Bookworm.
- **Basisimages**: Distro-Codename gepinnt (`bookworm`), Patch-Level floatet.
