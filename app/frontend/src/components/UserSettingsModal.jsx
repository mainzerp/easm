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
      setPwMsg('Die neuen Passwörter stimmen nicht überein.')
      return
    }
    if (!newPw) {
      setPwMsg('Neues Passwort darf nicht leer sein.')
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
        setPwMsg('Passwort geändert. Bitte erneut anmelden.')
        setTimeout(() => { onClose(); onLogout() }, 1200)
        return
      }
      const data = await res.json().catch(() => ({}))
      setPwMsg(data.detail || 'Änderung fehlgeschlagen.')
    } catch {
      setPwMsg('Verbindung zum Server fehlgeschlagen.')
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
        setSetupMsg('QR-Code scannen und Verifizierungscode eingeben.')
      } else {
        setSetupMsg(data.detail || 'Setup fehlgeschlagen.')
      }
    } catch {
      setSetupMsg('Verbindung zum Server fehlgeschlagen.')
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
        setSetupMsg('2FA aktiviert.')
        onToggled()
      } else {
        setSetupMsg(data.detail || 'Verifizierung fehlgeschlagen.')
      }
    } catch {
      setSetupMsg('Verbindung zum Server fehlgeschlagen.')
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
        setDisMsg('2FA deaktiviert.')
        onToggled()
      } else {
        setDisMsg(data.detail || 'Deaktivierung fehlgeschlagen.')
      }
    } catch {
      setDisMsg('Verbindung zum Server fehlgeschlagen.')
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
    <Modal open={open} onClose={onClose} title="Benutzereinstellungen">
      <div style={{
        display: 'flex', gap: 6,
        background: 'var(--bg3)', padding: 4, borderRadius: 9, marginBottom: 20,
      }}>
        {tabBtn('account', 'Account')}
        {tabBtn('security', 'Sicherheit')}
      </div>

      {tab === 'account' && (
        <form onSubmit={changePassword} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <div>
            <label style={{ display: 'block', fontSize: 12, color: 'var(--text3)', marginBottom: 6 }}>Benutzername</label>
            <div style={{
              padding: '10px 12px', fontSize: 14,
              background: 'var(--bg3)', border: '0.5px solid var(--border2)',
              borderRadius: 'var(--radius)', color: 'var(--text2)',
            }}>admin</div>
          </div>

          <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text)', marginTop: 4 }}>Passwort ändern</div>
          <Input
            type="password" placeholder="Aktuelles Passwort"
            value={curPw} onChange={e => setCurPw(e.target.value)}
          />
          <Input
            type="password" placeholder="Neues Passwort"
            value={newPw} onChange={e => setNewPw(e.target.value)}
          />
          <Input
            type="password" placeholder="Neues Passwort bestätigen"
            value={confPw} onChange={e => setConfPw(e.target.value)}
          />
          {pwMsg && <div style={{ fontSize: 12, color: pwMsg.includes('geändert') || pwMsg.includes('aktiviert') || pwMsg.includes('deaktiviert') ? 'var(--green)' : '#f85149', lineHeight: 1.5 }}>{pwMsg}</div>}
          <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
            <Btn type="submit" variant="primary" disabled={pwLoading || !curPw || !newPw || !confPw}>Passwort ändern</Btn>
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
              <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text)' }}>Zwei-Faktor-Authentifizierung</div>
              <div style={{ fontSize: 12, color: 'var(--text3)', marginTop: 2 }}>
                {totpEnabled ? 'Aktiviert' : 'Deaktiviert'}
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
                Aktiviert 2FA mit einer Authenticator-App (z. B. Google Authenticator, Aegis, Bitwarden).
              </div>
              <Input
                type="password" placeholder="Aktuelles Passwort"
                value={setupCurPw} onChange={e => setSetupCurPw(e.target.value)}
              />
              {setupMsg && <div style={{ fontSize: 12, color: setupMsg.includes('Aktiviert') || setupMsg.includes('aktiviert') || setupMsg.includes('QR-Code') ? 'var(--green)' : '#f85149', lineHeight: 1.5 }}>{setupMsg}</div>}
              <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
                <Btn type="submit" variant="primary" disabled={setupLoading || !setupCurPw}>2FA aktivieren</Btn>
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
                type="text" placeholder="Verifizierungscode" inputMode="numeric" autoComplete="one-time-code"
                value={verifyCode} onChange={e => setVerifyCode(e.target.value)}
                style={{ fontFamily: 'var(--font-mono)', letterSpacing: '0.2em' }}
              />
              {setupMsg && <div style={{ fontSize: 12, color: setupMsg.includes('aktiviert') ? 'var(--green)' : '#f85149', lineHeight: 1.5 }}>{setupMsg}</div>}
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <Btn type="button" variant="default" onClick={() => { setSetup(null); setSetupMsg('') }} disabled={setupLoading}>Abbrechen</Btn>
                <Btn type="submit" variant="primary" disabled={setupLoading || !verifyCode}>Verifizieren</Btn>
              </div>
            </form>
          )}

          {totpEnabled && (
            <form onSubmit={disableTotp} style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              <div style={{ fontSize: 12, color: 'var(--text3)', lineHeight: 1.5 }}>
                Gib das aktuelle Passwort und optional einen aktuellen 2FA-Code ein, um 2FA zu deaktivieren.
              </div>
              <Input
                type="password" placeholder="Aktuelles Passwort"
                value={disCurPw} onChange={e => setDisCurPw(e.target.value)}
              />
              <Input
                type="text" placeholder="Aktueller 2FA-Code (optional)" inputMode="numeric" autoComplete="one-time-code"
                value={disCode} onChange={e => setDisCode(e.target.value)}
                style={{ fontFamily: 'var(--font-mono)', letterSpacing: '0.2em' }}
              />
              {disMsg && <div style={{ fontSize: 12, color: disMsg.includes('deaktiviert') ? 'var(--green)' : '#f85149', lineHeight: 1.5 }}>{disMsg}</div>}
              <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
                <Btn type="submit" variant="danger" disabled={disLoading || !disCurPw}>2FA deaktivieren</Btn>
              </div>
            </form>
          )}
        </div>
      )}
    </Modal>
  )
}
