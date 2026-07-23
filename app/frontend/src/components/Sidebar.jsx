import { useEffect, useState } from 'react'

const NAV = [
  { key: 'dashboard', icon: 'ti-layout-dashboard', label: 'Dashboard' },
  { key: 'assets',    icon: 'ti-server-2',         label: 'Assets' },
  { key: 'scans',     icon: 'ti-history',           label: 'Scan history' },
  { key: 'findings',  icon: 'ti-bug',               label: 'Findings' },
  { key: 'config',    icon: 'ti-settings',           label: 'Configuration' },
]

export default function Sidebar({ active, onNav, onLogout, theme, onToggleTheme, username, onOpenSettings }) {
  const [targets, setTargets] = useState([])
  const [lastScan, setLastScan] = useState(null)

  useEffect(() => {
    fetch('/api/config')
      .then(r => r.json())
      .then(d => setTargets(d.targets || []))
      .catch(() => setTargets([]))

    fetch('/api/scans')
      .then(r => r.json())
      .then(d => d.length && setLastScan(d[0].date))
      .catch(() => {})
  }, [])

  return (
    <div style={{
      width: 220, minWidth: 220,
      background: 'var(--bg2)',
      borderRight: '1px solid var(--border)',
      display: 'flex', flexDirection: 'column',
      overflow: 'hidden',
    }}>
      {/* Logo */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 10,
        padding: '18px 20px 16px',
        borderBottom: '1px solid var(--border)',
      }}>
        <span style={{
          display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
          width: 30, height: 30, borderRadius: 9,
          background: 'var(--teal)', color: '#fff',
        }}>
          <i className="ti ti-shield-lock" style={{ fontSize: 17 }} aria-hidden />
        </span>
        <span style={{ fontSize: 15, fontWeight: 600, letterSpacing: '-0.01em' }}>EASM</span>
      </div>

      {/* Nav */}
      <div style={{ padding: '12px 12px 4px' }}>
        {NAV.map(({ key, icon, label }) => {
          const isActive = active === key
          return (
            <div
              key={key}
              onClick={() => onNav(key)}
              style={{
                display: 'flex', alignItems: 'center', gap: 10,
                padding: '8px 10px', marginBottom: 2,
                fontSize: 13, cursor: 'pointer',
                fontWeight: isActive ? 600 : 500,
                borderRadius: 8,
                color: isActive ? 'var(--teal)' : 'var(--text2)',
                background: isActive ? 'var(--teal-soft-bg)' : 'transparent',
                transition: 'all 0.12s ease',
                userSelect: 'none',
              }}
              onMouseEnter={e => { if (!isActive) { e.currentTarget.style.background = 'var(--bg3)'; e.currentTarget.style.color = 'var(--text)' } }}
              onMouseLeave={e => { if (!isActive) { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = 'var(--text2)' } }}
            >
              <i className={`ti ${icon}`} style={{ fontSize: 17, width: 20, textAlign: 'center', color: isActive ? 'var(--teal)' : 'var(--text3)' }} aria-hidden />
              {label}
            </div>
          )
        })}
      </div>

      {/* Targets */}
      {targets.length > 0 && (
        <div style={{ padding: '10px 12px' }}>
          <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text3)', textTransform: 'uppercase', letterSpacing: '0.07em', padding: '4px 10px 6px' }}>
            Targets
          </div>
          {targets.map(t => (
            <div key={t} style={{
              display: 'flex', alignItems: 'center', gap: 8,
              padding: '5px 10px', fontSize: 12, color: 'var(--text2)',
              fontFamily: 'var(--font-mono)',
            }}>
              <span style={{ width: 6, height: 6, borderRadius: 3, background: 'var(--teal)', flexShrink: 0 }} aria-hidden />
              {t}
            </div>
          ))}
        </div>
      )}

      {/* Bottom */}
      <div style={{
        marginTop: 'auto',
        padding: '14px 20px 16px',
        borderTop: '1px solid var(--border)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
          <div>
            <div style={{ fontSize: 11, color: 'var(--text3)', fontWeight: 500 }}>Last scan</div>
            <div style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text2)', marginTop: 3 }}>
              {lastScan ?? '—'}
            </div>
          </div>
          <button
            onClick={onToggleTheme}
            title={theme === 'dark' ? 'Zum Light-Theme wechseln' : 'Zum Dark-Theme wechseln'}
            style={{
              display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
              width: 32, height: 32, borderRadius: 8,
              border: '1px solid var(--border2)', background: 'var(--bg2)',
              color: 'var(--text2)', cursor: 'pointer', fontSize: 15,
              transition: 'all 0.12s ease',
            }}
          >
            <i className={`ti ${theme === 'dark' ? 'ti-sun' : 'ti-moon'}`} aria-hidden />
          </button>
        </div>
        {onOpenSettings && (
          <div
            onClick={onOpenSettings}
            style={{
              display: 'flex', alignItems: 'center', gap: 8,
              fontSize: 12, color: 'var(--text3)', cursor: 'pointer',
              padding: '4px 0', fontWeight: 500,
            }}
            onMouseEnter={e => e.currentTarget.style.color = 'var(--text)'}
            onMouseLeave={e => e.currentTarget.style.color = 'var(--text3)'}
          >
            <i className="ti ti-user-cog" style={{ fontSize: 15 }} aria-hidden />
            {username || 'Benutzer'}
          </div>
        )}
        {onLogout && (
          <div
            onClick={onLogout}
            style={{
              display: 'flex', alignItems: 'center', gap: 8,
              fontSize: 12, color: 'var(--text3)', cursor: 'pointer',
              padding: '4px 0', fontWeight: 500,
            }}
            onMouseEnter={e => e.currentTarget.style.color = 'var(--text)'}
            onMouseLeave={e => e.currentTarget.style.color = 'var(--text3)'}
          >
            <i className="ti ti-logout" style={{ fontSize: 15 }} aria-hidden />
            Abmelden
          </div>
        )}
      </div>
    </div>
  )
}
