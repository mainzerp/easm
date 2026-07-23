import { useEffect } from 'react'

/* ── Topbar ─────────────────────────────────────────────────────────────── */
export function Topbar({ title, children }) {
  return (
    <div style={{
      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      padding: '16px 28px',
      borderBottom: '1px solid var(--border)',
      flexShrink: 0, gap: 12, flexWrap: 'wrap',
      background: 'var(--bg2)',
    }}>
      <span style={{ fontSize: 16, fontWeight: 600, letterSpacing: '-0.01em' }}>{title}</span>
      <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>{children}</div>
    </div>
  )
}

/* ── Btn ─────────────────────────────────────────────────────────────────── */
export function Btn({ children, onClick, variant = 'default', size = 'md', disabled, type = 'button' }) {
  const base = {
    display: 'inline-flex', alignItems: 'center', gap: 6,
    padding: size === 'sm' ? '5px 12px' : '8px 16px',
    fontSize: size === 'sm' ? 12 : 13,
    fontWeight: 500,
    borderRadius: 8,
    border: '1px solid',
    cursor: disabled ? 'not-allowed' : 'pointer',
    opacity: disabled ? 0.45 : 1,
    fontFamily: 'var(--font-sans)',
    transition: 'all 0.12s ease',
  }
  const variants = {
    default: { background: 'var(--bg2)', color: 'var(--text2)', borderColor: 'var(--border2)' },
    primary: { background: 'var(--teal)',  color: '#fff',        borderColor: 'var(--teal)' },
    danger:  { background: 'var(--red)',   color: '#fff',        borderColor: 'var(--red)' },
  }
  return (
    <button type={type} style={{ ...base, ...variants[variant] }} onClick={!disabled ? onClick : undefined}>
      {children}
    </button>
  )
}

/* ── Stat card (label, large value, optional delta) ──────────────────────────── */
export function StatCard({ label, value, delta, deltaGood = true, icon, onClick }) {
  return (
    <div className="card" onClick={onClick}
      style={{ padding: '16px 18px', cursor: onClick ? 'pointer' : 'default' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <span style={{ fontSize: 13, color: 'var(--text2)' }}>{label}</span>
        {icon && <i className={`ti ${icon}`} style={{ fontSize: 16, color: 'var(--text3)' }} aria-hidden />}
      </div>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, marginTop: 4 }}>
        <span style={{ fontSize: 28, fontWeight: 600, letterSpacing: '-0.02em', lineHeight: 1.1, color: 'var(--text)' }}>
          {value}
        </span>
        {delta !== undefined && delta !== null && delta !== 0 && (
          <span style={{
            display: 'inline-flex', alignItems: 'center', gap: 2,
            fontSize: 12, fontWeight: 600,
            color: (delta > 0) === deltaGood ? 'var(--green)' : 'var(--red)',
          }}>
            <i className={`ti ${delta > 0 ? 'ti-arrow-up-right' : 'ti-arrow-down-right'}`} style={{ fontSize: 12 }} aria-hidden />
            {Math.abs(delta)}
          </span>
        )}
      </div>
      {delta !== undefined && (
        <div style={{ fontSize: 11, color: 'var(--text3)', marginTop: 2 }}>vs. vorheriger Scan</div>
      )}
    </div>
  )
}

/* ── Severity pill (solid, Referenz-Stil) ─────────────────────────────────── */
export function Badge({ sev, children }) {
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center',
      padding: '3px 10px', borderRadius: 999,
      fontSize: 11, fontWeight: 600, letterSpacing: '0.01em',
      background: `var(--sev-${sev}-solid, var(--sev-info-solid))`,
      color: '#fff',
      whiteSpace: 'nowrap', flexShrink: 0,
    }}>{children || sev}</span>
  )
}

/* ── Soft chip (subtle color, for counts) ──────────────────────────────────── */
export function SoftChip({ sev = 'info', children }) {
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center',
      padding: '2px 8px', borderRadius: 6,
      fontSize: 11, fontWeight: 600, fontFamily: 'var(--font-mono)',
      background: `var(--sev-${sev}-bg)`,
      color: `var(--sev-${sev}-fg)`,
      border: `1px solid var(--sev-${sev}-border)`,
      whiteSpace: 'nowrap',
    }}>{children}</span>
  )
}

