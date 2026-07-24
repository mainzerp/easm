# EASM Dashboard

[![ci](https://github.com/mainzerp/easm/actions/workflows/ci.yml/badge.svg)](https://github.com/mainzerp/easm/actions/workflows/ci.yml)
[![docker](https://img.shields.io/badge/docker-ghcr.io%2Fmainzerp%2Feasm-blue)](https://github.com/mainzerp/easm/pkgs/container/easm-backend)

Self-hosted **External Attack Surface Management** for small to medium
infrastructures, penetration testers, and security teams who want full
control over their scan data.

EASM Dashboard discovers and monitors publicly visible assets per domain:
subdomains, live hosts, open ports, and Nuclei findings — with historical
tracking, a security score, and diff-tracking between scans.

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

---

## Why EASM Dashboard?

- **No cloud, no subscriptions.** All data stays in your own PostgreSQL database.
- **Single-user, hardened security.** Login with Argon2 hashing, optional
  TOTP/2FA, rate-limiting, and HttpOnly session cookies.
- **Modular scan pipeline with live progress.** Subfinder, alterx (optional),
  dnsx, httpx, nmap, Nuclei as declarative pipeline steps — offloaded to an RQ
  worker so long scans never block the API, with real-time per-phase status
  and counters in the UI.
- **Service log viewer.** Read-only access to all container logs (history,
  filters, live tail) and historical scan logs directly from the UI.
- **History & diffs.** Assets and findings are recorded per scan. New and
  resolved entries are automatically flagged.
- **Cron scheduler.** Schedule recurring scans via a cron expression, e.g.
  daily at 3 AM.
- **Notifications.** Discord, Slack, and SMTP alerts on new assets, new
  findings, or scan failures.
- **Modern UI.** Light/dark theme, dashboard with security score, severity
  overview, paginated asset list, scan live view with WebSocket log.

---

## Quick Start

**Production** (uses pre-built GHCR images):

```bash
cp .env.example .env
echo "EASM_DB_PASSWORD=$(openssl rand -hex 32)" >> .env
docker compose pull
docker compose up -d
```

The UI is available at `http://localhost` and `https://localhost`.
On first start, a random admin password is written to the backend log:

```bash
docker compose logs backend | grep "Generiertes Erststart-Passwort"
```

Then set the password and optionally enable 2FA under **User Settings** in the
sidebar.

**Local development** (builds images locally):

```bash
docker compose -f docker-compose.local.yml up --build
```

Available at `http://localhost:3000` and `https://localhost:3443`. The first
build takes 5–10 minutes.

---

## Features at a Glance

| Area | Highlights |
|---|---|
| **Dashboard** | Security score (0–10), metric cards with trend deltas, findings trend by severity, per-domain overview |
| **Assets** | Inventory from the latest scan: hosts, IPs, HTTP status, title, technologies, open ports, open issues. Filterable, searchable, paginated |
| **Findings** | Open Nuclei findings by domain/severity, new/resolved delta |
| **Scans** | Manual trigger, cancel, live pipeline timeline with per-phase status and counters via WebSocket, scheduled cron scans |
| **Logs** | Container logs from all services (filter, search, live tail) and historical scan logs in the UI |
| **Config** | Targets, ports, Nuclei severity, pipeline phases (httpx/nmap/nuclei/alterx), notifications, cron schedule |
| **Security** | Admin password + optional 2FA, rate-limiting, security headers, TLS option |

---

## Technical Details

For architecture, API reference, deployment, development, and configuration
see [`docs/technical.md`](docs/technical.md).

- Pinned versions: [`VERSIONS.md`](VERSIONS.md)
- Roadmap: [`docs/project/roadmap.md`](docs/project/roadmap.md)
- SemVer changelog: [`VERSION.md`](VERSION.md)

---

## Security Note

The dashboard is designed to run behind a reverse proxy or on an internal
network. Use a strong admin password, enable 2FA, and set a dedicated,
random PostgreSQL password in production.

Container logs are exposed to the backend through a dedicated read-only
socket-proxy sidecar (`wollomatic/socket-proxy`): the Docker socket is never
mounted into app containers, the proxy only allows `GET` requests to the
container-list and container-log endpoints (`POST=0`), and it is reachable
only on the internal Docker network.
