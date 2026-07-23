import { useEffect, useState } from 'react'
import { Topbar, Content, Badge, Empty } from '../components/ui.jsx'

const SEVERITIES = ['all', 'critical', 'high', 'medium', 'low']

export default function Findings() {
  const [allFindings, setAllFindings] = useState([])
  const [filter, setFilter]           = useState('all')
  const [domains, setDomains]         = useState([])
  const [domain, setDomain]           = useState('all')
  const [loading, setLoading]         = useState(true)

  useEffect(() => {
    fetch('/api/domains')
      .then(r => r.json())
      .then(d => setDomains(d.domains || []))
      .catch(() => {})

    fetch('/api/findings/open')
      .then(r => r.json())
      .then(f => setAllFindings(Array.isArray(f) ? f : []))
      .finally(() => setLoading(false))
  }, [])

  const visible = allFindings.filter(f =>
    (filter === 'all' || f.severity === filter) &&
    (domain === 'all' || f.domain === domain)
  )

  const counts = SEVERITIES.slice(1).reduce((acc, s) => {
    acc[s] = allFindings.filter(f => f.severity === s).length
    return acc
  }, {})

  return (
    <>
      <Topbar title={`Findings (${visible.length})`}>
        {domains.length > 1 && (
          <div style={{ display: 'flex', gap: 6, marginRight: 8 }}>
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
                {d === 'all' ? 'Alle' : d}
              </button>
            ))}
          </div>
        )}
        <div style={{ display: 'flex', gap: 6 }}>
          {SEVERITIES.map(s => {
            const isActive = filter === s
            const solid = s === 'all' ? 'var(--teal)' : `var(--sev-${s}-solid)`
            return (
              <button
                key={s}
                onClick={() => setFilter(s)}
                style={{
                  padding: '5px 12px', fontSize: 12, borderRadius: 20,
                  border: '0.5px solid',
                  fontWeight: isActive ? 600 : 400,
                  borderColor: isActive ? solid : 'var(--border2)',
                  color: isActive ? '#fff' : 'var(--text2)',
                  background: isActive ? solid : 'var(--bg2)',
                  cursor: 'pointer', fontFamily: 'var(--font-sans)',
                }}
              >
                {s === 'all' ? `All (${allFindings.length})` : `${s} ${counts[s] > 0 ? `(${counts[s]})` : ''}`}
              </button>
            )
          })}
        </div>
      </Topbar>

      <Content>
        {loading ? <Empty icon="ti-loader" text="Lade Findings..." /> :
         visible.length === 0 ? <Empty icon="ti-circle-check" text="Keine offenen Findings in dieser Kategorie" /> : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
            {visible.map((f, i) => (
              <div
                key={i}
                style={{
                  display: 'flex', alignItems: 'flex-start', gap: 10,
                  padding: '10px 14px',
                  background: 'var(--bg2)', borderRadius: 'var(--radius)',
                  border: '0.5px solid var(--border)',
                  borderLeft: `3px solid var(--sev-${f.severity}-solid, var(--border))`,
                }}
              >
                <Badge sev={f.severity} />
                <span style={{
                  fontSize: 12, fontFamily: 'var(--font-mono)',
                  color: 'var(--text2)', lineHeight: 1.7, wordBreak: 'break-all', flex: 1,
                }}>{f.raw}</span>
                {f.domain && (
                  <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text3)', whiteSpace: 'nowrap' }}>
                    {f.domain}
                  </span>
                )}
              </div>
            ))}
          </div>
        )}
      </Content>
    </>
  )
}
