import { useEffect, useState } from 'react'
import { Topbar, Content, SectionHead, Empty } from '../components/ui.jsx'

export default function Scans() {
  const [scans, setScans]     = useState([])
  const [selected, setSelected] = useState(null)
  const [detail, setDetail]   = useState(null)
  const [loading, setLoading] = useState(true)
  const [tab, setTab]         = useState('subdomains.txt')
  const [domains, setDomains] = useState([])
  const [domain, setDomain]   = useState('all')

  useEffect(() => {
    fetch('/api/domains')
      .then(r => r.json())
      .then(d => setDomains(d.domains || []))
      .catch(() => {})
  }, [])

  useEffect(() => {
    setLoading(true)
    const url = domain === 'all' ? '/api/scans' : `/api/scans?domain=${encodeURIComponent(domain)}`
    fetch(url)
      .then(r => r.json())
      .then(d => {
        setScans(d)
        if (d.length && !d.find(s => s.date === selected)) setSelected(d[0].date)
        if (!d.length) setSelected(null)
      })
      .finally(() => setLoading(false))
  }, [domain])

  useEffect(() => {
    if (!selected) return
    setDetail(null)
    fetch(`/api/scans/${selected}`)
      .then(r => r.json())
      .then(setDetail)
  }, [selected])

  const FILES = ['subdomains.txt', 'http-results.txt', 'ports.txt', 'vulns.txt']

  return (
    <>
      <Topbar title="Scan history">
        {domains.length > 1 && (
          <div style={{ display: 'flex', gap: 6 }}>
            {['all', ...domains].map(d => (
              <button
                key={d}
                onClick={() => setDomain(d)}
                style={{
                  padding: '5px 12px', fontSize: 12, borderRadius: 'var(--radius)',
                  border: '0.5px solid',
                  borderColor: domain === d ? 'var(--teal)' : 'var(--border)',
                  color: domain === d ? 'var(--teal)' : 'var(--text2)',
                  background: 'transparent', cursor: 'pointer',
                  fontFamily: d === 'all' ? 'var(--font-sans)' : 'var(--font-mono)',
                }}
              >
                {d === 'all' ? 'Alle Domains' : d}
              </button>
            ))}
          </div>
        )}
      </Topbar>
      <Content>
        {loading ? <Empty icon="ti-loader" text="Lade Scans..." /> : scans.length === 0 ? (
          <Empty icon="ti-history" text="No scans yet — start the first one from the Dashboard" />
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: '260px 1fr', gap: 16, height: '100%' }}>

            {/* Scan list */}
            <div>
              <SectionHead>Scans</SectionHead>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                {scans.map(s => (
                  <div
                    key={s.date}
                    onClick={() => setSelected(s.date)}
                    style={{
                      padding: '10px 12px',
                      background: selected === s.date ? 'var(--bg3)' : 'var(--bg2)',
                      borderRadius: 'var(--radius)',
                      border: `0.5px solid ${selected === s.date ? 'var(--teal)' : 'var(--border)'}`,
                      cursor: 'pointer',
                    }}
                  >
                    <div style={{ fontSize: 12, fontFamily: 'var(--font-mono)', marginBottom: 6 }}>{s.date}</div>
                    <div style={{ display: 'flex', gap: 12 }}>
                      <span style={{ fontSize: 11, color: 'var(--text3)' }}><span style={{ color: 'var(--teal)', fontWeight: 500 }}>{s.subdomains}</span> domains</span>
                      <span style={{ fontSize: 11, color: 'var(--text3)' }}><span style={{ color: 'var(--text)', fontWeight: 500 }}>{s.live_hosts}</span> live</span>
                      <span style={{ fontSize: 11, color: 'var(--text3)' }}>
                        <span style={{ color: s.findings > 0 ? 'var(--red)' : 'var(--text)', fontWeight: 500 }}>{s.findings}</span> findings
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Detail panel */}
            <div>
              <SectionHead>Ergebnisse — {selected}</SectionHead>
              {detail ? (
                <>
                  <div style={{ display: 'flex', gap: 6, marginBottom: 12 }}>
                    {FILES.filter(f => detail.files[f]).map(f => (
                      <button
                        key={f}
                        onClick={() => setTab(f)}
                        style={{
                          padding: '4px 10px', fontSize: 11, borderRadius: 'var(--radius)',
                          border: '0.5px solid', fontFamily: 'var(--font-mono)',
                          borderColor: tab === f ? 'var(--teal)' : 'var(--border)',
                          color: tab === f ? 'var(--teal)' : 'var(--text2)',
                          background: 'transparent', cursor: 'pointer',
                        }}
                      >{f}</button>
                    ))}
                  </div>
                  <pre style={{
                    background: 'var(--bg2)', borderRadius: 'var(--radius)',
                    border: '0.5px solid var(--border)',
                    padding: 14, fontSize: 11, fontFamily: 'var(--font-mono)',
                    color: 'var(--text2)', overflowY: 'auto',
                    maxHeight: 380, whiteSpace: 'pre-wrap', wordBreak: 'break-all',
                    lineHeight: 1.7,
                  }}>
                    {detail.files[tab] || '(leer)'}
                  </pre>
                </>
              ) : (
                <Empty icon="ti-loader" text="Lade Details..." />
              )}
            </div>
          </div>
        )}
      </Content>
    </>
  )
}
