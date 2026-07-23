import { useEffect, useState } from 'react'
import { Topbar, Btn, Content, Empty, thStyle, tdStyle } from '../components/ui.jsx'

const TYPES = [
  ['all', 'Alle'],
  ['ipv4', 'IPv4'],
  ['http', 'HTTP'],
  ['ports', 'Ports'],
  ['tech', 'Tech'],
]

export default function Assets() {
  const [data, setData]       = useState(null)
  const [domains, setDomains] = useState([])
  const [type, setType]       = useState('all')
  const [domain, setDomain]   = useState('all')
  const [q, setQ]             = useState('')
  const [page, setPage]       = useState(1)
  const [perPage, setPerPage] = useState(50)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetch('/api/domains').then(r => r.json()).then(d => setDomains(d.domains || [])).catch(() => {})
  }, [])

  useEffect(() => {
    setLoading(true)
    const params = new URLSearchParams()
    if (type !== 'all') params.set('type', type)
    if (domain !== 'all') params.set('domain', domain)
    if (q.trim()) params.set('q', q.trim())
    params.set('page', String(page))
    params.set('per_page', String(perPage))
    fetch(`/api/assets?${params}`)
      .then(r => r.json())
      .then(setData)
      .finally(() => setLoading(false))
  }, [type, domain, q, page, perPage])

  function exportCsv() {
    const params = new URLSearchParams()
    if (type !== 'all') params.set('type', type)
    if (domain !== 'all') params.set('domain', domain)
    if (q.trim()) params.set('q', q.trim())
    params.set('page', '1')
    params.set('per_page', '200')
    fetch(`/api/assets?${params}`)
      .then(r => r.json())
      .then(d => {
        const rows = [['host', 'domain', 'ip', 'http_status', 'title', 'tech', 'ports']]
        d.items.forEach(a => rows.push([a.host, a.domain, a.ip ?? '', a.http_status ?? '', (a.title ?? '').replaceAll(',', ' '), (a.tech ?? '').replaceAll(',', ' '), a.ports ?? '']))
        const csv = rows.map(r => r.map(v => `"${String(v).replaceAll('"', '""')}"`).join(',')).join('\n')
        const blob = new Blob([csv], { type: 'text/csv' })
        const url = URL.createObjectURL(blob)
        const link = document.createElement('a')
        link.href = url
        link.download = `easm-assets-${new Date().toISOString().slice(0, 10)}.csv`
        link.click()
        URL.revokeObjectURL(url)
      })
  }

  const counts = data?.counts || {}
  const totalPages = data ? Math.max(1, Math.ceil(data.total / perPage)) : 1

  return (
    <>
      <Topbar title={`Assets${data?.scan ? ` — Scan ${data.scan}` : ''}`}>
        <input
          placeholder="Host suchen..."
          value={q}
          onChange={e => { setQ(e.target.value); setPage(1) }}
          style={{
            padding: '6px 10px', fontSize: 12, width: 200,
            background: 'var(--bg2)', border: '0.5px solid var(--border2)',
            borderRadius: 'var(--radius)', color: 'var(--text)', outline: 'none',
            fontFamily: 'var(--font-mono)',
          }}
        />
        {domains.length > 1 && (
          <select
            value={domain}
            onChange={e => { setDomain(e.target.value); setPage(1) }}
            style={{
              padding: '6px 10px', fontSize: 12, background: 'var(--bg2)',
              border: '0.5px solid var(--border2)', borderRadius: 'var(--radius)',
              color: 'var(--text)', cursor: 'pointer', fontFamily: 'var(--font-mono)',
            }}
          >
            <option value="all">Alle Domains</option>
            {domains.map(d => <option key={d} value={d}>{d}</option>)}
          </select>
        )}
        <Btn onClick={exportCsv} disabled={!data || data.total === 0}>
          <i className="ti ti-download" aria-hidden /> CSV
        </Btn>
      </Topbar>

      <Content>
        {/* Type chips */}
        <div style={{ display: 'flex', gap: 6, marginBottom: 16, flexWrap: 'wrap' }}>
          {TYPES.map(([key, label]) => (
            <button
              key={key}
              onClick={() => { setType(key); setPage(1) }}
              style={{
                padding: '5px 12px', fontSize: 12, borderRadius: 20,
                border: '0.5px solid', cursor: 'pointer',
                borderColor: type === key ? 'var(--teal)' : 'var(--border2)',
                color: type === key ? 'var(--teal)' : 'var(--text2)',
                background: type === key ? 'var(--bg3)' : 'var(--bg2)',
              }}
            >
              {label} <span style={{ fontFamily: 'var(--font-mono)', opacity: 0.75 }}>{counts[key] ?? 0}</span>
            </button>
          ))}
        </div>

        {loading ? <Empty icon="ti-loader" text="Lade Assets..." /> :
         !data || data.items.length === 0 ? <Empty icon="ti-server-off" text="Keine Assets in dieser Ansicht" /> : (
          <>
            <div className="card" style={{ overflow: 'hidden' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr style={{ background: 'var(--bg3)' }}>
                    <th style={thStyle}>Host</th>
                    <th style={thStyle}>Type</th>
                    <th style={thStyle}>Issues</th>
                    <th style={thStyle}>IP</th>
                    <th style={thStyle}>HTTP</th>
                    <th style={thStyle}>Tech</th>
                    <th style={thStyle}>Ports</th>
                  </tr>
                </thead>
                <tbody>
                  {data.items.map((a, i) => {
                    const showGroup = i === 0 || data.items[i - 1].domain !== a.domain
                    return (
                      <AssetRows key={a.host} asset={a} showGroup={showGroup}
                        groupCount={data.items.filter(x => x.domain === a.domain).length} />
                    )
                  })}
                </tbody>
              </table>
            </div>

            {/* Pagination */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: 14, fontSize: 12, color: 'var(--text2)' }}>
              <span>
                {(page - 1) * perPage + 1} – {Math.min(page * perPage, data.total)} / {data.total}
                <span style={{ color: 'var(--text3)', marginLeft: 10 }}>
                  Pro Seite
                  <select
                    value={perPage}
                    onChange={e => { setPerPage(Number(e.target.value)); setPage(1) }}
                    style={{
                      marginLeft: 6, padding: '3px 6px', fontSize: 12, background: 'var(--bg2)',
                      border: '1px solid var(--border2)', borderRadius: 6,
                      color: 'var(--text)', cursor: 'pointer', fontFamily: 'var(--font-mono)',
                    }}
                  >
                    {[25, 50, 100].map(n => <option key={n} value={n}>{n}</option>)}
                  </select>
                </span>
              </span>
              <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                <PgBtn disabled={page <= 1} onClick={() => setPage(p => p - 1)}><i className="ti ti-chevron-left" aria-hidden /></PgBtn>
                {pageNumbers(page, totalPages).map((p, i) => p === '…' ? (
                  <span key={`e${i}`} style={{ padding: '0 4px', color: 'var(--text3)' }}>…</span>
                ) : (
                  <PgBtn key={p} active={p === page} onClick={() => setPage(p)}>{p}</PgBtn>
                ))}
                <PgBtn disabled={page >= totalPages} onClick={() => setPage(p => p + 1)}><i className="ti ti-chevron-right" aria-hidden /></PgBtn>
              </div>
            </div>
          </>
        )}
      </Content>
    </>
  )
}

