# Technical Documentation

This document is intended for developers and operators. For a feature overview
and first-time setup, see [`README.md`](../README.md).

---

## Architecture

```
frontend (nginx, UI)  ──►  backend (FastAPI, API/WS/Scheduler)
                                │
                    ┌───────────┼───────────┐
                    ▼           ▼           ▼
                  db     redis (Queue)   worker (RQ, Scans)
              PostgreSQL       │         (2 parallel jobs)
                               │
                         survives backend restarts,
                         cancelable
```

- **Frontend:** React 18 + Vite, built to static HTML/JS and served by nginx.
  TLS is optionally terminated by the nginx container (`EASM_TLS=on|off`).
- **Backend:** FastAPI + Uvicorn. Manages config, scan queue, assets/findings,
  scheduler, and authentication.
- **Worker:** Separate container processing scan jobs from the Redis queue via
  RQ, so long scans never block the API.
- **PostgreSQL:** Persistent storage (scans, assets, findings, settings,
  credentials).
- **Redis:** Job queue for RQ + Pub/Sub for live logs during a scan.

---

## Project Structure

```
easm-ui/
├── app/
│   ├── backend/
│   │   ├── main.py              # FastAPI — config, scan, results, WebSocket
│   │   ├── auth.py              # DB-backed auth, TOTP, rate-limiting
│   │   ├── db.py                # SQLAlchemy models (settings, scans, assets, findings)
│   │   ├── scanner.py           # RQ job: subfinder, httpx, nmap, nuclei
│   │   ├── requirements.txt     # pinned Python dependencies
│   │   ├── requirements-dev.txt # pytest, ruff, httpx
│   │   ├── scripts/            # scan script (bundled into image)
│   │   ├── tests/               # pytest tests
│   │   └── Dockerfile           # multi-stage: Go tools + Python runtime
│   └── frontend/
│       ├── src/
│       │   ├── App.jsx
│       │   ├── components/      # Sidebar, UserSettingsModal, UI primitives
│       │   ├── views/           # Dashboard, Assets, Scans, Findings, Config, ScanLive
│       │   └── __tests__/       # Vitest tests
│       ├── eslint.config.js
│       ├── vitest.config.js
│       ├── nginx.conf
│       ├── Dockerfile
│       └── package.json
├── scripts/
│   └── run-easm.sh              # Subfinder -> dnsx -> httpx -> nmap -> Nuclei
├── .github/workflows/
│   └── ci.yml                   # lint → test → build (Docker + Trivy + GHCR)
├── docker-compose.yml           # Production: uses GHCR images
├── docker-compose.local.yml     # Local development: builds images locally
├── pyproject.toml               # ruff config
├── VERSIONS.md                  # pinned tool versions
├── VERSION.md                   # SemVer
└── README.md
```

---

## Authentication & Security

The tool is a single-user system (username `admin`).

- **First start:** If neither `EASM_ADMIN_PASSWORD` nor
  `EASM_ADMIN_PASSWORD_HASH` is set and no credentials exist in the database,
  the backend generates a random password and writes it once to the log:
  `docker compose logs backend`.
- **Set password:** Via the UI under **User Settings** (bottom left in the
  sidebar) or on first start via `.env`.
- **Generate password hash (for `.env`):**
  ```bash
  docker compose exec backend python -c \
    "from argon2 import PasswordHasher; print(PasswordHasher().hash('YOUR_PASSWORD'))"
  ```
- **TOTP/2FA:** Enable in the UI under **User Settings → Security**. Scan the
  QR code with an authenticator app (e.g. Google Authenticator, Aegis,
  Bitwarden) and enter the verification code. Both enabling and disabling
  require the current password.
- **Change password:** Requires the current password, terminates all sessions
  immediately.
- **Rate limit:** 5 failed attempts/minute → 5 minutes lockout (IP-based).
- **Sessions:** In-memory (24 h). Survive browser reload but not backend
  restart.
- **Security headers:** CSP, X-Frame-Options, X-Content-Type-Options,
  Referrer-Policy, optional HSTS (`EASM_HSTS=on`).

---

## API Reference

