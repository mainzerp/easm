# EASM Dashboard — Production Readiness Roadmap

> Context (decisions): Single-user with strong auth, deployment behind a
> reverse proxy (container provides self-signed cert for RP→Backend),
> PostgreSQL as data store, target size 10+ domains, priority: operations & security.

Legend: Effort S = small (< 0.5 days), M = medium (0.5–1.5 days), L = large (2+ days).

---

## Phase 1 — Operations & Security (first)

### M1: Reproducible Builds [M] — done (2026-07-21)
- Pin tool versions (subfinder/dnsx/httpx/nuclei/alterx to fixed tags instead of `@latest`).
- Fix Go toolchain version; build test in CI (`docker compose build` must always pass).
- Remove `app/backend/Dockerfile.scanner` or define it as a worker image (updated README).
- Acceptance: Fresh build on a clean system with no network surprises; versions documented in one file.

### M2: Auth (Single-User, Strong) [L] — done (2026-07-21, incl. TOTP)
- Backend: login endpoint, password hashing (argon2id/bcrypt), session cookie (HttpOnly, SameSite=Strict) or JWT with short TTL + refresh.
- Password via env/secret (`EASM_ADMIN_PASSWORD_HASH`), no cleartext in repo; first start forces setting.
- Protect all `/api/*` and `/ws/*` endpoints; rate-limit on login (e.g. 5/min) against brute-force.
- Frontend: login view, session handling, 401 → redirect to login; logout button.
- Security headers (CSP, X-Frame-Options, HSTS once TLS).
- Acceptance: No API/WS data without login; wrong password throttled; session survives reload, not server restart (OK).

### M3: TLS — Self-Signed Cert for RP↔Backend [M] — done (2026-07-21)
- Backend container generates a self-signed certificate on start (if not present), persisted in config volume (`/data/tls/`).
- nginx in frontend container continues terminating :3000; backend speaks HTTPS (Uvicorn with `--ssl-*`) OR nginx terminates TLS towards RP.
- Configurable: `EASM_TLS=on|off` (off for pure LAN development).
- Acceptance: RP can access backend via HTTPS; certificate survives container restarts; CN/SAN documented.

### M4: Scheduler [M] — done (2026-07-21)
- Config field `schedule` becomes active: APScheduler (or asyncio-cron) in backend executes scans per cron expression.
- Scheduler uses the same `scan_worker` path; prevents overlap (scan running → next is skipped + logged).
- Persistent job status; schedule continues after backend restart.
- Acceptance: Cron `*/15 * * * *` demonstrably triggers scans; UI shows "next scan: <time>".

### M5: Notifications Complete [M] — SMTP/Discord done (2026-07-21), Slack pending
- Implement Slack webhook in script (analogous to Discord) or move both into a Python module.
- Respect `notify_on` (`new_asset`, `new_vuln`).
- Addition: notification on scan failure.
- Acceptance: Test webhook shows diff alert; disabled categories send nothing.

**Phase 1 result:** The tool is secure to operate (auth + TLS + schedule + alerts + stable builds).

---

## Phase 2 — Data Model & Per-Domain

### M6: PostgreSQL [L] — done (2026-07-22; deviation: no `targets` table, per-domain via domain columns)
- Compose service `postgres` (pinned tag, volume, healthcheck); backend via SQLAlchemy 2 + Alembic migrations.
- Schema: `targets`, `scans (id, started, finished, status, trigger)`, `assets (scan_id, domain, host, ip, http_status, tech, ports)`, `findings (scan_id, domain, template, severity, host, first_seen, last_seen, raw)`, `settings`.
- Scan pipeline remains shell-based, but `scan_worker` parses result files and writes to DB; files remain as raw artifacts in volume.
- Migration: import existing `/results` folders once (script).
- API rework: `/api/scans`, `/api/findings` read from DB (incl. filters: domain, severity, time range).
- Acceptance: New scan lands in DB; old scans imported; UI shows identical data as before.

### M7: Per-Domain Display [M] — done (2026-07-22)
- Scan history: grouping/filter per domain; cards or tabs per domain (subdomains, live hosts, findings).
- Findings view: domain filter in addition to severity.
- Scan trigger: per domain OR all (existing remains).
- Acceptance: Each domain individually retrievable; combined overview remains.

### M8: Trends & Diffs [M] — done (2026-07-22)

