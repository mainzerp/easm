# Technical Documentation

This document is intended for developers and operators. For a feature overview
and first-time setup, see [`README.md`](../README.md).

---

## Architecture

```
frontend (nginx, UI)  ──►  backend (FastAPI, API/WS/Scheduler) ──► socket-proxy
                                │                                 (read-only
                    ┌───────────┼───────────┐                      Docker API:
                    ▼           ▼           ▼                       container
                  db     redis (Queue)   worker (RQ, Scans)         logs only)
              PostgreSQL       │         (2 parallel jobs)
                               │
                         survives backend restarts,
                         cancelable
```

- **Frontend:** React 18 + Vite, built to static HTML/JS and served by nginx.
  TLS is optionally terminated by the nginx container (`EASM_TLS=on|off`).
- **Backend:** FastAPI + Uvicorn. Manages config, scan queue, assets/findings,
  scheduler, authentication, and container log access.
- **Worker:** Separate container processing scan jobs from the Redis queue via
  RQ, so long scans never block the API. Runs the modular scan pipeline
  (`pipeline/` package: `steps`, `registry`, `runner`, `events`, `parsers`).
- **PostgreSQL:** Persistent storage (scans, assets, findings, settings,
  credentials).
- **Redis:** Job queue for RQ + Pub/Sub for live logs and structured pipeline
  events during a scan.
- **Socket proxy:** `wollomatic/socket-proxy` sidecar exposing only the
  read-only container-list and container-logs Docker API endpoints to the
  backend (see "Container Log Access").

---

## Project Structure