const SEVS = ['critical', 'high', 'medium', 'low']

function PgBtn({ children, active, disabled, onClick }) {
  return (
    <button
      onClick={!disabled ? onClick : undefined}
      style={{
        minWidth: 28, height: 28, padding: '0 6px',
        display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
        fontSize: 12, fontWeight: active ? 600 : 500, fontFamily: 'var(--font-mono)',
        borderRadius: 6, cursor: disabled ? 'not-allowed' : 'pointer',
        border: '1px solid',
        borderColor: active ? 'var(--teal)' : 'var(--border2)',
        background: active ? 'var(--teal)' : 'var(--bg2)',
        color: active ? '#fff' : 'var(--text2)',
        opacity: disabled ? 0.4 : 1,
      }}
    >{children}</button>
  )
}

function pageNumbers(page, total) {
  if (total <= 7) return Array.from({ length: total }, (_, i) => i + 1)
  if (page <= 4) return [1, 2, 3, 4, 5, '…', total]
  if (page >= total - 3) return [1, '…', total - 4, total - 3, total - 2, total - 1, total]
  return [1, '…', page - 1, page, page + 1, '…', total]
}

function IssueChips({ issues }) {
  return (
    <span style={{ display: 'inline-flex', gap: 4 }}>
      {SEVS.map(s => {
        const n = issues?.[s] || 0
        return (
          <span
            key={s}
            title={`${s}: ${n}`}
            style={{
              display: 'inline-block', minWidth: 22, textAlign: 'center',
              padding: '1px 6px', borderRadius: 5,
              fontSize: 11, fontFamily: 'var(--font-mono)', fontWeight: 600,
              background: n > 0 ? `var(--sev-${s}-solid)` : 'var(--bg3)',
              color: n > 0 ? '#fff' : 'var(--text3)',
              border: `0.5px solid ${n > 0 ? 'transparent' : 'var(--border)'}`,
            }}
          >{n}</span>
        )
      })}
    </span>
  )
}

