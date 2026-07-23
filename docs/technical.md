# Technische Dokumentation

Dieses Dokument richtet sich an Entwickler und Betreiber. Für einen Überblick über
Features und die erste Inbetriebnahme siehe [`README.md`](../README.md).

---

## Architektur

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

- **Frontend:** React 18 + Vite, wird zu statischem HTML/JS gebaut und von nginx
  ausgeliefert. TLS wird optional vom nginx-Container terminiert
  (`EASM_TLS=on|off`).
- **Backend:** FastAPI + Uvicorn. Verwaltet Config, Scan-Queue, Assets/Findings,
  Scheduler und Authentifizierung.
- **Worker:** Separater Container, der über RQ Scan-Jobs aus der Redis-Queue
  abarbeitet. Damit blockiert ein längerer Scan die API nicht.
- **PostgreSQL:** Persistente Datenhaltung (Scans, Assets, Findings, Settings,
  Credentials).
- **Redis:** Job-Queue für RQ + Pub/Sub für Live-Logs während eines Scans.

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
│       │   ├── components/      # Sidebar, UserSettingsModal, ui-Primitives
│       │   ├── views/           # Dashboard, Assets, Scans, Findings, Config, ScanLive
│       │   └── __tests__/       # Vitest-Tests
│       ├── eslint.config.js
│       ├── vitest.config.js
│       ├── Dockerfile
│       └── package.json
├── scripts/
│   └── run-easm.sh              # Subfinder -> dnsx -> httpx -> nmap -> Nuclei
├── .github/workflows/
│   └── ci.yml                   # lint → test → build (Docker + Trivy + GHCR)
├── docker-compose.yml           # Produktion: nutzt GHCR-Images
├── docker-compose.local.yml     # Lokale Entwicklung: baut Images selbst
├── nginx.conf
├── pyproject.toml               # ruff config
├── VERSIONS.md                  # gepinnte Tool-Versionen
├── VERSION.md                   # SemVer
└── README.md
```

---

## Authentifizierung & Sicherheit

Das Tool ist ein Single-User-System (Benutzername `admin`).

- **Erststart:** Wenn weder `EASM_ADMIN_PASSWORD` noch `EASM_ADMIN_PASSWORD_HASH`
  gesetzt sind und noch keine Credentials in der Datenbank existieren, generiert
  das Backend ein zufälliges Passwort und schreibt es einmalig ins Log:
  `docker compose logs backend`.
- **Passwort setzen:** Über die UI unter **Benutzereinstellungen** (unten links in
  der Sidebar) oder beim ersten Start über `.env`.
- **Passwort-Hash erzeugen (für `.env`):**
  ```bash
  docker compose exec backend python -c \
    "from argon2 import PasswordHasher; print(PasswordHasher().hash('DEIN_PASSWORT'))"
  ```
- **TOTP/2FA:** In der UI unter **Benutzereinstellungen → Sicherheit**
  aktivieren. QR-Code mit einer Authenticator-App scannen (z. B. Google
  Authenticator, Aegis, Bitwarden) und den Verifizierungscode eingeben.
  Aktivierung und Deaktivierung erfordern das aktuelle Passwort.
- **Passwort ändern:** Erfordert das aktuelle Passwort, beendet alle Sitzungen
  sofort.
- **Rate-Limit:** 5 Fehlversuche/Minute → 5 Minuten Sperre (IP-basiert).
- **Sessions:** In-Memory (24 h). Überleben Browser-Reload, aber keinen
  Backend-Neustart.
- **Security-Headers:** CSP, X-Frame-Options, X-Content-Type-Options,
  Referrer-Policy, optional HSTS (`EASM_HSTS=on`).

---

## API-Referenz

Sämtliche `/api/*`-Endpoints (außer `/api/auth/*`) benötigen ein gültiges
Session-Cookie.

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

## Deployment

### Produktion (GHCR-Images)

Die CI baut bei jedem Push auf `main` Images und pushed sie nach GHCR. Die
Produktions-Compose erwartet ein sicheres Datenbank-Passwort.

```bash
cp .env.example .env
# EASM_DB_PASSWORD setzen (mindestens)
echo "EASM_DB_PASSWORD=$(openssl rand -hex 32)" >> .env

docker compose pull
docker compose up -d
```

Frontend lauscht auf den Standard-Ports `80` und `443`. Für ein anderes
Registry/Tag können die Umgebungsvariablen `EASM_IMAGE_REGISTRY`,
`EASM_IMAGE_REPO` und `EASM_IMAGE_TAG` verwendet werden.

### Lokale Entwicklung (selbst bauen)

```bash
docker compose -f docker-compose.local.yml up --build
```

Frontend und API sind unter `http://localhost:3000` bzw.
`https://localhost:3443` erreichbar. Der erste Build dauert 5–10 Minuten, weil
Go-Tools kompiliert und Nuclei-Templates geladen werden.

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

---

## Konfiguration

Alle wichtigen Einstellungen werden über die UI oder `.env` vorgenommen.
Details stehen in `.env.example`. Wichtige Variablen:

- `EASM_ADMIN_PASSWORD` / `EASM_ADMIN_PASSWORD_HASH` — Ersteinrichtung.
- `EASM_DB_PASSWORD` — PostgreSQL-Passwort (in Produktion Pflicht).
- `EASM_TLS=on|off` — HTTPS im Frontend-Container aktivieren/deaktivieren.
- `EASM_TLS_SAN` — Subject Alternative Names für das Self-Signed-Cert.
- `EASM_HSTS=on|off` — HSTS-Header (nur hinter einem Reverse-Proxy empfohlen).
- `TZ` — Zeitzone für den Cron-Scheduler.

Gepinnte Versionen aller Tools, Images und Pakete sind in [`VERSIONS.md`](../VERSIONS.md)
dokumentiert.

---

## CI/CD

`.github/workflows/ci.yml`:

1. `lint` — `ruff check` (Backend) und `eslint` (Frontend).
2. `test` — `pytest` (Backend mit PostgreSQL-Service) und `vitest` (Frontend).
3. `build` — Docker-Images bauen, nach GHCR pushen, Trivy-Scan
   (CRITICAL/HIGH) laufen lassen.

`build` wird nur auf `main` ausgeführt und benötigt `packages: write`.
