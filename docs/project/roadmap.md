# EASM Dashboard — Roadmap zur Produktionsreife

> Kontext (Entscheidungen): Single-User mit starkem Auth, Betrieb später hinter
> Reverse-Proxy (Container stellt Self-Signed-Cert für RP→Backend bereit),
> PostgreSQL als Datenhaltung, Zielgröße 10+ Targets, Priorität: Betrieb & Sicherheit.

Legende: Aufwand S = klein (< 0,5 Tag), M = mittel (0,5–1,5 Tage), L = groß (2+ Tage).

---

## Phase 1 — Betrieb & Sicherheit (zuerst)

### M1: Reproduzierbare Builds [M] — ✅ erledigt (2026-07-21)
- Tool-Versionen pinnen (subfinder/dnsx/httpx/nuclei/alterx auf feste Tags statt `@latest`).
- Go-Toolchain-Version fixieren; Build-Test im CI (docker compose build muss immer grün sein).
- `app/backend/Dockerfile.scanner` entfernen oder als Worker-Image definieren (aktualisiert README).
- Abnahme: Frischer Build auf leerem System ohne Netz-Überraschungen; Versionen in einer Datei dokumentiert.

### M2: Auth (Single-User, stark) [L] — ✅ erledigt (2026-07-21, inkl. TOTP)
- Backend: Login-Endpoint, Passwort-Hashing (argon2id/bcrypt), Session-Cookie (HttpOnly, SameSite=Strict) oder JWT mit kurzer Laufzeit + Refresh.
- Passwort via Env/Secret (`EASM_ADMIN_PASSWORD_HASH`), kein Klartext im Repo; Erststart erzwingt Setzen.
- Schutz aller `/api/*` und `/ws/*` Endpunkte; Rate-Limit auf Login (z.B. 5/min) gegen Brute-Force.
- Frontend: Login-View, Session-Handling, 401 → Redirect Login; Logout-Button.
- Security-Headers (CSP, X-Frame-Options, HSTS sobald TLS).
- Abnahme: Ohne Login keine API-/WS-Daten; falsches Passwort gedrosselt; Session überlebt Reload, nicht Server-Neustart (ok).

### M3: TLS — Self-Signed-Cert für RP↔Backend [M] — ✅ erledigt (2026-07-21)
- Backend-Container erzeugt beim Start ein Self-Signed-Zertifikat (falls nicht vorhanden), Persistenz im Config-Volume (`/data/tls/`).
- nginx im Frontend-Container terminiert weiterhin :3000; Backend spricht HTTPS (Uvicorn mit `--ssl-*`) ODER nginx terminiert TLS Richtung RP.
- Konfigurierbar: `EASM_TLS=on|off` (off für reine LAN-Entwicklung).
- Abnahme: RP kann per HTTPS auf Backend zugreifen; Zertifikat überlebt Container-Neustart; CN/SAN dokumentiert.

### M4: Scheduler [M] — ✅ erledigt (2026-07-21)
- Config-Feld `schedule` wird real: APScheduler (oder asyncio-Cron) im Backend führt Scans nach Cron-Expression aus.
- Scheduler nutzt denselben `scan_worker`-Pfad; verhindert Überlappung (Scan läuft → nächster wird übersprungen + geloggt).
- Persistenter Job-Status; nach Backend-Neustart läuft Zeitplan weiter.
- Abnahme: Cron `*/15 * * * *` triggert nachweislich Scans; UI zeigt "nächster Scan: <Zeit>".

### M5: Notifications vervollständigen [M] — ✅ SMTP/Discord erledigt (2026-07-21), Slack ausstehend
- Slack-Webhook im Skript implementieren (analog Discord) oder beide in ein Python-Modul verlagern.
- `notify_on` respektieren (`new_asset`, `new_vuln`).
- Ergänzung: Benachrichtigung bei Scan-Fehlschlag.
- Abnahme: Test-Webhook zeigt Diff-Alert; deaktivierte Kategorien senden nichts.

**Ergebnis Phase 1:** Tool ist sicher betreibbar (Auth + TLS + Zeitplan + Alerts + stabile Builds).

---

## Phase 2 — Datenmodell & Per-Domain

### M6: PostgreSQL [L] — ✅ erledigt (2026-07-22; Abweichung: keine targets-Tabelle, Per-Domain via domain-Spalten)
- Compose-Service `postgres` (gepinnter Tag, Volume, Healthcheck); Backend via SQLAlchemy 2 + Alembic-Migrationen.
- Schema: `targets`, `scans (id, started, finished, status, trigger)`, `assets (scan_id, domain, host, ip, http_status, tech, ports)`, `findings (scan_id, domain, template, severity, host, first_seen, last_seen, raw)`, `settings`.
- Scan-Pipeline bleibt Shell-basiert, aber `scan_worker` parsed Ergebnisdateien und schreibt in DB; Dateien bleiben als Roh-Artefakte im Volume.
- Migration: bestehende `/results`-Ordner einmalig importieren (Skript).
- API-Umbau: `/api/scans`, `/api/findings` lesen aus DB (inkl. Filter: domain, severity, Zeitraum).
- Abnahme: Neuer Scan landet in DB; alte Scans importiert; UI zeigt identische Daten wie vorher.