/* ── Severity bubbles (Referenz: farbige Kreise mit Anzahl) ───────────────── */
export function SeverityBubbles({ counts }) {
  const order = ['critical', 'high', 'medium', 'low', 'info']
  return (
    <div style={{ display: 'inline-flex', gap: 8, alignItems: 'center' }}>
      {order.map(s => (
        <span key={s} title={`${s}: ${counts[s] ?? 0}`} style={{
          display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
          minWidth: 34, height: 34, padding: '0 6px', borderRadius: 999,
          fontSize: 13, fontWeight: 600, fontFamily: 'var(--font-mono)',
          background: `var(--sev-${s}-solid)`, color: '#fff',
        }}>{counts[s] ?? 0}</span>
      ))}
    </div>
  )
}

/* ── Table primitives ─────────────────────────────────────────────────────── */
export const thStyle = {
  textAlign: 'left', fontSize: 12, fontWeight: 600,
  color: 'var(--text2)', padding: '10px 14px',
  borderBottom: '1px solid var(--border)',
  whiteSpace: 'nowrap',
}
export const tdStyle = {
  padding: '10px 14px', fontSize: 13,
  borderBottom: '1px solid var(--border)',
  verticalAlign: 'middle',
}

/* ── Content wrapper ─────────────────────────────────────────────────────── */
export function Content({ children }) {
  return (
    <div style={{ padding: '24px 28px', flex: 1, overflowY: 'auto' }}>
      {children}
    </div>
  )
}

/* ── Section heading ─────────────────────────────────────────────────────── */
export function SectionHead({ children, style }) {
  return (
    <div style={{
      fontSize: 13, fontWeight: 600, color: 'var(--text)',
      marginBottom: 12, ...style,
    }}>{children}</div>
  )
}

/* ── Loading / empty state ───────────────────────────────────────────────── */
export function Empty({ icon = 'ti-inbox', text }) {
  return (
    <div style={{ textAlign: 'center', padding: '56px 0', color: 'var(--text3)' }}>
      <i className={`ti ${icon}`} style={{ fontSize: 34, display: 'block', marginBottom: 12 }} aria-hidden />
      <span style={{ fontSize: 13 }}>{text}</span>
    </div>
  )
}

/* ── Modal ────────────────────────────────────────────────────────────────── */
export function Modal({ open, onClose, title, children }) {
  useEffect(() => {
    if (!open) return
    function onKey(e) {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])

  if (!open) return null
  return (
    <div
      onClick={onClose}
      style={{
        position: 'fixed', inset: 0,
        background: 'rgba(0, 0, 0, 0.4)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        zIndex: 1000, padding: 16,
      }}
    >
      <div
        onClick={e => e.stopPropagation()}
        className="card"
        style={{
          width: '100%', maxWidth: 420,
          maxHeight: '90vh', overflowY: 'auto',
          padding: 0,
        }}
      >
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '18px 20px',
          borderBottom: '1px solid var(--border)',
        }}>
          <span style={{ fontSize: 15, fontWeight: 600, color: 'var(--text)' }}>{title}</span>
          <button
            onClick={onClose}
            aria-label="Close"
            style={{
              display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
              width: 28, height: 28, borderRadius: 7,
              border: 'none', background: 'transparent', color: 'var(--text3)',
              cursor: 'pointer', fontSize: 16,
            }}
          >
            <i className="ti ti-x" aria-hidden />
          </button>
        </div>
        <div style={{ padding: '20px' }}>
          {children}
        </div>
      </div>
    </div>
  )
}

/* ── Form input ───────────────────────────────────────────────────────────── */
export function Input({ type = 'text', value, onChange, placeholder, ...props }) {
  return (
    <input
      type={type}
      value={value}
      onChange={onChange}
      placeholder={placeholder}
      style={{
        width: '100%', padding: '10px 12px', fontSize: 14,
        background: 'var(--bg2)', border: '0.5px solid var(--border2)',
        borderRadius: 'var(--radius)', color: 'var(--text)',
        outline: 'none', boxSizing: 'border-box',
      }}
      {...props}
    />
  )
}

/* ── Legacy aliases (damit bestehende Views nicht brechen) ────────────────── */
export const Metric = StatCard
