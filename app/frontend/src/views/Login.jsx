import { useState } from 'react'

const inputStyle = {
  width: '100%', padding: '10px 12px', fontSize: 14,
  background: 'var(--bg2)', border: '0.5px solid var(--border2)',
  borderRadius: 'var(--radius)', color: 'var(--text)',
  outline: 'none', boxSizing: 'border-box',
}

export default function Login({ totpEnabled, onLogin }) {
  const [password, setPassword] = useState('')
  const [code, setCode]         = useState('')
  const [error, setError]       = useState('')
  const [loading, setLoading]   = useState(false)

  async function submit(e) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const res = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ password, code }),
      })
      if (res.ok) { onLogin(); return }
      const data = await res.json().catch(() => ({}))
      if (res.status === 429) setError(data.detail || 'Zu viele Versuche — bitte später erneut probieren.')
      else if (data.detail === 'totp_required') setError('Bitte 2FA-Code eingeben.')
      else setError(data.detail || 'Login fehlgeschlagen.')
    } catch {
      setError('Verbindung zum Server fehlgeschlagen.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{
      minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center',
      background: 'var(--bg)', padding: 16,
    }}>
      <form onSubmit={submit} style={{
        width: '100%', maxWidth: 340,
        background: 'var(--bg2)', border: '0.5px solid var(--border)',
        borderRadius: 'var(--radius-lg, 12px)', padding: '28px 24px',
        display: 'flex', flexDirection: 'column', gap: 12,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6 }}>
          <i className="ti ti-shield-lock" style={{ fontSize: 22, color: 'var(--teal)' }} aria-hidden />
          <span style={{ fontSize: 16, fontWeight: 500, color: 'var(--text)' }}>EASM Login</span>
        </div>

        <input
          type="password" placeholder="Passwort" autoFocus
          value={password} onChange={e => setPassword(e.target.value)}
          style={inputStyle}
        />
        {totpEnabled && (
          <input
            type="text" placeholder="2FA-Code" inputMode="numeric" autoComplete="one-time-code"
            value={code} onChange={e => setCode(e.target.value)}
            style={{ ...inputStyle, fontFamily: 'var(--font-mono)', letterSpacing: '0.2em' }}
          />
        )}

        {error && (
          <div style={{ fontSize: 12, color: '#f85149', lineHeight: 1.5 }}>{error}</div>
        )}

        <button
          type="submit" disabled={loading || !password}
          style={{
            padding: '10px 12px', fontSize: 14, fontWeight: 500,
            background: 'var(--teal)', color: '#04110b',
            border: 'none', borderRadius: 'var(--radius)', cursor: 'pointer',
            opacity: loading || !password ? 0.5 : 1,
          }}
        >
          {loading ? 'Prüfe...' : 'Anmelden'}
        </button>
      </form>
    </div>
  )
}
