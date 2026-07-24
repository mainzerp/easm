# Version

Current version: 0.4.1

## Version History

### 0.4.1 - 2026-07-24
- Fixed HTTP Probing phase: the Python `httpx` CLI shim (pulled in by the new socket-proxy dependency) shadowed the ProjectDiscovery httpx binary in `/usr/local/bin`, so the phase always failed and downstream nuclei scans were skipped. The Go binary is now installed as `httpx-pd` and the pipeline registry invokes that name.

### 0.4.0 - 2026-07-23
- Replaced the monolithic `run-easm.sh` shell orchestrator with a modular Python scan pipeline (`app/backend/pipeline/`): declarative `StepDefinition`s, config-driven tool registry, streamed subprocess execution with timeout/cancel semantics.
- Live per-phase progress: the worker publishes typed events (phase/counter/status) via Redis; `/ws/scan` relays them and the ScanLive view shows a real-time pipeline timeline with counters and per-phase elapsed time.
- Added `scan_id` selection to `/ws/scan`, `id` fields to `/api/scan/status` and `/api/scan/trigger`, and `status` on the WS `done` message.
- Added container log access via a read-only Docker socket-proxy sidecar: `GET /api/logs/services`, `GET /api/logs/{service}`, `GET /api/scans/{date}/log`, and live tail over `WS /ws/logs`; new Logs view in the UI.
- Added optional alterx subdomain-permutation step (`enable_alterx`, default off).
- Added Slack webhook notifications (`send_slack`), closing the M5 gap.
- Historical scan logs are written to `/results/<date>/scan.log` during the run.

### 0.3.0 - 2026-07-23
- Added pytest test suite for backend auth endpoints.
- Added vitest test suite for frontend components.
- Added ruff (Python) and eslint (JS) linting configurations.
- Added GitHub Actions workflows: quality (ruff+eslint), test (pytest+vitest), build (Docker+Trivy+GHCR).
- Added CI/CD status badges to README.
- Revised README with architecture diagram, development section, and improved structure.
- Container images are published to `ghcr.io/mainzerp/easm-backend` and `ghcr.io/mainzerp/easm-frontend`.

### 0.2.0 - 2026-07-22
- Added User Settings modal for admin password change and TOTP enable/disable.
- Moved admin credentials from environment variables to the database (`settings.credentials`).
- Removed `EASM_TOTP_SECRET` environment variable; TOTP is now configured via UI.
- Added new auth endpoints: `GET /api/auth/user`, `POST /api/auth/change-password`, `POST /api/auth/totp/setup`, `POST /api/auth/totp/verify`, `POST /api/auth/totp/disable`.
- Added `qrcode==8.2` dependency for server-side QR code generation.
- Added Alembic migration `0004` to seed existing env credentials into the database.

### 0.1.2 - 2026-07-22
- Restructured project layout: moved `backend/` to `app/backend/` and `frontend/` to `app/frontend/`.
- Updated `docker-compose.yml`, `README.md`, `docs/project/roadmap.md`, and `VERSIONS.md` to reflect the new paths.
- Backend and frontend remain separate Docker images and services.

### 0.1.1 - 2026-07-22
- Removed stale artifacts: `.playwright-mcp/`, `dashboard-final.png`, `easm-dashboard.png`, and `docs/SubAgent/FIX_FINDINGS_MULTITARGET/PLAN.md`.
- Verified Docker image tags `postgres:18-alpine` and `redis:8-alpine` against Docker Hub; both are valid, so no changes were made to `docker-compose.yml` or `VERSIONS.md`.
- Confirmed `.env` is listed in `.gitignore` and remains on disk.
- Documented test status: no backend or frontend test suites exist; CI runs smoke tests only.
