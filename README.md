# EASM Dashboard

Self-hosted External Attack Surface Management — FastAPI Backend + React Frontend + ProjectDiscovery Tools.

**Architektur:** `frontend` (nginx, UI) → `backend` (FastAPI, API/WS/Scheduler) →
`db` (PostgreSQL, Daten) + `redis` (Scan-Queue) → `worker` (RQ, führt Scans aus).
Scans laufen im Worker-Container (2 parallele Jobs), überleben Backend-Neustarts
und lassen sich abbrechen.

## Projektstruktur

```
easm-ui/
├── app/
│   ├── backend/
│   │   ├── main.py          # FastAPI — Config, Scan-Trigger, Results-API, WebSocket
│   │   ├── requirements.txt # gepinnte Python-Dependencies
│   │   └── Dockerfile       # Multi-stage: Go-Tools build + Python runtime
│   └── frontend/
│       ├── src/
│       │   ├── App.jsx
│       │   ├── components/
│       │   │   ├── Sidebar.jsx
│       │   │   └── ui.jsx       # Badge, Btn, Metric, Topbar, ...
│       │   └── views/
│       │       ├── Dashboard.jsx
│       │       ├── Scans.jsx
│       │       ├── Findings.jsx
│       │       ├── Config.jsx
│       │       └── ScanLive.jsx  # WebSocket Live-Log
│       ├── Dockerfile
│       ├── vite.config.js
│       └── package.json
├── scripts/
│   └── run-easm.sh      # Scan-Script (Subfinder → dnsx → httpx → nmap → Nuclei)
├── .github/workflows/
│   └── ci.yml           # Build + Smoke-Test
├── docker-compose.yml
├── nginx.conf
├── VERSIONS.md          # gepinnte Tool-Versionen + Update-Policy
└── README.md
```

Die Scanner-Tools (subfinder, dnsx, httpx, nuclei, alterx, nmap) sind fest im
Backend-Container installiert — es gibt keinen separaten Scanner-Service.
Versionen sind gepinnt, siehe [VERSIONS.md](VERSIONS.md).

## Setup

### 1. Scan-Script ausführbar machen

```bash
chmod +x scripts/run-easm.sh
```

### 2. Alles bauen und starten

```bash
docker compose up --build -d
```

Erster Build dauert ~5–10 Minuten (Go-Tools kompilieren, Nuclei-Templates laden).

### 3. UI aufrufen

```
http://localhost:3000    (HTTP)
https://localhost:3443   (HTTPS, Self-Signed-Cert — Browserwarnung bestätigen)
```

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


## UI

- **Light/Dark-Theme** — Umschalter unten in der Sidebar; Default ist die
  Systemeinstellung, die Wahl wird gespeichert.
- **Dashboard** — Security-Score (0–10 aus offenen Findings), Metriken mit
  Trend-Deltas, Findings-Verlauf nach Severity, Per-Domain-Karten,
  neue Assets/Findings, offene Findings.
- **Assets** — Inventar des letzten Scans: Typ-Filter (IPv4/HTTP/Ports/Tech),
  Suche, Domain-Filter, Pagination, CSV-Export.
- **Scan history** — Domain-Filter, Rohdaten je Scan.
- **Findings** — offene Findings mit Domain- und Severity-Filter.
- **Scan** — Live-Log via WebSocket.

## Konfiguration (via UI)

Unter **Configuration** kannst du einstellen:

| Setting | Beschreibung |
|---|---|
| Targets | Domains, die gescannt werden sollen |
| Schedule | Cron-Expression für automatische Scans |
| Ports | Ports für den nmap-Scan |
| Nuclei Severity | Welche Schweregrade Nuclei meldet |
| Nuclei aktiv | Schaltet den Nuclei-Scan ein/aus — aus lokalen Netzen mit Endpoint-Protection (ESET/IDS) deaktivieren, da Exploit-Templates dort Blocks auslösen |
| SMTP | E-Mail-Benachrichtigungen (Host, Port, User, TLS-Modus, Absender, Empfänger) |
| Discord/Slack Webhook | Alert bei neuen Assets oder Findings (Slack: geplant) |

## Benachrichtigungen

Nach jedem erfolgreichen Scan vergleicht das Backend die Ergebnisse mit dem
vorherigen Lauf und benachrichtigt bei Änderungen — gesteuert über **Alert bei**:

| Option | Inhalt |
|---|---|
| `new_asset` | Neu entdeckte Subdomains |
| `new_vuln` | Neue Nuclei-Findings |
| `scan_failed` | Scan ist fehlgeschlagen (Exit-Code ≠ 0 oder interner Fehler) |

**Kanäle:** SMTP-Mail (primär) und Discord-Webhook. In der Config-UI gibt es
einen **Test-Mail-Button** (`POST /api/notify/test`) zur Überprüfung der
SMTP-Einstellungen.

SMTP-Modi: `starttls` (Port 587), `ssl` (465), `none` (25, z.B. lokale
Mail-Relays ohne Verschlüsselung). Das SMTP-Passwort liegt in
`/data/config.json` im `easm-data` Volume — Volume entsprechend schützen.


Die Config wird in `/data/config.json` im `easm-data` Volume gespeichert.

## Manueller Scan

Entweder über den **"Jetzt scannen"**-Button im Dashboard (scannt alle
konfigurierten Targets), oder per API (erfordert Session-Cookie vom Login):