### M7: Per-Domain-Darstellung [M] — ✅ erledigt (2026-07-22)
- Scan History: Gruppierung/Filter pro Domain; Karten oder Tabs je Domain (Subdomains, Live Hosts, Findings).
- Findings-View: Domain-Filter zusätzlich zu Severity.
- Scan-Trigger: pro Domain ODER alle (bestehend bleibt).
- Abnahme: Für jede Domain einzeln abrufbar; kombinierte Gesamtsicht bleibt.

### M8: Trends & Diffs [M] — ✅ erledigt (2026-07-22)

### M8b: UI-Umbau (User-Request) [L] — ✅ erledigt (2026-07-22)
- Light/Dark-Theme (System-Default + Toggle, localStorage), IBM Plex Sans/Mono
- Dashboard: Score-Gauge, Metrik-Karten mit Trend-Deltas, Severity-Line-Chart
- Neue Assets-Inventar-Ansicht (Typ-Filter, Suche, Pagination, CSV-Export)
- Neue Endpunkte: `/api/assets`, `/api/stats/overview`; Findings-View auf offene Findings umgestellt
- **Senior-Redesign (2026-07-22):** komplettes Design-System neu ("Clinical Security
  Analytics") — weiße Karten auf kühlem Grund, 8px-Spacing-System, StatCard/SeverityBubbles/
  SoftChip-Komponenten, Referenz-Tabellen (Links, Type-Badges, Seitenzahlen-Pagination),
  subtile Sidebar, Severity-Farbsystem (soft + solid) in beiden Themes
- Dashboard: Verlauf (Assets/Findings über Zeit, einfache Sparklines), "Neu seit letztem Scan" pro Domain.
- Diff-Logik wandert von Shell-Diff in DB-Abfragen (`first_seen`).
- Abnahme: Neuer Subdomain/Finding wird als "neu" markiert und im Dashboard sichtbar.

**Ergebnis Phase 2:** Sauberes Datenmodell, Per-Domain-Sichten, historische Auswertung.

---

## Phase 3 — Skalierung (10+ Targets)

### M9: Worker-Queue [L] — ✅ erledigt (2026-07-22)
- Scans aus API-Prozess auslagern: Redis + RQ/Celery Worker-Container; parallele Scans pro Domain möglich.
- Scan-Queue mit Status (`queued/running/done/failed`), Abbruch-Funktion, Fortschritt aus DB statt In-Memory.
- Ressourcen-Limits für Worker (nuclei!), Rate-Limits pro Ziel.
- Abnahme: Zwei Scans parallel; API blockiert nie; Scan überlebt Backend-Restart (Job-State in Redis/DB).

### M10: Lifecycle & Härtung [M]
- Retention: Scans/Ergebnisse älter als X Tage löschen (konfigurierbar).
- Container: non-root User, Healthchecks in Compose, Ressourcen-Limits, Read-only FS wo möglich.
- Backup-Hinweis: Volumes `/data`, Postgres-Dump.
- Abnahme: Retention-Job läuft; Container laufen non-root; Healthchecks grün.

**Ergebnis Phase 3:** Tool skaliert auf viele Targets ohne Blockierung.

---

## Phase 4 — Reife & Pflege

### M11: Qualität & Doku [M]
- Backend-Tests (pytest: API, DB, Scan-Parsing), Frontend-Build im CI, Lint (ruff, eslint).
- `VERSION.md` + Changelog-Prozess einführen (SemVer, Conventional Commits).
- README aktualisieren (Auth, TLS, Postgres, Worker, Reverse-Proxy-Beispiel inkl. Self-Signed-Einbindung).
- Optional: Export (CSV/JSON), WebAuthn/Passkey für Login.
- Abnahme: CI grün (build + lint + tests); README-Schritt-für-Schritt produktiv nachvollziehbar.

---

## Abhängigkeiten & Reihenfolge

```
M1 (Builds)
 └─> M2 (Auth) ─> M3 (TLS) ─> M4 (Scheduler) ─> M5 (Notifications)
                                                          │
M6 (Postgres) <─ kann parallel zu M2–M5 beginnen ──────────┘
 └─> M7 (Per-Domain UI) ─> M8 (Trends/Diffs)
                                    │
                              M9 (Worker-Queue) ─> M10 (Härtung)
                                                          │
                                                       M11 (Qualität/Doku)
```

Empfohlene Umsetzungs-Reihenfolge: M1 → M2 → M3 → M4 → M5 → M6 → M7 → M8 → M9 → M10 → M11.
M6 kann früher starten, sobald Phase 1 läuft — DB-Umbau entkoppelt von Auth/TLS.

## Out of Scope (bewusst nicht geplant)
- Multi-User/Rollen (Single-User entschieden), SSO/LDAP.
- Cloud-Integrationen (Censys/Shodan-APIs), aktive Exploit-Verifikation.
- Multi-Tenancy.
