import { useState } from 'react'
import { Modal, Input, Btn } from './ui.jsx'

export default function UserSettingsModal({ open, onClose, totpEnabled, onToggled, onLogout }) {
  const [tab, setTab] = useState('account')

  // Password change
  const [curPw, setCurPw] = useState('')
  const [newPw, setNewPw] = useState('')
  const [confPw, setConfPw] = useState('')
  const [pwMsg, setPwMsg] = useState('')
  const [pwLoading, setPwLoading] = useState(false)

  // TOTP setup
  const [setup, setSetup] = useState(null)
  const [setupCurPw, setSetupCurPw] = useState('')
  const [verifyCode, setVerifyCode] = useState('')
  const [setupMsg, setSetupMsg] = useState('')
  const [setupLoading, setSetupLoading] = useState(false)

  // TOTP disable
  const [disCurPw, setDisCurPw] = useState('')
  const [disCode, setDisCode] = useState('')
  const [disMsg, setDisMsg] = useState('')
  const [disLoading, setDisLoading] = useState(false)

  async function changePassword(e) {
    e.preventDefault()
    setPwMsg('')
    if (newPw !== confPw) {
      setPwMsg('Passwords do not match.')
      return
    }
    if (!newPw) {
      setPwMsg('New password must not be empty.')
      return
    }
    setPwLoading(true)
    try {
      const res = await fetch('/api/auth/change-password', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ current_password: curPw, new_password: newPw }),
      })
      if (res.ok) {
        setPwMsg('Password changed. Please log in again.')
        setTimeout(() => { onClose(); onLogout() }, 1200)
        return
      }
      const data = await res.json().catch(() => ({}))
      setPwMsg(data.detail || 'Change failed.')
    } catch {
      setPwMsg('Server connection failed.')
    } finally {
      setPwLoading(false)
    }
  }

  async function startTotpSetup(e) {
    e.preventDefault()
    setSetupMsg('')
    setSetupLoading(true)
    try {
      const res = await fetch('/api/auth/totp/setup', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ current_password: setupCurPw }),
      })
      const data = await res.json().catch(() => ({}))
      if (res.ok) {
        setSetup(data)
        setSetupMsg('Scan the QR code and enter the verification code.')
      } else {
        setSetupMsg(data.detail || 'Setup failed.')
      }
    } catch {
      setSetupMsg('Server connection failed.')
    } finally {
      setSetupLoading(false)
    }
  }

  async function verifyTotp(e) {
    e.preventDefault()
    setSetupMsg('')
    setSetupLoading(true)
    try {
      const res = await fetch('/api/auth/totp/verify', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ current_password: setupCurPw, code: verifyCode }),
      })
      const data = await res.json().catch(() => ({}))
      if (res.ok) {
        setSetup(null)
        setSetupCurPw('')
        setVerifyCode('')
        setSetupMsg('2FA enabled.')
        onToggled()
      } else {
        setSetupMsg(data.detail || 'Verification failed.')
      }
    } catch {
      setSetupMsg('Server connection failed.')
    } finally {
      setSetupLoading(false)
    }
  }

  async function disableTotp(e) {
    e.preventDefault()
    setDisMsg('')
    setDisLoading(true)
    try {
      const res = await fetch('/api/auth/totp/disable', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ current_password: disCurPw, code: disCode }),
      })
      const data = await res.json().catch(() => ({}))
      if (res.ok) {
        setDisCurPw('')
        setDisCode('')
        setDisMsg('2FA disabled.')
        onToggled()
      } else {
        setDisMsg(data.detail || 'Disable failed.')
      }
    } catch {
      setDisMsg('Server connection failed.')
    } finally {
      setDisLoading(false)
    }
  }

  const tabBtn = (key, label) => (
    <button
      key={key}
      onClick={() => setTab(key)}
      style={{
        flex: 1, padding: '8px 0', fontSize: 13, fontWeight: 500,
        border: 'none', background: tab === key ? 'var(--teal)' : 'transparent',
        color: tab === key ? '#fff' : 'var(--text2)', borderRadius: 7,
        cursor: 'pointer',
      }}
    >
      {label}
    </button>
  )

  return (
    <Modal open={open} onClose={onClose} title="User Settings">
      <div style={{
        display: 'flex', gap: 6,
        background: 'var(--bg3)', padding: 4, borderRadius: 9, marginBottom: 20,
      }}>
        {tabBtn('account', 'Account')}
        {tabBtn('security', 'Security')}
      </div>

      {tab === 'account' && (
        <form onSubmit={changePassword} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <div>
            <label style={{ display: 'block', fontSize: 12, color: 'var(--text3)', marginBottom: 6 }}>Username</label>
            <div style={{
              padding: '10px 12px', fontSize: 14,
              background: 'var(--bg3)', border: '0.5px solid var(--border2)',
              borderRadius: 'var(--radius)', color: 'var(--text2)',
            }}>admin</div>
          </div>

          <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text)', marginTop: 4 }}>Change Password</div>
          <Input
            type="password" placeholder="Current password"
            value={curPw} onChange={e => setCurPw(e.target.value)}
          />
          <Input
            type="password" placeholder="New password"
            value={newPw} onChange={e => setNewPw(e.target.value)}
          />
          <Input
            type="password" placeholder="Confirm new password"
            value={confPw} onChange={e => setConfPw(e.target.value)}
          />
          {pwMsg && <div style={{ fontSize: 12, color: pwMsg.includes('changed') || pwMsg.includes('enabled') || pwMsg.includes('disabled') ? 'var(--green)' : '#f85149', lineHeight: 1.5 }}>{pwMsg}</div>}
          <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
            <Btn type="submit" variant="primary" disabled={pwLoading || !curPw || !newPw || !confPw}>Change Password</Btn>
          </div>
        </form>
      )}

      {tab === 'security' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            padding: '12px 14px', background: 'var(--bg3)', borderRadius: 'var(--radius)',
          }}>
            <div>
              <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text)' }}>Two-Factor Authentication</div>
              <div style={{ fontSize: 12, color: 'var(--text3)', marginTop: 2 }}>
                {totpEnabled ? 'Enabled' : 'Disabled'}
              </div>
            </div>
            <div style={{
              width: 10, height: 10, borderRadius: 5,
              background: totpEnabled ? 'var(--green)' : 'var(--text3)',
            }} />
          </div>

          {!totpEnabled && !setup && (
            <form onSubmit={startTotpSetup} style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              <div style={{ fontSize: 12, color: 'var(--text3)', lineHeight: 1.5 }}>
                Enable 2FA with an authenticator app (e.g., Google Authenticator, Aegis, Bitwarden).
              </div>
              <Input
                type="password" placeholder="Current password"
                value={setupCurPw} onChange={e => setSetupCurPw(e.target.value)}
              />
              {setupMsg && <div style={{ fontSize: 12, color: setupMsg.includes('2FA enabled') || setupMsg.includes('QR code') ? 'var(--green)' : '#f85149', lineHeight: 1.5 }}>{setupMsg}</div>}
              <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
                <Btn type="submit" variant="primary" disabled={setupLoading || !setupCurPw}>Enable 2FA</Btn>
              </div>
            </form>
          )}

          {!totpEnabled && setup && (
            <form onSubmit={verifyTotp} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              <div style={{ textAlign: 'center' }}>
                <img src={setup.qr_uri} alt="TOTP QR-Code" style={{ maxWidth: 200, borderRadius: 8 }} />
              </div>
              <div style={{ fontSize: 12, color: 'var(--text3)', textAlign: 'center', fontFamily: 'var(--font-mono)' }}>
                {setup.secret}
              </div>
              <Input
                type="text" placeholder="Verification code" inputMode="numeric" autoComplete="one-time-code"
                value={verifyCode} onChange={e => setVerifyCode(e.target.value)}
                style={{ fontFamily: 'var(--font-mono)', letterSpacing: '0.2em' }}
              />
              {setupMsg && <div style={{ fontSize: 12, color: setupMsg.includes('enabled') ? 'var(--green)' : '#f85149', lineHeight: 1.5 }}>{setupMsg}</div>}
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <Btn type="button" variant="default" onClick={() => { setSetup(null); setSetupMsg('') }} disabled={setupLoading}>Cancel</Btn>
                <Btn type="submit" variant="primary" disabled={setupLoading || !verifyCode}>Verify</Btn>
              </div>
            </form>
          )}

          {totpEnabled && (
            <form onSubmit={disableTotp} style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              <div style={{ fontSize: 12, color: 'var(--text3)', lineHeight: 1.5 }}>
                Enter your current password and optionally a current 2FA code to disable 2FA.
              </div>
              <Input
                type="password" placeholder="Current password"
                value={disCurPw} onChange={e => setDisCurPw(e.target.value)}
              />
              <Input
                type="text" placeholder="Current 2FA code (optional)" inputMode="numeric" autoComplete="one-time-code"
                value={disCode} onChange={e => setDisCode(e.target.value)}
                style={{ fontFamily: 'var(--font-mono)', letterSpacing: '0.2em' }}
              />
              {disMsg && <div style={{ fontSize: 12, color: disMsg.includes('disabled') ? 'var(--green)' : '#f85149', lineHeight: 1.5 }}>{disMsg}</div>}
              <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
                <Btn type="submit" variant="danger" disabled={disLoading || !disCurPw}>Disable 2FA</Btn>
              </div>
            </form>
          )}
        </div>
      )}
    </Modal>
  )
}
