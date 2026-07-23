# EASM Dashboard

[![ci](https://github.com/mainzerp/easm/actions/workflows/ci.yml/badge.svg)](https://github.com/mainzerp/easm/actions/workflows/ci.yml)
[![docker](https://img.shields.io/badge/docker-ghcr.io%2Fmainzerp%2Feasm-blue)](https://github.com/mainzerp/easm/pkgs/container/easm-backend)

Self-hosted External Attack Surface Management — FastAPI Backend + React Frontend + ProjectDiscovery Tools.

```
frontend (nginx, UI)  ──►  backend (FastAPI, API/WS/Scheduler)
                                │
                    ┌───────────┼───────────┐
                    ▼           ▼           ▼
                  db     redis (Queue)   worker (RQ, Scans)
              PostgreSQL       │         (2 parallele Jobs)
                               │
                         überlebt Backend-Neustarts,
                         abbrechbar
```

---

## Quick Start

```bash
chmod +x scripts/run-easm.sh
docker compose up --build -d
```

Erster Build dauert ~5–10 Minuten (Go-Tools kompilieren, Nuclei-Templates laden).

```
http://localhost:3000    (HTTP)
https://localhost:3443   (HTTPS, Self-Signed-Cert)
```

---

## Projektstruktur

```
easm-ui/
├── app/
│   ├── backend/
│   │   ├── main.py              # FastAPI — Config, Scan, Results, WebSocket
│   │   ├── auth.py              # DB-backed auth, TOTP, rate-limiting
│   │   ├── db.py                # SQLAlchemy models (settings, scans, assets, findings)
│   │   ├── scanner.py           # RQ job: subfinder, httpx, nmap, nuclei
│   │   ├── requirements.txt     # gepinnte Python-Dependencies
│   │   ├── requirements-dev.txt # pytest, ruff, httpx
│   │   ├── tests/               # Pytest-Tests
│   │   └── Dockerfile           # Multi-stage: Go-Tools + Python-Runtime
│   └── frontend/
│       ├── src/
│       │   ├── App.jsx
│       │   ├── components/
│       │   │   ├── Sidebar.jsx
│       │   │   ├── UserSettingsModal.jsx   # Passwort, 2FA
│       │   │   └── ui.jsx                  # Badge, Btn, Modal, Input, ...
│       │   ├── views/                      # Dashboard, Assets, Scans, Findings, Config, ScanLive
│       │   └── __tests__/                  # Vitest-Tests
│       ├── eslint.config.js
│       ├── vitest.config.js
│       ├── Dockerfile
│       └── package.json
├── scripts/
│   └── run-easm.sh          # Subfinder -> dnsx -> httpx -> nmap -> Nuclei
├── .github/workflows/
│   └── ci.yml               # lint (ruff+eslint) → test (pytest+vitest) → build (Docker+Trivy+GHCR)
├── docker-compose.yml
├── nginx.conf
├── pyproject.toml           # ruff config
├── VERSIONS.md              # gepinnte Tool-Versionen
├── VERSION.md               # SemVer
└── README.md
```

---

## Login & 2FA

Das Tool ist durch ein Admin-Passwort geschützt (Single-User: `admin`).

- **Erststart ohne Konfiguration:** Ein Zufalls-Passwort wird einmalig ins
  Backend-Log geschrieben — `docker compose logs backend`.
- **Eigenes Passwort setzen:** Über die UI unter **Benutzereinstellungen**
  (unten links in der Sidebar) oder beim ersten Start über
  `EASM_ADMIN_PASSWORD` / `EASM_ADMIN_PASSWORD_HASH` in `.env`.
- **Passwort-Hash erzeugen (optional, für .env-Seed):**
  ```bash
  docker compose exec backend python -c \
    "from argon2 import PasswordHasher; print(PasswordHasher().hash('DEIN_PASSWORT'))"
  ```
- **TOTP/2FA (optional):** In der UI unter **Benutzereinstellungen** →
  **Sicherheit** aktivieren. QR-Code mit einer Authenticator-App scannen
  (z. B. Google Authenticator, Aegis, Bitwarden) und den Verifizierungscode
  eingeben.
- **Passwort ändern:** Erfordert das aktuelle Passwort und beendet alle
  Sitzungen sofort (erneuter Login nötig).
- **Rate-Limit:** 5 Fehlversuche/Minute → 5 Minuten Sperre.
- Sessions sind In-Memory (24 h): überleben Reload, nicht Backend-Neustart.

---

## UI

- **Light/Dark-Theme** — Umschalter unten in der Sidebar; Default ist die
  Systemeinstellung, die Wahl wird gespeichert.
- **Dashboard** — Security-Score (0–10 aus offenen Findings), Metriken mit
  Trend-Deltas, Findings-Verlauf nach Severity, Per-Domain-Karten,
  Scan-Historie als Tabelle.
- **Assets** — Inventory aus dem letzten Scan: Hosts, IPs, HTTP-Status, Title,
  Technologies, offene Ports, offene Issues. Paginiert, filterbar nach Typ,
  domain-spezifisch, Fulltext-Suche.
- **Findings** — Open Issues per Domain/Severity, Neu/Gelöst-Delta, Scan-Detail
  mit Rohdaten pro Scan-Datum.
- **Scans** — Live-View mit WebSocket-Log (Tailwind-artig, schwarz/grün, Auto-Scroll).
  Manuell starten, abbrechen, Status (queue/running). Cron-Scheduler
  (`schedule` in Config).
- **Config** — Targets, Ports, Nuclei-Severity, Notifications (Discord, Slack,
  SMTP), Cron-Schedule. Config-Änderungen passen den Scheduler und die
  Nuclei-Severity sofort an.
- **Benutzereinstellungen** — Modal unten links in der Sidebar:
  - Benutzername (`admin`).
  - Passwort ändern (erfordert aktuelles Passwort).
  - 2FA aktivieren/deaktivieren per Authenticator-App.

---

## API Overview

Sämtliche `/api/*`-Endpoints (außer `/api/auth/*`) benötigen ein gültiges Session-Cookie.

| Methode | Endpoint | Beschreibung |
|---|---|---|
| POST | `/api/auth/login` | Login (`password`, optional `code` bei TOTP) |
| POST | `/api/auth/logout` | Logout |
| GET | `/api/auth/check` | Auth-Status (`authenticated`, `totp_enabled`) |
| GET | `/api/auth/user` | Aktueller Benutzer (`username`, `totp_enabled`) |
| POST | `/api/auth/change-password` | Passwort ändern (benötigt `current_password`) |
| POST | `/api/auth/totp/setup` | 2FA-Setup starten (gibt `secret` + `qr_uri`) |
| POST | `/api/auth/totp/verify` | 2FA mit Verifizierungscode aktivieren |
| POST | `/api/auth/totp/disable` | 2FA deaktivieren |
| GET | `/api/domains` | Konfigurierte Targets (Auth erforderlich) |
| GET | `/api/config` | Konfiguration (Targets, Notifications, Scheduler) |
| POST | `/api/config` | Konfiguration speichern |
| POST | `/api/scan/trigger` | Manuellen Scan starten |
| POST | `/api/scan/cancel` | Laufenden Scan abbrechen |
| GET | `/api/scan/status` | Status des aktuellen Scans |
| GET | `/api/scans` | Letzte 30 Scans |
| GET | `/api/scans/{date}` | Rohdaten eines Scans |
| GET | `/api/scans/{date}/findings` | Findings eines Scans (filterbar nach severity/domain) |
| GET | `/api/assets` | Assets des letzten Scans (paginiert, filterbar, durchsuchbar) |
| GET | `/api/stats/overview` | Dashboard-Aggregat (Score, Metriken, Deltas, Trends) |
| GET | `/api/findings/open` | Offene Findings (filterbar nach domain/severity) |
| GET | `/api/changes/latest` | Neue Assets/Findings seit letztem Scan |
| WS | `/ws/scan` | Live-Log via WebSocket |
| POST | `/api/notify/test` | Test-Mail senden |

---

## Entwicklung

### Backend (Tests + Linting)

```bash
# Postgres/Redis müssen laufen (docker compose up db redis -d)
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
npm run build     # Produktion
npm run dev       # Dev-Server mit HMR
```
