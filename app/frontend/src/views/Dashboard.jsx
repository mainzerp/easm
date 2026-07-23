import { useEffect, useState } from 'react'
import { Topbar, Btn, StatCard, Badge, SoftChip, SeverityBubbles, Content, SectionHead, Empty, thStyle, tdStyle } from '../components/ui.jsx'

export default function Dashboard({ onNav, onStartScan }) {
  const [stats, setStats]       = useState(null)
  const [findings, setFindings] = useState([])
  const [changes, setChanges]   = useState(null)
  const [config, setConfig]     = useState({ targets: [] })
  const [loading, setLoading]   = useState(true)
  const [scanStatus, setScanStatus] = useState({ running: false })
  const [domainStats, setDomainStats] = useState([])

  useEffect(() => {
    Promise.all([
      fetch('/api/scans').then(r => r.json()),
      fetch('/api/config').then(r => r.json()),
      fetch('/api/scan/status').then(r => r.json()),
      fetch('/api/findings/open').then(r => r.json()),
      fetch('/api/changes/latest').then(r => r.json()),
      fetch('/api/stats/overview').then(r => r.json()),
    ]).then(([s, c, st, openF, ch, ov]) => {
      setConfig(c)
      setScanStatus(st)
      setFindings(Array.isArray(openF) ? openF : [])
      setChanges(ch)
      setStats(ov)
      const targets = c.targets || []
      if (targets.length > 1 && s.length > 0) {
        Promise.all(
          targets.map(d =>
            fetch(`/api/scans?domain=${encodeURIComponent(d)}`)
              .then(r => r.json())
              .then(list => ({ domain: d, scan: list.find(x => x.subdomains > 0) || null }))
              .catch(() => ({ domain: d, scan: null }))
          )
        ).then(setDomainStats)
      }
    }).finally(() => setLoading(false))
  }, [])

  const sev = stats?.findings_by_severity || {}

  return (
    <>
      <Topbar title="Dashboard">
        {scanStatus.next_run && !scanStatus.running && (
          <span style={{ fontSize: 12, color: 'var(--text3)', marginRight: 4 }}>
            Nächster Scan: {new Date(scanStatus.next_run).toLocaleString('de-DE', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })}
          </span>
        )}
        {config.targets?.length > 0 && (
          <Btn onClick={() => onStartScan(config.targets.length > 1 ? '__all__' : config.targets[0])} variant="primary" disabled={scanStatus.running}>
            <i className="ti ti-player-play" aria-hidden />
            {scanStatus.running ? 'Scan läuft...' : 'Jetzt scannen'}
          </Btn>
        )}
      </Topbar>

      <Content>
        {loading ? (
          <Empty icon="ti-loader" text="Lade Daten..." />
        ) : (
          <>
            {/* ── Row 1: Score + Kernmetriken ─────────────────────────────── */}
            <div style={{ display: 'grid', gridTemplateColumns: '200px 1fr 1fr 1.2fr 1fr', gap: 12, marginBottom: 24 }}>
              <ScoreGauge score={stats?.score ?? 10} />
              <StatCard label="Assets" value={stats?.totals?.assets ?? '—'} delta={stats?.deltas?.assets} icon="ti-server-2" onClick={() => onNav('assets')} />
              <StatCard label="Live hosts" value={stats?.totals?.live_hosts ?? '—'} delta={stats?.deltas?.live_hosts} icon="ti-activity" onClick={() => onNav('assets')} />
              <div className="card" style={{ padding: '16px 18px', cursor: 'pointer' }} onClick={() => onNav('findings')}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <span style={{ fontSize: 13, color: 'var(--text2)' }}>Offene Findings</span>
                  <i className="ti ti-bug" style={{ fontSize: 16, color: 'var(--text3)' }} aria-hidden />
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginTop: 6 }}>
                  <span style={{ fontSize: 28, fontWeight: 600, letterSpacing: '-0.02em', color: stats?.totals?.open_findings > 0 ? 'var(--red)' : 'var(--text)' }}>
                    {stats?.totals?.open_findings ?? '—'}
                  </span>
                  <SeverityBubbles counts={sev} />
                </div>
                <div style={{ fontSize: 11, color: 'var(--text3)', marginTop: 4 }}>nach Schweregrad</div>
              </div>
              <StatCard label="Offene Ports" value={stats?.totals?.open_ports ?? '—'} icon="ti-door" onClick={() => onNav('assets')} />
            </div>

            {/* ── Alert banner wenn critical ──────────────────────────────── */}
            {(sev.critical ?? 0) > 0 && (
              <div style={{
                display: 'flex', alignItems: 'center', gap: 10,
                background: 'var(--sev-critical-bg)', border: '1px solid var(--sev-critical-border)',
                borderRadius: 'var(--radius)', padding: '12px 16px',
                marginBottom: 24, fontSize: 13,
              }}>
                <i className="ti ti-alert-triangle" style={{ color: 'var(--sev-critical-fg)', fontSize: 17 }} aria-hidden />
                <span style={{ color: 'var(--sev-critical-fg)', fontWeight: 600 }}>{sev.critical} kritische{sev.critical > 1 ? '' : 's'} Finding{sev.critical > 1 ? 's' : ''} offen</span>
                <span style={{ color: 'var(--text2)' }}>— sofortige Maßnahmen erforderlich</span>
                <Btn size="sm" onClick={() => onNav('findings')} style={{ marginLeft: 'auto' }}>
                  Details <i className="ti ti-arrow-right" aria-hidden />
                </Btn>
              </div>
            )}

            {/* ── Row 2: Severity-Chart + Zusammenfassung ─────────────────── */}
            <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: 12, marginBottom: 24 }}>
              {stats?.findings_by_scan?.length > 1 && (
                <div className="card" style={{ padding: '16px 18px' }}>
                  <SectionHead style={{ marginBottom: 8 }}>Findings-Verlauf nach Severity</SectionHead>
                  <SeverityChart series={stats.findings_by_scan} />
                </div>
              )}
              <div className="card" style={{ padding: '16px 18px' }}>
                <SectionHead style={{ marginBottom: 12 }}>Offene Findings</SectionHead>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                  {['critical', 'high', 'medium', 'low', 'info'].map(s => (
                    <div key={s} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                      <SoftChip sev={s}>{s}</SoftChip>
                      <span style={{ fontSize: 18, fontWeight: 600, fontFamily: 'var(--font-mono)', color: (sev[s] ?? 0) > 0 ? `var(--sev-${s}-fg)` : 'var(--text3)' }}>
                        {sev[s] ?? 0}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* ── Row 3: Pro Domain ───────────────────────────────────────── */}
            {domainStats.length > 0 && (
              <>
                <SectionHead>Pro Domain</SectionHead>
                <div style={{ display: 'grid', gridTemplateColumns: `repeat(${Math.min(domainStats.length, 3)}, 1fr)`, gap: 12, marginBottom: 24 }}>
                  {domainStats.map(({ domain, scan }) => (
                    <div key={domain} className="card" style={{ padding: '14px 16px' }}>
                      <div style={{ fontSize: 13, fontFamily: 'var(--font-mono)', color: 'var(--teal)', fontWeight: 600, marginBottom: 10 }}>
                        {domain}
                      </div>
                      {scan ? (
                        <div style={{ display: 'flex', gap: 16, fontSize: 12 }}>
                          <Stat label="domains" value={scan.subdomains} />
                          <Stat label="live" value={scan.live_hosts} />
                          <Stat label="findings" value={scan.findings} warn={scan.findings > 0} />
                        </div>
                      ) : (
                        <div style={{ fontSize: 12, color: 'var(--text3)' }}>Noch keine Daten</div>
                      )}
                      {scan && (
                        <div style={{ fontSize: 10, color: 'var(--text3)', marginTop: 10, fontFamily: 'var(--font-mono)' }}>
                          Scan: {scan.date}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </>
            )}

            {/* ── Row 4: Neu seit letztem Scan ────────────────────────────── */}
            {changes && changes.scan && (changes.new_assets.length > 0 || changes.new_findings.length > 0) && (
              <>
                <SectionHead>Neu seit letztem Scan <span style={{ color: 'var(--text3)', fontWeight: 400, fontFamily: 'var(--font-mono)', fontSize: 11 }}>({changes.scan})</span></SectionHead>
                <div className="card" style={{ padding: '14px 16px', marginBottom: 24, fontSize: 13, lineHeight: 1.8 }}>
                  {changes.new_assets.length > 0 && (
                    <div>
                      <span style={{ color: 'var(--teal)', fontWeight: 600 }}>{changes.new_assets.length} neue Assets</span>
                      <span style={{ color: 'var(--text2)' }}> — {changes.new_assets.slice(0, 4).map(a => a.host).join(', ')}{changes.new_assets.length > 4 ? `, +${changes.new_assets.length - 4} weitere` : ''}</span>
                    </div>
                  )}
                  {changes.new_findings.length > 0 && (
                    <div>
                      <span style={{ color: 'var(--red)', fontWeight: 600 }}>{changes.new_findings.length} neue Findings</span>
                      <span style={{ color: 'var(--text2)' }}> — {changes.new_findings.slice(0, 3).map(f => `${f.template} (${f.severity})`).join(', ')}{changes.new_findings.length > 3 ? `, +${changes.new_findings.length - 3} weitere` : ''}</span>
                    </div>
                  )}
                </div>
              </>
            )}

            {/* ── Row 5: Offene Findings Tabelle ──────────────────────────── */}
            <SectionHead>Offene Findings</SectionHead>
            {findings.length === 0 ? (
              <Empty icon="ti-circle-check" text="Keine offenen Findings — alles sauber" />
            ) : (
              <div className="card" style={{ overflow: 'hidden' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                  <thead>
                    <tr style={{ background: 'var(--bg3)' }}>
                      <th style={thStyle}>Severity</th>
                      <th style={thStyle}>Finding</th>
                      <th style={thStyle}>Domain</th>
                      <th style={thStyle}>Zuletzt gesehen</th>
                    </tr>
                  </thead>
                  <tbody>
                    {findings.slice(0, 8).map((f, i) => (
                      <tr key={i}>
                        <td style={tdStyle}><Badge sev={f.severity} /></td>
                        <td style={{ ...tdStyle, fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--text2)', maxWidth: 480, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={f.raw}>{f.raw}</td>
                        <td style={{ ...tdStyle, fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--text3)' }}>{f.domain}</td>
                        <td style={{ ...tdStyle, fontSize: 12, color: 'var(--text3)', whiteSpace: 'nowrap' }}>{f.last_seen ? new Date(f.last_seen).toLocaleDateString('de-DE') : '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {findings.length > 8 && (
                  <div onClick={() => onNav('findings')} style={{ padding: '10px 14px', fontSize: 12, color: 'var(--link)', cursor: 'pointer', textAlign: 'center', borderTop: '1px solid var(--border)' }}>
                    + {findings.length - 8} weitere ansehen
                  </div>
                )}
              </div>
            )}

            {/* Scan running indicator */}
            {scanStatus.running && (
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 20 }}>
                <span style={{ display: 'inline-block', width: 8, height: 8, borderRadius: '50%', background: 'var(--teal)', animation: 'pulse 1.8s ease-in-out infinite' }} />
                <span style={{ fontSize: 12, color: 'var(--text2)' }}>
                  Scan läuft: {scanStatus.target} —
                  <span style={{ color: 'var(--link)', cursor: 'pointer', marginLeft: 4 }} onClick={() => onNav('scan')}>
                    Live-Log ansehen
                  </span>
                </span>
              </div>
            )}
          </>
        )}
      </Content>

      <style>{`@keyframes pulse{0%,100%{opacity:1;transform:scale(1)}50%{opacity:.5;transform:scale(.75)}}`}</style>
    </>
  )
}

function Stat({ label, value, warn }) {
  return (
    <span style={{ fontSize: 12, color: 'var(--text3)' }}>
      <span style={{ fontSize: 15, fontWeight: 600, fontFamily: 'var(--font-mono)', color: warn ? 'var(--red)' : 'var(--text)', marginRight: 4 }}>{value}</span>
      {label}
    </span>
  )
}

function ScoreGauge({ score }) {
  const pct = Math.max(0, Math.min(1, score / 10))
  const r = 54
  const circ = 2 * Math.PI * r
  const color = score >= 8 ? 'var(--teal)' : score >= 5 ? 'var(--amber)' : 'var(--red)'
  return (
    <div className="card" style={{ padding: 14, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <svg width="132" height="132" viewBox="0 0 132 132" aria-hidden>
        <circle cx="66" cy="66" r={r} fill="none" stroke="var(--gauge-track)" strokeWidth="10" />
        <circle cx="66" cy="66" r={r} fill="none" stroke={color} strokeWidth="10"
          strokeLinecap="round"
          strokeDasharray={circ}
          strokeDashoffset={circ * (1 - pct)}
          transform="rotate(-90 66 66)"
          style={{ transition: 'stroke-dashoffset 0.9s ease' }}
        />
        <text x="66" y="64" textAnchor="middle" style={{ fontSize: 27, fontWeight: 600, fill: 'var(--text)', fontFamily: 'var(--font-mono)' }}>{score.toFixed(1)}</text>
        <text x="66" y="84" textAnchor="middle" style={{ fontSize: 9, fill: 'var(--text3)', letterSpacing: '0.1em' }}>SCORE / 10</text>
      </svg>
    </div>
  )
}

function SeverityChart({ series }) {
  const keys = [
    ['critical', 'var(--sev-critical-solid)'],
    ['high', 'var(--sev-high-solid)'],
    ['medium', 'var(--sev-medium-solid)'],
    ['low', 'var(--sev-low-solid)'],
  ]
  const W = 640, H = 170, pad = 12
  const max = Math.max(1, ...series.flatMap(s => keys.map(([k]) => s[k] ?? 0)))
  const x = i => pad + (series.length > 1 ? (i * (W - 2 * pad)) / (series.length - 1) : (W / 2))
  const y = v => H - pad - (v / max) * (H - 2 * pad)
  return (
    <div>
      <svg viewBox={`0 0 ${W} ${H}`} style={{ width: '100%', display: 'block' }} aria-hidden>
        {[0.25, 0.5, 0.75].map(f => (
          <line key={f} x1={pad} x2={W - pad} y1={H * f} y2={H * f} stroke="var(--border)" strokeWidth="1" />
        ))}
        {keys.map(([k, color]) => (
          <polyline key={k} fill="none" stroke={color} strokeWidth="2" strokeLinejoin="round" strokeLinecap="round"
            points={series.map((s, i) => `${x(i).toFixed(1)},${y(s[k] ?? 0).toFixed(1)}`).join(' ')} />
        ))}
      </svg>
      <div style={{ display: 'flex', gap: 16, fontSize: 12, color: 'var(--text2)', marginTop: 8 }}>
        {keys.map(([k, color]) => (
          <span key={k} style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
            <span style={{ width: 10, height: 3, borderRadius: 2, background: color, display: 'inline-block' }} /> {k}
          </span>
        ))}
      </div>
    </div>
  )
}
