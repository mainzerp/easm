# Version

Current version: 0.2.0

## Version History

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