```bash
# Login (Cookie in jar speichern)
curl -c cookies.txt -X POST http://localhost:3000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"password": "DEIN_PASSWORT"}'

# alle konfigurierten Targets
curl -b cookies.txt -X POST http://localhost:3000/api/scan/trigger \
  -H "Content-Type: application/json" \
  -d '{}'

# einzelnes Target
curl -b cookies.txt -X POST http://localhost:3000/api/scan/trigger \
  -H "Content-Type: application/json" \
  -d '{"target": "mainzer.one"}'
```

## Automatische Scans (Cron)

Das `schedule`-Feld in der Konfiguration steuert den eingebauten Scheduler
(APScheduler). Format: klassischer Cron-Ausdruck, z.B. `0 3 * * *` (täglich
03:00). Leeres Feld = Scheduler aus.

- Überlappung wird verhindert: Läuft ein Scan, wird der geplante Lauf
  übersprungen (Log-Meldung im Backend).
- Der Zeitplan überlebt Backend-Neustarts (aus `config.json` wiederhergestellt).
- Der nächste Lauf wird im Dashboard angezeigt ("Nächster Scan: …").
- Zeitzone: Container-Zeit (`TZ` in `.env`, Default UTC). Für lokale Zeit
  `TZ=Europe/Berlin` setzen.

## API-Übersicht

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
| GET | `/api/assets` | Asset-Inventar des letzten Scans — Filter `?type=&domain=&q=&page=` (Auth erforderlich) |
| GET | `/api/stats/overview` | Totals, Trend-Deltas, Score, Findings-Verlauf (Auth erforderlich) |
| GET | `/api/findings/open` | Offene Findings (Tracker) — Filter `?domain=&severity=` (Auth erforderlich) |
| GET | `/api/changes/latest` | Neue Assets/Findings des letzten Scans (Auth erforderlich) |
| GET | `/api/config` | Aktuelle Konfiguration (Auth erforderlich) |
| POST | `/api/config` | Konfiguration speichern (Auth erforderlich) |
| GET | `/api/scans` | Liste aller Scan-Ergebnisse (Auth erforderlich) |
| GET | `/api/scans/{date}` | Rohdaten eines Scans (Auth erforderlich) |
| GET | `/api/scans/{date}/findings` | Nuclei-Findings (filterbar per `?severity=critical`) (Auth erforderlich) |
| POST | `/api/scan/trigger` | Scan in Queue einreihen (leerer `target` = alle Targets) (Auth erforderlich) |
| POST | `/api/scan/cancel` | Laufende/wartende Scans abbrechen (Auth erforderlich) |
| GET | `/api/scan/status` | Queue-/Scan-Status aus DB + `next_run` (Auth erforderlich) |
| POST | `/api/notify/test` | Test-Mail mit aktueller SMTP-Config senden (Auth erforderlich) |
| WS | `/ws/scan` | Live-Log-Stream via WebSocket (Auth erforderlich) |

## TLS (HTTPS)

Der Frontend-Container erzeugt beim Start automatisch ein Self-Signed-Zertifikat
und serviert HTTPS auf Port **3443** (HTTP bleibt auf 3000). Das Zertifikat liegt
im Volume `easm-tls` und überlebt Container-Neustarts.

| Env-Variable | Default | Beschreibung |
|---|---|---|
| `EASM_TLS` | `on` | `off` deaktiviert den HTTPS-Listener |
| `EASM_TLS_SAN` | `DNS:localhost,DNS:easm.local,IP:127.0.0.1` | SANs fürs Zertifikat (kommagetrennt). Nach Änderung: Volume `easm-tls` löschen, damit neu generiert wird |
| `EASM_HSTS` | `off` | HSTS-Header auf 443. Erst im reinen HTTPS-Betrieb aktivieren (sperrt sonst HTTP auf demselben Host) |

## Hinter Caddy/OPNsense

Caddy-Snippet für externen Zugriff (z.B. `easm.intern.mainzer.one`).
Da der Container ein Self-Signed-Zertifikat nutzt, muss Caddy dieses akzeptieren:

```
easm.intern.mainzer.one {
    reverse_proxy https://localhost:3443 {
        transport http {
            tls_insecure_skip_verify
        }
    }
}
```

Alternativ das Container-Cert in Caddys Trust-Store legen (`tls_trust_pool`),
oder unverschlüsselt auf `localhost:3000` proxygen, wenn der Hop lokal bleibt.
WebSocket-Proxying funktioniert mit Caddy out of the box.


## Ergebnisse

Scan-Ergebnisse liegen in **PostgreSQL** (`scans`, `assets`, `findings` —
inkl. Domain-Zuordnung pro Asset/Finding) und zusätzlich als Roh-Artefakte im
Docker Volume `easm-results`, gemountet unter `/results`. Die Konfiguration
liegt ebenfalls in der DB (`settings`) und wird beim ersten Start einmalig aus
einer bestehenden `config.json` migriert. Struktur pro Scan:

```
/results/2025-06-24_03-00/
├── subdomains.txt    # alle gefundenen Subdomains
├── resolved.txt      # DNS-aufgelöste Hosts
├── http-results.txt  # httpx-Output mit Status/Tech
├── urls.txt          # saubere URL-Liste (Input für Nuclei)
├── ports.txt         # nmap-Output
└── vulns.txt         # Nuclei-Findings
```

Datenbank-Credentials: `EASM_DB_PASSWORD` in `.env` (Default nur für Dev).
Schema-Migrationen laufen automatisch beim Backend-Start (Alembic).