```
easm-ui/
├── app/
│   ├── backend/
│   │   ├── main.py              # FastAPI — config, scan, results, logs, WebSocket
│   │   ├── auth.py              # DB-backed auth, TOTP, rate-limiting
│   │   ├── config.py            # shared scan/notification config (DB-backed)
│   │   ├── containerlogs.py     # read-only container log client (socket proxy)
│   │   ├── logroutes.py         # log route handlers (REST + WS live tail)
│   │   ├── db.py                # SQLAlchemy models (settings, scans, assets, findings)
│   │   ├── scanner.py           # RQ job: runs the scan pipeline
│   │   ├── pipeline/            # modular scan pipeline
│   │   │   ├── steps.py         # StepDefinition per tool (subfinder … nuclei)
│   │   │   ├── registry.py      # build_steps(cfg): ordered, flag-filtered steps
│   │   │   ├── runner.py        # PipelineRunner: exec, timeouts, cancel, events
│   │   │   ├── events.py        # RedisPublisher: scanlog/scanlive/scanphase + scan.log
│   │   │   └── parsers.py       # pure output parsers (httpx, nmap, findings)
│   │   ├── requirements.txt     # pinned Python dependencies
│   │   ├── requirements-dev.txt # pytest, ruff
│   │   ├── tests/               # pytest tests
│   │   └── Dockerfile           # multi-stage: Go tools + Python runtime
│   └── frontend/
│       ├── src/
│       │   ├── App.jsx
│       │   ├── components/      # Sidebar, LogTerminal, UserSettingsModal, UI primitives
│       │   ├── views/           # Dashboard, Assets, Scans, Findings, Config, ScanLive, Logs
│       │   └── __tests__/       # Vitest tests
│       ├── eslint.config.js
│       ├── vitest.config.js
│       ├── nginx.conf
│       ├── Dockerfile
│       └── package.json
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
| POST | `/api/scan/trigger` | Start a manual scan (response includes the queued scan `id`) |
| POST | `/api/scan/cancel` | Cancel the running scan |
| GET | `/api/scan/status` | Current scan status (includes `id` of the current/latest scan) |
| GET | `/api/scans` | Last 30 scans |
| GET | `/api/scans/{date}` | Raw data of a scan |
| GET | `/api/scans/{date}/findings` | Findings of a scan (filterable by severity/domain) |
| GET | `/api/scans/{date}/log` | `scan.log` from disk; Redis backlog fallback for recent scans |
| GET | `/api/assets` | Assets of the latest scan (paginated, filterable, searchable) |
| GET | `/api/stats/overview` | Dashboard aggregate (score, metrics, deltas, trends) |
| GET | `/api/findings/open` | Open findings (filterable by domain/severity) |
| GET | `/api/changes/latest` | New assets/findings since the last scan |
| GET | `/api/logs/services` | Log-enabled services (`[{"name", "container", "status"}]`) |
| GET | `/api/logs/{service}` | Container logs; query: `tail` (≤5000), `since`, `until`, `lines`, `level` |
| WS | `/ws/scan?scan_id=` | Live scan feed (log + phase/counter/status events); unknown id → close 4404 |
| WS | `/ws/logs?services=&tail=` | Live tail of service logs, merged timestamp-ordered |
| POST | `/api/notify/test` | Send test email |

### WebSocket message schemas

`/ws/scan` — server → client:

```json
{"type":"log","line":"..."}
{"type":"phase","phase":"subfinder","title":"Subdomain Discovery","status":"queued|running|done|failed|skipped","seq":1,"total":7,"elapsed_ms":1234,"reason":null,"error":null}
{"type":"counter","counters":{"subdomains":12,"resolved":10,"http":5,"findings":0}}
{"type":"status","status":"running|done|failed|canceled","error":null}
{"type":"done","date":"2026-07-23_10-00-00-000","status":"done|failed|canceled"}
```

On connect the server replays the log backlog (`scanlog:{id}`), then the
recorded phase transitions (`scanphase:{id}`), then streams live events from
the `scanlive:{id}` channel. Pipeline events travel on that channel as
single-line JSON with an `{"easm": 1, ...}` envelope marker; the relay strips
the marker and forwards them as the typed messages above.

`/ws/logs` — server → client:

```json
{"type":"service_log","service":"backend","ts":"2026-07-23T10:00:00Z","line":"...","level":"info|warning|error"}
```

Both WebSocket endpoints require the session cookie (same manual check as the
`/api/*` middleware; unauthenticated connections are closed with code 4401).

---

## Scan Pipeline

Scans are executed by the worker as an ordered pipeline of declarative steps
(`app/backend/pipeline/`). Each step is a `StepDefinition` (key, title, command
builder, timeout, output file, critical flag, skip condition, counter key);
`registry.build_steps(cfg)` returns the ordered steps filtered by the config
enable flags.

| # | Key | Title | Command / action | Timeout | Critical | Enabled when | Counter |
|---|---|---|---|---|---|---|---|
| 1 | `subfinder` | Subdomain Discovery | `subfinder -d <d>... -silent -o subdomains.txt` | 300 s | yes | always | `subdomains` |
| 2 | `alterx` | Subdomain Permutation | `alterx -l subdomains.txt -silent -o alterx.txt` + merge into `subdomains.txt` | 300 s | no | `enable_alterx` (default off) | — |
| 3 | `dnsx` | DNS Resolution | `dnsx -l subdomains.txt -silent -o resolved.txt` | 300 s | yes | always | `resolved` |
| 4 | `httpx` | HTTP Probing | `httpx -l resolved.txt -silent -title -status-code -tech-detect -o http-results.txt` | 300 s | no | `enable_httpx` | `http` |
| 5 | `extract_urls` | URL Extraction | native: regex `https?://[^ ]+` over http-results.txt → urls.txt | — | no | always | — |
| 6 | `nmap` | Port Scan | `nmap -iL resolved.txt -p <ports> --open -oN ports.txt -T4` | 600 s | no | `enable_nmap` | — |
| 7 | `nuclei` | Vulnerability Scan | `nuclei -l urls.txt -severity <cfg> -o vulns.txt -silent` | 1200 s | no | `enable_nuclei` | `findings` |

Failure semantics: a failed **critical** step (subfinder, dnsx) aborts the
pipeline and marks the scan `failed`. A failed non-critical step marks the
phase `failed`, records a warning (stored in `Scan.error`), and the scan ends
`done`. Steps with empty input are `skipped`. Cancellation kills the step's
process group (SIGTERM, SIGKILL after a 10 s grace).

**Adding a new tool:** add a `StepDefinition` builder in `pipeline/steps.py`,
register it at the desired position in `pipeline/registry.py`, add the binary
to `app/backend/Dockerfile`, and rebuild the image. No orchestrator changes —
the runner, events, and UI pick up new phases automatically.

Result contract per scan: `/results/<date>/{subdomains,alterx,resolved,
http-results,urls,ports,vulns}.txt` plus `scan.log` (every log line and a
human-readable rendering of each pipeline event).

---

## Container Log Access

Service logs reach the UI through a Docker socket-proxy sidecar
(`wollomatic/socket-proxy`, service `socket-proxy` in both compose files):

- The Docker socket is mounted **read-only into the proxy only** — never into
  the backend/worker containers.
- The proxy denies all methods by default and only allows `GET` requests to
  `/containers/json` and `/containers/{id}/logs` (`POST=0`, `CONTAINERS=1`,
  `LOGS=1`); it is reachable only on the internal Docker network (no published
  ports).
- The backend talks plain HTTP to the proxy (`DOCKER_PROXY_URL`, default
  `http://socket-proxy:2375`) via `containerlogs.py`.
- Services opt into log collection with the Docker label `easm.logs=enabled`;
  the public name comes from the `easm.service` label (db, redis, backend,
  worker, frontend).
- Severity (`info`/`warning`/`error`) is a keyword **heuristic** — EASM app
  logs are plain `print()` lines without structured levels.

Historical scan logs are served from `/results/<date>/scan.log`; for recent
scans whose file is missing (e.g. pre-pipeline scans), the Redis log backlog
(`scanlog:{id}`, 24 h TTL) is used as a fallback.

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
- `DOCKER_PROXY_URL` — socket-proxy address for container logs (backend only;
  default `http://socket-proxy:2375`).

UI-managed scan config (Config page, stored in the database):
`enable_httpx` / `enable_nmap` / `enable_nuclei` toggle the optional pipeline
phases; `enable_alterx` (default off) inserts the alterx subdomain-permutation
step between subfinder and dnsx.

Pinned versions for all tools, images, and packages are documented in
[`VERSIONS.md`](../VERSIONS.md).

---

## CI/CD

`.github/workflows/ci.yml`:

1. `lint` — `ruff check` (backend) and `eslint` (frontend).
2. `test` — `pytest` (backend with PostgreSQL service) and `vitest` (frontend).
3. `build` — Docker image build, push to GHCR, Trivy scan (CRITICAL/HIGH).

`build` only runs on `main` and requires `packages: write`.
