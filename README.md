# EASM Dashboard

[![ci](https://github.com/mainzerp/easm/actions/workflows/ci.yml/badge.svg)](https://github.com/mainzerp/easm/actions/workflows/ci.yml)
[![docker](https://img.shields.io/badge/docker-ghcr.io%2Fmainzerp%2Feasm-blue)](https://github.com/mainzerp/easm/pkgs/container/easm-backend)

Self-hosted **External Attack Surface Management** für kleine bis mittlere
Infrastrukturen, Penetration-Tester und Security-Teams, die ihre Scan-Daten
selbst kontrollieren wollen.

EASM Dashboard entdeckt und überwacht öffentlich sichtbare Assets pro Domain:
Subdomains, Live-Hosts, offene Ports und Nuclei-Findings — mit historischem
Verlauf, Security-Score und Diff-Tracking, was sich zwischen zwei Scans
verändert hat.

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

## Warum EASM Dashboard?

- **Keine Cloud, keine Abos.** Alle Daten bleiben in der eigenen PostgreSQL-DB.
- **Single-User, stark abgesichert.** Login mit Argon2-Hash, optional TOTP/2FA,
  Rate-Limiting und HttpOnly-Session-Cookies.
- **Scan-Engine mit bewährten Tools.** Subfinder, dnsx, httpx, nmap, Nuclei —
  in einem RQ-Worker ausgelagert, damit lange Scans die API nicht blockieren.
- **Verlauf & Diffs.** Für jeden Scan werden Assets und Findings erfasst. Neue
  und gelöste Einträge werden automatisch markiert.
- **Cron-Scheduler.** Scans lassen sich über eine Cron-Expression planen, z. B.
  täglich um 3 Uhr.
- **Notifications.** Discord-, Slack- und SMTP-Benachrichtigungen bei neuen
  Assets, neuen Findings oder Scan-Fehlschlägen.
- **Modernes UI.** Light/Dark-Theme, Dashboard mit Security-Score,
  Severity-Übersicht, paginierte Asset-Liste, Scan-Live-View mit WebSocket-Log.

---

## Quick Start

**Produktion** (nutzt vor gebaute GHCR-Images):

```bash
cp .env.example .env
echo "EASM_DB_PASSWORD=$(openssl rand -hex 32)" >> .env
docker compose pull
docker compose up -d
```

Danach ist die UI unter `http://localhost` und `https://localhost` erreichbar.
Beim ersten Start wird ein zufälliges Admin-Passwort ins Backend-Log geschrieben:

```bash
docker compose logs backend | grep "Generiertes Erststart-Passwort"
```

Anschließend Passwort und optional 2FA unter **Benutzereinstellungen** in der
Sidebar setzen.

**Lokale Entwicklung** (baut Images selbst):

```bash
docker compose -f docker-compose.local.yml up --build
```

Erreichbar unter `http://localhost:3000` und `https://localhost:3443`. Der erste
Build dauert 5–10 Minuten.

---

## Features im Überblick

| Bereich | Highlights |
|---|---|
| **Dashboard** | Security-Score (0–10), Metrik-Karten mit Trend-Deltas, Findings-Verlauf nach Severity, Per-Domain-Übersicht |
| **Assets** | Inventar des letzten Scans: Hosts, IPs, HTTP-Status, Titel, Technologien, offene Ports, offene Issues. Filterbar, durchsuchbar, paginiert |
| **Findings** | Offene Nuclei-Findings pro Domain/Severity, Neu/Gelöst-Delta |
| **Scans** | Manuell starten, abbrechen, Live-Log per WebSocket, geplante Cron-Scans |
| **Config** | Targets, Ports, Nuclei-Severity, Notifications, Cron-Schedule |
| **Sicherheit** | Admin-Passwort + optional 2FA, Rate-Limiting, Security-Headers, TLS-Option |

---

## Technische Details

Für Architektur, API-Referenz, Deployment, Entwicklung und Konfiguration siehe
[`docs/technical.md`](docs/technical.md).

- Gepinnte Versionen: [`VERSIONS.md`](VERSIONS.md)
- Roadmap: [`docs/project/roadmap.md`](docs/project/roadmap.md)
- SemVer-Changelog: [`VERSION.md`](VERSION.md)

---

## Sicherheitshinweis

Das Dashboard ist für den Betrieb hinter einem Reverse-Proxy oder in einem
internen Netz konzipiert. Setze ein starkes Admin-Passwort, aktiviere 2FA und
verwende in Produktion ein eigenes, zufälliges PostgreSQL-Passwort.
