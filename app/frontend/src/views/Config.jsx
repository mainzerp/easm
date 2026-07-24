import { useEffect, useState } from 'react'
import { Topbar, Btn, Content, SectionHead } from '../components/ui.jsx'

const inputStyle = {
  padding: '8px 10px', fontSize: 13,
  background: 'var(--bg2)',
  border: '0.5px solid var(--border2)',
  borderRadius: 'var(--radius)',
  color: 'var(--text)', fontFamily: 'var(--font-mono)',
  width: '100%', outline: 'none',
}
const labelStyle = { fontSize: 12, color: 'var(--text2)', marginBottom: 5, display: 'block' }

export default function Config() {
  const [cfg, setCfg]       = useState(null)
  const [saved, setSaved]   = useState(false)
  const [newTarget, setNewTarget] = useState('')
  const [testState, setTestState] = useState(null)

  useEffect(() => {
    fetch('/api/config').then(r => r.json()).then(setCfg)
  }, [])

  function save() {
    fetch('/api/config', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(cfg) })
      .then(() => { setSaved(true); setTimeout(() => setSaved(false), 2500) })
  }

  function sendTestMail() {
    setTestState('sending')
    fetch('/api/notify/test', { method: 'POST' })
      .then(async r => {
        if (r.ok) { setTestState('ok') } else {
          const d = await r.json().catch(() => ({}))
          setTestState(d.detail || 'Fehler')
        }
      })
      .catch(() => setTestState('Verbindungsfehler'))
      .finally(() => setTimeout(() => setTestState(null), 4000))
  }

  function addTarget() {
    const t = newTarget.trim()
    if (!t || cfg.targets.includes(t)) return
    setCfg(c => ({ ...c, targets: [...c.targets, t] }))
    setNewTarget('')
  }

  function removeTarget(t) {
    setCfg(c => ({ ...c, targets: c.targets.filter(x => x !== t) }))
  }

  if (!cfg) return <div style={{ padding: 24, color: 'var(--text3)' }}>Lade Konfiguration...</div>

  return (
    <>
      <Topbar title="Configuration">
        <Btn variant="primary" onClick={save}>
          <i className="ti ti-device-floppy" aria-hidden />
          {saved ? 'Gespeichert ✓' : 'Speichern'}
        </Btn>
      </Topbar>

      <Content>
        <div style={{ maxWidth: 560, display: 'flex', flexDirection: 'column', gap: 24 }}>

          {/* Targets */}
          <div>
            <SectionHead>Targets</SectionHead>
            <div style={{ display: 'flex', gap: 8, marginBottom: 10 }}>
              <input
                style={{ ...inputStyle, flex: 1 }}
                placeholder="domain.tld"
                value={newTarget}
                onChange={e => setNewTarget(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && addTarget()}
              />
              <Btn onClick={addTarget}><i className="ti ti-plus" aria-hidden />Add</Btn>
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
              {cfg.targets.map(t => (
                <span key={t} style={{
                  display: 'inline-flex', alignItems: 'center', gap: 6,
                  padding: '4px 10px', borderRadius: 20,
                  background: 'var(--bg3)', border: '0.5px solid var(--border2)',
                  fontSize: 12, fontFamily: 'var(--font-mono)',
                }}>
                  {t}
                  <button onClick={() => removeTarget(t)} style={{ color: 'var(--text3)', fontSize: 14, lineHeight: 1 }}>×</button>
                </span>
              ))}
            </div>
          </div>

          {/* Schedule */}
          <div>
            <SectionHead>Zeitplan</SectionHead>
            <label style={labelStyle}>Cron-Expression</label>
            <input style={inputStyle} value={cfg.schedule}
              onChange={e => setCfg(c => ({ ...c, schedule: e.target.value }))} />
            <div style={{ fontSize: 11, color: 'var(--text3)', marginTop: 4 }}>
              Default: <code style={{ color: 'var(--teal)' }}>0 3 * * *</code> = daily at 03:00
            </div>
          </div>

          {/* Scan-Phasen */}
          <div>
            <SectionHead>Scan-Phasen</SectionHead>
            {[
              ['enable_alterx', 'alterx — Subdomain Permutation (optional)', false],
              ['enable_httpx', 'httpx — HTTP Probing + Tech Detection', true],
              ['enable_nmap', 'nmap — Port Scan', true],
              ['enable_nuclei', 'Nuclei — Vulnerability Scan', true],
            ].map(([key, label, def]) => (
              <label key={key} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8, cursor: 'pointer' }}>
                <input type="checkbox"
                  checked={cfg[key] ?? def}
                  onChange={e => setCfg(c => ({ ...c, [key]: e.target.checked }))}
                />
                <span style={{ fontSize: 13, color: 'var(--text2)' }}>{label}</span>
              </label>
            ))}
            <div style={{ fontSize: 11, color: 'var(--text3)', lineHeight: 1.5 }}>
              Disable phases if local security software (ESET, IDS) is triggered
              and locks the PC. Subfinder + dnsx (pure DNS) always run and
              virtually never trigger an IDS.
            </div>
          </div>

          {/* Ports */}
          <div>
            <SectionHead>Port-Scan</SectionHead>
            <label style={labelStyle}>Ports (kommagetrennt)</label>
            <input style={inputStyle} value={cfg.ports}
              onChange={e => setCfg(c => ({ ...c, ports: e.target.value }))} />
          </div>

          {/* Nuclei severity */}
          <div>
            <SectionHead>Nuclei Severity</SectionHead>
            <label style={labelStyle}>Welche Schweregrade soll Nuclei scannen?</label>
            {['critical', 'high', 'medium', 'low', 'info'].map(s => (
              <label key={s} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8, cursor: 'pointer' }}>
                <input type="checkbox"
                  checked={cfg.nuclei_severity.includes(s)}
                  onChange={e => {
                    const sev = e.target.checked
                      ? [...cfg.nuclei_severity, s]
                      : cfg.nuclei_severity.filter(x => x !== s)
                    setCfg(c => ({ ...c, nuclei_severity: sev }))
                  }}
                />
                <span style={{ fontSize: 13, color: 'var(--text2)' }}>{s}</span>
              </label>
            ))}
          </div>

          {/* SMTP */}
          <div>
            <SectionHead>E-Mail (SMTP)</SectionHead>
            <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: 10, marginBottom: 12 }}>
              <div>
                <label style={labelStyle}>SMTP-Host</label>
                <input style={inputStyle} placeholder="smtp.example.com"
                  value={cfg.smtp_host ?? ''}
                  onChange={e => setCfg(c => ({ ...c, smtp_host: e.target.value }))} />
              </div>
              <div>
                <label style={labelStyle}>Port</label>
                <input style={inputStyle} type="number"
                  value={cfg.smtp_port ?? 587}
                  onChange={e => setCfg(c => ({ ...c, smtp_port: parseInt(e.target.value) || 587 }))} />
              </div>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: 12 }}>
              <div>
                <label style={labelStyle}>Benutzer</label>
                <input style={inputStyle} value={cfg.smtp_user ?? ''}
                  onChange={e => setCfg(c => ({ ...c, smtp_user: e.target.value }))} />
              </div>
              <div>
                <label style={labelStyle}>Passwort</label>
                <input style={inputStyle} type="password" value={cfg.smtp_password ?? ''}
                  onChange={e => setCfg(c => ({ ...c, smtp_password: e.target.value }))} />
              </div>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: 12 }}>
              <div>
                <label style={labelStyle}>Absender</label>
                <input style={inputStyle} placeholder="easm@example.com" value={cfg.smtp_from ?? ''}
                  onChange={e => setCfg(c => ({ ...c, smtp_from: e.target.value }))} />
              </div>
              <div>
                <label style={labelStyle}>Encryption</label>
                <select
                  style={{ ...inputStyle, cursor: 'pointer' }}
                  value={cfg.smtp_tls ?? 'starttls'}
                  onChange={e => setCfg(c => ({ ...c, smtp_tls: e.target.value }))}
                >
                  <option value="starttls">STARTTLS (587)</option>
                  <option value="ssl">SSL/TLS (465)</option>
                  <option value="none">Keine (25)</option>
                </select>
              </div>
            </div>
            <label style={labelStyle}>Recipients (comma-separated)</label>
            <input style={{ ...inputStyle, marginBottom: 10 }} placeholder="admin@example.com"
              value={cfg.smtp_to ?? ''}
              onChange={e => setCfg(c => ({ ...c, smtp_to: e.target.value }))} />
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <Btn onClick={sendTestMail} disabled={testState === 'sending'}>
                <i className="ti ti-mail" aria-hidden />
                {testState === 'sending' ? 'Sende...' : 'Test-Mail senden'}
              </Btn>
              {testState && testState !== 'sending' && (
                <span style={{ fontSize: 12, color: testState === 'ok' ? 'var(--teal)' : '#f85149' }}>
                  {testState === 'ok' ? 'Test-Mail gesendet' : testState}
                </span>
              )}
            </div>
            <div style={{ fontSize: 11, color: 'var(--text3)', marginTop: 6 }}>
              Hinweis: Zuerst speichern, dann Test-Mail senden.
            </div>
          </div>

          {/* Webhooks */}
          <div>
            <SectionHead>Webhooks</SectionHead>
            <label style={labelStyle}>Discord Webhook</label>
            <input style={{ ...inputStyle, marginBottom: 12 }} type="password"
              placeholder="https://discord.com/api/webhooks/..."
              value={cfg.discord_webhook}
              onChange={e => setCfg(c => ({ ...c, discord_webhook: e.target.value }))} />
            <label style={labelStyle}>Slack Webhook</label>
            <input style={inputStyle} type="password"
              placeholder="https://hooks.slack.com/services/..."
              value={cfg.slack_webhook}
              onChange={e => setCfg(c => ({ ...c, slack_webhook: e.target.value }))} />
          </div>

          {/* Notify on */}
          <div>
            <SectionHead>Alert bei</SectionHead>
            {[['new_asset', 'Neuer Asset entdeckt'], ['new_vuln', 'Neues Finding'], ['scan_failed', 'Scan fehlgeschlagen']].map(([key, label]) => (
              <label key={key} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8, cursor: 'pointer' }}>
                <input type="checkbox"
                  checked={cfg.notify_on.includes(key)}
                  onChange={e => {
                    const val = e.target.checked
                      ? [...cfg.notify_on, key]
                      : cfg.notify_on.filter(x => x !== key)
                    setCfg(c => ({ ...c, notify_on: val }))
                  }}
                />
                <span style={{ fontSize: 13, color: 'var(--text2)' }}>{label}</span>
              </label>
            ))}
          </div>
        </div>
      </Content>
    </>
  )
}