All `/api/*` endpoints (except `/api/auth/*`) require a valid session cookie.

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/auth/login` | Login (`password`, optional `code` for TOTP) |
| POST | `/api/auth/logout` | Logout |
| GET | `/api/auth/check` | Auth status (`authenticated`, `totp_enabled`) |
| GET | `/api/auth/user` | Current user (`username`, `totp_enabled`) |
| POST | `/api/auth/change-password` | Change password (requires `current_password`) |
| POST | `/api/auth/totp/setup` | Start 2FA setup (returns `secret` + `qr_uri`) |
| POST | `/api/auth/totp/verify` | Activate 2FA with verification code |
| POST | `/api/auth/totp/disable` | Disable 2FA |
| GET | `/api/domains` | Configured targets (auth required) |
| GET | `/api/config` | Configuration (targets, notifications, scheduler) |
| POST | `/api/config` | Save configuration |
| POST | `/api/scan/trigger` | Start a manual scan |
| POST | `/api/scan/cancel` | Cancel the running scan |
| GET | `/api/scan/status` | Current scan status |
| GET | `/api/scans` | Last 30 scans |
| GET | `/api/scans/{date}` | Raw data of a scan |
| GET | `/api/scans/{date}/findings` | Findings of a scan (filterable by severity/domain) |
| GET | `/api/assets` | Assets of the latest scan (paginated, filterable, searchable) |
| GET | `/api/stats/overview` | Dashboard aggregate (score, metrics, deltas, trends) |
| GET | `/api/findings/open` | Open findings (filterable by domain/severity) |
| GET | `/api/changes/latest` | New assets/findings since the last scan |
| WS | `/ws/scan` | Live log via WebSocket |
| POST | `/api/notify/test` | Send test email |

---

## Deployment

### Production (GHCR Images)

CI builds and pushes images to GHCR on every push to `main`. The production
compose requires a secure database password.

```bash
cp .env.example .env
# Set EASM_DB_PASSWORD (minimum)
echo "EASM_DB_PASSWORD=$(openssl rand -hex 32)" >> .env

docker compose pull
docker compose up -d
```

Frontend listens on standard ports `80` and `443`. To use a different
registry or tag, set `EASM_IMAGE_REGISTRY`, `EASM_IMAGE_REPO`, and
`EASM_IMAGE_TAG`.

### Local Development (Build Locally)

```bash
docker compose -f docker-compose.local.yml up --build
```

Frontend and API are available at `http://localhost:3000` and
`https://localhost:3443`. The first build takes 5–10 minutes because Go
tools compile and Nuclei templates download.

---

## Development

### Backend (Tests + Linting)

```bash
# Postgres/Redis must be running (docker compose up db redis -d)
cd app/backend
pip install -r requirements.txt -r requirements-dev.txt
alembic upgrade head
pytest tests/ -v
ruff check . && ruff format --check --diff .
```

### Frontend (Tests + Linting)

```bash
cd app/frontend
npm install
npm test          # vitest
npm run lint      # eslint
npm run build     # production build
npm run dev       # dev server with HMR
```

---

## Configuration

All important settings are managed via the UI or `.env`. See `.env.example`
for details. Key variables:

- `EASM_ADMIN_PASSWORD` / `EASM_ADMIN_PASSWORD_HASH` — initial setup.
- `EASM_DB_PASSWORD` — PostgreSQL password (required in production).
- `EASM_TLS=on|off` — enable/disable HTTPS in the frontend container.
- `EASM_TLS_SAN` — Subject Alternative Names for the self-signed cert.
- `EASM_HSTS=on|off` — HSTS header (recommended only behind a reverse proxy).
- `TZ` — timezone for the cron scheduler.

Pinned versions for all tools, images, and packages are documented in
[`VERSIONS.md`](../VERSIONS.md).

---

## CI/CD

`.github/workflows/ci.yml`:

1. `lint` — `ruff check` (backend) and `eslint` (frontend).
2. `test` — `pytest` (backend with PostgreSQL service) and `vitest` (frontend).
3. `build` — Docker image build, push to GHCR, Trivy scan (CRITICAL/HIGH).

`build` only runs on `main` and requires `packages: write`.