function AssetRows({ asset: a, showGroup, groupCount }) {
  const types = []
  if (a.ip) types.push('IPv4')
  if (a.http_status != null) types.push('HTTP')
  if (a.ports) types.push('Ports')
  return (
    <>
      {showGroup && (
        <tr>
          <td colSpan={7} style={{
            padding: '8px 14px', fontSize: 12, fontWeight: 600,
            fontFamily: 'var(--font-mono)', color: 'var(--teal)',
            background: 'var(--bg3)', borderBottom: '1px solid var(--border)',
          }}>
            {a.domain || '(ohne Domain)'} <span style={{ color: 'var(--text3)', fontWeight: 400 }}>{groupCount} Assets</span>
          </td>
        </tr>
      )}
      <tr>
        <td style={{ ...tdStyle, fontFamily: 'var(--font-mono)', fontSize: 12 }}>
          <span style={{ color: 'var(--link)', cursor: 'pointer' }}>{a.host}</span>
        </td>
        <td style={tdStyle}>
          <span style={{ display: 'inline-flex', gap: 4 }}>
            {types.length ? types.map(t => (
              <span key={t} style={{
                padding: '2px 7px', borderRadius: 5, fontSize: 10, fontWeight: 600,
                background: 'var(--sev-medium-bg)', color: 'var(--sev-medium-fg)',
                border: '1px solid var(--sev-medium-border)',
              }}>{t}</span>
            )) : <span style={{ color: 'var(--text3)' }}>—</span>}
          </span>
        </td>
        <td style={tdStyle}><IssueChips issues={a.issues} /></td>
        <td style={{ ...tdStyle, fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--text2)' }}>{a.ip ?? '—'}</td>
        <td style={tdStyle}>
          {a.http_status != null ? (
            <span style={{
              fontFamily: 'var(--font-mono)', fontSize: 12, fontWeight: 600,
              color: a.http_status < 300 ? 'var(--teal)' : a.http_status < 400 ? 'var(--amber)' : 'var(--red)',
            }}>{a.http_status}</span>
          ) : '—'}
        </td>
        <td style={{ ...tdStyle, color: 'var(--text2)', fontSize: 12, maxWidth: 220, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={a.tech || ''}>{a.tech ?? '—'}</td>
        <td style={{ ...tdStyle, fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--text2)' }}>{a.ports ?? '—'}</td>
      </tr>
    </>
  )
}