### M8b: UI Redesign (User Request) [L] — done (2026-07-22)
- Light/dark theme (system default + toggle, localStorage), IBM Plex Sans/Mono
- Dashboard: score gauge, metric cards with trend deltas, severity line chart
- New asset inventory view (type filter, search, pagination, CSV export)
- New endpoints: `/api/assets`, `/api/stats/overview`; findings view switched to open findings
- **Senior redesign (2026-07-22):** complete new design system ("Clinical Security
  Analytics") — white cards on cool background, 8px spacing system, StatCard/SeverityBubbles/
  SoftChip components, reference tables (links, type badges, page-number pagination),
  subtle sidebar, severity color system (soft + solid) in both themes
- Dashboard: history (assets/findings over time, simple sparklines), "New since last scan" per domain.
- Diff logic moves from shell diff to DB queries (`first_seen`).
- Acceptance: New subdomain/finding is marked as "new" and visible in the dashboard.

**Phase 2 result:** Clean data model, per-domain views, historical analysis.

---

## Phase 3 — Scaling (10+ Targets)

### M9: Worker Queue [L] — done (2026-07-22)
- Offload scans from API process: Redis + RQ/Celery worker container; parallel scans per domain possible.
- Scan queue with status (`queued/running/done/failed`), cancel function, progress from DB instead of in-memory.
- Resource limits for worker (nuclei!), rate limits per target.
- Acceptance: Two parallel scans; API never blocks; scan survives backend restart (job state in Redis/DB).

### M10: Lifecycle & Hardening [M]
- Retention: Delete scans/results older than X days (configurable).
- Containers: non-root user, healthchecks in Compose, resource limits, read-only FS where possible.
- Backup note: volumes `/data`, PostgreSQL dump.
- Acceptance: Retention job runs; containers run non-root; healthchecks pass.

**Phase 3 result:** Tool scales to many targets without blocking.

---

## Phase 4 — Maturity & Maintenance

### M11: Quality & Docs [M] — done (2026-07-23)
- Backend tests (pytest: API, DB), frontend tests (vitest), CI lint (ruff, eslint).
- CI/CD pipeline: lint → test → build (Docker + Trivy + GHCR).
- `VERSION.md` + changelog process in place (SemVer, Conventional Commits).
- README restructured with project description, tech docs extracted to `docs/technical.md`.
- All documentation and UI translated to English.
- Acceptance: CI green (build + lint + tests); production deployment self-contained (no host file mounts).

**Phase 4 result:** Robust CI/CD, English documentation, production-ready images on GHCR.

---

## Phase 5 — Scan Engine Rework

### M12: Modular Scan Pipeline with Live Progress [L]
- **Modular architecture:** Replace the monolithic `run-easm.sh` shell script with a
  Python-based scan orchestrator. Each tool (subfinder, dnsx, httpx, nmap, nuclei)
  becomes a pluggable pipeline step defined declaratively (command, args, timeout,
  output parser, enabled flag).
- **Tool registry:** Steps are registered in a config-driven registry. Adding a new
  tool only requires a registry entry — no code changes to the orchestrator.
- **Structured logging:** Each phase emits JSON-line log events with typed fields
  (`phase`, `status`, `hosts_found`, `duration_ms`, `error`). Parsers are isolated
  per tool for clean separation of concerns.
- **Live progress streaming:** The worker publishes phase transition events via
  Redis Pub/Sub during the scan. The backend relays these to the frontend over the
  existing WebSocket. The ScanLive view shows a real-time pipeline timeline with
  per-phase status (queued → running → done/failed), live counters (subdomains
  discovered, hosts resolved, HTTP services found, findings detected), and elapsed
  time per phase.
- **Frontend enhancements:** ScanLive view gains a progress sidebar/timeline
  showing all pipeline phases with animated status indicators, live metrics, and
  phase-level logs. Users can see exactly which phase is running and what it has
  found so far, without waiting for the entire scan to finish.
- **Extensibility:** New tools (e.g., katana, naabu, uncover) can be added by
  defining a registry entry (command template, output parser, phase name) and
  rebuilding the image. The UI automatically reflects new phases.
- **Remote log access:** Scan logs (currently stored in Redis with a 24 h TTL)
  are exposed via a new API endpoint (`GET /api/scans/{date}/log`) so they can be
  reviewed even after the WebSocket connection closes. Past scan logs are
  fetched from the results directory on disk. A log viewer panel in the Scan
  detail view lets operators debug issues without accessing the server directly.
  Worker-level logs (RQ job output, tool stderr) are also captured and
  retrievable through the same endpoint.
- Acceptance: A scan shows per-phase progress in real time; adding a new tool is a
  config-only change; live phase counters update as the scan runs; pipeline
  timeline clears on scan completion; past scan logs are viewable from the UI
  without server access.

**Phase 5 result:** Modular, extensible scan engine with real-time per-phase progress visible in the UI.
---

## Dependencies & Order

```
M1 (Builds)
 └─> M2 (Auth) ─> M3 (TLS) ─> M4 (Scheduler) ─> M5 (Notifications)
                                                          │
M6 (Postgres) <─ can start in parallel to M2–M5 ───────────┘
 └─> M7 (Per-Domain UI) ─> M8 (Trends/Diffs)
                                    │
                              M9 (Worker Queue) ─> M10 (Hardening)
                                                          │
                                          M11 (Quality/Docs) ─> M12 (Scan Engine)
```

Recommended implementation order: M1 → M2 → M3 → M4 → M5 → M6 → M7 → M8 → M9 → M10 → M11 → M12.
M6 can start earlier once Phase 1 is running — DB migration decoupled from auth/TLS.
M12 depends on M9 (worker infrastructure) and M11 (CI/CD, WebSocket already present).

## Out of Scope (deliberately not planned)
- Multi-user/roles (single-user decided), SSO/LDAP.
- Cloud integrations (Censys/Shodan APIs), active exploit verification.
- Multi-tenancy.
- CSV/JSON export, WebAuthn/Passkey (deferred, not planned).
